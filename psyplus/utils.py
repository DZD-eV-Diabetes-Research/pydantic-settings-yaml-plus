from __future__ import annotations

import datetime
from typing import Annotated, Any, Generator, Literal, Union, cast, get_args, get_origin

from pydantic import (
    AwareDatetime,
    FutureDate,
    FutureDatetime,
    NaiveDatetime,
    PastDate,
    PastDatetime,
)
from pydantic import BaseModel
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


def clean_annotation(annotation: Any) -> Any:
    """Recursively unwrap Annotated and Optional/Union-with-None wrappers."""
    if get_origin(annotation) is Annotated:
        return clean_annotation(get_args(annotation)[0])
    if is_optional(annotation):
        return clean_annotation(unwrap_optional(annotation))
    return annotation


def has_literal(annotation: Any) -> bool:
    """Return True if annotation is or wraps a Literal type."""
    return get_origin(clean_annotation(annotation)) is Literal


def get_literal_list(annotation: Any) -> list[Any] | None:
    """Return the list of values in a Literal annotation, or None."""
    cleaned = clean_annotation(annotation)
    if get_origin(cleaned) is Literal:
        return list(get_args(cleaned))
    return None


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

        if is_optional(annot):
            return _stringify(clean_annotation(annot))

        if annot is Any or annot is None:
            return None

        if annot in PYTHON_SCALAR_TYPES:
            return annot.__name__

        origin = get_origin(annot)

        if origin is list or annot is list:
            args = get_args(annot)
            inner = _stringify(args) if args else None
            return f"List of {inner}" if inner else "List"

        if origin is dict or annot is dict:
            args = get_args(annot)
            inner = _stringify(args) if args else None
            return f"Dictionary of ({inner})" if inner else "Dictionary"

        if origin is Literal:
            return "Enum"

        if isinstance(annot, type) and issubclass(annot, (BaseModel, BaseSettings)):
            return f"Object ({annot.__name__})"

        return "Object"

    return _stringify(annotation)


def nested_pydantic_to_dict(obj: Any) -> Any:
    """Recursively convert pydantic models to plain dicts."""
    if isinstance(obj, (BaseModel, BaseSettings)):
        return nested_pydantic_to_dict(obj.model_dump())
    if isinstance(obj, dict):
        return {k: nested_pydantic_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [nested_pydantic_to_dict(item) for item in obj]
    return obj


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
