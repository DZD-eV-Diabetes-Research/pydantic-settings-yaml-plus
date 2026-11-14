from __future__ import annotations

import collections
import collections.abc
import datetime
import enum
import json
import re
import typing
from typing import Annotated, Any, Generator, Literal, Union, cast, get_args, get_origin

from pydantic import (
    AwareDatetime,
    FutureDate,
    FutureDatetime,
    NaiveDatetime,
    PastDate,
    PastDatetime,
)
from pydantic import AfterValidator, BaseModel, BeforeValidator, PlainValidator, WrapValidator
from pydantic_core import to_jsonable_python
import yaml
from pydantic_settings import BaseSettings

# Python 3.10-3.13: `X | Y` creates types.UnionType (distinct from typing.Union).
# Python 3.14: the two were merged; types.UnionType is typing.Union.
# We capture the native type once so is_optional/unwrap_optional handle both.
try:
    from types import UnionType as _NativeUnionType
except ImportError:
    _NativeUnionType = None  # type: ignore[assignment,misc]

PYTHON_SCALAR_TYPES = [
    int,
    float,
    str,
    bool,
    datetime.time,
    datetime.date,
    datetime.datetime,
    PastDate,
    FutureDate,
    PastDatetime,
    FutureDatetime,
    AwareDatetime,
    NaiveDatetime,
]


def is_union(annotation: Any) -> bool:
    """True for typing.Union[...] and PEP 604 X | Y unions (all Python versions)."""
    if get_origin(annotation) is Union:
        return True
    if _NativeUnionType is not None and isinstance(annotation, _NativeUnionType):
        return True
    return False


def is_optional(annotation: Any) -> bool:
    """Return True if annotation is Optional[X] or any Union containing None."""
    return is_union(annotation) and type(None) in get_args(annotation)


def unwrap_optional(annotation: Any) -> Any:
    """Strip None from a Union/Optional, returning the remaining type."""
    if is_union(annotation):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
        return Union[tuple(non_none)]
    return annotation


def is_nullable(annotation: Any) -> bool:
    """True when the annotation accepts None at its top level, looking through Annotated."""
    if get_origin(annotation) is Annotated:
        return is_nullable(get_args(annotation)[0])
    return is_optional(annotation)


def clean_annotation(annotation: Any) -> Any:
    """Recursively unwrap Annotated and Optional/Union-with-None wrappers."""
    if get_origin(annotation) is Annotated:
        return clean_annotation(get_args(annotation)[0])
    if is_optional(annotation):
        return clean_annotation(unwrap_optional(annotation))
    return annotation


# ``type X = ...`` aliases: ``typing.TypeAliasType`` from Python 3.12 on, and the
# ``typing_extensions`` variant (its own class on Python 3.11).
try:
    import typing_extensions as _typing_extensions
except ImportError:  # pragma: no cover
    _typing_extensions = None  # type: ignore[assignment]
TYPE_ALIAS_TYPES: tuple[type, ...] = tuple(
    {getattr(m, "TypeAliasType", None) for m in (typing, _typing_extensions)} - {None}
)


def unwrap_type_alias(annotation: Any) -> Any:
    """The value of a ``type X = ...`` alias (also nested ones), else *annotation*."""
    while isinstance(annotation, TYPE_ALIAS_TYPES):
        annotation = annotation.__value__
    return annotation


def is_list_like(annotation: Any) -> bool:
    """True for list, tuple, set, frozenset, deque and other sequence or set annotations.

    Looks through type aliases, Annotated and Optional. str and bytes do not count.
    """
    cleaned = unwrap_type_alias(clean_annotation(unwrap_type_alias(annotation)))
    origin = get_origin(cleaned) or cleaned
    if not isinstance(origin, type) or issubclass(origin, (str, bytes, bytearray, BaseModel)):
        return False
    return issubclass(origin, (collections.abc.Sequence, collections.abc.Set, collections.deque))


def _is_enum_class(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, enum.Enum)


def has_literal(annotation: Any) -> bool:
    """Return True if annotation is or wraps a Literal type or an Enum class."""
    cleaned = clean_annotation(annotation)
    return get_origin(cleaned) is Literal or _is_enum_class(cleaned)


def get_literal_list(annotation: Any) -> list[Any] | None:
    """Return the allowed values of a Literal annotation or Enum class, or None."""
    cleaned = clean_annotation(annotation)
    if get_origin(cleaned) is Literal:
        return list(get_args(cleaned))
    if _is_enum_class(cleaned):
        return [member.value for member in cleaned]
    return None


def is_model_class(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def model_members(annotation: Any) -> list[type[BaseModel]]:
    """The model classes a field can hold, in declaration order.

    ``Model`` and ``Optional[Model]`` give one class, ``Union[A, B]`` gives every
    model member (members that are not models, like ``str``, are left out).
    """
    cleaned = clean_annotation(annotation)
    if is_model_class(cleaned):
        return [cleaned]
    if not is_union(cleaned):
        return []
    members: list[type[BaseModel]] = []
    for arg in get_args(cleaned):
        arg = clean_annotation(arg)
        if is_model_class(arg) and arg not in members:
            members.append(arg)
    return members


def is_fixed_length_tuple(annotation: Any) -> bool:
    """True for ``Tuple[int, str]``, False for ``Tuple[int, ...]``, bare ``tuple`` and ``Tuple[()]``."""
    args = get_args(annotation)
    return get_origin(annotation) is tuple and bool(args) and args[-1] is not Ellipsis


def sequence_item_annotation(annotation: Any, index: int) -> Any:
    """The annotation of element ``index`` of a list, set or tuple annotation, or None.

    A fixed-length tuple has one annotation per position (``Tuple[int, str]``);
    every other sequence has the same annotation for all elements.
    """
    if annotation is None:
        return None
    cleaned = clean_annotation(annotation)
    args = get_args(cleaned)
    if is_fixed_length_tuple(cleaned):
        return args[index] if index < len(args) else None
    return args[0] if args else None


def md_code(text: str) -> str:
    """Wrap ``text`` in a Markdown inline code span that survives backticks in ``text``.

    CommonMark closes a code span at the first backtick run as long as the opening
    one, so the fence is one backtick longer than the longest run inside. A space on
    both sides keeps a leading or trailing backtick apart from the fence; renderers
    strip that one space again (and would strip it from text that starts and ends
    with a space, so such text gets the padding as well). Empty text has no code
    span form, callers show ``""`` instead.
    """
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    if text.startswith("`") or text.endswith("`") or (
        text.startswith(" ") and text.endswith(" ") and text.strip(" ")
    ):
        text = f" {text} "
    return f"{fence}{text}{fence}"


def md_table_cell(text: str) -> str:
    """Make ``text`` safe as one cell of a GFM table row.

    A ``|`` would end the cell (also inside a code span) and a line break would end
    the row. Line breaks become spaces, which is also how a code span renders them.
    """
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|")


MD_MAX_HEADING_LEVEL = 6


def md_heading(level: int, text: str) -> str:
    """A Markdown heading, capped at level 6 (``#######`` is not a heading in Markdown)."""
    return f"{'#' * min(level, MD_MAX_HEADING_LEVEL)} {text}"


def python_annotation_to_readable(annotation: Any) -> str | None:
    """Convert a Python type annotation to a human-readable string."""

    def _stringify(annot: Any) -> str | None:
        if isinstance(annot, tuple):
            parts: list[str] = []
            for a in cast(tuple[Any, ...], annot):
                s = _stringify(a)
                if s is not None:
                    parts.append(s)
            return ", ".join(parts) if parts else None

        if is_optional(annot) or get_origin(annot) is Annotated:
            return _stringify(clean_annotation(annot))

        if annot is Any or annot is None:
            return None

        if annot in PYTHON_SCALAR_TYPES:
            return annot.__name__

        origin = get_origin(annot)

        if is_fixed_length_tuple(annot):
            items = [_stringify(a) or "any" for a in get_args(annot)]
            count = f"exactly {len(items)} item" + ("s" if len(items) != 1 else "")
            return f"List of {count} ({', '.join(items)})"

        if origin in (list, set, frozenset, tuple) or annot in (list, set, frozenset, tuple):
            args = tuple(a for a in get_args(annot) if a is not Ellipsis)
            inner = _stringify(args) if args else None
            return f"List of {inner}" if inner else "List"

        if origin is dict or annot is dict:
            args = get_args(annot)
            inner = _stringify(args) if args else None
            return f"Dictionary of ({inner})" if inner else "Dictionary"

        if origin is Literal or _is_enum_class(annot):
            return "Enum"

        if is_union(annot):
            parts = [s for s in (_stringify(a) for a in get_args(annot)) if s]
            return " or ".join(parts) if parts else None

        if isinstance(annot, type) and issubclass(annot, (BaseModel, BaseSettings)):
            return f"Object ({annot.__name__})"

        if isinstance(annot, type):
            return annot.__name__

        return "Object"

    return _stringify(annotation)


def nested_pydantic_to_dict(obj: Any) -> Any:
    """Convert pydantic models (and Enum, Path, datetime, ...) to plain JSON-compatible data."""
    return to_jsonable_python(obj)


def to_json_text(obj: Any) -> str:
    """Render a default value as JSON, the way it is written to the YAML file."""
    try:
        return json.dumps(to_jsonable_python(obj), ensure_ascii=False)
    except Exception:
        return str(obj)


def to_yaml_text(obj: Any) -> str:
    """Render an example as YAML that PyYAML (and thus pydantic-settings) reads back."""
    return yaml.safe_dump(to_jsonable_python(obj), sort_keys=False, allow_unicode=True)


_VALIDATOR_TYPES = (AfterValidator, BeforeValidator, PlainValidator, WrapValidator)


def readable_constraints(metadata: list[Any]) -> str | None:
    """Join a field's constraint metadata (``MaxLen(max_length=3)``, ``pattern='^x'``) for display.

    Validator functions are left out: they carry no readable constraint, and their
    repr contains a memory address that would change on every run.
    """
    readable = [str(m) for m in metadata if not isinstance(m, _VALIDATOR_TYPES) and str(m)]
    return ", ".join(readable) if readable else None


def get_str_dict_as_table(d: dict[str, str]) -> str:
    """Format a dict as a right-padded two-column table string."""
    if not d:
        return ""
    col_width = max(len(k) for k in d.keys()) + 1
    lines = []
    for key, val in d.items():
        val_lines = str(val).split("\n")
        lines.append(f"{key.ljust(col_width)}{val_lines[0]}")
        for extra in val_lines[1:]:
            lines.append(f"{''.ljust(col_width)}{extra}")
    return "\n".join(lines)


def indent_multilines(
    text: list[str],
    indent_depth: int = 0,
    line_prefix: str = "",
    extra_indent_depth_after_prefix: int = 0,
    indent: str = "  ",
) -> Generator[str, None, None]:
    base = indent * indent_depth
    inner = indent * extra_indent_depth_after_prefix
    for line in text:
        yield f"{base}{line_prefix}{inner}{line}"
