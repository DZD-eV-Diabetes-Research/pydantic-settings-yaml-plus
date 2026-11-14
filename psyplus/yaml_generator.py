from __future__ import annotations

import inspect
import logging
from io import StringIO
from typing import Annotated, Any, get_args, get_origin

import yaml as pyyaml
from pydantic import BaseModel, SecretBytes, SecretStr
from pydantic.fields import FieldInfo
from pydantic_core import to_jsonable_python
from pydantic_settings import BaseSettings
from ruamel.yaml import YAML, CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import SingleQuotedScalarString

from psyplus.field_info import (
    DictKey,
    FieldInfoContainer,
    FieldKey,
    ListIndex,
    key_name,
    path_to_str,
    yaml_key_path,
    yaml_source_alias,
)
from psyplus.utils import clean_annotation, sequence_item_annotation

log = logging.getLogger(__name__)

# ruamel writes YAML 1.2, but pydantic-settings reads the file with PyYAML (YAML 1.1),
# where plain `yes`, `on`, `off`, `1:30` ... are bools/ints. Quote such strings.
_PYYAML_RESOLVER = pyyaml.resolver.Resolver()
_YAML_STR_TAG = "tag:yaml.org,2002:str"


def _yaml11_safe_str(value: str) -> str:
    if _PYYAML_RESOLVER.resolve(pyyaml.nodes.ScalarNode, value, (True, False)) != _YAML_STR_TAG:
        return SingleQuotedScalarString(value)
    return value


# ---------------------------------------------------------------------------
# Field values
# ---------------------------------------------------------------------------

# A required field without a default: written as an empty value (null).
_REQUIRED = object()
# A default factory that could not be called at generation time: written as null.
_UNRESOLVED = object()
_MISSING = object()

_UNRESOLVED_NOTE = (
    "Note: the default is computed from other values when the settings load. "
    "Remove this key to use it."
)
_ALIAS_PATH_NOTE = (
    "Note: this field is read from the AliasPath {path}, which is not written to this "
    "file. Add it by hand to set the value."
)
_UNREADABLE_NOTE = (
    "Note: this field is not written to this file. pydantic-settings reads it from the "
    "YAML file under its alias {alias}, but validation expects {key}, so no key works here."
)


def _model_class(annotation: Any) -> type[BaseModel] | None:
    """The model class a field is annotated with, or None.

    Only a plain (or ``Annotated``) model counts. For ``Optional[Model]`` and other
    unions null is a valid value or the member to show is unclear, so they get none.
    """
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation
    return None


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
        # Model classes walked without an instance right now, to stop on recursive models.
        self._walking: list[type[BaseModel]] = []

    def parse(self) -> None:
        """Build the internal CommentedMap from the settings class.

        The class is walked, nothing is instantiated or validated: fields with a
        default show it, a required field without a default is written as an empty
        value (null) and a required sub-model as the map of its fields. So the
        untouched template does not load until the user fills in the required values.
        """
        self._model = self._walk_class(self.settings_class, [])

    def get_yaml(self) -> str:
        """Return the generated YAML string. Call parse() first."""
        if self._model is None:
            raise RuntimeError("Call parse() before get_yaml().")
        stream = StringIO()
        self._yaml.dump(self._model, stream)
        return stream.getvalue().lstrip("\n")

    # ------------------------------------------------------------------
    # Internal: model / dict / list recursion
    # ------------------------------------------------------------------

    def _parse_model(
        self,
        cls: type[BaseModel],
        instance: BaseModel | None,
        parent_path: list[str | ListIndex | DictKey],
    ) -> CommentedMap:
        """Encode the fields of *cls*.

        A field's value comes from *instance* (a default sub-model or a list or dict
        item) when given, otherwise from the field's default.
        """
        result = CommentedMap()
        # The values so far, passed to default factories that take the validated data.
        data: dict[str, Any] = {}
        key_paths = {name: yaml_key_path(cls, name, fi) for name, fi in cls.model_fields.items()}
        # Keys of fields that sit directly in this map, an AliasPath must not reuse them.
        plain_keys = {kp[0] for kp in key_paths.values() if len(kp) == 1}
        # The maps created for AliasPath segments, which other AliasPath fields share.
        alias_path_maps: list[CommentedMap] = []
        # (map, key, comment lines, indent) of each written key, applied at the end.
        comments: list[tuple[CommentedMap, Any, list[str], int]] = []
        # Comment lines of fields that are not written, they go above the next key.
        pending: list[str] = []

        def add_comment(target: CommentedMap, key: Any, lines: list[str], depth: int) -> None:
            nonlocal pending
            comments.append((target, key, pending + lines, depth * self.indent_size))
            pending = []

        for name, fi in cls.model_fields.items():
            key_path = key_paths[name]
            path = parent_path + key_path
            value = self._field_value(name, fi, instance, data, path)
            if value is not _REQUIRED and value is not _UNRESOLVED:
                data[name] = value

            container = FieldInfoContainer(
                path=path,
                field_name=key_name(key_path),
                field_info=fi,
                root_settings_class=self.settings_class,
            )
            note = None
            source_alias = yaml_source_alias(self.settings_class, cls, fi, key_path)
            if source_alias is not None:
                note = _UNREADABLE_NOTE.format(alias=source_alias, key=key_path[0])
            target = None
            if note is None:
                target = self._target_map(
                    result, parent_path, key_path, plain_keys, alias_path_maps, add_comment
                )
                if target is None:
                    note = _ALIAS_PATH_NOTE.format(path=path_to_str(path))
            if target is None:
                log.warning(
                    f"`{path_to_str(path)}` (field `{name}` of `{cls.__name__}`) is left "
                    f"out of the YAML file. {note}"
                )
                pending.extend(container.build_comment_lines())
                pending.extend([note, ""])
                continue

            # A plain str: ruamel can not write the FieldKey subclass.
            key = str(key_path[-1])
            sub_cls = _model_class(fi.annotation) if value is _REQUIRED else None
            if sub_cls is not None and sub_cls not in self._walking:
                target[key] = self._walk_class(sub_cls, path)
            elif value is _REQUIRED or value is _UNRESOLVED:
                target[key] = None
            else:
                target[key] = self._encode_value(value, fi.annotation, path)

            comment_lines = container.build_comment_lines(
                list_sub_field_env_vars=target[key] is None
            )
            if value is _UNRESOLVED:
                comment_lines.append(_UNRESOLVED_NOTE)
            add_comment(target, key, comment_lines, len(path) - 1)

        if pending:
            if comments:
                # No written key follows, put them above the last one.
                target, key, lines, indent = comments[-1]
                comments[-1] = (target, key, pending + lines, indent)
            else:
                log.warning(
                    f"`{cls.__name__}` has no field that can be written to the YAML file."
                )
        for target, key, lines, indent in comments:
            target.yaml_set_comment_before_after_key(
                key=key, before="\n" + "\n".join(lines), indent=indent
            )

        return result

    @staticmethod
    def _target_map(
        result: CommentedMap,
        parent_path: list[str | ListIndex | DictKey],
        key_path: list[FieldKey | ListIndex],
        plain_keys: set[str],
        alias_path_maps: list[CommentedMap],
        add_comment: Any,
    ) -> CommentedMap | None:
        """The map a field's last key goes into: *result*, or nested maps for an AliasPath.

        The nested maps of an AliasPath are shared with other AliasPath fields of the
        model. None when the AliasPath can not be written: it has a list index, or it
        clashes with the key of another field.
        """
        if len(key_path) == 1:
            return result
        if any(isinstance(segment, ListIndex) for segment in key_path) or key_path[0] in plain_keys:
            return None
        target = result
        for depth, segment in enumerate(map(str, key_path[:-1])):
            if segment not in target:
                target[segment] = CommentedMap()
                alias_path_maps.append(target[segment])
                path = parent_path + key_path[: depth + 1]
                lines = [f"## {segment} ###"]
                if len(path) > 1:
                    lines.append(f"YAML-path: {path_to_str(path)}")
                add_comment(target, segment, lines, len(path) - 1)
            elif not any(target[segment] is m for m in alias_path_maps):
                return None
            target = target[segment]
        if key_path[-1] in target:
            return None
        return target

    def _walk_class(
        self,
        cls: type[BaseModel],
        path: list[str | ListIndex | DictKey],
    ) -> CommentedMap:
        """Encode a model class without an instance: its fields with their defaults."""
        self._walking.append(cls)
        try:
            return self._parse_model(cls, None, path)
        finally:
            self._walking.pop()

    def _field_value(
        self,
        name: str,
        fi: FieldInfo,
        instance: BaseModel | None,
        data: dict[str, Any],
        path: list[str | ListIndex | DictKey],
    ) -> Any:
        """The value to write for a field, or ``_REQUIRED`` / ``_UNRESOLVED``."""
        if instance is not None:
            # A model_construct()ed instance can lack fields; fall back to the class.
            value = getattr(instance, name, _MISSING)
            if value is not _MISSING:
                return value
        if fi.is_required():
            return _REQUIRED
        try:
            return fi.get_default(call_default_factory=True, validated_data=dict(data))
        except Exception as e:
            if fi.default_factory is None:
                raise
            # e.g. a factory that reads a required value from the validated data.
            log.warning(
                f"The default factory of `{path_to_str(path)}` failed at generation time "
                f"({e!r}), writing null."
            )
            return _UNRESOLVED

    def _encode_value(
        self,
        value: Any,
        annotation: Any,
        path: list[str | ListIndex | DictKey],
    ) -> Any:
        if isinstance(value, BaseModel):
            return self._parse_model(type(value), value, path)
        if isinstance(value, dict):
            return self._encode_dict(value, annotation, path)
        if isinstance(value, (list, tuple, set, frozenset)):
            return self._encode_list(list(value), annotation, path)
        if isinstance(value, (SecretStr, SecretBytes)):
            value = value.get_secret_value()
        if type(value) not in (int, float, bool, type(None)):
            # Enum, Path, Decimal, UUID, SecretStr, Url, time, ... are not representable
            # by ruamel; dump them the way pydantic serialises them to JSON.
            value = to_jsonable_python(value)
            if isinstance(value, (dict, list)):
                return self._encode_value(value, annotation, path)
        if isinstance(value, str):
            return _yaml11_safe_str(value)
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
            if isinstance(dict_key, str):
                dict_key = _yaml11_safe_str(dict_key)
            result[dict_key] = self._encode_value(dict_val, val_annotation, item_path)

            comment_lines = FieldInfoContainer(
                path=item_path,
                field_name=str(dict_key),
                annotation=val_annotation,
                root_settings_class=self.settings_class,
            ).build_comment_lines(overwrite_required=False)

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

        for index, item in enumerate(value):
            # list[T] has one item type, a fixed-length tuple one per position
            item_annotation = sequence_item_annotation(annotation, index)
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
