"""Env vars that set a single list element (``APP_ITEMS__0__NAME``) through load().

The rules are described in psyplus/sources.py. The env var names the generated files
document are checked in test_env_roundtrip.py.
"""
from __future__ import annotations

import enum
import os
from pathlib import Path
from typing import Annotated, Dict, List, Optional, Set, Tuple, Union
from unittest import mock

import pytest
import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic.alias_generators import to_camel
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
    YamlConfigSettingsSource,
)

from psyplus import YamlSettingsPlus


class Item(BaseModel):
    name: str
    size: int = 1
    tags: List[str] = ["d0", "d1"]
    attrs: Dict[str, str] = {}


class Color(enum.Enum):
    RED = "r"
    GREEN = "g"


class Cfg(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    items: List[Item] = [Item(name="default0")]
    tags: List[str] = ["t0"]
    required_list: List[str] = []
    maybe: Optional[List[str]] = ["m0"]
    pair: Tuple[str, int] = ("p", 1)
    many: Tuple[int, ...] = (1, 2)
    unique: Set[str] = {"u0"}
    groups: Dict[str, List[str]] = {}
    matrix: List[List[int]] = [[1, 2]]
    either: Union[List[str], Dict[str, str]] = []
    nullable_items: List[Optional[str]] = ["n0"]


YAML_DATA = {
    "items": [{"name": "y0", "tags": ["a", "b"]}, {"name": "y1", "size": 2}],
    "tags": ["x", "y"],
}


def load(model, tmp_path: Path, env: dict[str, str], data=YAML_DATA):
    config = tmp_path / "config.yaml"
    if data is not None:
        config.write_text(yaml.safe_dump(data))
    with mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", ""), **env}, clear=True):
        return YamlSettingsPlus(model, config).load()


def dump_items(cfg) -> list[dict]:
    return [i.model_dump() for i in cfg.items]


# ---------------------------------------------------------------------------
# Index inside the list: change that element
# ---------------------------------------------------------------------------

class TestChangeElement:
    def test_field_of_element_merges_into_yaml_element(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__0__NAME": "env"})
        assert dump_items(cfg) == [
            {"name": "env", "size": 1, "tags": ["a", "b"], "attrs": {}},
            {"name": "y1", "size": 2, "tags": ["d0", "d1"], "attrs": {}},
        ]

    def test_scalar_element(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_TAGS__1": "env"})
        assert cfg.tags == ["x", "env"]

    def test_list_inside_element(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__0__TAGS__1": "env"})
        assert cfg.items[0].tags == ["a", "env"]
        assert cfg.items[1].name == "y1"

    def test_list_missing_in_yaml_element_uses_the_field_default(self, tmp_path):
        # items[1] in the YAML file has no tags, Item.tags defaults to ["d0", "d1"]
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__1__TAGS__2": "d2"})
        assert cfg.items[1].tags == ["d0", "d1", "d2"]

    def test_dict_inside_element(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__1__ATTRS__team": "core"})
        assert cfg.items[1].attrs == {"team": "core"}
        assert cfg.items[1].size == 2

    def test_list_inside_dict(self, tmp_path):
        data = {"groups": {"admins": ["ann", "bob"]}}
        cfg = load(Cfg, tmp_path, {"APP_GROUPS__admins__1": "carl"}, data)
        assert cfg.groups == {"admins": ["ann", "carl"]}

    def test_list_inside_list(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_MATRIX__0__1": "9"}, {"matrix": [[1, 2], [3]]})
        assert cfg.matrix == [[1, 9], [3]]

    def test_json_object_merges_into_element(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__1": '{"name": "json"}'})
        assert dump_items(cfg)[1] == {"name": "json", "size": 2, "tags": ["d0", "d1"], "attrs": {}}

    def test_nested_var_beats_json_of_same_element(self, tmp_path):
        env = {"APP_ITEMS__1": '{"name": "json", "size": 7}', "APP_ITEMS__1__SIZE": "8"}
        cfg = load(Cfg, tmp_path, env)
        assert (cfg.items[1].name, cfg.items[1].size) == ("json", 8)

    def test_json_list_as_element_of_list(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_MATRIX__0": "[7, 8, 9]"}, {"matrix": [[1], [2]]})
        assert cfg.matrix == [[7, 8, 9], [2]]

    def test_invalid_json_for_model_element_is_an_error(self, tmp_path):
        with pytest.raises(SettingsError, match=r"APP_ITEMS__0: `items\[0\]` needs a JSON value"):
            load(Cfg, tmp_path, {"APP_ITEMS__0": "not json"})

    def test_lower_case_env_var_names(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"app_items__0__name": "env"})
        assert cfg.items[0].name == "env"

    def test_null_with_env_parse_none_str(self, tmp_path):
        class NoneStr(Cfg):
            model_config = SettingsConfigDict(env_parse_none_str="null")

        cfg = load(NoneStr, tmp_path, {"APP_NULLABLE_ITEMS__0": "null"}, {"nullable_items": ["a", "b"]})
        assert cfg.nullable_items == [None, "b"]


# ---------------------------------------------------------------------------
# Index at or beyond the end: add elements, no gaps
# ---------------------------------------------------------------------------

class TestAddElements:
    def test_index_equal_to_length_appends(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_TAGS__2": "z"})
        assert cfg.tags == ["x", "y", "z"]

    def test_several_new_indices_without_gap(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_TAGS__3": "w", "APP_TAGS__2": "z"})
        assert cfg.tags == ["x", "y", "z", "w"]

    def test_new_model_element_gets_field_defaults(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__2__NAME": "new", "APP_ITEMS__2__TAGS__2": "d2"})
        assert dump_items(cfg)[2] == {"name": "new", "size": 1, "tags": ["d0", "d1", "d2"], "attrs": {}}

    def test_new_model_element_still_needs_required_fields(self, tmp_path):
        with pytest.raises(ValidationError, match=r"items\.2\.name"):
            load(Cfg, tmp_path, {"APP_ITEMS__2__SIZE": "3"})

    def test_index_beyond_length_is_an_error(self, tmp_path):
        with pytest.raises(SettingsError) as e:
            load(Cfg, tmp_path, {"APP_ITEMS__3__NAME": "gap"})
        msg = str(e.value)
        assert "Environment variable APP_ITEMS__3__NAME" in msg
        assert "list index 3 is out of range, `items` has 2 element(s)" in msg
        assert "from the YAML file" in msg

    def test_gap_between_new_indices_is_an_error(self, tmp_path):
        with pytest.raises(SettingsError, match=r"APP_TAGS__4: list index 4 is out of range"):
            load(Cfg, tmp_path, {"APP_TAGS__2": "z", "APP_TAGS__4": "gap"})

    def test_fixed_tuple_can_change_but_not_grow(self, tmp_path):
        assert load(Cfg, tmp_path, {"APP_PAIR__1": "5"}, {"pair": ["a", 1]}).pair == ("a", 5)
        with pytest.raises(ValidationError, match="pair"):
            load(Cfg, tmp_path, {"APP_PAIR__2": "x"}, {"pair": ["a", 1]})

    def test_set_element_is_added(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_UNIQUE__1": "b"}, {"unique": ["a"]})
        assert cfg.unique == {"a", "b"}


# ---------------------------------------------------------------------------
# What the patch applies to when the YAML file has no list
# ---------------------------------------------------------------------------

class TestMissingList:
    def test_field_default_is_used(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_ITEMS__0__SIZE": "5", "APP_ITEMS__1__NAME": "n"}, data=None)
        assert [(i.name, i.size) for i in cfg.items] == [("default0", 5), ("n", 1)]

    def test_out_of_range_names_the_default(self, tmp_path):
        with pytest.raises(SettingsError, match=r"`tags` has 1 element\(s\) \(its default"):
            load(Cfg, tmp_path, {"APP_TAGS__2": "z"}, data={})

    def test_default_factory(self, tmp_path):
        class Factory(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            tags: List[str] = Field(default_factory=lambda: ["f0", "f1"])

        cfg = load(Factory, tmp_path, {"APP_TAGS__1": "env"}, data={})
        assert cfg.tags == ["f0", "env"]

    def test_required_list_is_built_from_index_0(self, tmp_path):
        class Required(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            names: List[str]

        cfg = load(Required, tmp_path, {"APP_NAMES__1": "b", "APP_NAMES__0": "a"}, data={})
        assert cfg.names == ["a", "b"]
        with pytest.raises(SettingsError, match="APP_NAMES__1: list index 1 is out of range"):
            load(Required, tmp_path, {"APP_NAMES__1": "b"}, data={})

    def test_null_in_yaml_counts_as_empty(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_MAYBE__0": "a"}, {"maybe": None})
        assert cfg.maybe == ["a"]

    def test_null_default_counts_as_empty(self, tmp_path):
        class NullDefault(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            maybe: Optional[List[int]] = None

        assert load(NullDefault, tmp_path, {"APP_MAYBE__0": "3"}, data={}).maybe == [3]

    def test_yaml_value_that_is_not_a_list_is_an_error(self, tmp_path):
        with pytest.raises(SettingsError, match=r"APP_TAGS__0: can not set element 0 of `tags`"):
            load(Cfg, tmp_path, {"APP_TAGS__0": "a"}, {"tags": "not a list"})


# ---------------------------------------------------------------------------
# Segments that are no list index
# ---------------------------------------------------------------------------

class TestBadSegments:
    @pytest.mark.parametrize(
        "env_name,segment",
        [("APP_TAGS__-1", "-1"), ("APP_TAGS__01", "01"), ("APP_ITEMS__0__TAGS__X", "X")],
    )
    def test_index_like_or_below_an_index_is_an_error(self, tmp_path, env_name, segment):
        with pytest.raises(SettingsError) as e:
            load(Cfg, tmp_path, {env_name: "v"})
        assert f"Environment variable {env_name}:" in str(e.value)
        assert f"so `{segment}` must be a list index (0, 1, 2, ...)" in str(e.value)

    def test_other_segments_are_left_to_pydantic_settings(self, tmp_path):
        # Without an index involved, pydantic-settings handles it as it always did:
        # next to a JSON list it ignores the env var, alone it fails list validation.
        env = {"APP_TAGS": '["j"]', "APP_TAGS__FOO": "1", "APP_ITEMS__1__NAME": "env"}
        cfg = load(Cfg, tmp_path, env)
        assert (cfg.tags, cfg.items[1].name) == (["j"], "env")
        with pytest.raises(ValidationError, match="valid list"):
            load(Cfg, tmp_path, {"APP_TAGS__FOO": "1", "APP_ITEMS__1__NAME": "env"})

    def test_union_with_dict_leaves_other_segments_to_pydantic_settings(self, tmp_path):
        assert load(Cfg, tmp_path, {"APP_EITHER__key": "v"}).either == {"key": "v"}
        assert load(Cfg, tmp_path, {"APP_EITHER__0": "v"}).either == ["v"]


# ---------------------------------------------------------------------------
# Whole list values and source priority
# ---------------------------------------------------------------------------

def with_dotenv(tmp_path: Path, content: str, base=Cfg):
    env_file = tmp_path / ".env"
    env_file.write_text(content)

    class WithDotenv(base):
        model_config = SettingsConfigDict(env_file=env_file)

    return WithDotenv


class TestWholeListAndSources:
    def test_index_vars_change_the_json_list_of_the_same_source(self, tmp_path):
        env = {"APP_TAGS": '["j0", "j1"]', "APP_TAGS__1": "env", "APP_TAGS__2": "new"}
        assert load(Cfg, tmp_path, env).tags == ["j0", "env", "new"]

    def test_index_vars_inside_json_of_a_sub_model(self, tmp_path):
        class Sub(BaseModel):
            tags: List[str] = []

        class WithSub(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            sub: Sub = Sub()

        env = {"APP_SUB": '{"tags": ["j0"]}', "APP_SUB__TAGS__1": "env"}
        assert load(WithSub, tmp_path, env, {"sub": {"tags": ["y0", "y1", "y2"]}}).sub.tags == [
            "j0", "env",
        ]

    def test_dotenv_index_vars(self, tmp_path):
        model = with_dotenv(tmp_path, "APP_ITEMS__1__NAME=dotenv\nAPP_TAGS__2=z\n")
        cfg = load(model, tmp_path, {})
        assert [i.name for i in cfg.items] == ["y0", "dotenv"]
        assert cfg.tags == ["x", "y", "z"]

    def test_dotenv_error_names_the_file(self, tmp_path):
        model = with_dotenv(tmp_path, "APP_TAGS__5=z\n")
        with pytest.raises(SettingsError, match=r"APP_TAGS__5 in the \.env file: list index 5"):
            load(model, tmp_path, {})

    def test_env_patches_on_top_of_dotenv_patches(self, tmp_path):
        model = with_dotenv(tmp_path, "APP_TAGS__1=dotenv\nAPP_TAGS__2=dotenv2\n")
        cfg = load(model, tmp_path, {"APP_TAGS__1": "env", "APP_TAGS__3": "env3"})
        assert cfg.tags == ["x", "env", "dotenv2", "env3"]

    def test_env_index_var_patches_the_dotenv_json_list(self, tmp_path):
        model = with_dotenv(tmp_path, "APP_TAGS='[\"d0\", \"d1\"]'\n")
        assert load(model, tmp_path, {"APP_TAGS__0": "env"}).tags == ["env", "d1"]

    def test_env_json_list_beats_dotenv_index_vars(self, tmp_path):
        model = with_dotenv(tmp_path, "APP_TAGS__0=dotenv\n")
        assert load(model, tmp_path, {}).tags == ["dotenv", "y"]
        assert load(model, tmp_path, {"APP_TAGS": '["e0"]'}).tags == ["e0"]

    def test_yaml_ranked_above_env_wins(self, tmp_path):
        class YamlFirst(Cfg):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings,
                file_secret_settings,
            ):
                return (init_settings, YamlConfigSettingsSource(settings_cls), env_settings)

        cfg = load(YamlFirst, tmp_path, {"APP_TAGS__0": "env", "APP_MAYBE__0": "env"})
        assert cfg.tags == ["x", "y"]  # the YAML list replaces the patched default
        assert cfg.maybe == ["env"]  # not in the YAML file: the patched default


# ---------------------------------------------------------------------------
# Model settings
# ---------------------------------------------------------------------------

class TestModelSettings:
    def test_case_sensitive(self, tmp_path):
        class Sens(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", case_sensitive=True
            )
            Items: List[Item] = []

        data = {"Items": [{"name": "y0"}]}
        assert load(Sens, tmp_path, {"APP_Items__0__name": "env"}, data).Items[0].name == "env"
        # Another case is another env var name, it is not read.
        assert load(Sens, tmp_path, {"APP_ITEMS__0__NAME": "env"}, data).Items[0].name == "y0"

    def test_max_split_counts_the_index_as_a_level(self, tmp_path):
        class Split(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="_", env_nested_max_split=2
            )
            items: List[Item] = []

        data = {"items": [{"name": "y0", "attrs": {}}]}
        cfg = load(Split, tmp_path, {"APP_ITEMS_0_NAME": "env"}, data)
        assert cfg.items[0].name == "env"

    def test_max_split_too_low_for_the_element_field(self, tmp_path):
        class Split(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="_", env_nested_max_split=1
            )
            items: List[Item] = []

        # "0_name" stays one segment, which is no list index; the element itself works.
        data = {"items": [{"name": "y0"}]}
        assert load(Split, tmp_path, {"APP_ITEMS_0": '{"name": "env"}'}, data).items[0].name == "env"
        with pytest.raises(ValidationError, match="valid list"):
            load(Split, tmp_path, {"APP_ITEMS_0_NAME": "env"}, data)

    def test_env_prefix_target_alias(self, tmp_path):
        class Target(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", env_prefix_target="alias"
            )
            tags: List[str] = []

        # The prefix only applies to aliases, so the field's env var has none.
        assert load(Target, tmp_path, {"TAGS__1": "env"}, {"tags": ["a", "b"]}).tags == ["a", "env"]

    def test_strict_model_gets_coerced_values(self, tmp_path):
        class Strict(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", strict=True
            )
            numbers: List[int] = [1, 2]

        assert load(Strict, tmp_path, {"APP_NUMBERS__1": "5"}, data={}).numbers == [1, 5]

    def test_env_parse_enums(self, tmp_path):
        class Enums(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", env_parse_enums=True
            )
            colors: List[Color] = [Color.RED, Color.RED]

        assert load(Enums, tmp_path, {"APP_COLORS__1": "GREEN"}, data={}).colors == [
            Color.RED, Color.GREEN,
        ]

    def test_field_alias_inside_element(self, tmp_path):
        class Aliased(BaseModel):
            name: str = Field("a", alias="Label")

        class WithAlias(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            entries: List[Aliased] = []

        cfg = load(WithAlias, tmp_path, {"APP_ENTRIES__0__LABEL": "env"}, {"entries": [{"Label": "y"}]})
        assert cfg.entries[0].name == "env"


# ---------------------------------------------------------------------------
# Source chains
# ---------------------------------------------------------------------------

class TestSourceChains:
    def test_model_without_env_settings_ignores_index_vars(self, tmp_path):
        env = {"APP_TAGS__0": "env", "APP_TAGS__9": "gap"}
        with pytest.raises(SettingsError, match="APP_TAGS__9"):
            load(Cfg, tmp_path, env)

        class NoEnv(Cfg):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings,
                file_secret_settings,
            ):
                return (init_settings,)

        assert load(NoEnv, tmp_path, env).tags == ["x", "y"]

    @pytest.mark.parametrize("own", ["plain", "dotenv", "subclass"])
    def test_source_built_by_the_model_works_as_pydantic_settings_makes_it(self, tmp_path, own):
        env_file = tmp_path / "other.env"
        env_file.write_text("APP_TAGS__1=dotenv\n")

        class MyEnv(EnvSettingsSource):
            pass

        def make(settings_cls):
            if own == "dotenv":
                return DotEnvSettingsSource(settings_cls, env_file=env_file)
            return (EnvSettingsSource if own == "plain" else MyEnv)(settings_cls)

        class OwnEnv(Cfg):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings,
                file_secret_settings,
            ):
                return (init_settings, make(settings_cls))

        class PassedOn(Cfg):
            model_config = SettingsConfigDict(env_file=env_file)

        env = {} if own == "dotenv" else {"APP_TAGS__1": "env"}
        # The sources load() passes in read the index, ...
        assert load(PassedOn, tmp_path, env).tags[1] in ("env", "dotenv")
        # ... one the model builds itself does what pydantic-settings does.
        with pytest.raises(ValidationError, match="valid list"):
            load(OwnEnv, tmp_path, env)

    def test_direct_instantiation_does_not_read_index_vars(self, tmp_path):
        # Only load() reads them, the model on its own works as pydantic-settings does.
        assert load(Cfg, tmp_path, {"APP_TAGS__0": "env"}).tags == ["env", "y"]
        with mock.patch.dict(os.environ, {"APP_TAGS__0": "env"}, clear=True):
            with pytest.raises(ValidationError, match="valid list"):
                Cfg()

    def test_chain_is_unchanged_without_index_vars(self):
        from psyplus.sources import ListIndexEnvSettingsSource, resolve_list_patches

        with mock.patch.dict(os.environ, {"APP_TAGS": '["a"]', "APP_TAGS__0": "x"}, clear=True):
            # APP_TAGS__0 sets a list element, so this chain is resolved
            sources = (ListIndexEnvSettingsSource(Cfg),)
            assert resolve_list_patches(Cfg, sources) is not sources
        with mock.patch.dict(os.environ, {"APP_TAGS": '["a"]', "APP_GROUPS__x": '["b"]'}, clear=True):
            sources = (ListIndexEnvSettingsSource(Cfg),)
            assert resolve_list_patches(Cfg, sources) is sources

    def test_model_fields_set(self, tmp_path):
        cfg = load(Cfg, tmp_path, {"APP_MAYBE__0": "env"}, data={})
        assert "maybe" in cfg.model_fields_set
        assert "tags" not in cfg.model_fields_set


# ---------------------------------------------------------------------------
# Review findings
# ---------------------------------------------------------------------------

class TestAliasKeys:
    def test_top_level_alias_with_populate_by_name(self, tmp_path):
        class A(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", populate_by_name=True
            )
            servers: List[str] = Field(default=["d"], alias="srv")

        # The YAML file may use the field name or the alias, so may the env var.
        for env_name in ("SRV__1", "APP_SERVERS__1"):
            for key in ("servers", "srv"):
                cfg = load(A, tmp_path, {env_name: "x"}, {key: ["a", "b"]})
                assert cfg.servers == ["a", "x"], (env_name, key)

    def test_top_level_alias_with_extra_ignore(self, tmp_path):
        class A(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", populate_by_name=True,
                extra="ignore",
            )
            servers: List[str] = Field(default=["d"], alias="srv")

        assert load(A, tmp_path, {"SRV__1": "x"}, {"servers": ["a", "b"]}).servers == ["a", "x"]

    def test_alias_choices(self, tmp_path):
        class B(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            servers: List[str] = Field(
                default=["d"], validation_alias=AliasChoices("srv", "servers2")
            )

        for key in ("srv", "servers2"):
            cfg = load(B, tmp_path, {"SERVERS2__1": "x"}, {key: ["a", "b"]})
            assert cfg.servers == ["a", "x"], key

    def test_alias_generator_in_sub_model_with_populate_by_name(self, tmp_path):
        class Sub(BaseModel):
            model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
            host_names: List[str] = []
            port_num: int = 1

        class Gen(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            sub: Sub = Sub()

        data = {"sub": {"host_names": ["a", "b"], "port_num": 5}}
        cfg = load(Gen, tmp_path, {"APP_SUB__HOST_NAMES__1": "x"}, data)
        assert (cfg.sub.host_names, cfg.sub.port_num) == (["a", "x"], 5)
        cfg = load(Gen, tmp_path, {"APP_SUB__HOST_NAMES__2": "x"}, data)
        assert cfg.sub.host_names == ["a", "b", "x"]
        data = {"sub": {"hostNames": ["a", "b"]}}
        assert load(Gen, tmp_path, {"APP_SUB__HOST_NAMES__0": "x"}, data).sub.host_names == [
            "x", "b",
        ]

    def test_mixed_case_field_with_json_of_the_same_source(self, tmp_path):
        class Sub(BaseModel):
            Tags: List[str] = []

        class Mixed(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            sub: Sub = Sub()

        env = {"APP_SUB__TAGS": '["j0", "j1"]', "APP_SUB__TAGS__1": "x"}
        cfg = load(Mixed, tmp_path, env, {"sub": {"Tags": ["a", "b", "c"]}})
        assert cfg.sub.Tags == ["j0", "x"]

    def test_default_with_serialization_alias(self, tmp_path):
        class Ser(BaseModel):
            host: str = Field(serialization_alias="Host")
            port: int = 1

        class S(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            items: List[Ser] = [Ser(host="h0", port=1)]

        cfg = load(S, tmp_path, {"APP_ITEMS__0__PORT": "2"}, data={})
        assert (cfg.items[0].host, cfg.items[0].port) == ("h0", 2)


class TestOtherSources:
    def test_settings_sources_data_keeps_the_documented_names(self, tmp_path):
        seen = {}

        class Peek(PydanticBaseSettingsSource):
            def get_field_value(self, field, field_name):
                return None, field_name, False

            def __call__(self):
                seen["names"] = list(self.settings_sources_data)
                seen["state"] = self.current_state
                return {}

        class P(Cfg):
            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings,
                file_secret_settings,
            ):
                return (init_settings, env_settings, dotenv_settings, Peek(settings_cls))

        cfg = load(P, tmp_path, {"APP_TAGS__0": "x", "APP_ITEMS": '[{"name": "e"}]'})
        assert cfg.tags == ["x", "y"]
        assert "EnvSettingsSource" in seen["names"]
        assert "DotEnvSettingsSource" in seen["names"]
        # A lower source sees plain data: the env var's list patch still waits for the
        # sources below, so it is not in there.
        assert seen["state"] == {"items": [{"name": "e"}]}
        # pydantic-settings' own error messages name the source the documented way too.
        with pytest.raises(SettingsError, match='from source "EnvSettingsSource"'):
            load(Cfg, tmp_path, {"APP_ITEMS": "not json", "APP_TAGS__0": "x"})


class TestSameSourceWholeValue:
    def test_out_of_range_error_is_not_wrapped(self, tmp_path):
        with pytest.raises(SettingsError) as e:
            load(Cfg, tmp_path, {"APP_TAGS": '["a"]', "APP_TAGS__5": "x"})
        assert str(e.value).startswith("Environment variable APP_TAGS__5: list index 5")
        assert "its whole value from the same source" in str(e.value)

    def test_null_whole_value_counts_as_empty(self, tmp_path):
        class N(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="APP_", env_nested_delimiter="__", env_parse_none_str="null"
            )
            tags: Optional[List[str]] = ["d"]

        env = {"APP_TAGS": "null", "APP_TAGS__0": "x"}
        assert load(N, tmp_path, env, {"tags": ["a"]}).tags == ["x"]
        assert load(N, tmp_path, {"APP_TAGS": "null"}, {"tags": ["a"]}).tags is None

    def test_no_decode_string_can_not_be_patched(self, tmp_path):
        class ND(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
            tags: Annotated[List[str], NoDecode] = []

            @field_validator("tags", mode="before")
            @classmethod
            def split(cls, v):
                return v.split(",") if isinstance(v, str) else v

        assert load(ND, tmp_path, {"APP_TAGS": "a,b"}, data={}).tags == ["a", "b"]
        # The split happens in validation, after the sources: nothing to patch yet.
        with pytest.raises(SettingsError, match=r"APP_TAGS__1: can not set element 1 of `tags`"):
            load(ND, tmp_path, {"APP_TAGS": "a,b", "APP_TAGS__1": "x"}, data={})
        # A list from the YAML file is patched as usual.
        assert load(ND, tmp_path, {"APP_TAGS__1": "x"}, {"tags": ["a", "b"]}).tags == ["a", "x"]

