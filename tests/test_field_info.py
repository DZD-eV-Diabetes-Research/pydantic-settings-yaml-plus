"""Tests for psyplus/field_info.py — FieldInfoContainer."""
from typing import Annotated, List, Literal, Optional

import pytest
from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings, SettingsConfigDict

from psyplus.field_info import DictKey, FieldInfoContainer, ListIndex


# ---------------------------------------------------------------------------
# Shared root class for env-var tests
# ---------------------------------------------------------------------------

class RootModel(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MY_", env_nested_delimiter="__")


# ---------------------------------------------------------------------------
# get_env_var
# ---------------------------------------------------------------------------

class TestGetEnvVar:
    def test_flat_field(self):
        c = FieldInfoContainer(
            path=["some_field"],
            field_name="some_field",
            root_settings_class=RootModel,
        )
        assert c.get_env_var() == "MY_SOME_FIELD"

    def test_nested_field(self):
        c = FieldInfoContainer(
            path=["parent", "child"],
            field_name="child",
            root_settings_class=RootModel,
        )
        assert c.get_env_var() == "MY_PARENT__CHILD"

    def test_list_index_in_path(self):
        c = FieldInfoContainer(
            path=["items", ListIndex(index=0), "name"],
            field_name="name",
            root_settings_class=RootModel,
        )
        env = c.get_env_var()
        assert "<list-index>" in env

    def test_dict_key_in_path(self):
        c = FieldInfoContainer(
            path=["mapping", DictKey(key="k"), "value"],
            field_name="value",
            root_settings_class=RootModel,
        )
        env = c.get_env_var()
        assert "<dict-key>" in env

    def test_no_prefix(self):
        class NoPrefixModel(BaseSettings):
            model_config = SettingsConfigDict(env_nested_delimiter="__")

        c = FieldInfoContainer(
            path=["field"],
            field_name="field",
            root_settings_class=NoPrefixModel,
        )
        assert c.get_env_var() == "FIELD"


# ---------------------------------------------------------------------------
# get_path_str
# ---------------------------------------------------------------------------

class TestGetPathStr:
    def test_flat(self):
        c = FieldInfoContainer(
            path=["field"], field_name="field", root_settings_class=RootModel
        )
        assert c.get_path_str() == "field"

    def test_nested(self):
        c = FieldInfoContainer(
            path=["a", "b", "c"], field_name="c", root_settings_class=RootModel
        )
        assert c.get_path_str() == "a.b.c"

    def test_with_list_index(self):
        c = FieldInfoContainer(
            path=["items", ListIndex(index=2)],
            field_name="[2]",
            root_settings_class=RootModel,
        )
        assert "[2]" in c.get_path_str()


# ---------------------------------------------------------------------------
# get_type_string
# ---------------------------------------------------------------------------

class TestGetTypeString:
    def test_str_annotation(self):
        fi = FieldInfo(annotation=str)
        c = FieldInfoContainer(
            path=["f"], field_name="f", root_settings_class=RootModel, field_info=fi
        )
        assert c.get_type_string() == "str"

    def test_list_annotation(self):
        fi = FieldInfo(annotation=List[str])
        c = FieldInfoContainer(
            path=["f"], field_name="f", root_settings_class=RootModel, field_info=fi
        )
        assert c.get_type_string() == "List of str"

    def test_literal_annotation(self):
        fi = FieldInfo(annotation=Literal["X", "Y"])
        c = FieldInfoContainer(
            path=["f"], field_name="f", root_settings_class=RootModel, field_info=fi
        )
        assert c.get_type_string() == "Enum"

    def test_annotation_fallback(self):
        # No field_info, use annotation kwarg
        c = FieldInfoContainer(
            path=["f"],
            field_name="f",
            root_settings_class=RootModel,
            annotation=int,
        )
        assert c.get_type_string() == "int"


# ---------------------------------------------------------------------------
# get_enum_vals
# ---------------------------------------------------------------------------

class TestGetEnumVals:
    def test_literal(self):
        fi = FieldInfo(annotation=Literal["A", "B", "C"])
        c = FieldInfoContainer(
            path=["f"], field_name="f", root_settings_class=RootModel, field_info=fi
        )
        assert c.get_enum_vals() == ["A", "B", "C"]

    def test_optional_literal(self):
        fi = FieldInfo(annotation=Optional[Literal["X", "Y"]])
        c = FieldInfoContainer(
            path=["f"], field_name="f", root_settings_class=RootModel, field_info=fi
        )
        assert c.get_enum_vals() == ["X", "Y"]

    def test_non_literal_returns_none(self):
        fi = FieldInfo(annotation=str)
        c = FieldInfoContainer(
            path=["f"], field_name="f", root_settings_class=RootModel, field_info=fi
        )
        assert c.get_enum_vals() is None


# ---------------------------------------------------------------------------
# build_comment_lines
# ---------------------------------------------------------------------------

class TestBuildCommentLines:
    def _make(self, fi: FieldInfo, path=None) -> FieldInfoContainer:
        return FieldInfoContainer(
            path=path or ["my_field"],
            field_name="my_field",
            root_settings_class=RootModel,
            field_info=fi,
        )

    def test_header_present(self):
        fi = FieldInfo(annotation=str)
        lines = self._make(fi).build_comment_lines()
        assert any("## my_field ###" in l for l in lines)

    def test_required_true(self):
        fi = FieldInfo(annotation=str)  # no default → required
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "Required:      True" in comment or "Required:" in comment

    def test_required_false_with_default(self):
        fi = FieldInfo(annotation=str, default="hello")
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "Required:" in comment
        assert "False" in comment

    def test_default_shown(self):
        fi = FieldInfo(annotation=str, default="world")
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "Default:" in comment
        assert "world" in comment

    def test_default_null(self):
        fi = FieldInfo(annotation=Optional[str], default=None)
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "null" in comment

    def test_env_var_shown(self):
        fi = FieldInfo(annotation=str, default="x")
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "Env-var:" in comment
        assert "MY_MY_FIELD" in comment

    def test_description_shown(self):
        fi = FieldInfo(annotation=str, default="x", description="My description")
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "My description" in comment

    def test_allowed_vals_shown(self):
        fi = FieldInfo(annotation=Literal["A", "B"])
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "Allowed vals:" in comment
        assert "A" in comment
        assert "B" in comment

    def test_title_in_header(self):
        fi = FieldInfo(annotation=str, default="x", title="My Title")
        lines = self._make(fi).build_comment_lines()
        assert any("My Title" in l for l in lines)

    def test_overwrite_required_false(self):
        fi = FieldInfo(annotation=str)  # would be required normally
        comment = "\n".join(self._make(fi).build_comment_lines(overwrite_required=False))
        assert "False" in comment

    def test_examples_shown(self):
        fi = FieldInfo(annotation=str, default="x", examples=["ex1", "ex2"])
        comment = "\n".join(self._make(fi).build_comment_lines())
        assert "Example" in comment
        assert "ex1" in comment

    def test_yaml_path_shown_for_nested(self):
        fi = FieldInfo(annotation=str, default="x")
        c = FieldInfoContainer(
            path=["parent", "child"],
            field_name="child",
            root_settings_class=RootModel,
            field_info=fi,
        )
        comment = "\n".join(c.build_comment_lines())
        assert "YAML-path:" in comment
        assert "parent.child" in comment

    def test_yaml_path_hidden_for_flat(self):
        fi = FieldInfo(annotation=str, default="x")
        comment = "\n".join(self._make(fi).build_comment_lines())
        # When key == path there should be no YAML-path row
        assert "YAML-path:" not in comment
