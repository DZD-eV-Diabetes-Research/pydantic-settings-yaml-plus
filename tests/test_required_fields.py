"""Required fields and default values in the generated YAML template.

A required field without a default is written as an empty value (null), so the
untouched template does not load: load() fails with a ValidationError that names
every value still to fill in.
"""
from __future__ import annotations

import datetime
import enum
import logging
import os
from pathlib import Path
from typing import Annotated, Dict, List, Optional

import pytest
import yaml
from pydantic import BaseModel, Field, HttpUrl, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from psyplus import YamlSettingsPlus
from tests.models.readme_example import MyAppConfig


def _generate(model_cls) -> tuple[str, dict]:
    raw = YamlSettingsPlus(model_cls).render_yaml()
    return raw, yaml.safe_load(raw)


def _error_paths(exc: ValidationError) -> set[str]:
    return {".".join(str(part) for part in err["loc"]) for err in exc.errors()}


def _clear_env(monkeypatch, prefix: str) -> None:
    for name in list(os.environ):
        if name.upper().startswith(prefix):
            monkeypatch.delenv(name)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class RequiredTypes(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PSYREQ_", env_nested_delimiter="__")

    data_dir: Path
    color: Color
    since: datetime.datetime
    token: SecretStr
    homepage: HttpUrl
    workers: Annotated[int, Field(gt=0)]
    name: str = Field(min_length=1)
    keep: int = 7


REQUIRED_TYPES_FILLED = {
    "data_dir": "/srv/data",
    "color": "blue",
    "since": "2024-01-02T03:04:05",
    "token": "s3cret",
    "homepage": "https://example.org/",
    "workers": 3,
    "name": "x",
}


class Sub(BaseModel):
    host: str = "localhost"
    password: str
    nicknames: List[str]


class RequiredKinds(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PSYKIND_", env_nested_delimiter="__")

    text: str
    items: List[str]
    mapping: Dict[str, int]
    sub: Sub
    sub_list: List[Sub]
    maybe_sub: Optional[Sub]


# ---------------------------------------------------------------------------
# Required fields without a default
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_special_and_constrained_types_generate(self):
        raw, parsed = _generate(RequiredTypes)
        for key in REQUIRED_TYPES_FILLED:
            assert parsed[key] is None, key
            assert f"\n{key}:\n" in raw, key
        assert parsed["keep"] == 7

    def test_untouched_template_does_not_load(self, tmp_path, monkeypatch):
        _clear_env(monkeypatch, "PSYREQ_")
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(RequiredTypes, path)
        handler.generate_config_file()
        with pytest.raises(ValidationError) as info:
            handler.load()
        assert _error_paths(info.value) == set(REQUIRED_TYPES_FILLED)

    def test_filled_template_loads(self, tmp_path, monkeypatch):
        _clear_env(monkeypatch, "PSYREQ_")
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(RequiredTypes, path)
        handler.generate_config_file()
        data = yaml.safe_load(path.read_text())
        data.update(REQUIRED_TYPES_FILLED)
        path.write_text(yaml.safe_dump(data))
        config = handler.load()
        assert config.data_dir == Path("/srv/data")
        assert config.color is Color.BLUE
        assert config.since == datetime.datetime(2024, 1, 2, 3, 4, 5)
        assert config.token.get_secret_value() == "s3cret"
        assert str(config.homepage) == "https://example.org/"
        assert config.workers == 3
        assert config.name == "x"
        assert config.keep == 7

    def test_untouched_readme_template_does_not_load(self, tmp_path, monkeypatch):
        _clear_env(monkeypatch, "APP_")
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(MyAppConfig, path)
        handler.generate_config_file()
        with pytest.raises(ValidationError) as info:
            handler.load()
        assert _error_paths(info.value) == {
            "admin_pw",
            "database_server.database_names",
            "init_values",
        }

    def test_filled_readme_template_loads(self, tmp_path, monkeypatch):
        _clear_env(monkeypatch, "APP_")
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(MyAppConfig, path)
        handler.generate_config_file()
        text = path.read_text()
        for empty, filled in [
            ("\nadmin_pw:\n", "\nadmin_pw: secret\n"),
            ("\n  database_names:\n", "\n  database_names: [db1]\n"),
            ("\ninit_values:\n", "\ninit_values: {k: v}\n"),
        ]:
            assert empty in text
            text = text.replace(empty, filled)
        path.write_text(text)
        config = handler.load()
        assert config.admin_pw == "secret"
        assert config.database_server.database_names == ["db1"]
        assert config.init_values == {"k": "v"}

    def test_empty_form_per_kind(self):
        raw, parsed = _generate(RequiredKinds)
        # Leaves, lists, dicts and lists of models are null.
        assert parsed["text"] is None
        assert parsed["items"] is None
        assert parsed["mapping"] is None
        assert parsed["sub_list"] is None
        # A required sub-model shows its fields: defaults filled in, required ones null.
        assert parsed["sub"] == {"host": "localhost", "password": None, "nicknames": None}
        assert "  # YAML-path: sub.password\n" in raw
        # Optional[Model] accepts null, so it is null and its comment lists the env
        # vars of its fields.
        assert parsed["maybe_sub"] is None
        assert "maybe_sub.password: 'PSYKIND_MAYBE_SUB__PASSWORD'" in raw

    def test_empty_form_per_kind_does_not_load(self, tmp_path, monkeypatch):
        _clear_env(monkeypatch, "PSYKIND_")
        path = tmp_path / "config.yaml"
        handler = YamlSettingsPlus(RequiredKinds, path)
        handler.generate_config_file()
        with pytest.raises(ValidationError) as info:
            handler.load()
        # maybe_sub is missing: null is a valid value for Optional[Sub].
        assert _error_paths(info.value) == {
            "text",
            "items",
            "mapping",
            "sub.password",
            "sub.nicknames",
            "sub_list",
        }

    def test_recursive_required_model_terminates(self):
        class Node(BaseSettings):
            name: str = "n"
            child: Node

        Node.model_rebuild()
        _, parsed = _generate(Node)
        assert parsed == {"name": "n", "child": None}


# ---------------------------------------------------------------------------
# default_factory that takes the validated data (pydantic 2.10+)
# ---------------------------------------------------------------------------

class TestDefaultFactoryWithData:
    def test_factory_gets_preceding_values(self):
        class M(BaseSettings):
            host: str = "db.local"
            port: int = Field(default_factory=lambda: 5432)
            url: str = Field(default_factory=lambda data: f"pg://{data['host']}:{data['port']}")

        _, parsed = _generate(M)
        assert parsed == {"host": "db.local", "port": 5432, "url": "pg://db.local:5432"}

    def test_factory_in_sub_models(self):
        class Item(BaseModel):
            name: str = "main"
            label: str = Field(default_factory=lambda data: data["name"].upper())

        class M(BaseSettings):
            sub: Item = Field(default_factory=Item)
            required_sub: Item
            items: List[Item] = [Item(name="a")]

        _, parsed = _generate(M)
        assert parsed["sub"] == {"name": "main", "label": "MAIN"}
        assert parsed["required_sub"] == {"name": "main", "label": "MAIN"}
        assert parsed["items"] == [{"name": "a", "label": "A"}]

    def test_factory_needing_a_required_value_is_written_empty(self, caplog):
        class M(BaseSettings):
            host: str
            url: str = Field(default_factory=lambda data: f"http://{data['host']}")

        with caplog.at_level(logging.WARNING, logger="psyplus.yaml_generator"):
            raw, parsed = _generate(M)
        assert parsed == {"host": None, "url": None}
        assert "Remove this key to use it." in raw.split("\nurl:", 1)[0]
        assert "`url`" in caplog.text


# ---------------------------------------------------------------------------
# Values of default sub-model instances
# ---------------------------------------------------------------------------

class TestDefaultInstances:
    def test_instance_values_win_over_class_defaults(self):
        class Inner(BaseModel):
            host: str = "class-default"
            port: int = 1

        class M(BaseSettings):
            sub: Inner = Inner(host="instance-value")

        _, parsed = _generate(M)
        assert parsed["sub"] == {"host": "instance-value", "port": 1}

    def test_constructed_instance_missing_a_required_field(self):
        class Inner(BaseModel):
            host: str = "h"
            password: str

        class M(BaseSettings):
            sub: Inner = Inner.model_construct(host="given")

        _, parsed = _generate(M)
        assert parsed["sub"] == {"host": "given", "password": None}
