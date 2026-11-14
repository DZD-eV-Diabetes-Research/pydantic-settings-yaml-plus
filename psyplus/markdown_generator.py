from __future__ import annotations

import logging
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings

from psyplus.field_info import (
    ANY_ITEM,
    DictKey,
    FieldInfoContainer,
    ListIndex,
    key_name,
    path_to_str,
    yaml_key_path,
    yaml_keyed,
    yaml_source_alias,
)
from psyplus.utils import (
    clean_annotation,
    md_code,
    md_heading,
    md_table_cell,
    model_members,
    readable_constraints,
    to_json_text,
    to_yaml_text,
)

log = logging.getLogger(__name__)

_UNREADABLE_NOTE = (
    "**Note:** this field can not be set in the YAML file. pydantic-settings reads it "
    "from the YAML file under its alias {alias}, but validation expects {key}, so no "
    "key works there. Set it through its environment variable.\n"
)


def _value_code(value: Any) -> str:
    """A value as inline code: as is, or as JSON when it is empty or spans lines."""
    text = str(value)
    if not text or "\n" in text or "\r" in text:
        text = to_json_text(value)
    return md_code(text)


class MarkdownDocGenerator:
    """Generate a Markdown reference document from a pydantic-settings model class."""

    def __init__(self, settings_class: type[BaseSettings]) -> None:
        self.settings_class = settings_class

    def generate(self) -> str:
        """Return the full markdown document as a string."""
        lines: list[str] = []
        name = self.settings_class.__name__
        lines.append(f"# Configuration Reference: `{name}`\n")
        lines.append(
            "This document is auto-generated from the pydantic-settings model. "
            "All settings can be provided via the YAML config file or overridden with environment variables.\n"
        )
        lines.append("---\n")
        self._walk_model(self.settings_class, parent_path=[], heading_level=2, lines=lines)
        return "\n".join(lines)

    # ------------------------------------------------------------------

    def _walk_model(
        self,
        cls: type[BaseModel],
        parent_path: list[str | ListIndex | DictKey],
        heading_level: int,
        lines: list[str],
        _seen: tuple[type[BaseModel], ...] = (),
    ) -> None:
        _seen = _seen + (cls,)
        for name, fi in cls.model_fields.items():
            key_path = yaml_key_path(cls, name, fi)
            path = parent_path + key_path
            container = FieldInfoContainer(
                path=path,
                field_name=key_name(key_path),
                field_info=fi,
                root_settings_class=self.settings_class,
            )
            section = self._field_section(container, fi, heading_level)
            source_alias = yaml_source_alias(self.settings_class, cls, fi, key_path)
            if source_alias is not None:
                note = _UNREADABLE_NOTE.format(
                    alias=md_code(source_alias), key=md_code(str(key_path[0]))
                )
                # Before the closing rule of the section.
                section[-1:-1] = [note]
            lines.extend(section)

            # Recurse into nested models: direct, Optional, Union of models, list or dict items
            annotation = clean_annotation(fi.annotation) if fi.annotation else None
            if not annotation:
                continue
            models, item_path = self._extract_nested(annotation, path)
            for number, nested_cls in enumerate(models, start=1):
                if nested_cls in _seen:
                    continue
                if len(models) > 1:
                    # One section per alternative of a Union, its fields one level below.
                    option = f"(option {number} of {len(models)})"
                    lines.extend(self._schema_intro(nested_cls, item_path, heading_level + 1, option))
                    self._walk_model(nested_cls, item_path, heading_level + 2, lines, _seen)
                    continue
                if item_path != path:
                    # A list or dict item schema: the field section above describes the
                    # collection, so the item fields get a small intro of their own.
                    lines.extend(self._schema_intro(nested_cls, item_path, heading_level + 1))
                self._walk_model(nested_cls, item_path, heading_level + 1, lines, _seen)

    def _extract_nested(
        self,
        annotation: Any,
        path: list[str | ListIndex | DictKey],
    ) -> tuple[list[type[BaseModel]], list[str | ListIndex | DictKey]]:
        """Return (nested model classes, path to use as parent), or ([], []).

        Handles three cases, each with a single model or a Union of models:
          - direct sub-field (``Model``, ``Union[A, B]``): the path stays the same
            (e.g. ``database.host``)
          - ``List[Model]``: the path is appended with ``key[*]``
          - ``Dict[K, Model]``: the path is appended with ``key[*]``
        """
        models = model_members(annotation)
        if models:
            return models, path

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is list and args:
            models = model_members(args[0])
            if models:
                return models, path + [ListIndex(index=ANY_ITEM)]

        if origin is dict and len(args) >= 2:
            models = model_members(args[1])
            if models:
                return models, path + [DictKey(key=ANY_ITEM)]

        return [], []

    def _schema_intro(
        self,
        nested_cls: type[BaseModel],
        item_path: list[str | ListIndex | DictKey],
        heading_level: int,
        suffix: str = "",
    ) -> list[str]:
        """A heading that introduces the fields of a list/dict item or Union alternative."""
        text = f"{md_code(path_to_str(item_path))}: {md_code(nested_cls.__name__)} schema"
        if suffix:
            text += f" {suffix}"
        return [md_heading(heading_level, text) + "\n", "---\n"]

    def _field_section(
        self,
        container: FieldInfoContainer,
        fi: Any,
        heading_level: int,
    ) -> list[str]:
        lines: list[str] = [md_heading(heading_level, md_code(container.get_path_str())) + "\n"]

        if fi.title:
            lines.append(f"*{fi.title}*\n")

        if fi.description:
            lines.append(f"{fi.description}\n")

        rows: list[tuple[str, str]] = []

        type_str = container.get_type_string()
        if type_str:
            rows.append(("Type", type_str))

        is_req = fi.is_required()
        rows.append(("Required", "**Yes**" if is_req else "No"))

        if fi.default is not PydanticUndefined:
            if fi.default is None:
                rows.append(("Default", "`null`"))
            else:
                rows.append(("Default", md_code(to_json_text(yaml_keyed(fi.default)))))

        enum_vals = container.get_enum_vals()
        if enum_vals:
            rows.append(("Allowed values", " · ".join(_value_code(v) for v in enum_vals)))

        constraints = readable_constraints(fi.metadata)
        if constraints:
            rows.append(("Constraints", md_code(constraints)))

        env_var = container.get_env_var()
        if env_var:
            notes: list[str] = []
            if container.needs_env_var_null_note():
                none_str = container.get_env_parse_none_str()
                if none_str is not None:
                    notes.append(f"{_value_code(none_str)} sets null")
                else:
                    notes.append("can not set null, use `null` in the YAML file")
            entry_env_var = container.get_lowercased_dict_entry_env_var()
            if entry_env_var:
                notes.append(f"{md_code(entry_env_var)} sets one entry, its key arrives in lower case")
            env_cell = md_code(env_var)
            if notes:
                env_cell += f" ({'; '.join(notes)})"
            rows.append(("Environment variable", env_cell))
            element_env_var = container.get_list_element_env_var()
            if element_env_var:
                rows.append((
                    "Environment variable (one element)",
                    f"`{element_env_var}` (0 is the first; psyplus `load()` only)",
                ))

        if rows:
            lines.append("| Property | Value |")
            lines.append("|---|---|")
            for k, v in rows:
                lines.append(f"| {k} | {md_table_cell(v)} |")
            lines.append("")

        if fi.examples:
            lines.append("**Examples:**\n")
            for i, example in enumerate(fi.examples):
                if len(fi.examples) > 1:
                    lines.append(f"*Example {i + 1}:*\n")
                try:
                    as_yaml = to_yaml_text({container.field_name: yaml_keyed(example)})
                    lines.append(f"```yaml\n{as_yaml.rstrip()}\n```\n")
                except Exception:
                    lines.append(f"```\n{repr(example)}\n```\n")

        lines.append("---\n")
        return lines
