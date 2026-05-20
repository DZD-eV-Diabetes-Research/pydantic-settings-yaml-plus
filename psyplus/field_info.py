from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic import fields as pydantic_fields
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings
import yaml

from psyplus.utils import (
    get_literal_list,
    get_str_dict_as_table,
    has_literal,
    nested_pydantic_to_dict,
    python_annotation_to_readable,
)

log = logging.getLogger(__name__)

ENV_VAR_LISTINDEX_PLACEHOLDER = "<list-index>"
ENV_VAR_DICTKEY_PLACEHOLDER = "<dict-key>"


@dataclass
class ListIndex:
    index: int

    def __str__(self) -> str:
        return f"[{self.index}]"


@dataclass
class DictKey:
    key: Any

    def __str__(self) -> str:
        return f"['{self.key}']"


@dataclass
class FieldInfoContainer:
    """Wraps metadata for a single settings field and generates YAML comments / markdown."""

    path: list[str | ListIndex | DictKey]
    field_name: str
    root_settings_class: type[BaseSettings]
    field_info: pydantic_fields.FieldInfo | None = None
    # annotation is used for dict/list items where field_info is not available
    annotation: Any = None

    def get_annotation(self) -> Any:
        if self.field_info is not None and self.field_info.annotation is not None:
            return self.field_info.annotation
        return self.annotation

    def get_env_var(self) -> str | None:
        config = self.root_settings_class.model_config
        delimiter = config.get("env_nested_delimiter") or ""
        prefix = config.get("env_prefix") or ""

        if len(self.path) > 1 and not delimiter:
            if not os.getenv("PSYPLUS_SUPPRESS_ENV_WARNING"):
                log.warning(
                    f"Nested model without `env_nested_delimiter` configured on "
                    f"`{self.root_settings_class.__name__}`. "
                    "Set env var PSYPLUS_SUPPRESS_ENV_WARNING=true to silence this warning. "
                    "See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#nested-model-default-partial-updates"
                )

        parts: list[str] = []
        for segment in self.path:
            if isinstance(segment, str):
                parts.append(segment.upper())
            elif isinstance(segment, ListIndex):
                parts.append(ENV_VAR_LISTINDEX_PLACEHOLDER)
            else:
                parts.append(ENV_VAR_DICTKEY_PLACEHOLDER)
        return prefix + delimiter.join(parts)

    def get_path_str(self) -> str:
        return ".".join(str(p) for p in self.path)

    def get_type_string(self) -> str | None:
        return python_annotation_to_readable(self.get_annotation())

    def get_enum_vals(self) -> list[Any] | None:
        if has_literal(self.get_annotation()):
            return get_literal_list(self.get_annotation())
        return None

    def build_comment_lines(self, overwrite_required: bool | None = None) -> list[str]:
        """Build the list of lines that form the YAML comment block above a key."""
        fi = self.field_info or pydantic_fields.FieldInfo()
        key = self.field_name
        path = self.get_path_str()

        header = f"## {key}"
        if fi.title:
            header += f" - {fi.title}"
        header += " ###"

        data: dict[str, str] = {}

        if key != path:
            data["YAML-path:"] = path

        type_str = self.get_type_string()
        if type_str:
            data["Type:"] = type_str

        is_required = fi.is_required() if overwrite_required is None else overwrite_required
        data["Required:"] = str(is_required)

        if fi.default is not PydanticUndefined:
            if fi.default is None:
                data["Default:"] = "null"
            else:
                try:
                    data["Default:"] = json.dumps(nested_pydantic_to_dict(fi.default))
                except Exception:
                    data["Default:"] = str(fi.default)

        enum_vals = self.get_enum_vals()
        if enum_vals is not None:
            data["Allowed vals:"] = str(enum_vals)

        if fi.metadata:
            # Filter out internal pydantic metadata objects that add no user value
            readable = [
                str(m)
                for m in fi.metadata
                if not str(m).startswith("annotated_types") and str(m) != ""
            ]
            if readable:
                data["Constraints:"] = ", ".join(readable)

        env_var = self.get_env_var()
        if env_var:
            data["Env-var:"] = f"'{env_var}'"

        if fi.description:
            data["Description:"] = fi.description

        table = get_str_dict_as_table(data)
        lines = [header]
        if table:
            lines.extend(table.split("\n"))

        if fi.examples:
            lines.extend(self._example_lines(key))

        return lines

    def _example_lines(self, key: str) -> list[str]:
        if not self.field_info or not self.field_info.examples:
            return []
        examples = self.field_info.examples
        lines: list[str] = []
        for i, example in enumerate(examples):
            label = f"Example No. {i + 1}:" if len(examples) > 1 else "Example:"
            lines.append(label)
            try:
                as_yaml = yaml.dump(
                    nested_pydantic_to_dict({key: example}), sort_keys=False
                )
                for line in as_yaml.rstrip("\n").split("\n"):
                    lines.append(f" >{line}")
            except Exception:
                lines.append(f" >{repr(example)}")
        return lines
