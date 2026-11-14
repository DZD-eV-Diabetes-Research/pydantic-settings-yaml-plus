"""Tests for psyplus/main.py — YamlSettingsPlus integration."""
import os

import pytest
import yaml
from pathlib import Path

from psyplus import YamlSettingsPlus
from tests.models.readme_example import MyAppConfig
from tests.models.simple import SimpleModel


# ---------------------------------------------------------------------------
# generate_config_file
# ---------------------------------------------------------------------------

class TestGenerateConfigFile:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "config.yaml"
        YamlSettingsPlus(SimpleModel, path).generate_config_file()
        assert path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "path" / "config.yaml"
        YamlSettingsPlus(SimpleModel, path).generate_config_file()
        assert path.exists()

    def test_file_is_valid_yaml(self, tmp_path):
        path = tmp_path / "config.yaml"
        YamlSettingsPlus(SimpleModel, path).generate_config_file()
        parsed = yaml.safe_load(path.read_text())
        assert isinstance(parsed, dict)

    def test_file_contains_all_fields(self, tmp_path):
        path = tmp_path / "config.yaml"
        YamlSettingsPlus(SimpleModel, path).generate_config_file()
        parsed = yaml.safe_load(path.read_text())
        for field_name in SimpleModel.model_fields:
            assert field_name in parsed

    def test_file_contains_comments(self, tmp_path):
        path = tmp_path / "config.yaml"
        YamlSettingsPlus(SimpleModel, path).generate_config_file()
        content = path.read_text()
        assert "#" in content
        assert "Required:" in content

    # -- on_exists="skip" (default) --

    def test_on_exists_skip_does_not_overwrite(self, tmp_path):
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(SimpleModel, path)
        handler.generate_config_file()
        path.write_text("sentinel: true\n")
        handler.generate_config_file()  # on_exists="skip" by default
        assert "sentinel" in path.read_text()

    def test_on_exists_skip_explicit(self, tmp_path):
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(SimpleModel, path)
        handler.generate_config_file()
        path.write_text("sentinel: true\n")
        handler.generate_config_file(on_exists="skip")
        assert "sentinel" in path.read_text()

    # -- on_exists="overwrite" --

    def test_on_exists_overwrite_replaces_file(self, tmp_path):
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(SimpleModel, path)
        handler.generate_config_file()
        path.write_text("sentinel: true\n")
        handler.generate_config_file(on_exists="overwrite")
        content = path.read_text()
        assert "sentinel" not in content
        assert "a_string" in content

    # -- on_exists="error" --

    def test_on_exists_error_raises_when_file_exists(self, tmp_path):
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(SimpleModel, path)
        handler.generate_config_file()
        with pytest.raises(FileExistsError, match="on_exists='overwrite'"):
            handler.generate_config_file(on_exists="error")

    def test_on_exists_unknown_value_raises(self, tmp_path):
        path = tmp_path / "config.yaml"
        with pytest.raises(ValueError, match="on_exists"):
            YamlSettingsPlus(SimpleModel, path).generate_config_file(on_exists="replace")
        assert not path.exists()

    def test_on_exists_error_creates_when_missing(self, tmp_path):
        path = tmp_path / "config.yaml"
        YamlSettingsPlus(SimpleModel, path).generate_config_file(on_exists="error")
        assert path.exists()

    # -- validation --

    def test_no_file_path_raises(self):
        with pytest.raises(ValueError, match="file_path"):
            YamlSettingsPlus(SimpleModel).generate_config_file()

    def test_readme_example_model(self, tmp_path):
        path = tmp_path / "config.yaml"
        YamlSettingsPlus(MyAppConfig, path).generate_config_file()
        assert path.exists()
        parsed = yaml.safe_load(path.read_text())
        assert "log_level" in parsed
        assert "database_server" in parsed


# ---------------------------------------------------------------------------
# generate_markdown_doc
# ---------------------------------------------------------------------------

class TestGenerateMarkdownDoc:
    def test_writes_file(self, tmp_path):
        out = tmp_path / "settings.md"
        YamlSettingsPlus(SimpleModel).generate_markdown_doc(out)
        assert out.exists()

    def test_file_contains_model_name(self, tmp_path):
        out = tmp_path / "settings.md"
        YamlSettingsPlus(SimpleModel).generate_markdown_doc(out)
        assert "SimpleModel" in out.read_text()

    def test_no_config_file_path_needed(self, tmp_path):
        # generate_markdown_doc only needs the model, not a YAML file_path
        out = tmp_path / "settings.md"
        YamlSettingsPlus(SimpleModel).generate_markdown_doc(out)
        assert out.exists()


# ---------------------------------------------------------------------------
# render_yaml
# ---------------------------------------------------------------------------

class TestRenderYaml:
    def test_returns_string(self):
        result = YamlSettingsPlus(SimpleModel).render_yaml()
        assert isinstance(result, str)

    def test_valid_yaml(self):
        result = YamlSettingsPlus(SimpleModel).render_yaml()
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_contains_comments(self):
        result = YamlSettingsPlus(SimpleModel).render_yaml()
        assert "#" in result

    def test_contains_all_fields(self):
        result = YamlSettingsPlus(SimpleModel).render_yaml()
        parsed = yaml.safe_load(result)
        for field_name in SimpleModel.model_fields:
            assert field_name in parsed

    def test_no_file_path_needed(self):
        # render_yaml works without a config file path
        result = YamlSettingsPlus(SimpleModel).render_yaml()
        assert "a_string" in result


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------

class TestRenderMarkdown:
    def test_returns_string(self):
        result = YamlSettingsPlus(SimpleModel).render_markdown()
        assert isinstance(result, str)

    def test_contains_model_name(self):
        result = YamlSettingsPlus(SimpleModel).render_markdown()
        assert "SimpleModel" in result

    def test_contains_all_fields(self):
        result = YamlSettingsPlus(SimpleModel).render_markdown()
        for field_name in SimpleModel.model_fields:
            assert field_name in result

    def test_no_file_path_needed(self):
        result = YamlSettingsPlus(SimpleModel).render_markdown()
        assert "a_string" in result


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

class TestLoad:
    def _write_yaml(self, path: Path, content: dict) -> None:
        path.write_text(yaml.dump(content))

    def test_returns_model_instance(self, tmp_path):
        path = tmp_path / "config.yaml"
        self._write_yaml(path, {"a_string": "hi", "required_string": "req", "required_list": []})
        config = YamlSettingsPlus(SimpleModel, path).load()
        assert isinstance(config, SimpleModel)

    def test_loads_values_from_yaml(self, tmp_path):
        path = tmp_path / "config.yaml"
        self._write_yaml(
            path,
            {"a_string": "from_yaml", "an_int": 99, "required_string": "r", "required_list": []},
        )
        config = YamlSettingsPlus(SimpleModel, path).load()
        assert config.a_string == "from_yaml"
        assert config.an_int == 99

    def test_env_var_overrides_yaml(self, tmp_path, monkeypatch):
        path = tmp_path / "config.yaml"
        self._write_yaml(
            path,
            {"a_string": "from_yaml", "required_string": "r", "required_list": []},
        )
        monkeypatch.setenv("SIMPLE_A_STRING", "from_env")
        config = YamlSettingsPlus(SimpleModel, path).load()
        assert config.a_string == "from_env"

    def test_no_file_path_raises(self):
        with pytest.raises(ValueError, match="file_path"):
            YamlSettingsPlus(SimpleModel).load()

    def test_generated_file_is_loadable(self, tmp_path, monkeypatch):
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(MyAppConfig, path)
        handler.generate_config_file()
        # Provide required values via env vars so validation passes
        monkeypatch.setenv("APP_ADMIN_PW", "secret")
        monkeypatch.setenv("APP_DATABASE_SERVER__DATABASE_NAMES", '["db1"]')
        monkeypatch.setenv("APP_INIT_VALUES", '{"k": "v"}')
        config = handler.load()
        assert isinstance(config, MyAppConfig)
        assert config.admin_pw == "secret"
        assert config.database_server.database_names == ["db1"]
        assert config.init_values == {"k": "v"}


class TestLoadNestedEnv:
    def test_nested_leaf_env_keeps_yaml_siblings(self, tmp_path, monkeypatch):
        from tests.models.nested import NestedModel

        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump({
            "admin_password": "pw",
            "database": {"host": "yamlhost", "port": 1111, "name": "yamlname"},
        }))
        monkeypatch.setenv("APP_DATABASE__PORT", "2222")
        config = YamlSettingsPlus(NestedModel, path).load()
        assert config.database.port == 2222
        assert config.database.host == "yamlhost"
        assert config.database.name == "yamlname"

    def test_dotenv_file_is_read(self, tmp_path):
        from pydantic_settings import BaseSettings, SettingsConfigDict

        env_file = tmp_path / ".env"
        env_file.write_text("DOT_VALUE=from_dotenv\n")

        class DotenvModel(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="DOT_", env_file=env_file)
            value: str = "default"

        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump({"value": "from_yaml"}))
        assert YamlSettingsPlus(DotenvModel, path).load().value == "from_dotenv"

    def test_secrets_dir_overrides_yaml(self, tmp_path):
        from pydantic_settings import BaseSettings, SettingsConfigDict

        secrets = tmp_path / "secrets"
        secrets.mkdir()
        (secrets / "value").write_text("from_secret")

        class SecretModel(BaseSettings):
            model_config = SettingsConfigDict(secrets_dir=secrets)
            value: str = "default"

        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump({"value": "from_yaml"}))
        assert YamlSettingsPlus(SecretModel, path).load().value == "from_secret"


    def test_missing_file_gives_defaults(self, tmp_path, monkeypatch):
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class DefaultsModel(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="DEF_")
            name: str = "default"
            port: int = 80

        monkeypatch.setenv("DEF_PORT", "8080")
        path = tmp_path / "does-not-exist.yaml"
        config = YamlSettingsPlus(DefaultsModel, path).load()
        assert not path.exists()
        assert config.name == "default"
        assert config.port == 8080

    def test_documented_sub_field_env_var_of_null_sub_model(self, tmp_path, monkeypatch):
        from tests.models.nested import NestedModel

        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(NestedModel, path)
        handler.generate_config_file()
        assert "#   cache.host: 'APP_CACHE__HOST'" in path.read_text()
        monkeypatch.setenv("APP_ADMIN_PASSWORD", "pw")
        monkeypatch.setenv("APP_DATABASE__NAME", "db")
        monkeypatch.setenv("APP_CACHE__HOST", "cachehost")
        config = handler.load()
        assert config.cache is not None
        assert config.cache.host == "cachehost"
        assert config.cache.port == 6379


class TestRoundTrip:
    """generate_config_file() then load() must give back the model defaults."""

    def test_special_values_round_trip(self, tmp_path):
        import enum
        from typing import Dict, Literal

        from pydantic_settings import BaseSettings

        class Color(str, enum.Enum):
            RED = "red"

        class M(BaseSettings):
            yes_str: str = "yes"
            time_like: str = "1:30"
            switch: Literal["on", "off"] = "on"
            color: Color = Color.RED
            where: Path = Path("/tmp/x")
            keys: Dict[str, int] = {"on": 1}

        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(M, path)
        handler.generate_config_file()
        # load() returns an instance of a subclass of M, so compare the values.
        assert handler.load().model_dump() == M().model_dump()
