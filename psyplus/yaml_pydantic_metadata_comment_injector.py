from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import List, get_args, Generator, Dict, get_origin
from typing_extensions import Self
import yaml

from psyplus.utils import nested_pydantic_to_dict, get_str_dict_as_table
from psyplus.field_info_container import (
    FieldInfoContainer,
    ModelPathMember,
    ModelPathFragment,
)

from dataclasses import dataclass
from pydantic_core import PydanticUndefined
import json

# https://yaml-multiline.info/
YAML_BLOCK_SCALAR_INDICATOR = (">", "|", ">-", "|-", ">+", "|+")


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

    @property
    def parent_key_line(self) -> Self | None:
        # The first previous line that is a higher in the tree hirarchy

        if self.depth == 0 and not self.is_list_item:
            return None
        if self.is_list_item:
            parent_line = self.list_item_first_sibling_line.previous_line
            if parent_line.is_list_item:
                # we have a list items. the need to walk the list up and find the key element.
                # maybe its even a nested list, so keep climping up if the first match is a list as well
                while True:
                    if (
                        parent_line.is_list_item
                        and parent_line.depth < self.list_item_first_sibling_line.depth
                    ):
                        return parent_line
                    elif not parent_line.is_list_item:
                        return parent_line
                    parent_line = parent_line.previous_line
            else:
                return self.list_item_first_sibling_line.previous_line

        current_line = self
        while True:
            prev = current_line.previous_line
            if prev is None:
                return None
            if prev.depth < self.depth and prev.line_key:
                return prev
            else:
                current_line = prev

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

            if (
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
                    return None
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
    def path(self) -> List[str | ListIndex]:
        """Return the path in the yaml structure. similar to a json path

        Returns:
            _type_: _description_
        """
        path = []
        print("-----------", self.line_raw)
        print("-------next", self.previous_line)

        iter_line = self
        while iter_line is not None:
            # ##############################################
            #  you are here. path return bs for nested dicts (current testcase)
            ################################################
            print("###----")
            print("iter_line", iter_line.line_raw)
            if iter_line.line_key:
                line_key = iter_line.line_key
                if iter_line.line_key.startswith("- "):
                    line_key = iter_line.line_key.replace("- ", " ", 1)
                path.insert(0, line_key.strip())
            if iter_line.is_list_item:
                path.insert(0, ListIndex(index=iter_line.list_index))
            if iter_line.parent_key_line:
                print("iter_line.parent_key_line", iter_line.parent_key_line.line_raw)
            iter_line = iter_line.parent_key_line
        print(path)
        return path

    @property
    def indent_depth(self):
        # depth by indent. can be a little bit inconsistent for listsitems, as they are allowed to be on the same depth as the parent key.
        # see https://stackoverflow.com/questions/17014460/yaml-indentation-for-array-in-hash
        # for a more consistent depth value, that is based on the hierachry and not the indent use `YamlLine.depth`
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
        import inspect

        for line in self.source_yaml.lines:
            field_root_model_path = self._get_model_hierarchy_by_yaml_path(line.path)
            if (
                field_root_model_path
                and field_root_model_path[-1].field_info is not None
            ):
                field_info_wrapper = FieldInfoContainer(
                    field_name=line.line_key,
                    # field_info=field_root_model_path[-1],
                    container_model_hierachy=field_root_model_path,
                )
                line.leading_comment = "\n".join(
                    self._indent_multilines(
                        text=self._generate_comment(
                            yaml_line=line,
                            path=line.path,
                            key=line.line_key,
                            field=field_info_wrapper,
                        ),
                        indent_depth=line.indent_depth,
                    )
                )

    def _generate_output_yaml(self):
        output = ""
        for line in self.source_yaml.lines:
            if line.leading_comment:
                output += "\n" + line.leading_comment + "\n"
            output += line.line_raw + "\n"
            if line.multiline_value:
                for mlv in line.multiline_value[1:]:
                    output += (
                        f"{line.indent_depth * line.parent_yaml_file.indent}  {mlv}\n"
                    )
        return output

    def _get_model_hierarchy_by_yaml_path(
        self,
        yaml_path: List[str | ListIndex],
    ) -> List[ModelPathFragment]:
        container_model_hierachy: List[ModelPathFragment] = []
        model_chapter = self.model
        for path_fragment in yaml_path:
            if len(container_model_hierachy) == 0:
                container_model_hierachy.append(
                    ModelPathFragment(
                        model_instance=self.model,
                        key=path_fragment,
                    )
                )
            else:
                previous_model = container_model_hierachy[-1]
                next_annotation_fragment = previous_model.get_next_annotation_fragment()
                if next_annotation_fragment is None and isinstance(
                    previous_model.model_instance,
                    (BaseModel, BaseSettings),
                ):
                    container_model_hierachy.append(
                        ModelPathFragment(
                            model_instance=getattr(
                                previous_model.model_instance,
                                previous_model.key,
                            ),
                            key=path_fragment,
                        )
                    )
                elif get_origin(next_annotation_fragment) == dict:
                    container_model_hierachy.append(
                        ModelPathFragment(
                            model_instance=previous_model.model_instance,
                            key=DictKey(key=path_fragment),
                            annotation_fragment=next_annotation_fragment,
                        )
                    )
                elif get_origin(next_annotation_fragment) == list and isinstance(
                    path_fragment, ListIndex
                ):
                    container_model_hierachy.append(
                        ModelPathFragment(
                            model_instance=previous_model.model_instance,
                            key=path_fragment,
                            annotation_fragment=next_annotation_fragment,
                        )
                    )
                elif get_origin(next_annotation_fragment) == list and isinstance(
                    path_fragment, ListIndex
                ):
                    # debug if branch
                    print("previous_model", previous_model)
                    print("next_annotation_fragment", next_annotation_fragment)
                    print("path_fragment", path_fragment)
                    raise ValueError("Something is wrong")
        print("container_model_hierachy", container_model_hierachy)
        return container_model_hierachy
        print("-+-+-+-+-+", yaml_path)
        container_model_hierachy: List[ModelPathMember] = []
        model_chapter = self.model
        for path_fragment in yaml_path:
            if isinstance(model_chapter, (BaseModel, BaseSettings)):
                if path_fragment in model_chapter.model_fields:
                    model_path_member = ModelPathMember(
                        model_instance=model_chapter,
                        key=path_fragment,
                    )
                    model_chapter = getattr(model_chapter, path_fragment)
                    container_model_hierachy.append(model_path_member)
                    continue
            elif isinstance(path_fragment, ListIndex):
                model_path_member = ModelPathMember(
                    model_instance=List,
                    key=path_fragment,
                )
                container_model_hierachy.append(model_path_member)

                model_chapter = model_chapter[path_fragment.index]
                continue
            elif type(model_chapter) == dict:
                container_model_hierachy.append(model_path_member)
                try:
                    content = model_chapter[path_fragment]
                    key = path_fragment

                except:
                    raise
                    # maybe it an int key
                    content = model_chapter[int(path_fragment)]
                    key = int(path_fragment)
                # print("content", content)
                model_path_member = ModelPathMember(
                    model_instance=model_chapter,
                    key=key,
                )

                model_chapter = model_chapter[key]
        print("-+", container_model_hierachy)
        return container_model_hierachy

    def _generate_comment(
        self,
        yaml_line: YamlLine,
        path: List[ListIndex | str],
        key: str,
        field: FieldInfoContainer,
        comment_prefixer="#",
    ) -> str:
        """Generates the key and texts for the header of a config variable.

        Args:
            yaml_line (YamlLine): An instance of YamlLine that contains the raw yaml line that will be commented and some metadata
            path (List[ListIndex  |  str]): The yaml path of the commented field will
            key (str): The yaml key of the commented field
            field (FieldInfoContainer): All metadata of the pydantic-settings config field
            comment_prefixer (str, optional): A prefix that is attached to every line. Defaults to "#".

        Returns:
            str:
        """
        comment: List[str] = []
        data_header = {}
        # Title

        header_line = f"## {key}"

        if field.field_info.title:
            header_line += f" - {field.field_info.title}"
        header_line += f" ###"
        comment.append(header_line)
        # Data fields
        key_path = ".".join(str(p) for p in path)
        if key != key_path:
            data_header[" YAML-path: "] = f"{key_path}"

        if field.field_value_type_name:
            data_header[" Type: "] = f"{field.field_value_type_name}"
        data_header[" Required: "] = f"{field.field_info.is_required()}"
        if (
            hasattr(field.field_info, "default")
            and field.field_info.default != PydanticUndefined
        ):
            if field.field_info.default is not None:
                def_val = (
                    f"'{json.dumps(nested_pydantic_to_dict(field.field_info.default))}'"
                )
            else:
                def_val = "null/None"
            data_header[" Default: "] = def_val
        if field.field_value_enum:
            data_header[" Allowed vals: "] = f"{field.field_value_enum}"

        if field.field_info.metadata:
            data_header[" Constraints: "] = f"{field.field_info.metadata}"

        data_header[" Env-var: "] = f"'{field.env_var_name}'"
        if field.field_info.description:
            data_header[" Description: "] = f"{field.field_info.description}"

        comment.extend(get_str_dict_as_table(data_header).rstrip().split("\n"))

        if field.field_info.examples:
            comment.extend(self._generate_examples_comment_text(key, field, yaml_line))
        comment = [comment_prefixer + l for l in comment]

        return comment

    def _generate_examples_comment_text(
        self, key: str, field: FieldInfoContainer, yaml_line: YamlLine
    ) -> List[str] | None:
        if not field.field_info.examples:
            return None
        text_lines = []
        for index, example in enumerate(field.field_info.examples):
            text_lines.append(
                f" Example No. {index+1}:"
                if len(field.field_info.examples) > 1
                else " Example:"
            )

            example_as_yaml = yaml.dump(nested_pydantic_to_dict({key: example}))
            text_lines.extend(
                self._indent_multilines(
                    text=example_as_yaml.split("\n"),
                    indent_depth=0,
                    line_prefix=" >",
                    extra_indent_depth_after_prefix=yaml_line.indent_depth,
                    add_extra_indent_for_subsequent_lines_after_line_prefix=False,
                )
            )

        return text_lines[:-1]

    def _indent_multilines(
        self,
        text: List[str],
        indent_depth: int = 0,
        line_prefix: str = "",
        line_suffix: str = "",
        extra_indent_depth_after_prefix: int = 0,
        add_extra_indent_for_subsequent_lines_after_line_prefix: bool = False,
    ) -> Generator[str, None, None]:
        indent = f"{indent_depth*self.source_yaml.indent}"
        inner_indent = f"{extra_indent_depth_after_prefix*self.source_yaml.indent}"
        for index, line in enumerate(text):
            line_prefix_real = f"{line_prefix}{inner_indent}"
            if index != 0 and add_extra_indent_for_subsequent_lines_after_line_prefix:
                line_prefix_real = f"{line_prefix_real}{self.source_yaml.indent}"
            yield f"{indent}{line_prefix_real}{line}{line_suffix}"
