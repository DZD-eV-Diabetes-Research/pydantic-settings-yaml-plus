from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, Type, Union

import yaml
from pydantic_settings import BaseSettings

from psyplus.markdown_generator import MarkdownDocGenerator
from psyplus.yaml_generator import YamlFileGenerator

log = logging.getLogger(__name__)


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

        self.config_file.write_text(self.render_yaml())

    def generate_markdown_doc(self, output_path: Union[str, Path]) -> None:
        """Write a Markdown reference document for the settings model to *output_path*."""
        Path(output_path).write_text(self.render_markdown())

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

        The YAML file is added as the *lowest*-priority pydantic-settings source, leaving
        the standard sources above it untouched. Effective precedence, highest first:

        1. init arguments
        2. environment variables (respecting ``env_prefix`` / ``env_nested_delimiter``)
        3. a dotenv file (``env_file``)
        4. a secrets directory (``secrets_dir``) — Docker/Kubernetes secrets
        5. the YAML file
        6. model defaults

        Sources 3 and 4 matter even though psyplus does not configure them itself: a model
        that sets ``env_file`` or ``secrets_dir`` in its ``SettingsConfigDict`` expects them
        to be honoured, and silently outranking a mounted secret with a committed YAML value
        is the kind of thing nobody notices until it is a credential.

        Tip: if you want this behaviour without psyplus, configure
        ``yaml_file`` directly in your model's ``model_config``::

            class MyConfig(BaseSettings):
                model_config = SettingsConfigDict(
                    yaml_file="config.yaml",
                    env_prefix="APP_",
                    env_nested_delimiter="__",
                )

            config = MyConfig()  # reads YAML + env vars automatically
        """
        if self.config_file is None:
            raise ValueError("file_path must be set to load a config file.")

        yaml_path = self.config_file
        base_cls = self.model

        try:
            try:
                from pydantic_settings import YamlSettingsSource as _YamlSource
            except ImportError:
                from pydantic_settings import YamlConfigSettingsSource as _YamlSource  # type: ignore[assignment]

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
                    # Pass every source through in pydantic-settings' own order and merely
                    # append the YAML file beneath them. Dropping dotenv_settings or
                    # file_secret_settings here would let a YAML value quietly win over an
                    # `env_file` entry or a mounted `secrets_dir` secret.
                    return (
                        init_settings,
                        env_settings,
                        dotenv_settings,
                        file_secret_settings,
                        _YamlSource(settings_cls, yaml_file=yaml_path),
                    )

            return _ModelWithYaml()

        except ImportError:
            log.warning(
                "pydantic-settings >= 2.3 is required for automatic env-var overlay "
                "in load(). Falling back to YAML-only loading."
            )
            with open(yaml_path) as fh:
                data = yaml.safe_load(fh) or {}
            return self.model.model_validate(data)
