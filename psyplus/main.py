from __future__ import annotations

from pathlib import Path
from typing import Literal, Type, Union

from pydantic_settings import BaseSettings, YamlConfigSettingsSource

from psyplus.markdown_generator import MarkdownDocGenerator
from psyplus.yaml_generator import YamlFileGenerator


class YamlSettingsPlus:
    """Central helper for generating and reading pydantic-settings YAML configs.

    Args:
        model:     The pydantic-settings ``BaseSettings`` subclass to work with.
        file_path: Path of the YAML config file to read/write.
    """

    def __init__(
        self,
        model: Type[BaseSettings],
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

    def load(self) -> BaseSettings:
        """Load the YAML file and return a validated settings instance.

        Environment variables (respecting the model's ``env_prefix`` /
        ``env_nested_delimiter``) take priority over YAML file values,
        following standard pydantic-settings source precedence.

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

        yaml_path = self.config_file
        base_cls = self.model
        # The generated file is written as UTF-8, so read it as UTF-8 unless the
        # model asks for another encoding.
        encoding = base_cls.model_config.get("yaml_file_encoding") or "utf-8"

        class _ModelWithYaml(base_cls):  # type: ignore[valid-type,misc]
            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: Type[BaseSettings],
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            ):
                # The YAML file is the lowest file based source: env vars, the
                # .env file and the secrets directory all override it.
                return (
                    init_settings,
                    env_settings,
                    dotenv_settings,
                    file_secret_settings,
                    YamlConfigSettingsSource(
                        settings_cls, yaml_file=yaml_path, yaml_file_encoding=encoding
                    ),
                )

        return _ModelWithYaml()
