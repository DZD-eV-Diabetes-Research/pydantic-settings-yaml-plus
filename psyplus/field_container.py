from pydantic import fields, BaseModel
from pydantic_settings import BaseSettings
from typing import List, Any
from typing_extensions import Self
import yaml

from dataclasses import dataclass
from pydantic_core import PydanticUndefined
import json


from psyplus.utils import (
    nested_pydantic_to_dict,
    get_str_dict_as_table,
    python_annotation_to_generic_readable,
    has_literal,
    get_literal_list,
    indent_multilines,
)

ENV_VAR_LISTINDEX_PLACEHOLDER: str = "<list-index>"
ENV_VAR_DICTKEY_PLACEHOLDER: str = "<dict-key>"


@dataclass
class ListIndex:
    index: int

    def __str__(self):
        return f"[{self.index}]"


@dataclass
class DictKey:
    key: int

    def __str__(self):
        return f"['{self.key}']"


@dataclass
class FieldInfoContainer:
    """A wrapper class to store and simplify access to certain (meta-)informations in/of a `pydantic.fields.FieldInfo` instance.
    Intended for internal use only"""

    path: List[str | ListIndex | DictKey]
    field_name: str
    field_info: fields.FieldInfo | None = None
    annotation: Any = None

    def get_annotation(self) -> Any:
        if self.field_info:
            return self.field_info.annotation
        return self.annotation

    def get_env_var_scheme(
        self, env_var_delimiter: str = "__", prefix: str = ""
    ) -> str:
        result = []
        for key in self.path:
            if isinstance(key, str):
                result.append(key.upper())
            elif isinstance(key, ListIndex):
                result.append(ENV_VAR_LISTINDEX_PLACEHOLDER)
            elif isinstance(key, DictKey):
                result.append(ENV_VAR_DICTKEY_PLACEHOLDER)
            else:
                # unsupported type; we can not generate a env var
                return None
        return prefix + env_var_delimiter.join(result)

    def get_path_str(self) -> str:
        return ".".join(str(p) for p in self.path)

    def get_type_annotation_string(self):
        return python_annotation_to_generic_readable(self.get_annotation())

    def get_enum_vals(
        self,
    ) -> List[Any] | None:
        """If the value has a fixed list of allowed values, this return the list of these values

        Returns:
            List[Any]: List of allowed values for the field
        """
        annot = self.get_annotation()
        if has_literal(annot):
            return get_literal_list(annot)
        return None

    def get_entry_comment_header(self):
        """Generates a more simple header comment of keys that do not have its in pydantic.fields.FieldInfo instance"""
        comment: List[str] = []
        data_header = {}
        # Title
        key = self.field_name
        path = self.get_path_str()
        header_line = f"## {key}"
        data_header["YAML-path: "] = f"{path}"
        data_header["Env-var: "] = f"'{self.get_env_var_scheme()}'"
        comment.append(header_line)
        comment.extend(get_str_dict_as_table(data_header).rstrip().split("\n"))
        return comment

    def get_field_comment_header(self):
        comment: List[str] = []
        data_header = {}
        # Title
        key = self.field_name
        path = self.get_path_str()
        header_line = f"## {key}"
        field_info: fields.FieldInfo = (
            self.field_info if self.field_info else fields.FieldInfo()
        )

        if field_info.title:
            header_line += f" - {field_info.title}"
        header_line += f" ###"
        comment.append(header_line)
        # Data fields
        if key != path:
            data_header["YAML-path: "] = f"{path}"

        if self.get_type_annotation_string():
            data_header["Type: "] = f"{self.get_type_annotation_string()}"
        data_header["Required: "] = f"{field_info.is_required()}"
        if hasattr(field_info, "default") and field_info.default != PydanticUndefined:
            if field_info.default is not None:
                def_val = f"'{json.dumps(nested_pydantic_to_dict(field_info.default))}'"
            else:
                def_val = "null/None"
            data_header["Default: "] = def_val
        if self.get_enum_vals():
            data_header["Allowed vals: "] = f"{self.get_enum_vals()}"

        if field_info.metadata:
            data_header["Constraints: "] = f"{field_info.metadata}"

        data_header["Env-var: "] = f"'{self.get_env_var_scheme()}'"
        if field_info.description:
            data_header["Description: "] = f"{field_info.description}"

        comment.extend(get_str_dict_as_table(data_header).rstrip().split("\n"))

        if field_info.examples:
            comment.extend(self._generate_examples_comment_text(key))

        return comment

    def _generate_examples_comment_text(
        self, key: str, indent_depth: int = 0
    ) -> List[str] | None:
        if not self.field_info.examples:
            return None
        text_lines = []
        for index, example in enumerate(self.field_info.examples):
            text_lines.append(
                f"Example No. {index+1}:"
                if len(self.field_info.examples) > 1
                else "Example:"
            )

            example_as_yaml = yaml.dump(nested_pydantic_to_dict({key: example}))
            text_lines.extend(
                indent_multilines(
                    text=example_as_yaml.split("\n"),
                    indent_depth=0,
                    line_prefix=">",
                    extra_indent_depth_after_prefix=indent_depth,
                    add_extra_indent_for_subsequent_lines_after_line_prefix=False,
                )
            )
        return text_lines[:-1]
