"""Tests for psyplus/yaml_generator.py — YamlFileGenerator."""
import yaml
import pytest

from psyplus.yaml_generator import YamlFileGenerator, build_settings_instance, _placeholder_for
from tests.models.simple import SimpleModel
from tests.models.nested import DatabaseConfig, NestedModel, MultiNestedModel
from tests.models.readme_example import MyAppConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate(model_cls) -> tuple[str, dict]:
    """Return (raw_yaml_string, parsed_dict) for *model_cls*."""
    gen = YamlFileGenerator(model_cls)
    gen.parse()
    raw = gen.get_yaml()
    parsed = yaml.safe_load(raw)
    return raw, parsed


# ---------------------------------------------------------------------------
# _placeholder_for
# ---------------------------------------------------------------------------

class TestPlaceholderFor:
    def test_str(self):
        assert _placeholder_for(str) == ""

    def test_int(self):
        assert _placeholder_for(int) == 0

    def test_float(self):
        assert _placeholder_for(float) == 0.0

    def test_bool(self):
        assert _placeholder_for(bool) is False

    def test_list(self):
        assert _placeholder_for(list) == []

    def test_typed_list(self):
        from typing import List
        assert _placeholder_for(List[str]) == []

    def test_dict(self):
        assert _placeholder_for(dict) == {}

    def test_optional_uses_inner(self):
        from typing import Optional
        assert _placeholder_for(Optional[str]) == ""

    def test_optional_none_only(self):
        from typing import Optional, Union
        assert _placeholder_for(type(None)) is None

    def test_literal_returns_first_value(self):
        from typing import Literal
        assert _placeholder_for(Literal["A", "B"]) == "A"

    def test_base_model(self):
        from pydantic import BaseModel
        class M(BaseModel):
            x: str = "hi"
            y: int  # required
        result = _placeholder_for(M)
        assert isinstance(result, dict)
        assert result["x"] == "hi"
        assert result["y"] == 0  # placeholder for required int


# ---------------------------------------------------------------------------
# build_settings_instance
# ---------------------------------------------------------------------------

class TestBuildSettingsInstance:
    def test_simple_model(self):
        inst = build_settings_instance(SimpleModel)
        assert inst.a_string == "hello"
        assert inst.an_int == 42
        # required fields get placeholders
        assert inst.required_string == ""
        assert inst.required_list == []

    def test_nested_model(self):
        inst = build_settings_instance(NestedModel)
        assert inst.database.host == "localhost"
        assert inst.database.port == 5432
        assert inst.database.name == ""  # required → empty string placeholder


# ---------------------------------------------------------------------------
# YamlFileGenerator — flat model
# ---------------------------------------------------------------------------

class TestFlatModelGeneration:
    def test_output_is_valid_yaml(self):
        raw, parsed = _generate(SimpleModel)
        assert isinstance(parsed, dict)

    def test_defaults_preserved(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["a_string"] == "hello"
        assert parsed["an_int"] == 42
        assert parsed["a_float"] == pytest.approx(3.14)
        assert parsed["a_bool"] is True

    def test_optional_none_field(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["optional_none"] is None

    def test_required_string_gets_empty(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["required_string"] == ""

    def test_required_list_gets_empty(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["required_list"] == []

    def test_factory_default_evaluated(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["with_factory"] == "from_factory"

    def test_all_fields_present(self):
        _, parsed = _generate(SimpleModel)
        for field_name in SimpleModel.model_fields:
            assert field_name in parsed

    def test_comments_present(self):
        raw, _ = _generate(SimpleModel)
        assert "## a_string ###" in raw
        assert "## required_string ###" in raw

    def test_required_annotation_in_comment(self):
        raw, _ = _generate(SimpleModel)
        # Find the comment block for required_string
        idx = raw.index("## required_string ###")
        block = raw[idx: idx + 300]
        assert "Required:" in block
        assert "True" in block

    def test_optional_annotation_in_comment(self):
        raw, _ = _generate(SimpleModel)
        idx = raw.index("## a_string ###")
        block = raw[idx: idx + 300]
        assert "Required:" in block
        assert "False" in block

    def test_env_var_in_comment(self):
        raw, _ = _generate(SimpleModel)
        assert "SIMPLE_A_STRING" in raw

    def test_literal_allowed_vals_in_comment(self):
        raw, _ = _generate(SimpleModel)
        assert "Allowed vals:" in raw
        assert "'A'" in raw or "A" in raw

    def test_description_in_comment(self):
        raw, _ = _generate(SimpleModel)
        assert "A fully documented optional string field." in raw

    def test_examples_in_comment(self):
        raw, _ = _generate(SimpleModel)
        assert "Example" in raw
        assert "ex1" in raw

    def test_title_in_comment(self):
        raw, _ = _generate(SimpleModel)
        assert "Great String" in raw

    def test_list_field_values(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["string_list"] == ["x", "y"]

    def test_dict_field_values(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["string_dict"] == {"one": 1}


# ---------------------------------------------------------------------------
# YamlFileGenerator — nested model
# ---------------------------------------------------------------------------

class TestNestedModelGeneration:
    def test_output_is_valid_yaml(self):
        raw, parsed = _generate(NestedModel)
        assert isinstance(parsed, dict)

    def test_nested_defaults_present(self):
        _, parsed = _generate(NestedModel)
        assert parsed["database"]["host"] == "localhost"
        assert parsed["database"]["port"] == 5432

    def test_nested_required_field_placeholder(self):
        _, parsed = _generate(NestedModel)
        assert parsed["database"]["name"] == ""

    def test_nested_env_var_in_comment(self):
        raw, _ = _generate(NestedModel)
        # prefix "APP_" + delimiter "__" → APP_DATABASE__HOST
        assert "APP_DATABASE__HOST" in raw

    def test_nested_yaml_path_in_comment(self):
        raw, _ = _generate(NestedModel)
        assert "YAML-path:" in raw
        assert "database.host" in raw

    def test_optional_nested_model_none(self):
        _, parsed = _generate(NestedModel)
        assert parsed["cache"] is None

    def test_factory_default_evaluated(self):
        _, parsed = _generate(NestedModel)
        # Path normalises trailing slash, so check without it
        assert ".config/app" in parsed["storage_dir"]


# ---------------------------------------------------------------------------
# YamlFileGenerator — multi-nested (List/Dict of BaseModel)
# ---------------------------------------------------------------------------

class TestMultiNestedGeneration:
    def test_output_is_valid_yaml(self):
        raw, parsed = _generate(MultiNestedModel)
        assert isinstance(parsed, dict)

    def test_list_of_base_model(self):
        _, parsed = _generate(MultiNestedModel)
        assert isinstance(parsed["servers"], list)
        assert parsed["servers"][0]["host"] == "a.example.com"
        assert parsed["servers"][1]["host"] == "b.example.com"

    def test_dict_of_base_model(self):
        _, parsed = _generate(MultiNestedModel)
        assert isinstance(parsed["server_map"], dict)
        assert parsed["server_map"]["primary"]["host"] == "primary.example.com"
        assert parsed["server_map"]["primary"]["port"] == 443


# ---------------------------------------------------------------------------
# YamlFileGenerator — README example model
# ---------------------------------------------------------------------------

class TestReadmeExampleModel:
    def test_output_is_valid_yaml(self):
        raw, parsed = _generate(MyAppConfig)
        assert isinstance(parsed, dict)

    def test_all_top_level_fields_present(self):
        _, parsed = _generate(MyAppConfig)
        for field_name in MyAppConfig.model_fields:
            assert field_name in parsed

    def test_log_level_value(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["log_level"] == "INFO"

    def test_app_name_value(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["app_name"] == "THE APP"

    def test_nested_database_server(self):
        _, parsed = _generate(MyAppConfig)
        assert "database_server" in parsed
        db = parsed["database_server"]
        assert db["host"] == "localhost"
        assert db["port"] == 5678

    def test_required_admin_pw_placeholder(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["admin_pw"] == ""

    def test_required_database_names_placeholder(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["database_server"]["database_names"] == []

    def test_required_init_values_placeholder(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["init_values"] == {}

    def test_example_in_comment(self):
        raw, _ = _generate(MyAppConfig)
        assert "Example" in raw
        assert "db.company.org" in raw

    def test_env_vars_in_comments(self):
        raw, _ = _generate(MyAppConfig)
        assert "APP_LOG_LEVEL" in raw
        # prefix "APP_" + delimiter "__" → APP_DATABASE_SERVER__HOST
        assert "APP_DATABASE_SERVER__HOST" in raw


# ---------------------------------------------------------------------------
# get_yaml called before parse raises
# ---------------------------------------------------------------------------

def test_get_yaml_before_parse_raises():
    gen = YamlFileGenerator(SimpleModel)
    with pytest.raises(RuntimeError, match="parse"):
        gen.get_yaml()
