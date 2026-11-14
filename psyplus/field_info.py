from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, get_origin

from pydantic import fields as pydantic_fields
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings

from psyplus.utils import (
    clean_annotation,
    get_literal_list,
    get_str_dict_as_table,
    has_literal,
    is_nullable,
    model_members,
    python_annotation_to_readable,
    readable_constraints,
    to_json_text,
    to_yaml_text,
)

log = logging.getLogger(__name__)

ENV_VAR_DICTKEY_PLACEHOLDER = "<dict-key>"
# Stands for "any element" in a path, e.g. ``servers[*].host`` in the Markdown doc.
ANY_ITEM = "*"

_warned_no_delimiter: set[type] = set()


@dataclass
class ListIndex:
    index: int | str

    def __str__(self) -> str:
        return f"[{self.index}]"


@dataclass
class DictKey:
    key: Any

    def __str__(self) -> str:
        if self.key == ANY_ITEM:
            return "[*]"
        return f"['{self.key}']"


def yaml_key(field_name: str, field_info: pydantic_fields.FieldInfo) -> str:
    """The key of a model field in the YAML file.

    The single place that decides it: the YAML generator, the Markdown generator and
    the env var names all build their paths from this key.
    """
    return field_name


def path_to_str(path: list[str | ListIndex | DictKey]) -> str:
    """``["servers", ListIndex(0), "host"]`` -> ``servers[0].host``."""
    out = ""
    for segment in path:
        if isinstance(segment, str):
            out += f".{segment}" if out else segment
        else:
            out += str(segment)
    return out


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
        """The env var that sets this field, or None when pydantic-settings offers none.

        pydantic-settings can not set a single list element: ``APP_ITEMS__0`` is read
        as the dict ``{"0": ...}`` and fails list validation, so list elements only
        change through the JSON value of the whole list. Without
        ``env_nested_delimiter`` only top-level fields have an env var.
        """
        config = self.root_settings_class.model_config
        delimiter = config.get("env_nested_delimiter") or ""
        case_sensitive = bool(config.get("case_sensitive", False))
        prefix = config.get("env_prefix") or ""
        if not case_sensitive:
            prefix = prefix.upper()

        if any(isinstance(segment, ListIndex) for segment in self.path):
            return None

        if len(self.path) > 1 and not delimiter:
            if (
                not os.getenv("PSYPLUS_SUPPRESS_ENV_WARNING")
                and self.root_settings_class not in _warned_no_delimiter
            ):
                _warned_no_delimiter.add(self.root_settings_class)
                log.warning(
                    f"`{self.root_settings_class.__name__}` has nested fields but no "
                    "`env_nested_delimiter`, so they can only be set through the JSON value "
                    "of their top-level env var. "
                    "Set env var PSYPLUS_SUPPRESS_ENV_WARNING=true to silence this warning. "
                    "See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#parsing-environment-variable-values"
                )
            return None

        parts: list[str] = []
        for segment in self.path:
            if isinstance(segment, str):
                parts.append(segment if case_sensitive else segment.upper())
            else:
                parts.append(ENV_VAR_DICTKEY_PLACEHOLDER)
        return prefix + delimiter.join(parts)

    def get_lowercased_dict_entry_env_var(self) -> str | None:
        """For a dict field: the env var of one entry (``APP_MAP__<dict-key>``) when
        pydantic-settings lowercases its key, else None.

        Unless the model sets ``case_sensitive=True``, pydantic-settings lowercases env
        var names before it splits them, so ``APP_MAP__Second__SIZE`` creates the key
        ``second``. Keys in the JSON value of ``APP_MAP`` keep their case.
        """
        config = self.root_settings_class.model_config
        delimiter = config.get("env_nested_delimiter")
        if config.get("case_sensitive", False) or not delimiter:
            return None
        annotation = clean_annotation(self.get_annotation())
        if not (annotation is dict or get_origin(annotation) is dict):
            return None
        env_var = self.get_env_var()
        return env_var + delimiter + ENV_VAR_DICTKEY_PLACEHOLDER if env_var else None

    def get_path_str(self) -> str:
        return path_to_str(self.path)

    def get_type_string(self) -> str | None:
        type_str = python_annotation_to_readable(self.get_annotation())
        if type_str and is_nullable(self.get_annotation()):
            type_str += " or null"
        return type_str

    def needs_env_var_null_note(self) -> bool:
        """True for a nullable field whose default is not null.

        Only there does a user have a reason to set null through the env var, and
        pydantic-settings can not do that unless the model sets
        ``env_parse_none_str``: without it an int or bool field fails validation,
        a str field gets the literal text, and a list, dict or model field silently
        keeps its default.
        """
        if self.field_info is None or self.field_info.default is None:
            return False
        return is_nullable(self.get_annotation())

    def get_env_parse_none_str(self) -> str | None:
        """The env var value that means null (``env_parse_none_str``), if the model sets one."""
        return self.root_settings_class.model_config.get("env_parse_none_str")

    def get_enum_vals(self) -> list[Any] | None:
        if has_literal(self.get_annotation()):
            return get_literal_list(self.get_annotation())
        return None

    def get_sub_field_env_vars(self) -> list[tuple[str, str]]:
        """``(path, env var)`` for the fields of this field's sub-model, recursively.

        Only direct sub-models are followed (``Optional[Model]`` included). For a
        Union of models the fields of every member are listed, each path once.
        Fields without an env var of their own (list elements, no
        ``env_nested_delimiter``) are left out.
        """
        out: dict[str, str] = {}

        def walk(container: FieldInfoContainer, seen: tuple[type, ...]) -> None:
            for cls in model_members(container.get_annotation()):
                if cls in seen:
                    continue
                for name, fi in cls.model_fields.items():
                    key = yaml_key(name, fi)
                    child = FieldInfoContainer(
                        path=container.path + [key],
                        field_name=key,
                        field_info=fi,
                        root_settings_class=self.root_settings_class,
                    )
                    env_var = child.get_env_var()
                    if env_var:
                        out.setdefault(child.get_path_str(), env_var)
                    walk(child, seen + (cls,))

        walk(self, ())
        return list(out.items())

    def build_comment_lines(
        self,
        overwrite_required: bool | None = None,
        list_sub_field_env_vars: bool = False,
    ) -> list[str]:
        """Build the list of lines that form the YAML comment block above a key.

        ``list_sub_field_env_vars`` adds the env vars of the sub-model's fields. The
        YAML generator sets it when the sub-model is null, because its fields (and
        their comments) are then not written to the file.
        """
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
                data["Default:"] = to_json_text(fi.default)

        enum_vals = self.get_enum_vals()
        if enum_vals is not None:
            data["Allowed vals:"] = str(enum_vals)

        constraints = readable_constraints(fi.metadata)
        if constraints:
            data["Constraints:"] = constraints

        env_var = self.get_env_var()
        if env_var:
            data["Env-var:"] = f"'{env_var}'"
            if self.needs_env_var_null_note():
                none_str = self.get_env_parse_none_str()
                if none_str is not None:
                    data["Env-var:"] += f" ('{none_str}' sets null)"
                else:
                    data["Env-var:"] += " (can not set null, use null in the YAML file)"
            entry_env_var = self.get_lowercased_dict_entry_env_var()
            if entry_env_var:
                data["Env-var:"] += f"\n'{entry_env_var}' sets one entry, its key arrives in lower case"

        if fi.description:
            data["Description:"] = fi.description

        table = get_str_dict_as_table(data)
        lines = [header]
        if table:
            lines.extend(table.split("\n"))

        if list_sub_field_env_vars:
            sub_env_vars = self.get_sub_field_env_vars()
            if sub_env_vars:
                lines.append("Env-vars of the sub-fields:")
                lines.extend(f"  {sub_path}: '{env}'" for sub_path, env in sub_env_vars)

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
                as_yaml = to_yaml_text({key: example})
                for line in as_yaml.rstrip("\n").split("\n"):
                    lines.append(f" >{line}")
            except Exception:
                lines.append(f" >{repr(example)}")
        return lines
