"""Tests for psyplus/markdown_generator.py — MarkdownDocGenerator."""
import pytest

from psyplus.markdown_generator import MarkdownDocGenerator
from tests.models.simple import SimpleModel
from tests.models.nested import MultiNestedModel, NestedModel
from tests.models.readme_example import MyAppConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate(model_cls) -> str:
    return MarkdownDocGenerator(model_cls).generate()


# ---------------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------------

class TestMarkdownStructure:
    def test_starts_with_heading(self):
        doc = _generate(SimpleModel)
        assert doc.startswith("# ")

    def test_class_name_in_heading(self):
        doc = _generate(SimpleModel)
        assert "SimpleModel" in doc

    def test_contains_horizontal_rule(self):
        doc = _generate(SimpleModel)
        assert "---" in doc

    def test_all_fields_have_sections(self):
        doc = _generate(SimpleModel)
        for field_name in SimpleModel.model_fields:
            assert f"`{field_name}`" in doc

    def test_nested_fields_have_sections(self):
        doc = _generate(NestedModel)
        # The nested DatabaseConfig fields should appear as sub-headings
        assert "database.host" in doc
        assert "database.port" in doc
        assert "database.name" in doc

    def test_property_table_present(self):
        doc = _generate(SimpleModel)
        assert "| Property | Value |" in doc
        assert "|---|---|" in doc


# ---------------------------------------------------------------------------
# Field metadata
# ---------------------------------------------------------------------------

class TestMarkdownFieldMetadata:
    def test_required_yes(self):
        doc = _generate(SimpleModel)
        # required_string is required
        idx = doc.index("`required_string`")
        section = doc[idx: idx + 400]
        assert "**Yes**" in section

    def test_required_no(self):
        doc = _generate(SimpleModel)
        idx = doc.index("`a_string`")
        section = doc[idx: idx + 400]
        assert "| Required | No |" in section

    def test_default_shown(self):
        doc = _generate(SimpleModel)
        assert '"hello"' in doc or "hello" in doc  # a_string default

    def test_env_var_shown(self):
        doc = _generate(SimpleModel)
        assert "SIMPLE_A_STRING" in doc

    def test_description_shown(self):
        doc = _generate(SimpleModel)
        assert "A fully documented optional string field." in doc

    def test_literal_allowed_values(self):
        doc = _generate(SimpleModel)
        # literal_field has Literal["A", "B", "C"]
        assert "`A`" in doc
        assert "`B`" in doc
        assert "`C`" in doc

    def test_title_shown(self):
        doc = _generate(SimpleModel)
        assert "Great String" in doc

    def test_examples_shown(self):
        doc = _generate(SimpleModel)
        assert "ex1" in doc

    def test_type_shown(self):
        doc = _generate(SimpleModel)
        assert "str" in doc

    def test_list_type_shown(self):
        doc = _generate(SimpleModel)
        assert "List of str" in doc


# ---------------------------------------------------------------------------
# README example model
# ---------------------------------------------------------------------------

class TestReadmeExampleMarkdown:
    def test_all_top_level_fields(self):
        doc = _generate(MyAppConfig)
        for field_name in MyAppConfig.model_fields:
            assert field_name in doc

    def test_nested_database_server_fields(self):
        doc = _generate(MyAppConfig)
        assert "database_server.host" in doc
        assert "database_server.port" in doc
        assert "database_server.database_names" in doc

    def test_nested_env_vars(self):
        doc = _generate(MyAppConfig)
        # prefix "APP_" + delimiter "__" → APP_DATABASE_SERVER__HOST
        assert "APP_DATABASE_SERVER__HOST" in doc

    def test_example_content(self):
        doc = _generate(MyAppConfig)
        assert "db.company.org" in doc  # from DatabaseServerSettings example


# ---------------------------------------------------------------------------
# List[BaseModel] and Dict[str, BaseModel] recursion
# ---------------------------------------------------------------------------

class TestCollectionNestedRecursion:
    def test_list_item_schema_heading(self):
        doc = _generate(MultiNestedModel)
        assert "servers[*]" in doc

    def test_list_item_sub_fields_present(self):
        doc = _generate(MultiNestedModel)
        assert "servers[*].host" in doc
        assert "servers[*].port" in doc

    def test_dict_item_schema_heading(self):
        doc = _generate(MultiNestedModel)
        assert "server_map[*]" in doc

    def test_dict_item_sub_fields_present(self):
        doc = _generate(MultiNestedModel)
        assert "server_map[*].host" in doc
        assert "server_map[*].port" in doc

    def test_sub_fields_have_property_tables(self):
        doc = _generate(MultiNestedModel)
        # Each sub-field section should include a property table
        assert doc.count("| Property | Value |") >= 4  # servers + server_map + 2 sub-fields each

    def test_direct_nested_model_unaffected(self):
        # Direct BaseModel fields still recurse without [*] path
        doc = _generate(NestedModel)
        assert "database.host" in doc
        assert "database.port" in doc
        assert "database[*]" not in doc
