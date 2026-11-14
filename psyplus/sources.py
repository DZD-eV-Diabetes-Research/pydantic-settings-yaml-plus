"""Env var sources that can set single list elements, used by ``YamlSettingsPlus.load()``.

pydantic-settings reads ``APP_ITEMS__0__NAME`` as the dict ``{"0": {"name": ...}}``,
which fails list validation. The sources here read a numeric path segment at a list
position as a list index instead. Such an env var does not set a whole list but
changes one element of the list that the lower priority sources (mainly the YAML file)
provide. A source can not see those lists while pydantic-settings calls it (highest
priority first, and a higher list replaces a lower one wholesale). So ``load()`` runs
:func:`resolve_list_patches` on its source chain: it calls every source once, applies
each source's list patches to the merged data of the sources below it, and hands
pydantic-settings sources that replay the results.

Index rules (``n`` is the length of the list the patch is applied to):

* ``0 <= index < n`` changes that element. A dict value (the fields of an element
  model, or a JSON object) is merged into the element, anything else replaces it.
* ``index >= n`` adds elements. The new indices must continue the list without a gap:
  ``n``, ``n + 1``, ... Any other index is an error that names the env var.
* The list the patch is applied to is the merged value of the lower priority sources,
  looked up under every key the field may have (name, alias, alias choices; the key
  validation reads comes first, which is the name with ``validate_by_alias=False``);
  the result goes under the key found. When no lower source has the list, it is the
  field's default (an empty list when the field has none or it is null); a
  ``default_factory`` that takes the other values is an error. A null value counts as
  an empty list.
* Where a dict fits too (``Union[List[X], Dict[str, X]]``), a number is an index only
  when the value it changes is a list; otherwise it is a dict key, as in pydantic-settings.
  Dict keys are converted to the key type (``Dict[int, ...]``).
* A whole value in the same source (``APP_ITEMS='[...]'`` next to ``APP_ITEMS__0__NAME``)
  is what the patch is applied to. One that is not a list after JSON decoding (a
  ``NoDecode`` string, for example) is an error.
* ``-1`` or ``01`` where only a list fits is an error. Any other segment that is not an
  index is left to pydantic-settings, as without psyplus.
* Tuples and sets work like lists, a set's elements in the order the lower source lists
  them (a set default is sorted when its elements can be compared).

Only the env and ``.env`` sources ``load()`` passes to the model's
``settings_customise_sources`` read list indices. A source the model builds itself is
used as pydantic-settings makes it.

Private pydantic-settings API this module relies on (checked with 2.13.1 to 2.16.3;
the weekly "Newest dependencies" CI workflow, ``.github/workflows/newest-deps.yml``,
runs the tests against the newest releases so a breaking change shows up early):

* ``PydanticBaseEnvSettingsSource._extract_field_info`` (env var names of a field),
* the ``env_vars`` attribute of ``EnvSettingsSource``, replaced for one call,
* ``PydanticBaseSettingsSource._set_current_state`` and ``_set_settings_sources_data``
  (to call the sources the way ``BaseSettings._settings_build_values`` does).

``load()`` itself hands the resulting chain to the model through the private
``_build_sources`` argument of ``BaseSettings.__init__``.
"""
from __future__ import annotations

import collections
import collections.abc
import enum
import inspect
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Iterable, get_args, get_origin

from dotenv import dotenv_values
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic.dataclasses import is_pydantic_dataclass
from pydantic.fields import FieldInfo
from pydantic_settings import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsError,
)
from pydantic_settings.sources import DefaultSettingsSource

from psyplus.field_info import yaml_keyed
from psyplus.utils import TYPE_ALIAS_TYPES, is_list_like, is_union

_INDEX = re.compile(r"0|[1-9][0-9]*")
_INDEX_LIKE = re.compile(r"-?[0-9]+")


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

def _members(annotation: Any) -> list[Any]:
    """The types a value of *annotation* can have, without None and Annotated."""
    while get_origin(annotation) is Annotated or isinstance(annotation, TYPE_ALIAS_TYPES):
        annotation = (
            get_args(annotation)[0] if get_origin(annotation) is Annotated
            else annotation.__value__
        )
    if annotation is None or annotation is Any:
        return []
    if is_union(annotation):
        return [m for a in get_args(annotation) if a is not type(None) for m in _members(a)]
    return [annotation]


def _is_dict_like(annotation: Any) -> bool:
    origin = get_origin(annotation) or annotation
    return isinstance(origin, type) and issubclass(origin, collections.abc.Mapping)


def _model_fields(annotation: Any) -> dict[str, FieldInfo]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return dict(annotation.model_fields)
    if is_pydantic_dataclass(annotation):
        return dict(annotation.__pydantic_fields__)  # type: ignore[attr-defined]
    return {}


def _model_config(model: Any) -> Any:
    return getattr(model, "model_config", None) or getattr(model, "__pydantic_config__", {})


def _element_annotation(list_annotation: Any, index: int) -> Any:
    args = get_args(list_annotation)
    if get_origin(list_annotation) is tuple and Ellipsis not in args:  # Tuple[str, int]
        return args[index] if index < len(args) else None
    return args[0] if args else None


def _field_names(name: str, field: FieldInfo, model: Any) -> list[str]:
    """The keys of a field: the one to file a value under first, then the others.

    The first is the one validation reads: the alias, or the name when the model sets
    ``validate_by_alias=False`` (the rule ``yaml_key_path`` follows too). The others
    are where a lower source may hold the value, and what an env var may call it.
    """
    names: list[str] = []
    for alias in (field.validation_alias, field.alias):
        if isinstance(alias, str):
            names.append(alias)
        names.extend(c for c in getattr(alias, "choices", ()) if isinstance(c, str))
    if _model_config(model).get("validate_by_alias") is False:
        return list(dict.fromkeys([name, *names]))
    return list(dict.fromkeys([*names, name]))


# ---------------------------------------------------------------------------
# Patches and how they are applied
# ---------------------------------------------------------------------------

class _Node(dict):
    """Part of what the index env vars of a source set, keyed like the settings data.

    A list node (``is_list``) holds element changes keyed by index; it is a patch for
    the list the lower priority sources set. Other nodes are dicts of field or dict
    keys; ``alt`` lists the other keys the same field can be found under. ``whole`` is
    a value an env var sets for this position as a whole (JSON), which the changes
    below it apply to.
    """

    def __init__(self, path: str, is_list: bool = False, field_info: FieldInfo | None = None):
        super().__init__()
        self.path = path
        self.is_list = is_list
        self.field_info = field_info  # of the list field, for its default
        self.whole: Any = MISSING
        self.alt: dict[Any, list[str]] = {}
        self.env_names: dict[Any, list[str]] = {}
        self.in_dotenv = False
        # The position also allows a dict (``Union[List[X], Dict[str, X]]``).
        self.ambiguous = False

    def __repr__(self) -> str:
        if not self.is_list:
            return super().__repr__()
        names = ", ".join(n for names in self.env_names.values() for n in names)
        return f"<list element changes for {self.path} from {names}, applied by load()>"

    def describe(self, index: Any) -> str:
        return _describe(self.env_names.get(index, []), self.in_dotenv)

    def raw_default(self) -> Any:
        """The field's default, None when it has none."""
        fi = self.field_info
        if fi is None or fi.is_required():
            return None
        if fi.default_factory is not None and _takes_data(fi.default_factory):
            raise SettingsError(
                f"{self.describe(min(self))}: `{self.path}` is not in the YAML file or "
                "another lower priority source, and its default comes from a "
                "default_factory that depends on other values, so a single element of "
                "it can not be set. Put the list in the YAML file, or set it as a whole."
            )
        return fi.get_default(call_default_factory=True, validated_data={})

    def patch(self, base: Any, same_source: bool = False) -> Any:
        if self.ambiguous:
            value = self.raw_default() if base is MISSING else base
            if not isinstance(value, (list, tuple, set, frozenset, collections.deque)):
                # Not a list here: the indices are dict keys, as pydantic-settings reads them.
                as_dict = {str(i): v for i, v in self.items()}
                return _apply(base if isinstance(base, dict) else MISSING, as_dict, True)
        if base is MISSING:
            default = self.raw_default()
            result = yaml_keyed(_as_list(default)) if isinstance(default, Iterable) else []
            where = "its default, no lower priority source sets it"
        elif base is None:
            result, where = [], "it is null"
        elif isinstance(base, (list, tuple, set, frozenset, collections.deque)):
            result = _as_list(base)
            where = ("its whole value from the same source" if same_source
                     else "from the YAML file or another lower priority source")
        else:
            index = min(self)
            raise SettingsError(
                f"{self.describe(index)}: can not set element {index} of `{self.path}`, "
                f"the value it would change is not a list: {base!r}"
            )
        length = len(result)
        for expected, index in enumerate(sorted(i for i in self if i >= length), start=length):
            if index != expected:
                raise SettingsError(
                    f"{self.describe(index)}: list index {index} is out of range, "
                    f"`{self.path}` has {length} element(s) ({where}). Use an index "
                    f"below {length} to change an element, or {length}, {length + 1}, "
                    "... without gaps to add elements."
                )
        for index in sorted(self):
            if index < length:
                result[index] = _apply(result[index], self[index], final=True)
            else:
                result.append(_apply(MISSING, self[index], final=True))
        return result


def _takes_data(factory: Any) -> bool:
    """Whether a ``default_factory`` takes the validated data (pydantic's own rule)."""
    try:
        parameters = inspect.signature(factory).parameters
    except (ValueError, TypeError):
        return False
    return len(parameters) == 1


def _describe(env_names: list[str], in_dotenv: bool) -> str:
    """``Environment variable APP_X`` or ``APP_X in the .env file``, for error messages."""
    names = ", ".join(env_names)
    if in_dotenv:
        return f"{names} in the .env file"
    return f"Environment variable{'s' if len(env_names) > 1 else ''} {names}"


def _path_str(steps: list[Any]) -> str:
    out = ""
    for step in steps:
        out += f"[{step.key}]" if step.index else (f".{step.key}" if out else str(step.key))
    return out


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (set, frozenset)):
        try:
            return sorted(value)
        except TypeError:
            return list(value)
    return list(value)


def _pending(value: Any) -> bool:
    return isinstance(value, _Node) or (
        isinstance(value, dict) and any(_pending(v) for v in value.values())
    )


def _plain(value: Any) -> Any:
    """*value* without the list patches that still wait for the lower sources.

    Returns MISSING for a node that holds nothing else.
    """
    if not isinstance(value, dict):
        return value
    if isinstance(value, _Node) and value.is_list and value.whole is MISSING:
        return MISSING
    out = {k: v for k, v in ((k, _plain(v)) for k, v in value.items()) if v is not MISSING}
    if isinstance(value, _Node) and not out and value.whole is MISSING:
        return MISSING
    return out


def _apply(base: Any, overlay: Any, final: bool, same_source: bool = False) -> Any:
    """Merge *overlay* into *base* the way pydantic-settings merges sources (``deep_update``).

    Dicts are merged key by key, any other value replaces. A list node patches the list
    in *base*. Where *base* has no value, a list node waits (stays in the result as it
    is) unless *final* is set; then it patches the field default. *same_source* says
    that *base* comes from the source of the patches (for error messages).
    """
    if not isinstance(overlay, dict):
        return overlay
    if isinstance(overlay, _Node):
        if overlay.whole is not MISSING:
            base = _apply(base, overlay.whole, final=True)
            same_source = True
        if overlay.is_list:
            if base is MISSING and not final:
                return overlay
            return overlay.patch(base, same_source)
        if base is MISSING and not final:
            return overlay
    out: dict[Any, Any] = dict(base) if isinstance(base, dict) else {}
    if not final and isinstance(overlay, _Node):
        node = _Node(overlay.path)
        node.alt, node.in_dotenv = overlay.alt, overlay.in_dotenv
        node.update(out)
        out = node
    alt = getattr(overlay, "alt", {})
    for key, value in overlay.items():
        found = next((k for k in (key, *alt.get(key, ())) if k in out), key)
        out[found] = _apply(out.get(found, MISSING), value, final, same_source)
    return out


# ---------------------------------------------------------------------------
# The sources
# ---------------------------------------------------------------------------

@dataclass
class _Step:
    key: Any  # field key, dict key, or list index
    annotation: Any  # annotation of the value this step leads to
    field_info: FieldInfo | None = None  # set when the step is a model field
    alt: tuple[Any, ...] = ()  # other keys of the same field or dict entry
    index: bool = False  # the key is a list index
    ambiguous: bool = False  # a list index where a dict fits too


class ListIndexEnvMixin:
    """Reads numeric path segments at list positions as list indices.

    Mixed into ``EnvSettingsSource`` and ``DotEnvSettingsSource``. Env vars without a
    list index are left to pydantic-settings: they are hidden from it only while it
    builds its data for the env vars that set list elements.
    """

    _in_dotenv = False

    def has_list_index_vars(self) -> bool:
        """True when an env var of this source sets a single list element."""
        return bool(self._list_patches()[1])

    def __call__(self) -> dict[str, Any]:
        patches, used = self._list_patches()
        if not used:
            return super().__call__()  # type: ignore[misc]
        env_vars = self.env_vars  # type: ignore[has-type]
        self.env_vars = {k: v for k, v in env_vars.items() if k not in used}
        try:
            data = super().__call__()  # type: ignore[misc]
        finally:
            self.env_vars = env_vars
        return _apply(data, patches, final=False, same_source=True)

    # -- building the patches ----------------------------------------------

    def _list_patches(self) -> tuple[_Node, set[str]]:
        """``(patches for all fields, names of the env vars they come from)``, cached."""
        cached = self.__dict__.get("_psyplus_list_patches")
        if cached is None:
            cached = self.__dict__["_psyplus_list_patches"] = self._build_list_patches()
        return cached

    def _build_list_patches(self) -> tuple[_Node, set[str]]:
        root = _Node("")
        root.in_dotenv = self._in_dotenv
        used: set[str] = set()
        delimiter = self.env_nested_delimiter  # type: ignore[attr-defined]
        if not delimiter:
            return root, used
        maxsplit = (self.env_nested_max_split or 0) - 1  # type: ignore[attr-defined]
        for field_name, field in self.settings_cls.model_fields.items():  # type: ignore[attr-defined]
            prefixes = [
                f"{env_name}{delimiter}"
                for _, env_name, _ in self._extract_field_info(field, field_name)  # type: ignore[attr-defined]
            ]
            for env_name, value in self.env_vars.items():  # type: ignore[attr-defined]
                prefix = next((p for p in prefixes if env_name.startswith(p)), None)
                if prefix is None or value is None:
                    continue
                segments = env_name[len(prefix):].split(delimiter, maxsplit)
                steps = self._walk(field_name, field, segments, env_name)
                if steps is not None:
                    used.add(env_name)
                    self._insert(root, steps, value, env_name)
        return root, used

    def _display(self, name: str) -> str:
        """*name* as written: env var names arrive in lower case unless case-sensitive."""
        if self.case_sensitive:  # type: ignore[attr-defined]
            return name
        originals = self.__dict__.get("_psyplus_originals")
        if originals is None:
            originals = self.__dict__["_psyplus_originals"] = {
                k.lower(): k for k in self._written_names()
            }
        return originals.get(name, name.upper())

    def _written_names(self) -> Iterable[str]:
        return os.environ.keys()

    def _where(self, env_name: str) -> str:
        return _describe([self._display(env_name)], self._in_dotenv)

    def _keys(self, names: list[str]) -> tuple[str, ...]:
        if self.case_sensitive:  # type: ignore[attr-defined]
            return tuple(names)
        return tuple(dict.fromkeys([*names, *(n.lower() for n in names)]))

    def _walk(self, field_name: str, field: FieldInfo, segments: list[str],
              env_name: str) -> list[_Step] | None:
        """The steps of an env var from its field down, or None when it sets no list element."""
        names = _field_names(field_name, field, self.settings_cls)  # type: ignore[attr-defined]
        steps = [_Step(names[0], field.annotation, field, self._keys(names[1:]))]
        annotation: Any = field.annotation
        for segment in segments:
            members = _members(annotation)
            lists = [m for m in members if is_list_like(m)]
            only_lists = bool(lists) and len(lists) == len(members)
            if lists and _INDEX.fullmatch(segment):
                annotation = _element_annotation(lists[0], int(segment))
                ambiguous = any(_is_dict_like(m) for m in members)
                steps.append(_Step(int(segment), annotation, index=True, ambiguous=ambiguous))
                continue
            if only_lists:
                if not any(s.index for s in steps) and not _INDEX_LIKE.fullmatch(segment):
                    return None  # not meant as an index, pydantic-settings handles it
                original = self._display(env_name)
                at = original.lower().rfind(segment.lower())
                raise SettingsError(
                    f"{self._where(env_name)}: `{_path_str(steps)}` is a list, so "
                    f"`{original[at:at + len(segment)]}` must be a list index (0, 1, 2, ...). "
                    "Negative indices and leading zeros are not supported."
                )
            step = _Step(segment, None)  # an unknown key, left to validation
            wanted = segment if self.case_sensitive else segment.lower()  # type: ignore[attr-defined]
            for member in members:
                for name, fi in _model_fields(member).items():
                    keys = _field_names(name, fi, member)
                    if wanted in self._keys(keys):
                        step = _Step(keys[0], fi.annotation, fi, self._keys(keys[1:]))
                        break
                if step.field_info is not None:
                    break
                if _is_dict_like(member):
                    step = self._dict_step(segment, get_args(member))
                    break
            steps.append(step)
            annotation = step.annotation
        return steps if any(s.index for s in steps) else None

    @staticmethod
    def _dict_step(segment: str, args: tuple[Any, ...]) -> _Step:
        """A dict entry; the key converted to the dict's key type (``Dict[int, ...]``)."""
        key: Any = segment
        if len(args) == 2 and args[0] not in (str, Any):
            try:
                key = TypeAdapter(args[0]).validate_strings(segment)
            except (ValidationError, TypeError):
                pass
        return _Step(key, args[1] if len(args) == 2 else None,
                     alt=(segment,) if key != segment else ())

    def _insert(self, root: _Node, steps: list[_Step], value: str, env_name: str) -> None:
        node = root
        for i, step in enumerate(steps):
            path = _path_str(steps[: i + 1])
            if node.is_list:
                node.env_names.setdefault(step.key, []).append(self._display(env_name))
                node.ambiguous = node.ambiguous or step.ambiguous
            elif step.alt:
                node.alt[step.key] = list(step.alt)
            if i == len(steps) - 1:
                leaf = self._decode(value, step.annotation, env_name, path)
                child = node.get(step.key)
                if isinstance(child, _Node):
                    child.whole = leaf
                else:
                    node[step.key] = leaf
                return
            child = node.get(step.key)
            if not isinstance(child, _Node):
                new = _Node(path, steps[i + 1].index, step.field_info)
                new.in_dotenv = self._in_dotenv
                if step.key in node:  # an env var set this position as a whole
                    new.whole = child
                node[step.key] = new
                child = new
            node = child

    def _decode(self, value: str, annotation: Any, env_name: str, path: str) -> Any:
        if value == getattr(self, "env_parse_none_str", None):
            return None
        members = _members(annotation)
        complex_ = [m for m in members
                    if is_list_like(m) or _is_dict_like(m) or _model_fields(m)]
        if complex_:
            try:
                decoded = json.loads(value)
            except ValueError as e:
                if len(complex_) < len(members):
                    return value
                raise SettingsError(
                    f"{self._where(env_name)}: `{path}` needs a JSON value: {e}"
                ) from e
            if len(complex_) < len(members) and not isinstance(decoded, (list, dict)):
                return value
            return decoded
        if getattr(self, "env_parse_enums", None):
            for member in members:
                if isinstance(member, type) and issubclass(member, enum.Enum) \
                        and value in member.__members__:
                    return member[value]
        if self.config.get("strict") and annotation is not None:  # type: ignore[attr-defined]
            try:
                return TypeAdapter(annotation).validate_strings(value, strict=True)
            except ValidationError:
                pass  # validation reports it
        return value


class ListIndexEnvSettingsSource(ListIndexEnvMixin, EnvSettingsSource):
    """``EnvSettingsSource`` that also sets single list elements (``APP_ITEMS__0__NAME``)."""


class ListIndexDotEnvSettingsSource(ListIndexEnvMixin, DotEnvSettingsSource):
    """``DotEnvSettingsSource`` that also sets single list elements (``APP_ITEMS__0__NAME``)."""

    _in_dotenv = True

    def _written_names(self) -> Iterable[str]:
        files = self.env_file
        if files is None:
            return []
        if isinstance(files, (str, os.PathLike)):
            files = [files]
        return [
            name for file in files if Path(file).expanduser().is_file()
            for name in dotenv_values(Path(file).expanduser())
        ]


# pydantic-settings names a source's data (``settings_sources_data``) and its error
# messages after the class name. Keep the documented names.
ListIndexEnvSettingsSource.__name__ = "EnvSettingsSource"
ListIndexDotEnvSettingsSource.__name__ = "DotEnvSettingsSource"


# ---------------------------------------------------------------------------
# Applying the patches across sources
# ---------------------------------------------------------------------------

class _ReplaySource(PydanticBaseSettingsSource):
    """Returns the data an already called source produced (with list patches applied)."""

    def __init__(self, settings_cls: type[Any], data: dict[str, Any], name: str) -> None:
        super().__init__(settings_cls)
        self._data = data
        # pydantic-settings names a source's data after ``__name__`` when it has one.
        self.__name__ = name

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.__name__})"


def resolve_list_patches(
    settings_cls: type[Any], sources: tuple[Any, ...], created: tuple[Any, ...] = ()
) -> tuple[Any, ...]:
    """Apply the single list element env vars of *sources* to the lists below them.

    *created* are the list index sources ``load()`` made; the model may have wrapped them
    in a source of its own, whose data then holds their list patches too.

    Returns *sources* unchanged when no source sets a single list element. Otherwise it
    calls every source once, highest priority first, the way
    ``BaseSettings._settings_build_values`` does (a source sees the data of the sources
    above it without the list patches that still wait for lower data). Then, from the
    lowest priority source up, it applies each source's list patches to the merged data
    of the sources below. The result is a chain of sources that return these data,
    which pydantic-settings merges as usual. ``DefaultSettingsSource`` stays itself
    (pydantic-settings treats it specially), it is cheap to call again.
    """
    def has_vars(source: Any) -> bool:
        try:
            return source.has_list_index_vars()
        except SettingsError:
            if any(source is s for s in sources):
                raise
            return True  # a wrapped source raises it when it is called

    if not any(
        isinstance(s, ListIndexEnvMixin) and has_vars(s) for s in (*sources, *created)
    ):
        return sources

    outputs: list[dict[str, Any]] = []
    names: list[str] = []
    state: dict[str, Any] = {}
    states: dict[str, dict[str, Any]] = {}
    for source in sources:
        if isinstance(source, PydanticBaseSettingsSource):
            source._set_current_state(state)
            source._set_settings_sources_data(states)
        name = source.__name__ if hasattr(source, "__name__") else type(source).__name__
        output = source()
        plain = _plain(output)
        states[name] = {} if plain is MISSING else plain
        state = _apply(states[name], state, final=True)
        outputs.append(output)
        names.append(name)

    below: dict[str, Any] = {}
    for i in range(len(outputs) - 1, -1, -1):
        if _pending(outputs[i]):
            outputs[i] = _apply(below, outputs[i], final=True)
        below = _apply(below, outputs[i], final=True)

    return tuple(
        source if isinstance(source, DefaultSettingsSource)
        else _ReplaySource(settings_cls, data, name)
        for source, data, name in zip(sources, outputs, names)
    )
