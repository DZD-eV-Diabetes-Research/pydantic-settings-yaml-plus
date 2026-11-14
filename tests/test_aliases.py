"""Fields with an alias: the validation alias is the YAML key, the path segment and the env var name.

test_env_roundtrip.py checks that every env var documented for the alias models in
tests/models/env_cases.py sets its value. These tests check the keys, the names that are
(and are not) documented, AliasPath fields, defaults and the Markdown document.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional
from unittest import mock

import pydantic
import pytest
import yaml
from pydantic import AliasChoices, AliasGenerator, AliasPath, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings, SettingsConfigDict

from psyplus import YamlSettingsPlus
from tests.models import env_cases as cases
from tests.test_env_roundtrip import md_env_names, yaml_env_names


def _template(model) -> dict:
    return yaml.safe_load(YamlSettingsPlus(model).render_yaml())


def _load(model, data: dict, tmp_path, env: dict | None = None):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(data))
    env_vars = {"PSYPLUS_SUPPRESS_ENV_WARNING": "1", **(env or {})}
    with mock.patch.dict(os.environ, env_vars, clear=True):
        return YamlSettingsPlus(model, config).load()


# ---------------------------------------------------------------------------
# YAML keys
# ---------------------------------------------------------------------------

class TestYamlKeys:
    def test_issue_example_uses_the_alias(self, tmp_path):
        class S(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            my_field: str = Field("x", alias="MY_ALIAS")

        rendered = YamlSettingsPlus(S).render_yaml()
        assert yaml.safe_load(rendered) == {"MY_ALIAS": "x"}
        assert "# Env-var:  'MY_ALIAS'" in rendered
        assert _load(S, {"MY_ALIAS": "y"}, tmp_path).my_field == "y"
        assert _load(S, {"MY_ALIAS": "y"}, tmp_path, {"MY_ALIAS": "e"}).my_field == "e"

    def test_every_alias_kind_becomes_the_key(self):
        template = _template(cases.Aliases)
        assert list(template) == [
            "MY_ALIAS",  # alias=
            "V_ALIAS",  # validation_alias=
            "C_ONE",  # AliasChoices: the first choice
            "C_STR",  # AliasChoices(AliasPath, str): the first str choice
            "outer",  # AliasPath("outer", "inner")
            "s_field",  # serialization_alias only: the field name
            "plain",
            "sub",
            "theSub",
            "opt_sub",
            "items",
            "item_map",
            "REQ",
        ]
        assert template["outer"] == {"inner": "x"}
        for sub in ("sub", "theSub", "opt_sub"):
            assert list(template[sub]) == ["subAlias", "plain", "subChoice"]
        assert template["items"] == [{"itemName": "n", "item_size": 1}]
        assert template["item_map"] == {"first": {"itemName": "n", "item_size": 1}}

    def test_alias_generator_keys_at_every_level(self):
        template = _template(cases.Camel)
        assert template == {
            "logLevel": "INFO",
            "port": 8080,
            "midModel": {
                "midValue": "m",
                "leafModel": {"innerValue": "d", "count": 1},
                "optLeaf": {"innerValue": "d", "count": 1},
            },
            "leaves": [{"innerValue": "d", "count": 1}],
            "leafMap": {"k": {"innerValue": "d", "count": 1}},
        }

    def test_populate_by_name_keeps_the_alias_as_key(self):
        template = _template(cases.AliasesByName)
        assert "MY_ALIAS" in template and "my_field" not in template
        assert "theSub" in template and "asub" not in template

    def test_validation_alias_wins_over_alias_in_sub_models(self, tmp_path):
        class Sub(BaseModel):
            both: str = Field("x", alias="A", validation_alias="B")

        class S(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            sub: Sub = Sub()

        assert _template(S) == {"sub": {"B": "x"}}
        assert yaml_env_names(S)["sub.B"] == "APP_SUB__B"
        assert _load(S, {"sub": {"B": "y"}}, tmp_path).sub.both == "y"

    def test_top_level_alias_differing_from_validation_alias_is_left_out(
        self, tmp_path, caplog
    ):
        # The YAML source files a top-level value under `alias`, validation reads
        # `validation_alias`: no key works, so the template leaves the field out.
        class S(BaseSettings):
            model_config = SettingsConfigDict(alias_generator=to_camel, env_prefix="APP_")
            both: str = Field("x", alias="A", validation_alias="B")
            explicit_val: str = Field("x", validation_alias="VAL")
            log_level: str = "INFO"

        with caplog.at_level(logging.WARNING):
            rendered = YamlSettingsPlus(S).render_yaml()
        assert yaml.safe_load(rendered) == {"logLevel": "INFO"}
        assert "under its alias A, but validation expects B" in rendered
        assert "under its alias explicitVal, but validation expects VAL" in rendered
        assert "# Env-var:  'B'" in rendered
        assert len([r for r in caplog.records if "left out" in r.getMessage()]) == 2
        loaded = _load(S, yaml.safe_load(rendered), tmp_path, {"B": "e", "VAL": "v"})
        assert (loaded.both, loaded.explicit_val, loaded.log_level) == ("e", "v", "INFO")

    def test_serialization_alias_changes_nothing(self):
        class Sub(BaseModel):
            s_field: str = Field("x", serialization_alias="SER")

        class S(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            sub: Sub = Sub()

        rendered = YamlSettingsPlus(S).render_yaml()
        assert yaml.safe_load(rendered) == {"sub": {"s_field": "x"}}
        assert "SER" not in rendered
        assert "SER" not in YamlSettingsPlus(S).render_markdown()
        assert yaml_env_names(S)["sub.s_field"] == "APP_SUB__S_FIELD"

    @pytest.mark.skipif(
        tuple(int(p) for p in pydantic.VERSION.split(".")[:2]) < (2, 11),
        reason="validate_by_alias needs pydantic 2.11",
    )
    def test_validate_by_alias_false_keeps_field_names(self, tmp_path):
        class Sub(BaseModel):
            model_config = ConfigDict(validate_by_name=True, validate_by_alias=False)
            inner: str = Field("i", alias="INNER")

        class S(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_",
                env_nested_delimiter="__",
                validate_by_name=True,
                validate_by_alias=False,
            )
            my_field: str = Field("x", alias="MY_ALIAS")
            sub: Sub = Sub()

        rendered = YamlSettingsPlus(S).render_yaml()
        # The YAML source files the top-level my_field under its alias, which
        # validation rejects, so it is left out. The sub-model keeps the field name.
        assert yaml.safe_load(rendered) == {"sub": {"inner": "i"}}
        assert "under its alias MY_ALIAS, but validation expects my_field" in rendered
        assert '# Default:  {"inner": "i"}' in rendered
        assert yaml_env_names(S) == {
            "my_field": "APP_MY_FIELD",
            "sub": "APP_SUB",
            "sub.inner": "APP_SUB__INNER",
        }
        loaded = _load(S, {"sub": {"inner": "j"}}, tmp_path, {"APP_MY_FIELD": "e"})
        assert (loaded.my_field, loaded.sub.inner) == ("e", "j")


# ---------------------------------------------------------------------------
# The generated YAML loads
# ---------------------------------------------------------------------------

class TestLoad:
    @pytest.mark.parametrize(
        "model,required",
        [
            (cases.Aliases, {"REQ": "r"}),
            (cases.AliasesByName, {"REQ": "r"}),
            (cases.AliasesPrefixAll, {"REQ": "r"}),
            (cases.Camel, {}),
        ],
        ids=lambda v: getattr(v, "__name__", ""),
    )
    def test_template_loads_to_the_defaults(self, model, required, tmp_path):
        template = _template(model)
        template.update(required)
        loaded = _load(model, template, tmp_path)
        expected = model.model_construct(**{
            name: fi.get_default(call_default_factory=True)
            for name, fi in model.model_fields.items()
            if not fi.is_required()
        })
        for name in model.model_fields:
            if name != "required_field":
                assert getattr(loaded, name) == getattr(expected, name), name

    def test_values_are_read_from_the_alias_keys(self, tmp_path):
        template = _template(cases.Aliases)
        template["REQ"] = "r"
        template["MY_ALIAS"] = "a"
        template["C_STR"] = "c"
        template["outer"]["inner"] = "o"
        template["theSub"]["subAlias"] = "t"
        template["theSub"]["subChoice"] = "tc"
        template["items"][0]["itemName"] = "i"
        template["item_map"]["first"]["itemName"] = "m"
        loaded = _load(cases.Aliases, template, tmp_path)
        assert loaded.my_field == "a"
        assert loaded.cp_field == "c"
        assert loaded.p_field == "o"
        assert loaded.asub.sub_field == "t"
        assert loaded.asub.choice_field == "tc"
        assert loaded.items[0].item_name == "i"
        assert loaded.item_map["first"].item_name == "m"
        assert loaded.required_field == "r"

    def test_default_instance_values_under_alias_keys(self, tmp_path):
        class S(BaseSettings):
            sub: cases.AliasSub = cases.AliasSub(subAlias="custom", subChoice="ch")
            items: List[cases.AliasItem] = [cases.AliasItem(itemName="first")]

        template = _template(S)
        assert template["sub"] == {"subAlias": "custom", "plain": 1, "subChoice": "ch"}
        assert template["items"] == [{"itemName": "first", "item_size": 1}]
        rendered = YamlSettingsPlus(S).render_yaml()
        assert '"subAlias": "custom"' in rendered
        assert _load(S, template, tmp_path).sub.sub_field == "custom"

    def test_default_factory_gets_the_values_by_field_name(self, tmp_path):
        class S(BaseSettings):
            a_field: str = Field("x", alias="A")
            b_field: str = Field(default_factory=lambda data: data["a_field"] + "!", alias="B")

        assert _template(S) == {"A": "x", "B": "x!"}
        assert _load(S, _template(S), tmp_path).b_field == "x!"

    def test_examples_are_shown_under_the_alias(self):
        class S(BaseSettings):
            ex_field: str = Field("x", alias="EX", examples=["v"])

        assert " >EX: v" in YamlSettingsPlus(S).render_yaml()
        assert "EX: v" in YamlSettingsPlus(S).render_markdown()


# ---------------------------------------------------------------------------
# AliasPath
# ---------------------------------------------------------------------------

class TestAliasPath:
    def test_fields_sharing_a_root_go_into_one_map(self, tmp_path):
        class S(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            db_host: str = Field("localhost", validation_alias=AliasPath("database", "host"))
            db_port: int = Field(5432, validation_alias=AliasPath("database", "port"))
            db_user: str = Field(validation_alias=AliasPath("database", "auth", "user"))
            name: str = "n"

        rendered = YamlSettingsPlus(S).render_yaml()
        template = yaml.safe_load(rendered)
        assert template == {
            "database": {"host": "localhost", "port": 5432, "auth": {"user": None}},
            "name": "n",
        }
        # No env var sets just one AliasPath value.
        assert yaml_env_names(S) == {"name": "APP_NAME"}
        assert md_env_names(S) == {"name": "APP_NAME"}
        assert "# YAML-path: database.auth.user" in rendered
        template["database"]["auth"]["user"] = "u"
        template["database"]["port"] = 1
        loaded = _load(S, template, tmp_path)
        assert (loaded.db_host, loaded.db_port, loaded.db_user) == ("localhost", 1, "u")

    def test_path_inside_sub_models_and_list_items(self, tmp_path):
        class Item(BaseModel):
            host: str = Field("h", validation_alias=AliasPath("conn", "host"))

        class S(BaseSettings):
            sub: Item = Item()
            items: List[Item] = [Item(), Item()]

        rendered = YamlSettingsPlus(S).render_yaml()
        template = yaml.safe_load(rendered)
        assert template == {"sub": {"conn": {"host": "h"}}, "items": [{"conn": {"host": "h"}}] * 2}
        assert '# Default:  {"conn": {"host": "h"}}' in rendered
        assert "# YAML-path: items[1].conn.host" in rendered
        template["sub"]["conn"]["host"] = "s"
        template["items"][1]["conn"]["host"] = "x"
        loaded = _load(S, template, tmp_path)
        assert (loaded.sub.host, loaded.items[0].host, loaded.items[1].host) == ("s", "h", "x")

    def test_choices_of_paths_only_use_the_first_path(self, tmp_path):
        class S(BaseSettings):
            c_field: str = Field("x", validation_alias=AliasChoices(AliasPath("a", "b"), AliasPath("c")))

        assert _template(S) == {"a": {"b": "x"}}
        assert _load(S, {"a": {"b": "y"}}, tmp_path).c_field == "y"

    def test_path_with_list_index_is_left_out_with_a_note(self, tmp_path, caplog):
        class S(BaseSettings):
            first: str = "f"
            l_field: str = Field("x", validation_alias=AliasPath("lst", 1))
            last: str = "l"

        with caplog.at_level(logging.WARNING):
            rendered = YamlSettingsPlus(S).render_yaml()
        assert yaml.safe_load(rendered) == {"first": "f", "last": "l"}
        assert "# ## lst[1] ###" in rendered
        assert "read from the AliasPath lst[1]" in rendered
        assert rendered.index("lst[1]") < rendered.index("last:")
        assert any("lst[1]" in r.getMessage() for r in caplog.records)
        assert "## `lst[1]`" in YamlSettingsPlus(S).render_markdown()
        assert _load(S, {"first": "f", "lst": ["a", "b"]}, tmp_path).l_field == "b"

    def test_path_left_out_as_last_field_keeps_its_note(self):
        class S(BaseSettings):
            first: str = "f"
            l_field: str = Field("x", validation_alias=AliasPath("lst", 0))

        rendered = YamlSettingsPlus(S).render_yaml()
        assert yaml.safe_load(rendered) == {"first": "f"}
        assert "read from the AliasPath lst[0]" in rendered

    def test_path_clashing_with_a_field_key_is_left_out(self):
        class S(BaseSettings):
            p_field: str = Field("x", validation_alias=AliasPath("plain", "inner"))
            plain: str = "p"

        rendered = YamlSettingsPlus(S).render_yaml()
        assert yaml.safe_load(rendered) == {"plain": "p"}
        assert "read from the AliasPath plain.inner" in rendered


# ---------------------------------------------------------------------------
# Env var names
# ---------------------------------------------------------------------------

def _names(model) -> dict[str, str]:
    names = yaml_env_names(model)
    md = md_env_names(model)
    # The Markdown doc shows the same names, with [*] for list and dict elements. It
    # has no section of its own for a dict element.
    for path, env in names.items():
        if path.endswith("]"):
            continue
        md_path = path.replace("['first']", "[*]").replace("['k']", "[*]")
        assert md.get(md_path) == env, path
    return names


class TestEnvNames:
    def test_default_prefix_target_puts_no_prefix_on_aliases(self):
        names = _names(cases.Aliases)
        assert names["MY_ALIAS"] == "MY_ALIAS"
        assert names["V_ALIAS"] == "V_ALIAS"
        assert names["C_ONE"] == "C_ONE"
        assert names["C_STR"] == "C_STR"
        assert names["s_field"] == "APP_S_FIELD"
        assert names["sub.subAlias"] == "APP_SUB__SUBALIAS"
        assert names["sub.subChoice"] == "APP_SUB__SUBCHOICE"
        assert names["theSub"] == "THESUB"
        assert names["theSub.subAlias"] == "THESUB__SUBALIAS"
        assert names["opt_sub.subAlias"] == "APP_OPT_SUB__SUBALIAS"
        assert names["item_map['first'].item_size"] == "APP_ITEM_MAP__<dict-key>__ITEM_SIZE"
        assert names["REQ"] == "REQ"
        # An AliasPath, a list element, and an upper case key below a dict (the
        # lower cased env var name does not match it) have no env var.
        assert "outer.inner" not in names
        assert "items[0].itemName" not in names
        assert "item_map['first'].itemName" not in names

    def test_prefix_target_alias(self):
        names = _names(cases.AliasesPrefixAlias)
        assert names["MY_ALIAS"] == "APP_MY_ALIAS"
        assert names["s_field"] == "S_FIELD"
        assert names["sub.subAlias"] == "SUB__SUBALIAS"
        assert names["theSub.plain"] == "APP_THESUB__PLAIN"

    def test_prefix_target_all(self):
        names = _names(cases.AliasesPrefixAll)
        assert names["MY_ALIAS"] == "APP_MY_ALIAS"
        assert names["s_field"] == "APP_S_FIELD"
        assert names["sub.subAlias"] == "APP_SUB__SUBALIAS"
        assert names["theSub.plain"] == "APP_THESUB__PLAIN"

    def test_case_sensitive_keeps_the_alias_case(self):
        names = _names(cases.AliasesCaseSens)
        assert names["MY_ALIAS"] == "MY_ALIAS"
        assert names["sub.subAlias"] == "APP_sub__subAlias"
        assert names["theSub.subAlias"] == "theSub__subAlias"
        assert names["item_map['first'].itemName"] == "APP_item_map__<dict-key>__itemName"

    def test_populate_by_name_has_no_env_var_below_an_aliased_field(self):
        # pydantic-settings files them under the field name next to the alias from the
        # YAML file, and load() fails. The JSON env var of the whole field works.
        names = _names(cases.AliasesByName)
        assert names["MY_ALIAS"] == "MY_ALIAS"
        assert names["theSub"] == "THESUB"
        assert not any(path.startswith("theSub.") for path in names)
        assert names["sub.subAlias"] == "APP_SUB__SUBALIAS"

    def test_alias_generator(self):
        names = _names(cases.Camel)
        assert names["logLevel"] == "LOGLEVEL"
        assert names["midModel.leafModel.innerValue"] == "MIDMODEL__LEAFMODEL__INNERVALUE"
        assert names["midModel.optLeaf.count"] == "MIDMODEL__OPTLEAF__COUNT"
        # Below an Optional sub-model deeper down and below a dict the case of
        # innerValue is not restored.
        assert "midModel.optLeaf.innerValue" not in names
        assert "leafMap['k'].innerValue" not in names
        assert names["leafMap['k'].count"] == "LEAFMAP__<dict-key>__COUNT"

    def test_alias_generator_prefix_all_and_case_sensitive(self):
        assert _names(cases.CamelPrefixAll)["logLevel"] == "APP_LOGLEVEL"
        names = _names(cases.CamelCaseSens)
        assert names["midModel.optLeaf.innerValue"] == "midModel__optLeaf__innerValue"
        assert names["leafMap['k'].innerValue"] == "leafMap__<dict-key>__innerValue"

    def test_null_sub_model_lists_sub_field_env_vars_by_alias(self):
        class S(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            opt: Optional[cases.AliasSub] = Field(None, alias="optAlias")
            dflt: Optional[cases.AliasSub] = None

        rendered = YamlSettingsPlus(S).render_yaml()
        assert "  optAlias.subAlias: 'OPTALIAS__SUBALIAS'" in rendered
        assert "  dflt.subChoice: 'APP_DFLT__SUBCHOICE'" in rendered


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

class TestMarkdown:
    def test_headings_and_paths_use_the_alias(self):
        md = YamlSettingsPlus(cases.Aliases).render_markdown()
        for heading in (
            "## `MY_ALIAS`",
            "## `outer.inner`",
            "### `theSub.subAlias`",
            "### `items[*].itemName`",
            "### `item_map[*].item_size`",
        ):
            assert f"\n{heading}\n" in md, heading
        assert "my_field" not in md
        assert "sub_field" not in md

    def test_field_left_out_of_the_yaml_file_has_the_note(self):
        class Sub(BaseModel):
            both: str = Field("x", alias="A", validation_alias="B")

        class S(BaseSettings):
            model_config = SettingsConfigDict(alias_generator=to_camel, env_prefix="APP_")
            both: str = Field("x", alias="A", validation_alias="B")
            explicit_val: str = Field("x", validation_alias="VAL")
            log_level: str = "INFO"
            sub: Sub = Sub()

        md = YamlSettingsPlus(S).render_markdown()
        sections = {s.split("\n", 1)[0]: s for s in md.split("\n## ")[1:]}
        assert "under its alias `A`, but validation expects `B`" in sections["`B`"]
        assert "| Environment variable | `B` |" in sections["`B`"]
        assert "under its alias `explicitVal`, but validation expects `VAL`" in sections["`VAL`"]
        # Readable fields, and sub-model fields (validated by pydantic), get no note.
        assert md.count("can not be set in the YAML file") == 2
        assert "can not be set" not in sections["`logLevel`"]

    def test_default_of_a_sub_model_uses_the_yaml_keys(self):
        # Validation reads camelCase, serialization keeps the field names: the Default
        # shows the keys of the YAML file, not what pydantic would dump.
        class Leaf(BaseModel):
            model_config = ConfigDict(alias_generator=AliasGenerator(validation_alias=to_camel))
            inner_value: str = "d"

        class S(BaseSettings):
            leaf_model: Leaf = Leaf()

        md = YamlSettingsPlus(S).render_markdown()
        rendered = YamlSettingsPlus(S).render_yaml()
        default = '{"innerValue": "d"}'
        assert f"| Default | `{default}` |" in md
        assert f"# Default:  {default}" in rendered
        assert yaml.safe_load(rendered) == {"leaf_model": {"innerValue": "d"}}
