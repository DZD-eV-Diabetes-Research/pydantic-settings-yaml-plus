"""Tests for psyplus/yaml_generator.py — YamlFileGenerator."""
import yaml
import pytest

from psyplus.yaml_generator import YamlFileGenerator
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

    def test_required_string_is_empty(self):
        raw, parsed = _generate(SimpleModel)
        assert parsed["required_string"] is None
        assert "\nrequired_string:\n" in raw

    def test_required_list_is_empty(self):
        _, parsed = _generate(SimpleModel)
        assert parsed["required_list"] is None

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

    def test_nested_required_field_is_empty(self):
        _, parsed = _generate(NestedModel)
        assert parsed["database"]["name"] is None

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

    def test_list_field_comment_shows_env_var_for_one_element(self):
        raw, _ = _generate(MultiNestedModel)
        assert (
            "# Env-var:  'MULTI_SERVERS'\n"
            "#           'MULTI_SERVERS__<list-index>' "
            "(one element, 0 is the first; psyplus load() only)\n"
            "servers:"
        ) in raw
        # Dicts get no such line, nor do lists without env_nested_delimiter.
        assert "MULTI_SERVER_MAP__<list-index>" not in raw
        assert "<list-index>" not in _generate(SimpleModel)[0]

    def test_list_elements_show_env_var_with_list_index(self):
        raw, _ = _generate(MultiNestedModel)
        assert raw.count("# Env-var:   'MULTI_SERVERS__<list-index>'\n") == 2
        assert raw.count("# Env-var:   'MULTI_SERVERS__<list-index>__HOST'\n") == 2


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

    def test_required_admin_pw_is_empty(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["admin_pw"] is None

    def test_required_database_names_is_empty(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["database_server"]["database_names"] is None

    def test_required_init_values_is_empty(self):
        _, parsed = _generate(MyAppConfig)
        assert parsed["init_values"] is None

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


class TestValueEncoding:
    def test_no_leading_blank_line(self):
        raw, _ = _generate(SimpleModel)
        assert not raw.startswith("\n")

    def test_special_default_types_render(self):
        import decimal
        import enum
        import uuid
        from pathlib import Path
        from typing import FrozenSet, Set, Tuple

        from pydantic import SecretStr
        from pydantic_settings import BaseSettings

        class Color(enum.Enum):
            RED = "red"

        class M(BaseSettings):
            where: Path = Path("/tmp/x")
            color: Color = Color.RED
            amount: decimal.Decimal = decimal.Decimal("1.5")
            ident: uuid.UUID = uuid.UUID(int=1)
            secret: SecretStr = SecretStr("pw")
            tags: Set[int] = {1}
            frozen: FrozenSet[int] = frozenset({2})
            pair: Tuple[int, int] = (1, 2)

        _, parsed = _generate(M)
        assert parsed == {
            "where": "/tmp/x",
            "color": "red",
            "amount": "1.5",
            "ident": "00000000-0000-0000-0000-000000000001",
            "secret": "pw",
            "tags": [1],
            "frozen": [2],
            "pair": [1, 2],
        }

    def test_yaml11_bool_and_sexagesimal_strings_are_quoted(self):
        from typing import Dict

        from pydantic_settings import BaseSettings

        class M(BaseSettings):
            yes_str: str = "yes"
            time_like: str = "1:30"
            keys: Dict[str, int] = {"on": 1}

        _, parsed = _generate(M)
        assert parsed == {"yes_str": "yes", "time_like": "1:30", "keys": {"on": 1}}

    def test_dict_entries_are_not_required(self):
        from typing import Dict

        from pydantic_settings import BaseSettings

        class M(BaseSettings):
            labels: Dict[str, int] = {"team": 1}

        raw, _ = _generate(M)
        entry = raw.split("# ## team ###", 1)[1]
        assert "Required:  False" in entry.split("team:", 1)[0]


class TestTupleElementComments:
    def _element_types(self, raw: str, path: str) -> list[str]:
        out = []
        for block in raw.split(f"# YAML-path: {path}[")[1:]:
            out.append(block.split("# Type:", 1)[1].split("\n", 1)[0].strip())
        return out

    def test_fixed_length_tuple_elements_have_their_own_type(self):
        from typing import Tuple

        from pydantic_settings import BaseSettings

        class M(BaseSettings):
            pair: Tuple[int, str] = (1, "a")
            many: Tuple[int, ...] = (1, 2)

        raw, parsed = _generate(M)
        assert parsed == {"pair": [1, "a"], "many": [1, 2]}
        assert "# Type:     List of exactly 2 items (int, str)" in raw
        assert self._element_types(raw, "pair") == ["int", "str"]
        assert self._element_types(raw, "many") == ["int", "int"]


class TestDictKeyCaseNote:
    def test_dict_field_comment_has_the_note(self):
        raw, _ = _generate(MultiNestedModel)
        assert (
            "# Env-var:  'MULTI_SERVER_MAP'\n"
            "#           'MULTI_SERVER_MAP__<dict-key>' sets one entry, its key arrives in lower case"
        ) in raw
        assert raw.count("lower case") == 1


class TestNullUnionOfModels:
    def test_sub_field_env_vars_of_every_member_are_listed_once(self):
        from typing import Literal, Optional, Union

        from pydantic import BaseModel
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class Cat(BaseModel):
            kind: Literal["cat"] = "cat"
            lives: int = 9

        class Dog(BaseModel):
            kind: Literal["dog"] = "dog"
            bark: str = "woof"

        class M(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            pet: Union[Cat, Dog]
            maybe_pet: Optional[Union[Cat, Dog]] = None

        raw, parsed = _generate(M)
        assert parsed == {"pet": None, "maybe_pet": None}
        for field in ("pet", "maybe_pet"):
            env = field.upper()
            assert (
                "# Env-vars of the sub-fields:\n"
                f"#   {field}.kind: 'APP_{env}__KIND'\n"
                f"#   {field}.lives: 'APP_{env}__LIVES'\n"
                f"#   {field}.bark: 'APP_{env}__BARK'\n"
                f"{field}:"
            ) in raw

    def test_null_sub_model_lists_the_env_vars_of_its_list_elements(self):
        from typing import List, Optional

        from pydantic import BaseModel
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class Srv(BaseModel):
            host: str = "h"

        class Pool(BaseModel):
            servers: List[Srv] = []

        class M(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            pool: Optional[Pool] = None

        raw, _ = _generate(M)
        assert (
            "# Env-vars of the sub-fields:\n"
            "#   pool.servers: 'APP_POOL__SERVERS'\n"
            "#   pool.servers[*]: 'APP_POOL__SERVERS__<list-index>' "
            "(one element, 0 is the first; psyplus load() only)\n"
            "#   pool.servers[*].host: 'APP_POOL__SERVERS__<list-index>__HOST'\n"
            "pool:"
        ) in raw
