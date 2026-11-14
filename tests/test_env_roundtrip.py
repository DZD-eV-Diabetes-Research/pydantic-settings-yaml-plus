"""Every env var name psyplus documents must actually set that value in load().

For each scalar (str/int) leaf that has an env var in the generated YAML comments or in
the Markdown doc:
  1. write the generated YAML template to disk,
  2. set the documented env var (placeholders replaced by a real key) to a sentinel,
  3. call YamlSettingsPlus.load(),
  4. assert the leaf now holds the sentinel.
"""
from __future__ import annotations

import os
import re
from typing import get_args, get_origin
from unittest import mock

import pytest
import yaml

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
    NestedModel,
    MultiNestedModel,
    MyAppConfig,
]

_SEGMENT = re.compile(r"\[(\d+|\*|'[^']*')\]|([^.\[\]]+)")


# ---------------------------------------------------------------------------
# Read the env var names the way a user sees them
# ---------------------------------------------------------------------------

def yaml_env_names(model) -> dict[str, str]:
    """Parse the generated YAML and return {yaml_path: env_var_name}."""
    out: dict[str, str] = {}
    key = path = None
    for raw in YamlSettingsPlus(model).render_yaml().splitlines():
        line = raw.strip()
        m = re.match(r"# ## (.+?)(?: - .*)? ###$", line)
        if m:
            key, path = m.group(1), None
            continue
        m = re.match(r"# YAML-path:\s+(.+)$", line)
        if m:
            path = m.group(1)
            continue
        m = re.match(r"# Env-var:\s+'([^']+)'", line)
        if m and key is not None:
            out[path or key] = m.group(1)
    return out


def md_env_names(model) -> dict[str, str]:
    """Parse the generated Markdown and return {heading_path: env_var_name}."""
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


def get_attr_path(obj, segments):
    for seg in segments:
        if isinstance(seg, int) or isinstance(obj, dict):
            obj = obj[seg]
        else:
            obj = getattr(obj, seg)
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
                m.model_fields[seg].annotation
                for m in members
                if seg in getattr(m, "model_fields", {})
            )
    return ann


def is_dict_key(model, prefix) -> bool:
    """True if the segment after *prefix* is a dict key, not a field name."""
    return get_origin(clean_annotation(annotation_at(model, prefix))) is dict


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def collect():
    params = []
    for model in MODELS:
        template = yaml.safe_load(YamlSettingsPlus(model).render_yaml())
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
    # Each <dict-key> placeholder becomes the concrete key of this element.
    keys = iter(
        [s for i, s in enumerate(concrete) if isinstance(s, str) and is_dict_key(model, concrete[:i])]
    )
    concrete_env = re.sub(r"<dict-key>", lambda _m: next(keys), env)

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
