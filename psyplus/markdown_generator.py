from __future__ import annotations

import inspect
import json
import logging
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings
import yaml

from psyplus.field_info import DictKey, FieldInfoContainer, ListIndex
from psyplus.utils import clean_annotation, nested_pydantic_to_dict

log = logging.getLogger(__name__)


class MarkdownDocGenerator:
    """Generate a Markdown reference document from a pydantic-settings model class."""

    def __init__(self, settings_class: type[BaseSettings]) -> None:
        self.settings_class = settings_class

    def generate(self) -> str:
        """Return the full markdown document as a string."""
        lines: list[str] = []
        name = self.settings_class.__name__
        lines.append(f"# Configuration Reference — `{name}`\n")
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
    ) -> None:
        for key, fi in cls.model_fields.items():
            path = parent_path + [key]
            container = FieldInfoContainer(
                path=path,
                field_name=key,
                field_info=fi,
                root_settings_class=self.settings_class,
            )
            lines.extend(self._field_section(container, fi, heading_level))

            # Recurse into nested BaseModel / BaseSettings fields (direct, list, or dict)
            annotation = clean_annotation(fi.annotation) if fi.annotation else None
            if not annotation:
                continue
            nested_cls, item_path = self._extract_nested(annotation, parent_path, key)
            if nested_cls is not None:
                lines.extend(self._item_schema_intro(key, nested_cls, item_path, heading_level + 1))
                self._walk_model(nested_cls, item_path, heading_level + 1, lines)

    def _extract_nested(
        self,
        annotation: Any,
        parent_path: list[str | ListIndex | DictKey],
        key: str,
    ) -> tuple[type[BaseModel] | None, list[str | ListIndex | DictKey]]:
        """Return (nested model class, path to use as parent) or (None, []).

        Handles three cases:
          - direct BaseModel sub-field  → path stays the same (e.g. ``database.host``)
          - List[BaseModel]             → path appended with ``key[*]``
          - Dict[K, BaseModel]          → path appended with ``key[*]``
        """
        path = parent_path + [key]

        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            return annotation, path

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is list and args:
            inner = args[0]
            if inspect.isclass(inner) and issubclass(inner, BaseModel):
                return inner, parent_path + [f"{key}[*]"]

        if origin is dict and len(args) >= 2:
            inner = args[1]
            if inspect.isclass(inner) and issubclass(inner, BaseModel):
                return inner, parent_path + [f"{key}[*]"]

        return None, []

    def _item_schema_intro(
        self,
        field_key: str,
        nested_cls: type[BaseModel],
        item_path: list[str | ListIndex | DictKey],
        heading_level: int,
    ) -> list[str]:
        """Emit a small intro heading when recursing into a list/dict item schema."""
        # Direct sub-model already has its own field section as the intro — no extra header needed.
        # Only add one for list/dict item types where the parent section describes the collection.
        path_str = ".".join(str(p) for p in item_path)
        if path_str == field_key:
            return []
        hashes = "#" * heading_level
        return [f"{hashes} `{path_str}` — `{nested_cls.__name__}` schema\n", "---\n"]

    def _field_section(
        self,
        container: FieldInfoContainer,
        fi: Any,
        heading_level: int,
    ) -> list[str]:
        hashes = "#" * heading_level
        path_str = container.get_path_str()
        lines: list[str] = [f"{hashes} `{path_str}`\n"]

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
                try:
                    rows.append(("Default", f"`{json.dumps(nested_pydantic_to_dict(fi.default))}`"))
                except Exception:
                    rows.append(("Default", f"`{fi.default}`"))

        enum_vals = container.get_enum_vals()
        if enum_vals:
            rows.append(("Allowed values", " · ".join(f"`{v}`" for v in enum_vals)))

        if fi.metadata:
            readable = [
                str(m)
                for m in fi.metadata
                if not str(m).startswith("annotated_types") and str(m) != ""
            ]
            if readable:
                rows.append(("Constraints", ", ".join(readable)))

        env_var = container.get_env_var()
        if env_var:
            env_cell = f"`{env_var}`"
            if container.needs_env_var_null_note():
                none_str = container.get_env_parse_none_str()
                if none_str is not None:
                    env_cell += f" (`{none_str}` sets null)"
                else:
                    env_cell += " (can not set null, use `null` in the YAML file)"
            rows.append(("Environment variable", env_cell))

        if rows:
            lines.append("| Property | Value |")
            lines.append("|---|---|")
            for k, v in rows:
                lines.append(f"| {k} | {v} |")
            lines.append("")

        if fi.examples:
            lines.append("**Examples:**\n")
            for i, example in enumerate(fi.examples):
                if len(fi.examples) > 1:
                    lines.append(f"*Example {i + 1}:*\n")
                try:
                    as_yaml = yaml.dump(
                        nested_pydantic_to_dict({container.field_name: example}),
                        sort_keys=False,
                    )
                    lines.append(f"```yaml\n{as_yaml.rstrip()}\n```\n")
                except Exception:
                    lines.append(f"```\n{repr(example)}\n```\n")

        lines.append("---\n")
        return lines
