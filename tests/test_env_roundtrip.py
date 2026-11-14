"""Every env var name psyplus documents must actually set that value in load().

For each scalar (str/int) leaf that has an env var in the generated YAML comments or in
the Markdown doc (including the env var for one element of a list field):
  1. write the generated YAML template to disk (with its empty required values filled in),
  2. set the documented env var (placeholders replaced by a real key or list index) to
     a sentinel,
  3. call YamlSettingsPlus.load(),
  4. assert the leaf now holds the sentinel and every other value is still the one from
     the YAML file (a list element env var changes one element, not the whole list).
"""
from __future__ import annotations

import copy
import os
import re
from typing import get_args, get_origin
from unittest import mock

import pytest
import yaml
from pydantic import AliasChoices

from psyplus import YamlSettingsPlus
from psyplus.utils import clean_annotation, get_literal_list
from tests.models import env_cases as cases
from tests.models.nested import MultiNestedModel, NestedModel
from tests.models.readme_example import MyAppConfig

MODELS = [
    cases.Deep,
    cases.WithSubSettings,
    cases.Collections,
    cases.Edge,
    cases.NoDelim,
    cases.CaseSens,
    cases.MaxSplit,
    cases.Aliases,
    cases.AliasesPrefixAlias,
    cases.AliasesPrefixAll,
    cases.AliasesCaseSens,
    cases.AliasesByName,
    cases.Camel,
    cases.CamelPrefixAll,
    cases.CamelCaseSens,
    cases.UnionAliases,
    cases.UnionAliasesByName,
    cases.ListCases,
    cases.MaxSplitLists,
    cases.MaxSplitOneLevel,
    cases.CaseSensLists,
    NestedModel,
    MultiNestedModel,
    MyAppConfig,
]

# The template leaves required values without a default empty (null), so it does not
# load untouched. These fill them in; fill_required() checks each replaces a null.
REQUIRED_VALUES = {
    **{
        model: {"REQ": "r"}
        for model in (
            cases.Aliases,
            cases.AliasesPrefixAlias,
            cases.AliasesPrefixAll,
            cases.AliasesCaseSens,
            cases.AliasesByName,
        )
    },
    NestedModel: {"admin_password": "pw", "database": {"name": "db"}},
    MyAppConfig: {
        "admin_pw": "pw",
        "database_server": {"database_names": ["db"]},
        "init_values": {"k": "v"},
    },
}

_SEGMENT = re.compile(r"\[(\d+|\*|'[^']*')\]|([^.\[\]]+)")


# ---------------------------------------------------------------------------
# Read the env var names the way a user sees them
# ---------------------------------------------------------------------------

def yaml_env_names(model) -> dict[str, str]:
    """Parse the generated YAML and return {yaml_path: env_var_name}.

    The env var for one element of a list field (second line of ``Env-var:``) is
    returned for the path ``<list field>[*]``.
    """
    out: dict[str, str] = {}
    key = path = None
    in_env_var = False
    for raw in YamlSettingsPlus(model).render_yaml().splitlines():
        line = raw.strip()
        m = re.match(r"# ## (.+?)(?: - .*)? ###$", line)
        if m:
            key, path, in_env_var = m.group(1), None, False
            continue
        m = re.match(r"# YAML-path:\s+(.+)$", line)
        if m:
            path = m.group(1)
            continue
        m = re.match(r"# Env-var:\s+'([^']+)'", line)
        if m and key is not None:
            out[path or key] = m.group(1)
            in_env_var = True
            continue
        m = re.match(r"#\s+'([^']+)' \(one element", line)
        if m and in_env_var:
            out[f"{path or key}[*]"] = m.group(1)
            continue
        in_env_var = False
    return out


def md_env_names(model) -> dict[str, str]:
    """Parse the generated Markdown and return {heading_path: env_var_name}.

    The env var for one element of a list field is returned for ``<list field>[*]``.
    """
    out: dict[str, str] = {}
    path = None
    for line in YamlSettingsPlus(model).render_markdown().splitlines():
        m = re.match(r"#+ `([^`]+)`\s*$", line)
        if m:
            path = m.group(1)
            continue
        m = re.match(r"\| Environment variable \| `([^`]+)`", line)
        if m and path:
            out[path] = m.group(1)
        m = re.match(r"\| Environment variable \(one element\) \| `([^`]+)`", line)
        if m and path:
            out[f"{path}[*]"] = m.group(1)
    return out


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def parse_path(path: str) -> list:
    """``servers[0].host`` -> ``["servers", 0, "host"]``; ``[*]`` stays ``"*"``."""
    out: list = []
    for idx, name in _SEGMENT.findall(path):
        if name:
            out.append(name)
        elif idx == "*":
            out.append("*")
        elif idx.startswith("'"):
            out.append(idx[1:-1])
        else:
            out.append(int(idx))
    return out


def resolve(data, segments):
    """Walk data along segments, ``"*"`` meaning the first element or key."""
    concrete = []
    cur = data
    for seg in segments:
        if seg == "*":
            seg = 0 if isinstance(cur, list) else next(iter(cur))
        cur = cur[seg]
        concrete.append(seg)
    return cur, concrete


def field_name(model_cls, key):
    """The name of the field of *model_cls* whose YAML key is *key*, or None.

    The key is the validation alias (of ``AliasChoices`` the first str), else the name.
    """
    for name, fi in getattr(model_cls, "model_fields", {}).items():
        alias = fi.validation_alias
        if isinstance(alias, AliasChoices):
            alias = next((c for c in alias.choices if isinstance(c, str)), None)
        if (alias if isinstance(alias, str) else name) == key:
            return name
    return None
def set_path(data, segments, value):
    for seg in segments[:-1]:
        data = data[seg]
    data[segments[-1]] = value


def get_attr_path(obj, segments):
    for seg in segments:
        if isinstance(obj, (set, frozenset)):
            obj = sorted(obj)  # the test sets have one element
        if isinstance(seg, int) or isinstance(obj, dict):
            obj = obj[seg]
        else:
            obj = getattr(obj, field_name(type(obj), seg))
    return obj


def annotation_at(model, prefix):
    ann = model
    for seg in prefix:
        cleaned = clean_annotation(ann)
        if isinstance(seg, int):
            ann = get_args(cleaned)[0]
        elif get_origin(cleaned) is dict:
            ann = get_args(cleaned)[1]
        else:
            members = (
                get_args(cleaned)
                if get_origin(cleaned) is not None and not hasattr(cleaned, "model_fields")
                else (cleaned,)
            )
            ann = next(
                m.model_fields[field_name(m, seg)].annotation
                for m in members
                if field_name(m, seg) is not None
            )
    return ann


def fill_required(template: dict, values: dict) -> None:
    for key, value in values.items():
        if isinstance(value, dict) and isinstance(template.get(key), dict):
            fill_required(template[key], value)
        else:
            assert template[key] is None, f"{key!r} is not empty in the template"
            template[key] = value


def is_dict_key(model, prefix) -> bool:
    """True if the segment after *prefix* is a dict key, not a field name."""
    return get_origin(clean_annotation(annotation_at(model, prefix))) is dict


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def collect():
    params = []
    for model in MODELS:
        try:
            template = yaml.safe_load(YamlSettingsPlus(model).render_yaml())
            fill_required(template, REQUIRED_VALUES.get(model, {}))
        except Exception as e:  # noqa: BLE001
            # Fail this model's test instead of the collection of all models.
            params.append(
                pytest.param(model, "template", "", "", None, [], e, id=f"{model.__name__}-template")
            )
            continue
        names = [("yaml", p, n) for p, n in yaml_env_names(model).items()]
        names += [("md", p, n) for p, n in md_env_names(model).items()]
        for source, path, env in names:
            try:
                value, concrete = resolve(template, parse_path(path))
            except (KeyError, IndexError, TypeError, StopIteration):
                continue  # e.g. an Optional sub-model that is null in the template
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                continue
            params.append(
                pytest.param(
                    model, source, path, env, template, concrete, value,
                    id=f"{model.__name__}-{source}-{path}",
                )
            )
    return params


@pytest.mark.parametrize("model,source,path,env,template,concrete,value", collect())
def test_documented_env_var_sets_value(
    model, source, path, env, template, concrete, value, tmp_path
):
    if source == "template":
        pytest.fail(f"the template of {model.__name__} can not be filled in: {value!r}")
    # Each <dict-key> placeholder becomes the concrete key of this element, each
    # <list-index> placeholder the concrete index.
    keys = iter(
        [s for i, s in enumerate(concrete) if isinstance(s, str) and is_dict_key(model, concrete[:i])]
    )
    indices = iter([s for s in concrete if isinstance(s, int)])
    concrete_env = re.sub(r"<dict-key>", lambda _m: next(keys), env)
    concrete_env = re.sub(r"<list-index>", lambda _m: str(next(indices)), concrete_env)

    sentinel = "ENVVAL" if isinstance(value, str) else 4242
    allowed = get_literal_list(annotation_at(model, concrete))
    if allowed:
        others = [v for v in allowed if v != value]
        if not others:
            pytest.skip("single-value Literal")
        sentinel = others[0]

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(template))
    env_vars = {
        "PSYPLUS_SUPPRESS_ENV_WARNING": "1",
        "PATH": os.environ.get("PATH", ""),
        concrete_env: str(sentinel),
    }
    with mock.patch.dict(os.environ, env_vars, clear=True):
        try:
            loaded = YamlSettingsPlus(model, config_path).load()
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"documented env var {concrete_env!r} ({source}) breaks load(): {e}")
    got = get_attr_path(loaded, concrete)
    assert got == sentinel, (
        f"documented env var {concrete_env!r} ({source}) did not set {path}: got {got!r}"
    )
    # Everything else keeps the value from the YAML file.
    expected = copy.deepcopy(template)
    set_path(expected, concrete, sentinel)
    assert loaded == model.model_validate(expected), (
        f"documented env var {concrete_env!r} ({source}) changed more than {path}"
    )


def test_list_element_env_vars_are_documented():
    """The names above only reach the roundtrip test when the generated files show them."""
    yaml_names = yaml_env_names(cases.ListCases)
    md_names = md_env_names(cases.ListCases)
    assert yaml_names["tagged[*]"] == "APP_TAGGED__<list-index>"
    assert yaml_names["tagged[0].name"] == "APP_TAGGED__<list-index>__NAME"
    assert yaml_names["tagged[1].tags[0]"] == "APP_TAGGED__<list-index>__TAGS__<list-index>"
    assert yaml_names["groups['admins'][1]"] == "APP_GROUPS__<dict-key>__<list-index>"
    assert yaml_names["matrix[1][0]"] == "APP_MATRIX__<list-index>__<list-index>"
    assert md_names["tagged[*].tags[*]"] == "APP_TAGGED__<list-index>__TAGS__<list-index>"
    assert md_names["nested.tags[*]"] == "APP_NESTED__TAGS__<list-index>"
