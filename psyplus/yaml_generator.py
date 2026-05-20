from __future__ import annotations

import inspect
import logging
from io import StringIO
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings
from ruamel.yaml import YAML, CommentedMap, CommentedSeq

from psyplus.field_info import DictKey, FieldInfoContainer, ListIndex
from psyplus.utils import clean_annotation, is_union

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Placeholder building
# ---------------------------------------------------------------------------

def _placeholder_for(annotation: Any) -> Any:
    """Return a type-appropriate placeholder value for a required field with no default.

    Produces valid values so pydantic model_validate() won't reject the data.
    The generated YAML will show empty strings / empty collections to signal
    that the user must fill in required values.
    """
    if annotation is None or annotation is Any:
        return None

    origin = get_origin(annotation)

    if is_union(annotation):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if not non_none:
            return None
        return _placeholder_for(non_none[0])

    if origin is Literal:
        return get_args(annotation)[0]

    if annotation is str:
        return ""
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is bool:
        return False

    if origin is list or annotation is list:
        return []
    if origin is dict or annotation is dict:
        return {}
    if origin is set or annotation is set:
        return []  # sets become lists in YAML

    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return _build_dict_for_class(annotation)

    return None


def _build_dict_for_class(cls: type[BaseModel]) -> dict[str, Any]:
    """Build a dict of placeholder values for every field in *cls*."""
    result: dict[str, Any] = {}
    for key, fi in cls.model_fields.items():
        if fi.default is not PydanticUndefined:
            result[key] = fi.default
        elif fi.default_factory is not None:
            result[key] = fi.default_factory()
        else:
            result[key] = _placeholder_for(fi.annotation)
    return result


def build_settings_instance(cls: type[BaseSettings]) -> BaseSettings:
    """Instantiate *cls* with placeholder values for all required fields.

    Uses model_validate (not __init__) so that pydantic-settings env-var
    reading is bypassed — we only want the template structure.
    """
    data = _build_dict_for_class(cls)
    return cls.model_validate(data)


# ---------------------------------------------------------------------------
# YAML generator
# ---------------------------------------------------------------------------

class YamlFileGenerator:
    """Generates a commented YAML string from a pydantic-settings model class."""

    def __init__(
        self,
        settings_class: type[BaseSettings],
        indent_size: int = 2,
    ) -> None:
        self.settings_class = settings_class
        self.indent_size = indent_size
        self._yaml = YAML()
        # https://yaml.readthedocs.io/en/latest/detail/#indentation-of-block-sequences
        self._yaml.indent(sequence=indent_size + 2, offset=indent_size)
        self._model: CommentedMap | None = None

    def parse(self) -> None:
        """Build the internal CommentedMap from the settings class."""
        instance = build_settings_instance(self.settings_class)
        self._model = self._parse_model(instance, parent_path=[])

    def get_yaml(self) -> str:
        """Return the generated YAML string. Call parse() first."""
        if self._model is None:
            raise RuntimeError("Call parse() before get_yaml().")
        stream = StringIO()
        self._yaml.dump(self._model, stream)
        return stream.getvalue()

    # ------------------------------------------------------------------
    # Internal: model / dict / list recursion
    # ------------------------------------------------------------------

    def _parse_model(
        self,
        instance: BaseSettings | BaseModel,
        parent_path: list[str | ListIndex | DictKey],
    ) -> CommentedMap:
        level = len(parent_path)
        result = CommentedMap()

        for key, fi in type(instance).model_fields.items():
            path = parent_path + [key]
            value = getattr(instance, key)
            result[key] = self._encode_value(value, fi.annotation, path)

            comment_lines = FieldInfoContainer(
                path=path,
                field_name=key,
                field_info=fi,
                root_settings_class=self.settings_class,
            ).build_comment_lines()

            result.yaml_set_comment_before_after_key(
                key=key,
                before="\n" + "\n".join(comment_lines),
                indent=level * self.indent_size,
            )

        return result

    def _encode_value(
        self,
        value: Any,
        annotation: Any,
        path: list[str | ListIndex | DictKey],
    ) -> Any:
        if isinstance(value, (BaseSettings, BaseModel)):
            return self._parse_model(value, path)
        if isinstance(value, dict):
            return self._encode_dict(value, annotation, path)
        if isinstance(value, list):
            return self._encode_list(value, annotation, path)
        return value

    def _encode_dict(
        self,
        value: Any,
        annotation: Any,
        parent_path: list[str | ListIndex | DictKey],
    ) -> CommentedMap:
        level = len(parent_path)
        result = CommentedMap()

        # Safely extract value-type annotation from dict[K, V]
        clean = clean_annotation(annotation) if annotation is not None else None
        args = get_args(clean) if clean is not None else ()
        val_annotation = args[1] if len(args) >= 2 else None

        for dict_key, dict_val in value.items():
            item_path = parent_path + [DictKey(key=dict_key)]
            result[dict_key] = self._encode_value(dict_val, val_annotation, item_path)

            comment_lines = FieldInfoContainer(
                path=item_path,
                field_name=str(dict_key),
                annotation=val_annotation,
                root_settings_class=self.settings_class,
            ).build_comment_lines()

            result.yaml_set_comment_before_after_key(
                key=dict_key,
                before="\n" + "\n".join(comment_lines),
                indent=level * self.indent_size,
            )

        return result

    def _encode_list(
        self,
        value: Any,
        annotation: Any,
        parent_path: list[str | ListIndex | DictKey],
    ) -> CommentedSeq:
        level = len(parent_path)
        result = CommentedSeq()

        # Safely extract item-type annotation from list[T]
        clean = clean_annotation(annotation) if annotation is not None else None
        args = get_args(clean) if clean is not None else ()
        item_annotation = args[0] if args else None

        for index, item in enumerate(value):
            item_path = parent_path + [ListIndex(index=index)]
            result.append(self._encode_value(item, item_annotation, item_path))

            comment_lines = FieldInfoContainer(
                path=item_path,
                field_name=f"List[{index}]",
                annotation=item_annotation,
                root_settings_class=self.settings_class,
            ).build_comment_lines(overwrite_required=False)

            result.yaml_set_comment_before_after_key(
                key=index,
                before="\n" + "\n".join(comment_lines),
                indent=level * self.indent_size,
            )

        return result
