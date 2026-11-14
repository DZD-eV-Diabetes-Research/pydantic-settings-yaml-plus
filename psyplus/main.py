from __future__ import annotations

from pathlib import Path
from typing import Generic, Literal, Type, TypeVar, Union

from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    YamlConfigSettingsSource,
)
from pydantic_settings.sources import DefaultSettingsSource

from psyplus.markdown_generator import MarkdownDocGenerator
from psyplus.yaml_generator import YamlFileGenerator

SettingsT = TypeVar("SettingsT", bound=BaseSettings)


class YamlSettingsPlus(Generic[SettingsT]):
    """Central helper for generating and reading pydantic-settings YAML configs.

    Args:
        model:     The pydantic-settings ``BaseSettings`` subclass to work with.
        file_path: Path of the YAML config file to read/write.
    """

    def __init__(
        self,
        model: Type[SettingsT],
        file_path: Union[str, Path, None] = None,
    ) -> None:
        self.model = model
        self.config_file: Path | None = Path(file_path) if file_path is not None else None

    # ------------------------------------------------------------------
    # Write to disk
    # ------------------------------------------------------------------

    def generate_config_file(
        self,
        on_exists: Literal["skip", "overwrite", "error"] = "skip",
    ) -> None:
        """Write a documented YAML config template to *file_path*.

        Args:
            on_exists: What to do when the file already exists.
                - ``"skip"``      — silently do nothing (default, safe for init scripts).
                - ``"overwrite"`` — replace the existing file.
                - ``"error"``     — raise ``FileExistsError``.
        """
        if self.config_file is None:
            raise ValueError("file_path must be set to generate a config file.")
        if on_exists not in ("skip", "overwrite", "error"):
            raise ValueError(
                f"on_exists must be 'skip', 'overwrite' or 'error', not {on_exists!r}."
            )

        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        if self.config_file.is_file():
            if on_exists == "skip":
                return
            elif on_exists == "error":
                raise FileExistsError(
                    f"Config file already exists at '{self.config_file}'. "
                    "Pass on_exists='overwrite' to replace it."
                )
            # on_exists == "overwrite" → fall through

        self.config_file.write_text(self.render_yaml(), encoding="utf-8")

    def generate_markdown_doc(self, output_path: Union[str, Path]) -> None:
        """Write a Markdown reference document for the settings model to *output_path*."""
        Path(output_path).write_text(self.render_markdown(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Render to string (no file I/O)
    # ------------------------------------------------------------------

    def render_yaml(self) -> str:
        """Render the documented YAML config template and return it as a string."""
        gen = YamlFileGenerator(self.model)
        gen.parse()
        return gen.get_yaml()

    def render_markdown(self) -> str:
        """Render a Markdown reference document and return it as a string."""
        return MarkdownDocGenerator(self.model).generate()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self) -> SettingsT:
        """Load the YAML file and return a validated instance of the model.

        The result is an instance of the model class itself
        (``type(config) is model``), so it compares equal to and pickles like
        an instance created directly. It is built in a single validation
        pass: validators and ``model_post_init`` run once per call.

        Sources: load() builds the sources pydantic-settings builds for the
        model (init arguments, env vars, ``.env`` file and secrets directory,
        each configured by the model's ``model_config``), passes them through
        the model's own ``settings_customise_sources`` and adds the YAML file
        after whatever that returns, so YAML values only beat the field
        defaults. For a model without its own ``settings_customise_sources``
        the priority is (highest first): env vars, ``.env`` file, secrets
        directory, YAML file, defaults. load() takes no init arguments, so
        the init source is always empty. A source the model drops in
        ``settings_customise_sources`` (for example ``env_settings``) stays
        dropped in load().

        If the model's ``settings_customise_sources`` already returns a
        ``YamlConfigSettingsSource`` (or a subclass of it), load() adds no
        second one. Instead it replaces each of them, at the same position,
        with a source that reads *file_path*. The model decides how YAML
        ranks against the other sources, *file_path* decides which file is
        read.

        If the model's ``model_config`` sets ``cli_parse_args`` or
        ``cli_settings_source``, command line arguments are parsed and beat
        all other sources, as they do when the model is instantiated
        directly.

        The YAML file is read with the model's ``yaml_file_encoding``, or as
        UTF-8 (the encoding generate_config_file() writes) when the model
        sets none. A missing YAML file is not an error, the other sources and
        the defaults still apply.

        Tip: to get similar behaviour without psyplus, set ``yaml_file`` in
        your model's ``model_config`` and add a ``YamlConfigSettingsSource``
        in ``settings_customise_sources``. Setting ``yaml_file`` alone is not
        enough, pydantic-settings does not read it by default::

            class MyConfig(BaseSettings):
                model_config = SettingsConfigDict(
                    yaml_file="config.yaml",
                    env_prefix="APP_",
                    env_nested_delimiter="__",
                )

                @classmethod
                def settings_customise_sources(
                    cls, settings_cls, init_settings, env_settings,
                    dotenv_settings, file_secret_settings,
                ):
                    return (
                        init_settings, env_settings, dotenv_settings,
                        file_secret_settings,
                        YamlConfigSettingsSource(settings_cls),
                    )
        """
        if self.config_file is None:
            raise ValueError("file_path must be set to load a config file.")
        # ``_build_sources`` makes BaseSettings.__init__ use these sources
        # instead of building its own, so the model class itself is
        # instantiated and validated exactly once.
        return self.model(_build_sources=(self._settings_sources(), {}))

    def _settings_sources(self) -> tuple[PydanticBaseSettingsSource, ...]:
        """Return the source chain load() hands to the model, highest priority first."""
        model = self.model
        yaml_source = YamlConfigSettingsSource(
            model,
            yaml_file=self.config_file,
            yaml_file_encoding=model.model_config.get("yaml_file_encoding") or "utf-8",
        )
        sources = model.settings_customise_sources(
            model,
            init_settings=InitSettingsSource(model, init_kwargs={}),
            env_settings=self._env_settings_source(),
            dotenv_settings=DotEnvSettingsSource(model),
            file_secret_settings=SecretsSettingsSource(model),
        )
        if any(isinstance(s, YamlConfigSettingsSource) for s in sources):
            sources = tuple(
                yaml_source if isinstance(s, YamlConfigSettingsSource) else s
                for s in sources
            )
        else:
            sources = (*sources, yaml_source)
        return (*self._with_cli_source(sources), DefaultSettingsSource(model))

    def _env_settings_source(self) -> PydanticBaseSettingsSource:
        """Return the env var source passed to ``settings_customise_sources``."""
        return EnvSettingsSource(self.model)

    def _with_cli_source(
        self, sources: tuple[PydanticBaseSettingsSource, ...]
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Add the command line source that the model's ``model_config`` asks for.

        Mirrors what ``BaseSettings.__init__`` does with ``cli_parse_args`` and
        ``cli_settings_source`` from ``model_config``.
        """
        config = self.model.model_config
        cli_parse_args = config.get("cli_parse_args")
        own_cli = [s for s in sources if isinstance(s, CliSettingsSource)]
        if own_cli:
            if cli_parse_args not in (None, False) and not own_cli[0].env_vars:
                own_cli[0](args=cli_parse_args)
            return sources
        cli_source = config.get("cli_settings_source")
        if not isinstance(cli_source, CliSettingsSource):
            if cli_parse_args is None:
                return sources
            cli_source = CliSettingsSource(
                self.model,
                cli_parse_args=cli_parse_args,
                cli_parse_none_str=(
                    config.get("env_parse_none_str") or config.get("cli_parse_none_str")
                ),
                case_sensitive=config.get("case_sensitive"),
            )
        return (cli_source, *sources)
