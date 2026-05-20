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
        monkeypatch.setenv("APP__DATABASE_SERVER__DATABASE_NAMES", '["db1"]')
        monkeypatch.setenv("APP_INIT_VALUES", '{"k": "v"}')
        config = handler.load()
        assert isinstance(config, MyAppConfig)
