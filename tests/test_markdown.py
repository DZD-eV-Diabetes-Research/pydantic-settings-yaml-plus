"""Tests for psyplus/markdown_generator.py — MarkdownDocGenerator."""
from typing import Dict, List, Literal, Optional, Union

import pytest
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    def test_dict_item_env_var_uses_placeholder(self):
        doc = _generate(MultiNestedModel)
        assert "`MULTI_SERVER_MAP__<dict-key>__HOST`" in doc
        assert "[*]__" not in doc

    def test_list_item_fields_use_list_index_placeholder(self):
        # load() can set a single list element, <list-index> stands for its position
        doc = _generate(MultiNestedModel)
        assert "`MULTI_SERVERS__<list-index>__HOST`" in doc
        assert "`MULTI_SERVERS__<list-index>__PORT`" in doc
        assert "MULTI_SERVERS[" not in doc

    def test_list_field_shows_env_var_for_one_element(self):
        doc = _generate(MultiNestedModel)
        assert (
            "| Environment variable (one element) | `MULTI_SERVERS__<list-index>` "
            "(0 is the first; psyplus `load()` only) |"
        ) in doc
        # Dicts get no such row
        assert "MULTI_SERVER_MAP__<dict-key>` (" not in doc

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


class _Node(BaseModel):
    name: str = "n"
    children: List["_Node"] = []


_Node.model_rebuild()


class TestMarkdownEdgeCases:
    def test_self_referencing_model_does_not_recurse_forever(self):
        class Tree(BaseSettings):
            root: _Node = _Node()

        doc = _generate(Tree)
        assert "`root.children`" in doc
        # The item schema of _Node is already documented under `root`.
        assert "root.children[*]" not in doc

    def test_pipe_in_table_cell_is_escaped(self):
        class Piped(BaseSettings):
            sep: str = Field(default="a|b")

        doc = _generate(Piped)
        assert '`"a\\|b"`' in doc


# ---------------------------------------------------------------------------
# Union of models, inline code, heading depth, dict keys from env vars
# ---------------------------------------------------------------------------

class _Cat(BaseModel):
    kind: Literal["cat"] = "cat"
    lives: int = 9


class _Dog(BaseModel):
    kind: Literal["dog"] = "dog"
    bark: str = "woof"


class _Pets(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PETS_", env_nested_delimiter="__")

    pet: Union[_Cat, _Dog] = _Cat()
    maybe_pet: Optional[Union[_Cat, _Dog]] = None
    pets: List[Union[_Cat, _Dog]] = []
    pet_map: Dict[str, Union[_Cat, _Dog]] = {}


class _L6(BaseModel):
    v: int = 1


class _L5(BaseModel):
    l6: _L6 = _L6()


class _L4(BaseModel):
    l5: _L5 = _L5()


class _L3(BaseModel):
    l4: _L4 = _L4()


class _L2(BaseModel):
    l3: _L3 = _L3()


class _L1(BaseModel):
    l2: _L2 = _L2()


def _headings(doc: str) -> list[str]:
    return [line for line in doc.splitlines() if line.startswith("#")]


def _table_rows(doc: str, path: str) -> list[str]:
    section = doc.split(f"`{path}`\n", 1)[1].split("\n---", 1)[0]
    return [line for line in section.splitlines() if line.startswith("|")]


class TestMarkdownUnionOfModels:
    def test_each_alternative_has_its_own_section(self):
        doc = _generate(_Pets)
        assert "### `pet`: `_Cat` schema (option 1 of 2)" in doc
        assert "### `pet`: `_Dog` schema (option 2 of 2)" in doc

    def test_fields_of_every_alternative_are_documented(self):
        doc = _generate(_Pets)
        assert "#### `pet.lives`" in doc
        assert "#### `pet.bark`" in doc
        assert "`PETS_PET__BARK`" in doc

    def test_alternative_fields_come_after_their_own_heading(self):
        doc = _generate(_Pets)
        dog = doc.index("`_Dog` schema (option 2 of 2)")
        assert doc.index("#### `pet.lives`") < dog < doc.index("#### `pet.bark`")

    def test_optional_union_is_expanded(self):
        doc = _generate(_Pets)
        assert "`maybe_pet.bark`" in doc
        assert "`maybe_pet.lives`" in doc

    def test_list_and_dict_of_union_are_expanded(self):
        doc = _generate(_Pets)
        assert "`pets[*]`: `_Dog` schema (option 2 of 2)" in doc
        assert "`pets[*].bark`" in doc
        assert "`pet_map[*].bark`" in doc
        assert "`PETS_PET_MAP__<dict-key>__BARK`" in doc

    def test_single_model_keeps_plain_layout(self):
        doc = _generate(NestedModel)
        assert "option 1" not in doc
        assert "### `database.host`" in doc


class TestMarkdownInlineCode:
    def test_backtick_in_default_gets_a_longer_fence(self):
        class Ticks(BaseSettings):
            tick: str = "a`b"

        doc = _generate(Ticks)
        assert '| Default | ``"a`b"`` |' in doc

    def test_value_that_starts_with_backtick_is_padded(self):
        class Ticks(BaseSettings):
            quoted: Literal["`q`", "plain"] = "plain"

        doc = _generate(Ticks)
        assert "| Allowed values | `` `q` `` · `plain` |" in doc

    def test_pipe_and_line_break_stay_inside_the_cell(self):
        class Odd(BaseSettings):
            odd: Literal["x|y", "a\nb"] = "x|y"

        doc = _generate(Odd)
        rows = _table_rows(doc, "odd")
        assert '| Allowed values | `x\\|y` · `"a\\nb"` |' in rows
        assert all(row.endswith("|") for row in rows)

    def test_constraints_are_code(self):
        class Pattern(BaseSettings):
            pat: str = Field(default="a", pattern=r"^a*`b|c$")

        doc = _generate(Pattern)
        assert "| Constraints | ``pattern='^a*`b\\|c$'`` |" in doc


class TestMarkdownHeadingDepth:
    def test_headings_stop_at_level_six(self):
        class Deep(BaseSettings):
            deep: _L1 = _L1()

        doc = _generate(Deep)
        assert not any(h.startswith("#######") for h in _headings(doc))
        assert "###### `deep.l2.l3.l4.l5`" in doc
        assert "###### `deep.l2.l3.l4.l5.l6.v`" in doc

    def test_nested_model_gets_no_extra_schema_heading(self):
        class Deep(BaseSettings):
            deep: _L1 = _L1()

        doc = _generate(Deep)
        assert "schema" not in doc


class TestMarkdownDictKeyCase:
    def test_dict_field_gets_the_lower_case_note(self):
        doc = _generate(MultiNestedModel)
        assert (
            "| Environment variable | `MULTI_SERVER_MAP` (`MULTI_SERVER_MAP__<dict-key>` "
            "sets one entry, its key arrives in lower case) |"
        ) in _table_rows(doc, "server_map")
        assert doc.count("lower case") == 1

    def test_no_note_when_case_sensitive(self):
        class Sensitive(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="S_", env_nested_delimiter="__", case_sensitive=True
            )
            labels: Dict[str, str] = {}

        doc = _generate(Sensitive)
        assert "`S_labels`" in doc
        assert "lower case" not in doc

    def test_no_note_for_fields_outside_dicts(self):
        doc = _generate(NestedModel)
        assert "lower case" not in doc
