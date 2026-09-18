"""Nullable fields: "or null" in the type and the note on setting null through env vars."""
import pytest

from psyplus.field_info import FieldInfoContainer
from psyplus.markdown_generator import MarkdownDocGenerator
from psyplus.yaml_generator import YamlFileGenerator
from tests.models.nullable import NullableEnvNoneModel, NullableModel


def _container(model_cls, name: str) -> FieldInfoContainer:
    return FieldInfoContainer(
        path=[name],
        field_name=name,
        field_info=model_cls.model_fields[name],
        root_settings_class=model_cls,
    )


def _markdown_section(model_cls, name: str) -> str:
    doc = MarkdownDocGenerator(model_cls).generate()
    start = doc.index(f"## `{name}`")
    return doc[start: doc.index("\n---", start)]


def _yaml_block(model_cls, name: str) -> str:
    gen = YamlFileGenerator(model_cls)
    gen.parse()
    raw = gen.get_yaml()
    start = raw.index(f"## {name} ###")
    return raw[start: raw.index("\n\n", start)]


class TestTypeString:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("max_age_days", "int or null"),
            ("labels", "List of str or null"),
            ("annotated_limit", "int or null"),
            ("null_by_default", "str or null"),
            ("not_nullable", "int"),
        ],
    )
    def test_nullable_fields_say_or_null(self, name, expected):
        assert _container(NullableModel, name).get_type_string() == expected

    def test_markdown_type_row(self):
        assert "| Type | int or null |" in _markdown_section(NullableModel, "max_age_days")

    def test_yaml_type_line(self):
        assert "int or null" in _yaml_block(NullableModel, "max_age_days")


class TestEnvVarNullNote:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("max_age_days", True),
            ("labels", True),
            ("annotated_limit", True),
            # Leaving the env var unset already gives null.
            ("null_by_default", False),
            ("not_nullable", False),
        ],
    )
    def test_which_fields_get_the_note(self, name, expected):
        assert _container(NullableModel, name).needs_env_var_null_note() is expected

    def test_markdown_without_env_parse_none_str(self):
        section = _markdown_section(NullableModel, "max_age_days")
        assert (
            "| Environment variable | `NUL_MAX_AGE_DAYS` "
            "(can not set null, use `null` in the YAML file) |"
        ) in section

    def test_markdown_with_env_parse_none_str(self):
        section = _markdown_section(NullableEnvNoneModel, "max_age_days")
        assert "| Environment variable | `NUL_MAX_AGE_DAYS` (`null` sets null) |" in section

    def test_markdown_no_note_on_non_nullable_field(self):
        section = _markdown_section(NullableModel, "not_nullable")
        assert "| Environment variable | `NUL_NOT_NULLABLE` |" in section

    def test_yaml_without_env_parse_none_str(self):
        block = _yaml_block(NullableModel, "max_age_days")
        assert "'NUL_MAX_AGE_DAYS' (can not set null, use null in the YAML file)" in block

    def test_yaml_with_env_parse_none_str(self):
        block = _yaml_block(NullableEnvNoneModel, "max_age_days")
        assert "'NUL_MAX_AGE_DAYS' ('null' sets null)" in block


class TestNoteMatchesPydanticSettings:
    """The note makes a claim about pydantic-settings; check the claim still holds."""

    def test_without_env_parse_none_str_env_can_not_set_null(self, monkeypatch):
        monkeypatch.setenv("NUL_LABELS", "null")
        # A list field silently keeps its default.
        assert NullableModel().labels == ["a", "b"]
        monkeypatch.setenv("NUL_MAX_AGE_DAYS", "null")
        # An int field fails validation.
        with pytest.raises(Exception):
            NullableModel()

    def test_with_env_parse_none_str_env_sets_null(self, monkeypatch):
        monkeypatch.setenv("NUL_MAX_AGE_DAYS", "null")
        monkeypatch.setenv("NUL_LABELS", "null")
        config = NullableEnvNoneModel()
        assert config.max_age_days is None
        assert config.labels is None
