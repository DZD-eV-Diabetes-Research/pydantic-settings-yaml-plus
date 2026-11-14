"""Tests for psyplus/utils.py — annotation helpers and formatting utilities."""
import enum
from pathlib import Path
from typing import Annotated, Any, Dict, FrozenSet, List, Literal, Optional, Set, Tuple, Union

import pytest
import yaml
from pydantic import AfterValidator, BaseModel, Field

from psyplus.utils import (
    clean_annotation,
    get_literal_list,
    get_str_dict_as_table,
    has_literal,
    is_optional,
    nested_pydantic_to_dict,
    python_annotation_to_readable,
    readable_constraints,
    to_json_text,
    to_yaml_text,
    unwrap_optional,
)


class _Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


# ---------------------------------------------------------------------------
# is_optional / unwrap_optional
# ---------------------------------------------------------------------------

class TestIsOptional:
    def test_simple_optional(self):
        assert is_optional(Optional[str]) is True

    def test_union_with_none(self):
        assert is_optional(Union[str, None]) is True

    def test_union_without_none(self):
        assert is_optional(Union[str, int]) is False

    def test_plain_type(self):
        assert is_optional(str) is False

    def test_none_type_alone(self):
        # type(None) is not a Union, so is_optional returns False
        assert is_optional(type(None)) is False


class TestUnwrapOptional:
    def test_simple_optional(self):
        assert unwrap_optional(Optional[str]) is str

    def test_non_optional_passthrough(self):
        assert unwrap_optional(str) is str

    def test_union_multiple_non_none(self):
        result = unwrap_optional(Union[str, int, None])
        # should be Union[str, int]
        assert str in result.__args__
        assert int in result.__args__
        assert type(None) not in result.__args__


# ---------------------------------------------------------------------------
# clean_annotation
# ---------------------------------------------------------------------------

class TestCleanAnnotation:
    def test_optional_str(self):
        assert clean_annotation(Optional[str]) is str

    def test_nested_optional(self):
        # Optional[Optional[str]] is just Optional[str] at runtime, but check pass-through
        assert clean_annotation(Optional[str]) is str

    def test_non_optional_passthrough(self):
        assert clean_annotation(str) is str
        assert clean_annotation(int) is int

    def test_list_passthrough(self):
        result = clean_annotation(List[str])
        assert result == List[str]

    def test_optional_list(self):
        result = clean_annotation(Optional[List[str]])
        assert result == List[str]

    def test_optional_literal(self):
        result = clean_annotation(Optional[Literal["A", "B"]])
        assert result == Literal["A", "B"]


# ---------------------------------------------------------------------------
# has_literal / get_literal_list
# ---------------------------------------------------------------------------

class TestLiteralHelpers:
    def test_has_literal_true(self):
        assert has_literal(Literal["A", "B"]) is True

    def test_has_literal_optional(self):
        assert has_literal(Optional[Literal["X", "Y"]]) is True

    def test_has_literal_false_str(self):
        assert has_literal(str) is False

    def test_has_literal_false_list(self):
        assert has_literal(List[str]) is False

    def test_get_literal_list(self):
        assert get_literal_list(Literal["A", "B"]) == ["A", "B"]

    def test_get_literal_list_optional(self):
        assert get_literal_list(Optional[Literal["X", "Y"]]) == ["X", "Y"]

    def test_get_literal_list_non_literal_returns_none(self):
        assert get_literal_list(str) is None

    def test_get_literal_list_int_values(self):
        assert get_literal_list(Literal[1, 2, 3]) == [1, 2, 3]


# ---------------------------------------------------------------------------
# python_annotation_to_readable
# ---------------------------------------------------------------------------

class TestAnnotationToReadable:
    def test_str(self):
        assert python_annotation_to_readable(str) == "str"

    def test_int(self):
        assert python_annotation_to_readable(int) == "int"

    def test_float(self):
        assert python_annotation_to_readable(float) == "float"

    def test_bool(self):
        assert python_annotation_to_readable(bool) == "bool"

    def test_optional_str(self):
        # Optional is unwrapped
        assert python_annotation_to_readable(Optional[str]) == "str"

    def test_list_typed(self):
        assert python_annotation_to_readable(List[str]) == "List of str"

    def test_list_untyped(self):
        assert python_annotation_to_readable(list) == "List"

    def test_dict_typed(self):
        result = python_annotation_to_readable(Dict[str, int])
        assert result == "Dictionary of (str, int)"

    def test_dict_untyped(self):
        assert python_annotation_to_readable(dict) == "Dictionary"

    def test_literal(self):
        assert python_annotation_to_readable(Literal["A", "B"]) == "Enum"

    def test_any(self):
        assert python_annotation_to_readable(Any) is None

    def test_base_model(self):
        class MyModel(BaseModel):
            x: int = 1

        result = python_annotation_to_readable(MyModel)
        assert "Object" in result
        assert "MyModel" in result

    def test_union(self):
        assert python_annotation_to_readable(Union[int, str]) == "int or str"
        assert python_annotation_to_readable(int | str) == "int or str"

    def test_enum_class(self):
        assert python_annotation_to_readable(_Color) == "Enum"
        assert has_literal(_Color)
        assert get_literal_list(_Color) == ["red", "blue"]

    def test_set_and_tuple_read_as_list(self):
        assert python_annotation_to_readable(Set[int]) == "List of int"
        assert python_annotation_to_readable(FrozenSet[str]) == "List of str"
        assert python_annotation_to_readable(Tuple[int, ...]) == "List of int"

    def test_annotated_is_unwrapped(self):
        assert python_annotation_to_readable(Annotated[int, Field(gt=1)]) == "int"

    def test_other_class_uses_its_name(self):
        assert python_annotation_to_readable(Path) == "Path"


# ---------------------------------------------------------------------------
# readable_constraints / to_json_text / to_yaml_text
# ---------------------------------------------------------------------------

class TestReadableConstraints:
    def _metadata(self, annotation):
        class M(BaseModel):
            x: annotation

        return M.model_fields["x"].metadata

    def test_annotated_types_constraints_are_shown(self):
        meta = self._metadata(Annotated[int, Field(gt=1, le=5)])
        assert readable_constraints(meta) == "Gt(gt=1), Le(le=5)"

    def test_validator_functions_are_dropped(self):
        meta = self._metadata(Annotated[str, Field(max_length=3), AfterValidator(str.strip)])
        assert readable_constraints(meta) == "MaxLen(max_length=3)"

    def test_empty(self):
        assert readable_constraints([]) is None


class TestTextRendering:
    def test_json_keeps_non_ascii_and_converts_path_and_enum(self):
        assert to_json_text("Grüße") == '"Grüße"'
        assert to_json_text(Path("/tmp/x")) == '"/tmp/x"'
        assert to_json_text(_Color.RED) == '"red"'

    def test_yaml_keeps_non_ascii_and_is_plain_yaml(self):
        text = to_yaml_text({"greeting": "Grüße", "where": Path("/tmp/x")})
        assert "Grüße" in text
        assert "!!" not in text
        assert yaml.safe_load(text) == {"greeting": "Grüße", "where": "/tmp/x"}


# ---------------------------------------------------------------------------
# nested_pydantic_to_dict
# ---------------------------------------------------------------------------

class TestNestedPydanticToDict:
    def test_plain_dict_passthrough(self):
        assert nested_pydantic_to_dict({"a": 1}) == {"a": 1}

    def test_plain_list_passthrough(self):
        assert nested_pydantic_to_dict([1, 2, 3]) == [1, 2, 3]

    def test_scalar_passthrough(self):
        assert nested_pydantic_to_dict("hello") == "hello"
        assert nested_pydantic_to_dict(42) == 42

    def test_base_model_instance(self):
        class M(BaseModel):
            x: int = 1
            y: str = "hi"

        assert nested_pydantic_to_dict(M()) == {"x": 1, "y": "hi"}

    def test_nested_model(self):
        class Inner(BaseModel):
            v: int = 5

        class Outer(BaseModel):
            inner: Inner = Inner()

        result = nested_pydantic_to_dict(Outer())
        assert result == {"inner": {"v": 5}}

    def test_list_of_models(self):
        class M(BaseModel):
            n: int = 0

        result = nested_pydantic_to_dict([M(n=1), M(n=2)])
        assert result == [{"n": 1}, {"n": 2}]

    def test_dict_with_model_values(self):
        class M(BaseModel):
            n: int = 7

        result = nested_pydantic_to_dict({"a": M()})
        assert result == {"a": {"n": 7}}


# ---------------------------------------------------------------------------
# get_str_dict_as_table
# ---------------------------------------------------------------------------

class TestGetStrDictAsTable:
    def test_empty(self):
        assert get_str_dict_as_table({}) == ""

    def test_alignment(self):
        d = {"Short:": "val1", "A much longer key:": "val2"}
        result = get_str_dict_as_table(d)
        lines = result.split("\n")
        # Both value columns should start at the same position
        positions = [line.index("val") for line in lines]
        assert positions[0] == positions[1]

    def test_multiline_value(self):
        d = {"Key:": "line1\nline2"}
        result = get_str_dict_as_table(d)
        assert "line1" in result
        assert "line2" in result
