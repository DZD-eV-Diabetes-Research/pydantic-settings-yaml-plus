from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, get_args, get_origin

from pydantic import AliasChoices, AliasPath, BaseModel
from pydantic import fields as pydantic_fields
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings

from psyplus.utils import (
    clean_annotation,
    get_literal_list,
    get_str_dict_as_table,
    has_literal,
    is_list_like,
    is_nullable,
    is_optional,
    model_members,
    python_annotation_to_readable,
    readable_constraints,
    to_json_text,
    to_yaml_text,
    unwrap_type_alias,
)

log = logging.getLogger(__name__)

ENV_VAR_LISTINDEX_PLACEHOLDER = "<list-index>"
# Shown after the env var of one list element (``APP_TAGS__<list-index>``).
LIST_ELEMENT_ENV_VAR_NOTE = "(one element, 0 is the first; psyplus load() only)"
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


class FieldKey(str):
    """A path segment that names a model field: its key in the YAML file.

    It remembers the field and where the key comes from, because the env var name
    depends on it (see ``FieldInfoContainer.get_env_var``).
    """

    field_info: pydantic_fields.FieldInfo | None
    # The key is the field's validation alias, not its name.
    is_alias: bool
    # The key is a segment of an ``AliasPath``.
    in_alias_path: bool

    def __new__(
        cls,
        key: str,
        field_info: pydantic_fields.FieldInfo | None = None,
        is_alias: bool = False,
        in_alias_path: bool = False,
    ) -> FieldKey:
        obj = super().__new__(cls, key)
        obj.field_info = field_info
        obj.is_alias = is_alias
        obj.in_alias_path = in_alias_path
        return obj


def yaml_key_path(
    model_cls: type[BaseModel] | None,
    field_name: str,
    field_info: pydantic_fields.FieldInfo,
) -> list[FieldKey | ListIndex]:
    """Where the value of a model field sits in the YAML file, relative to its model.

    The single place that decides it: the YAML generator, the Markdown generator and
    the env var names all build their paths from it.

    * No alias: ``[field_name]``.
    * A validation alias (``alias=``, ``validation_alias=``, an ``alias_generator``)
      is the key, since the YAML file is validated by alias. Of ``AliasChoices`` the
      first plain string choice. This holds with ``populate_by_name`` as well.
    * An ``AliasPath`` (or ``AliasChoices`` of ``AliasPath`` entries only): its
      segments, so the value sits in nested maps (``outer.inner``) or in a list
      element (``items[1]``).

    Only a model with ``validate_by_alias=False`` keeps the field name.
    """
    alias: Any = field_info.validation_alias
    if model_cls is not None and model_cls.model_config.get("validate_by_alias") is False:
        alias = None
    if isinstance(alias, AliasChoices):
        choices = [c for c in alias.choices if isinstance(c, str)]
        alias = choices[0] if choices else alias.choices[0]
    if alias is None:
        return [FieldKey(field_name, field_info)]
    if isinstance(alias, AliasPath):
        return [
            FieldKey(segment, field_info, is_alias=True, in_alias_path=True)
            if isinstance(segment, str)
            else ListIndex(index=segment)
            for segment in alias.path
        ]
    return [FieldKey(alias, field_info, is_alias=True)]


def yaml_source_alias(
    root_settings_class: type[BaseModel],
    model_cls: type[BaseModel],
    field_info: pydantic_fields.FieldInfo,
    key_path: list[FieldKey | ListIndex],
) -> str | None:
    """The alias under which the YAML source files a field that validation rejects there.

    pydantic-settings' YAML source files each top-level value under the field's
    ``alias``. When validation reads another name (a different ``validation_alias``,
    an ``alias_generator`` next to an explicit ``validation_alias``, or
    ``validate_by_alias=False``), the field can not be set from the YAML file under
    any key. None when the field reads fine.
    """
    if model_cls is not root_settings_class or not isinstance(field_info.alias, str):
        return None
    if field_info.alias == key_path[0]:
        return None
    return field_info.alias


def yaml_keyed(value: Any) -> Any:
    """*value* with every model in it turned into a dict under its YAML keys.

    pydantic would dump a model under its serialization aliases, which are not the
    keys of the YAML file. Fields read from an AliasPath with a list index are left
    out, as in the YAML file.
    """
    if isinstance(value, BaseModel):
        out: dict[str, Any] = {}
        for name, fi in type(value).model_fields.items():
            key_path = yaml_key_path(type(value), name, fi)
            if any(isinstance(segment, ListIndex) for segment in key_path):
                continue
            target: Any = out
            for segment in key_path[:-1]:
                if not isinstance(target, dict):
                    break
                target = target.setdefault(str(segment), {})
            if isinstance(target, dict):
                target[str(key_path[-1])] = yaml_keyed(getattr(value, name, None))
        return out
    if isinstance(value, dict):
        return {k: yaml_keyed(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [yaml_keyed(v) for v in value]
    return value


def key_name(key_path: list[FieldKey | ListIndex]) -> str:
    """The name to show for a field in a comment header: its key, or its whole ``AliasPath``."""
    last = key_path[-1]
    return str(last) if isinstance(last, str) else path_to_str(list(key_path))


def _restores_key_case(field_info: pydantic_fields.FieldInfo, top_level: bool) -> bool:
    """Whether pydantic-settings restores the case of the env var keys below this field.

    Mirrors ``PydanticBaseEnvSettingsSource._replace_field_names_case_insensitively``:
    it enters a top-level field that is a model or ``Optional[Model]`` (it takes the
    first member of a two member union with None), below that only plain model fields.
    """
    annotation = field_info.annotation
    if top_level and is_optional(annotation):
        args = get_args(annotation)
        if len(args) == 2:
            annotation = args[0]
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _env_keys_match_case_insensitively(path: list[str | ListIndex | DictKey]) -> bool:
    """Whether a case-insensitive env var reaches the value at *path*.

    Without ``case_sensitive`` the env var name arrives in lower case and
    pydantic-settings maps each key back to its field (``subalias`` -> ``subAlias``),
    but only along plain sub-model fields. Below a dict or an ``Optional`` sub-model
    deeper down, a key with upper case letters (a camelCase alias, for example) stays
    lower case, matches no field and the value is silently dropped.
    """
    restoring = True
    for i, segment in enumerate(path):
        if not isinstance(segment, str):
            restoring = False
            continue
        if not restoring and segment != segment.lower():
            return False
        if isinstance(segment, FieldKey) and segment.field_info is not None:
            restoring = restoring and _restores_key_case(segment.field_info, top_level=i == 0)
    return True


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
        """The env var that sets this field, or None when there is none.

        A list element gets ``<list-index>`` in its name (``APP_ITEMS__<list-index>__NAME``).
        Plain pydantic-settings can not read such names, ``YamlSettingsPlus.load()`` can
        (see ``psyplus.sources``). Without ``env_nested_delimiter`` only top-level fields
        have an env var, and with ``env_nested_max_split`` only fields that many levels
        below the top-level field.

        A field with an alias is named by its alias, and ``env_prefix`` goes in front
        of the top-level key only where ``env_prefix_target`` says so: ``"variable"``
        (the default) for field names, ``"alias"`` for aliases, ``"all"`` for both.
        pydantic-settings reads each element of an ``AliasPath`` as an env var of its
        own, so no env var sets just a field with an ``AliasPath``.
        """
        config = self.root_settings_class.model_config
        delimiter = config.get("env_nested_delimiter") or ""
        case_sensitive = bool(config.get("case_sensitive", False))
        prefix = config.get("env_prefix") or ""
        if not case_sensitive:
            prefix = prefix.upper()

        if any(isinstance(segment, FieldKey) and segment.in_alias_path for segment in self.path):
            return None
        # An env var with a list index is read by psyplus.sources, which matches field
        # keys at any depth itself and files the value under the key the YAML file uses.
        has_list_index = any(isinstance(segment, ListIndex) for segment in self.path)

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

        if (
            not case_sensitive
            and not has_list_index
            and not _env_keys_match_case_insensitively(self.path)
        ):
            return None

        top = self.path[0]
        top_is_alias = isinstance(top, FieldKey) and top.is_alias
        if (
            top_is_alias
            and len(self.path) > 1
            and not has_list_index
            and (config.get("populate_by_name") or config.get("validate_by_name"))
        ):
            # pydantic-settings files these env vars under the field name, next to the
            # alias key from the YAML file, and validation rejects the field name.
            return None
        prefix_target = config.get("env_prefix_target") or "variable"
        if prefix_target not in (("alias", "all") if top_is_alias else ("variable", "all")):
            prefix = ""

        max_split = config.get("env_nested_max_split")
        if max_split and len(self.path) - 1 > max_split:
            return None

        parts: list[str] = []
        for segment in self.path:
            if isinstance(segment, str):
                parts.append(segment if case_sensitive else segment.upper())
            elif isinstance(segment, ListIndex):
                parts.append(ENV_VAR_LISTINDEX_PLACEHOLDER)
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
        # The entry's own env var, so the alias and case rules of get_env_var apply.
        return FieldInfoContainer(
            path=self.path + [DictKey(key=ANY_ITEM)],
            field_name=ENV_VAR_DICTKEY_PLACEHOLDER,
            root_settings_class=self.root_settings_class,
        ).get_env_var()

    def get_list_element_env_var(self) -> str | None:
        """For a list field, the env var that sets one element (``APP_TAGS__<list-index>``).

        Only ``YamlSettingsPlus.load()`` reads these names.
        """
        if not is_list_like(self.get_annotation()):
            return None
        element = FieldInfoContainer(
            path=self.path + [ListIndex(index=ANY_ITEM)],
            field_name=self.field_name,
            root_settings_class=self.root_settings_class,
        )
        return element.get_env_var()

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

        Only direct sub-models are followed (``Optional[Model]`` included), and the
        elements of their list fields (``servers[*]``, ``servers[*].host``). For a
        Union of models the fields of every member are listed, each path once.
        Fields without an env var of their own (no ``env_nested_delimiter``) are
        left out.
        """
        out: dict[str, str] = {}

        def walk(container: FieldInfoContainer, seen: tuple[type, ...]) -> None:
            for cls in model_members(container.get_annotation()):
                if cls in seen:
                    continue
                for name, fi in cls.model_fields.items():
                    key_path = yaml_key_path(cls, name, fi)
                    child = FieldInfoContainer(
                        path=container.path + key_path,
                        field_name=key_name(key_path),
                        field_info=fi,
                        root_settings_class=self.root_settings_class,
                    )
                    env_var = child.get_env_var()
                    if env_var:
                        out.setdefault(child.get_path_str(), env_var)
                    walk(child, seen + (cls,))
                    element_env_var = child.get_list_element_env_var()
                    element_args = get_args(unwrap_type_alias(clean_annotation(fi.annotation)))
                    if element_env_var and element_args:
                        element = FieldInfoContainer(
                            path=child.path + [ListIndex(index=ANY_ITEM)],
                            field_name=child.field_name,
                            annotation=element_args[0],
                            root_settings_class=self.root_settings_class,
                        )
                        out.setdefault(element.get_path_str(), element_env_var)
                        walk(element, seen + (cls,))

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
                data["Default:"] = to_json_text(yaml_keyed(fi.default))

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

        element_env_var = self.get_list_element_env_var() if env_var else None
        if element_env_var:
            data["Env-var:"] += (
                f"\n'{element_env_var}' {LIST_ELEMENT_ENV_VAR_NOTE}"
            )

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
                lines.extend(
                    f"  {sub_path}: '{env}'"
                    + (f" {LIST_ELEMENT_ENV_VAR_NOTE}" if sub_path.endswith("[*]") else "")
                    for sub_path, env in sub_env_vars
                )

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
                as_yaml = to_yaml_text({key: yaml_keyed(example)})
                for line in as_yaml.rstrip("\n").split("\n"):
                    lines.append(f" >{line}")
            except Exception:
                lines.append(f" >{repr(example)}")
        return lines
