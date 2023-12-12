from pydantic import BaseModel, fields
from pydantic_settings import BaseSettings
from typing import get_args, get_origin, _GenericAlias, Union
from typing import (
    List,
    Dict,
    Any,
    get_args,
    Annotated,
    get_type_hints,
    Tuple,
    Generator,
    Type,
)
from typing_extensions import Self
import yaml
from psyplus.field_info_container import FieldInfoContainer
from dataclasses import dataclass
from pydantic_core import PydanticUndefined


class YamlNullVal:
    pass


# https://yaml-multiline.info/
YAML_BLOCK_SCALAR_INDICATOR = (">", "|", ">-", "|-", ">+", "|+")


@dataclass
class ListIndex:
    index: int

    def __str__(self):
        return f"_{self.index}_"


@dataclass
class YamlLine:
    parent_yaml_file: "YamlFile"
    line_raw: str
    leading_comment: str = None
    # https://yaml-multiline.info/
    multiline_value: List[str] = None

    @property
    def previous_line(self) -> Self | None:
        self_index = self.parent_yaml_file.lines.index(self)
        if self_index > 0 and self_index + 1 <= len(self.parent_yaml_file.lines):
            return self.parent_yaml_file.lines[self_index - 1]
        return None

    """dead code?
    @property
    def next_line(self) -> Self | None:
        self_index = self.parent_yaml_file.lines.index(self)
        if self_index + 1 < len(self.parent_yaml_file.lines):
            return self.parent_yaml_file.lines[self_index + 1]
        return None
    """

    @property
    def parent_key_line(self) -> Self | None:
        # The first previous line that is a higher in the tree hirarchy
        if self.depth == 0 and not self.line_no_indent.startswith("- "):
            return None
        current_line = self
        parent_found = False
        while not parent_found:
            if current_line.is_list_item:
                return current_line.list_item_first_sibling_line.previous_line
            prev = current_line.previous_line
            if prev is None:
                return None
            if prev.depth < self.depth and prev.line_key:
                return prev
            else:
                current_line = prev

    """dead code?
    @property
    def is_list_key(self) -> bool:
        # has this line a key and is the value to this key a list
        if self.line_scalar_value in ("[]", []):
            return True
        if not self.line_scalar_value and self.next_line.is_list_item:
            print("IS LIST:", self.line_raw, self.line_key)
            return True
        print("NOT A LIST", self.line_key, self.line_scalar_value)
        return False
    """

    @property
    def is_list_item(self) -> bool:
        if self.list_item_leading_attr_line is not None:
            return True
        return False

    @property
    def is_list_inline_style(self) -> bool:
        top_list_item_line = self.list_item_first_sibling_line
        if (
            top_list_item_line.previous_line
            and top_list_item_line.indent_depth
            == top_list_item_line.previous_line.indent_depth
        ):
            return True
        return False

    @property
    def list_index(self) -> int:
        return len(list(self.walk_back_list_item_lines())) - 1

    @property
    def list_item_leading_attr_line(self) -> Self | None:
        # if this lines key/value is part of a list item/object return the leading item with "-" in front
        # eg:
        # - attr1: value1
        #   attr2: value2 # <-this line is self
        # self.list_item_leading_attr() will return a YamlLine object for line "- attr1: value1"
        # return None if not a list item

        if self.line_no_indent.startswith("- "):
            # hey, we are the leading list item. that was easy
            return self
        previous_line = self.previous_line

        while True:
            if previous_line is None:
                return None
            elif (
                previous_line.indent_depth == self.indent_depth - 1
                and previous_line.line_no_indent.startswith("- ")
            ):
                return previous_line
            elif (
                previous_line.indent_depth == self.indent_depth - 1
                and not previous_line.line_no_indent.startswith("- ")
            ):
                # we are walked up in the hirachy but there is no list item. seems we are not in a list
                return None
            else:
                previous_line = previous_line.previous_line

    def walk_back_list_item_lines(self) -> Generator[Self, None, None]:
        # iter list to the begining. starting from the from the 'self'-item
        # TODO: TEST THIS and then use it in depth

        # if part of a list return the first item of this list
        if self.is_list_item:
            source_leading_list_item_attr_line = self.list_item_leading_attr_line

            leading_list_item_attr_line = source_leading_list_item_attr_line

            while True:
                if (
                    leading_list_item_attr_line is None
                    or leading_list_item_attr_line.indent_depth
                    != source_leading_list_item_attr_line.indent_depth
                ):
                    # we left the origin list or there is no more list item

                    return None
                if leading_list_item_attr_line is None:
                    return
                yield leading_list_item_attr_line
                # catch previous list item if exists
                prev_line = leading_list_item_attr_line.previous_line
                if prev_line:
                    leading_list_item_attr_line = (
                        leading_list_item_attr_line.previous_line.list_item_leading_attr_line
                    )
                else:
                    return None

    @property
    def list_item_first_sibling_line(self) -> Self | None:
        # TODO: TEST THIS and then use it in depth

        # if part of a list return the first item of this list
        list_item_lines = list(self.walk_back_list_item_lines())
        if list_item_lines:
            return list_item_lines[-1]

    @property
    def path(self) -> List[str | type(List)]:
        path = []

        iter_line = self
        while iter_line is not None:
            if iter_line.line_key:
                line_key = iter_line.line_key
                if iter_line.line_key.startswith("- "):
                    line_key = iter_line.line_key.replace("- ", " ", 1)
                path.insert(0, line_key.strip())
            if iter_line.is_list_item:
                path.insert(0, ListIndex(index=iter_line.list_index))
            iter_line = iter_line.parent_key_line
        return path

    @property
    def indent_depth(self):
        # a more simple depth metric. it does not alway represent the correct hirachical depth of an item.
        return int(
            (len(self.line_raw) - len(self.line_no_indent))
            / len(self.parent_yaml_file.indent)
        )

    @property
    def depth(self) -> int:
        indent_depth = self.indent_depth

        # list item with same depth as parent key exception
        # this cases are both possible:
        # inline_list:
        # - 1
        # - 2
        # block_list2:
        #   - 1
        #   - 2
        # with our simple solution above these would become different depth which would be wrong
        #
        # todo: this is way too hacky. find a better solution

        if self.is_list_item and self.is_list_inline_style:
            indent_depth + 1
        return indent_depth

    """dead code?
    @property
    def has_children(self) -> bool:
        nl = self.next_line
        if nl is not None and nl.depth > self.depth:
            return True
        return False
    """

    @property
    def line_no_indent(self) -> str:
        # line with NO indent
        return self.line_raw.strip()

    @property
    def line_content(self) -> str:
        # line with NO indent and/or comments
        return self.line_no_indent.split("#", 1)[0].strip()

    @property
    def line_key(self) -> str | None:
        split_line = self.line_content.split(":", 1)
        if len(split_line) == 2:
            return split_line[0].replace("- ", "", 1).strip()
        return None

    @property
    def line_value(self) -> str | None:
        # raise NotImplementedError
        split_line = self.line_content.split(":", 1)
        if len(split_line) == 2 and split_line[1]:
            return split_line[1].strip()
        if len(split_line) == 1:
            # return scalar value but remove possible list indicator
            return self.line_content.replace("- ", "", 1).strip()
        return None

    @property
    def line_comment(self) -> str | None:
        # line with NO indent and/or comments
        try:
            self.line_no_indent.split("#", 1)[1].strip()
        except IndexError:
            return None

    @property
    def initiates_multiline_value(self) -> bool:
        if not self.line_value:
            return False
        if self.is_multiline_block_scalar:
            return True
        if self.line_value.startswith(
            ("'", '"', "“", "”")
        ) and not self.line_value.endswith(("'", '"', "“", "”")):
            return True
        return False

    @property
    def is_multiline_block_scalar(self) -> bool:
        if len(self.line_value) < 3 and self.line_value.endswith(
            YAML_BLOCK_SCALAR_INDICATOR
        ):
            return True
        return False

    @property
    def multiline_flow_scalar_first_line(self) -> str | None:
        # if line is a multiline flow scalar value (https://yaml-multiline.info/)
        # return the first line after the key.
        # e.g.
        #   example: 'Several lines of text,\n
        #   ··containing ''single quotes''. Escapes (like \n) don''t do anything.\n'
        # in this case this func will return `'Several lines of text,\n`
        # will return None if line is not a multiline flow scalar
        if self.initiates_multiline_value:
            return


class YamlFile:
    def __init__(self, yaml: str, indent: str = "  "):
        self.input_yaml: str = yaml
        self.indent = indent
        self.lines: List[YamlLine] = []
        self._parse_yaml()

    def _parse_yaml(self):
        comments_and_emptylines = ""
        multiline_value_parent_line: YamlLine = None
        multiline_value: List[str] = []
        for line_raw in self.input_yaml.split("\n"):
            line = YamlLine(
                parent_yaml_file=self,
                line_raw=line_raw,
                leading_comment=comments_and_emptylines
                if comments_and_emptylines
                else None,
            )
            if (
                multiline_value_parent_line is not None
                and line.indent_depth > multiline_value_parent_line.indent_depth
            ):
                multiline_value.append(line_raw)
                continue
            elif (
                multiline_value_parent_line is not None
                and line.indent_depth <= multiline_value_parent_line.indent_depth
            ):
                multiline_value_parent_line.multiline_value = multiline_value
                multiline_value_parent_line = None
                multiline_value = []

            if line_raw.strip().startswith("#") or line_raw.strip() == "":
                # just a comment line. store it to attach it to next comming line as leading_comment
                # and continue
                comments_and_emptylines += line_raw
                continue

            if line.initiates_multiline_value and multiline_value_parent_line is None:
                if not line.is_multiline_block_scalar:
                    # this is flow scalar and will have data in the first line unlike a block scalar (https://yaml-multiline.info/)
                    multiline_value.append(line.line_value)
                multiline_value_parent_line = line

            comments_and_emptylines = ""
            self.lines.append(line)


class YamlPydanticMetadataCommentInjector:
    def __init__(self, yaml: str, model: BaseSettings | BaseModel):
        self.source_yaml: YamlFile = YamlFile(yaml)
        self.model: BaseSettings = model
        self._inject_field_headers()
        self.output_yaml: str = self._generate_output_yaml()

    def _inject_field_headers(self) -> str:
        for line in self.source_yaml.lines:
            parent_model_path, field_info = self._get_model_field_by_yaml_path(
                line.path
            )

            if field_info is not None:
                field_info_wrapper = FieldInfoContainer(
                    field_name=line.line_key,
                    field_info=field_info,
                    container_model_hierachy=parent_model_path,
                )
                line.leading_comment = self._indent_text(
                    self._generate_comment(
                        yaml_line=line.line_raw,
                        path=line.path,
                        key=line.line_key,
                        field=field_info_wrapper,
                    ),
                    indent_depth=line.indent_depth,
                )

    def _generate_output_yaml(self):
        output = ""
        for line in self.source_yaml.lines:
            if line.leading_comment:
                output += line.leading_comment
            output += line.line_raw
        return output

    def _get_model_field_by_yaml_path(
        self,
        yaml_path: List[str | ListIndex],
    ) -> Tuple[List[Dict[Type[BaseSettings], str]] | None, fields.FieldInfo | None]:
        container_model_hierachy: List[Dict[Type[BaseSettings], str]] = []
        model_chapter = self.model
        for index, path_fragment in enumerate(yaml_path):
            if isinstance(path_fragment, ListIndex):
                list_annotation = self._get_field_list_item_annotation(model_chapter)

                if len(list_annotation) == 1 and issubclass(
                    list_annotation[0], (BaseModel, BaseSettings)
                ):
                    # we have a nested setting class in a list
                    container_model_hierachy.append({list_annotation[0]: path_fragment})
                    model_chapter = list_annotation[0]
                else:
                    # we have just a list with no meta info or some other construct we can not or dont want to deconstruct any furthr
                    return None, None
            elif (
                issubclass(model_chapter.__class__, (BaseModel, BaseSettings))
                and path_fragment in model_chapter.model_fields
            ):
                container_model_hierachy.append(
                    {model_chapter.__class__: path_fragment}
                )

                model_chapter = model_chapter.model_fields[path_fragment]
            elif isinstance(model_chapter, fields.FieldInfo):
                container_model_hierachy.append(
                    {model_chapter.annotation: path_fragment}
                )
                return container_model_hierachy, model_chapter
        return container_model_hierachy, model_chapter

    def explode_field_annotation(self, annotation) -> List[Any]:
        annotation_path = []
        if get_origin(annotation) is Union:
            # warning. no union supported
            raise NotImplementedError(
                "Union annotation is not supported. please remove it from your config model if you want to use pydantic-settings-yaml-plus"
            )
        elif annotation.__class__ == _GenericAlias:
            annotation_path.append(annotation.__origin__)
        else:
            annotation_path.append(annotation)
        for arg in get_args(annotation):
            annotation_path.extend(self.explode_field_annotation(arg))

        return annotation_path

    def _generate_comment(
        self,
        yaml_line: str,
        path: List[ListIndex | str],
        key: str,
        field: FieldInfoContainer,
    ):
        print("----")
        print("key", key)
        print("path", path)
        print("object_path", field.container_model_hierachy)
        print("field.field_info", field.field_info)
        comment = ""
        comment += f"### {'.'.join(str(p) for p in path)}"
        if hasattr(field.field_info, "title"):
            comment += f"{field.field_info.title}  ###"
        if (
            hasattr(field.field_info, "default")
            and field.field_info.default != PydanticUndefined
        ):
            comment += f"# Defaults to '{field.field_info.default if not None else 'null/None'}'"
        if field.field_value_enum:
            comment += f"# Allowed values: {field.field_value_enum}"
        """
        if field.field_info.metadata:
            comment += f"# Constraints: {field.field_info.metadata}"
        """
        comment += f"# Env var name: '{field.env_var_name}'"
        if field.field_info.description:
            comment += f"# Description: {field.field_info.description}"
        if field.field_info.examples:
            comment += self._generate_examples_comment_text(field)
        return comment

    def _generate_examples_comment_text(self, field: FieldInfoContainer):
        if not field.field_info.examples:
            return None
        text_lines = []
        for index, example in enumerate(field.field_info.examples):
            text_lines.append(f"# Example No. {index}:")
            # todo: this is uncompleted
            text_lines.append(f"# > {example}")
        return "\n".join(text_lines)

    def _indent_text(self, text: str, indent_depth: int = 0):
        lines = text.split("\n")
        indented_lines = []
        indent_space = self.source_yaml.indent * indent_depth
        for line in lines:
            indented_lines.append(f"{indent_space}{line}")
        return "\n".join(indented_lines)

    def _get_field_list_item_annotation(self, field: fields.FieldInfo) -> Tuple[Any]:
        if field.annotation == list:
            return tuple()
        elif hasattr(field.annotation, "__args__"):
            return field.annotation.__args__
        return tuple()

    """dead code
    def _has_list_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, list):
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
            return True
        return False
    
    def _has_dict_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, dict):
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is dict:
            return True
        return False
    
    def _get_field_dict_item_annotation(self, field: fields.FieldInfo) -> Tuple[Any]:
        if field.annotation == dict:
            return tuple()
        else:
            return field.annotation.__args__
    
    def _has_subclass_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(
            annotation, (BaseSettings, BaseModel)
        ):
            return True
        return False

    def _has_scalar_value(self, field: fields.FieldInfo):
        scalar_types = (bool, str, int, float, complex)
        annotation = field.annotation
        if isinstance(annotation, scalar_types) and issubclass(
            annotation, scalar_types
        ):
            return True
        elif (
            hasattr(annotation, "__origin__") and annotation.__origin__ is scalar_types
        ):
            return True
        return False
    """
