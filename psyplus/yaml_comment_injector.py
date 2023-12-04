from pydantic import BaseModel, fields
from pydantic_settings import BaseSettings
from typing import List, Dict, Any, get_args, Annotated, get_type_hints, Tuple
from typing_extensions import Self
import yaml
from psyplus.field_info_container import FieldInfoContainer
from dataclasses import dataclass


class YamlLineNoScalarVal:
    pass


YAML_BLOCK_SCALAR_INDICATOR = (">", "|", ">-", "|-", ">+", "|+")


@dataclass
class ListIndex:
    index: int


@dataclass
class YamlLine:
    parent_yaml_file: "YamlFile"
    line_raw: str
    leading_comment: str = None

    @property
    def previous_line(self) -> Self | None:
        self_index = self.parent_yaml_file.lines.index(self)
        if self_index > 0 and self_index + 1 < len(self.parent_yaml_file.lines):
            return self.parent_yaml_file.lines[self_index - 1]
        return None

    @property
    def next_line(self) -> Self | None:
        self_index = self.parent_yaml_file.lines.index(self)
        if self_index + 1 < len(self.parent_yaml_file.lines):
            return self.parent_yaml_file.lines[self_index + 1]
        return None

    @property
    def parent_key_line(self) -> Self | None:
        # The most previous line that is a higher in the tree hirarchy
        if self.depth == 0:
            return None
        current_line = self
        parent_found = False
        while not parent_found:
            prev = current_line.previous_line
            if prev is None:
                return None
            if prev.depth < self.depth and prev.line_key:
                return prev
            else:
                current_line = prev

    @property
    def is_list_key(self) -> bool:
        # has this line a key and is it the start key of a list
        if self.line_scalar_value in ("[]", []):
            return True
        print("###", self.line_raw, self.line_scalar_value)
        if (
            not self.line_scalar_value
            and self.next_line.depth > self.depth
            and self.next_line.line_no_indent.startswith("- ")
        ):
            print("IS LIST:", self.line_key)
            return True
        if (
            not self.line_scalar_value
            and self.next_line.depth == self.depth
            and not self.line_no_indent.startswith("- ")
            and self.next_line.line_no_indent.startswith("- ")
        ):
            print("IS LIST:", self.line_key)
            return True
        print("NOT A LIST", self.line_key, self.line_scalar_value)
        return False

    @property
    def leading_top_sibling(self) -> Self | None:
        # the first attr of parent object
        raise NotImplementedError()

    @property
    def leading_list_siblings(self) -> Self | None:
        # if self is a list item, return all other items of the list that are in front of self

        raise NotImplementedError()

    @property
    def is_list_item(self) -> bool:
        if self.list_item_leading_attr_line:
            return True
        return False

    @property
    def list_item_leading_attr_line(self) -> Self | None:
        # if part of a list item return the leading item with "-" in front
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
            if (
                previous_line.indent_depth == self.indent_depth - 1
                and previous_line.line_no_indent.startswith("- ")
            ):
                return previous_line
            elif (
                previous_line.indent_depth == self.indent_depth - 1
                and not previous_line.line_no_indent.startswith("- ")
            ):
                # we are walked up in the hirachy but there is not list item. seems we are not in a list
                return None
            else:
                previous_line = previous_line.previous_line

    @property
    def list_item_top_sibling(self) -> Self | None:

        # TODO: TEST THIS and then use it in depth

        # if part of a list return the first item of this list
        if self.is_list_item:
            leading_list_item_attr_line = self.list_item_leading_attr_line
            prev_line = leading_list_item_attr_line.previous_line
            while True:
                if leading_list_item_attr_line.indent_depth == prev_line.indent_depth and not prev_line.line_no_indent.startswith("- "):
                    # inline style list
                    return prev_line
                elif leading_list_item_attr_line.indent_depth > prev_line.indent_depth:
                    # block style list
                    return prev_line
                elif leading_list_item_attr_line.indent_depth < prev_line.indent_depth or leading_list_item_attr_line.indent_depth == prev_line.indent_depth and prev_line.line_no_indent.startswith("- "):
                    # we are still somewhere in the list. walk another line up.
                    prev_line = prev_line.previous_line
                else:
                    # there is not list
                    return None

    @property
    def path(self) -> List[str | type(List)]:
        path = []
        current_key_line = self.parent_key_line
        while current_key_line is not None:
            if current_key_line.is_list_key:
                path.insert(0, ListIndex(index=0))
            path.insert(0, current_key_line.line_key)
            current_key_line = current_key_line.parent_key_line
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
        indent_depth = self.indent_depth()
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

        if self.is_list_item:
            leading_list_item_attr_line = self.list_item_leading_attr_line
            prev_line = leading_list_item_attr_line.previous_line
            while True:
                if leading_list_item_attr_line.indent_depth >= prev_line.indent_depth and not prev_line.line_no_indent.startswith("- "):
                    
                if (
                    not prev_line.line_no_indent.startswith("- ")
                    and prev_line_depth == indent_depth
                ):
                    # we found the parent of a inline list. we need to add one point to the depth
                    return indent_depth + 1
                elif (
                    not prev_line.line_no_indent.startswith("- ")
                    and prev_line_depth < indent_depth
                ):
                    # we have parent of a block style list. the depth is correct for our logic
                    return indent_depth
                else:
                    prev_line = prev_line.previous_line

        return indent_depth
        if len(self.path) != indent_depth:
            raise ValueError(
                f"The calculated depth missmatches the counted depth. There may be a bug. path: '{self.path}', line: {self.line_raw}"
            )
        # /sanity check end
        return len(self.path)

    @property
    def has_children(self) -> bool:
        nl = self.next_line
        if nl is not None and nl.depth > self.depth:
            return True
        return False

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
            return split_line[0]
        return None

    @property
    def line_scalar_value(self) -> str | int | float | bool | None:
        # raise NotImplementedError
        split_line = self.line_content.split(":", 1)
        if (
            len(split_line) == 2
            and split_line[1]
            and not split_line[1].endswith(YAML_BLOCK_SCALAR_INDICATOR)
        ):
            return split_line[1].lstrip()
        if len(split_line) == 1:
            # return scalar value but remove possible list indicator
            return self.line_content.replace("- ", "", 1).lstrip()
        return None

    @property
    def line_comment(self) -> str | None:
        # line with NO indent and/or comments
        try:
            self.line_no_indent.split("#", 1)[1].strip()
        except IndexError:
            return None


class YamlFile:
    def __init__(self, yaml: str, indent: str = "  "):
        self.input_yaml: str = yaml
        self.indent = indent
        self.lines: List[YamlLine] = []
        self._parse_yaml()
        print("---------------")
        for line in self.lines:
            print(line, line.path)

        exit()

    def _parse_yaml(self):
        comments = ""
        for line_raw in self.input_yaml.split("\n"):
            if line_raw.strip().startswith("#"):
                # just a comment line. store it to attach it to next comming line as leading_comment
                # and continue
                comments += line_raw
                continue
            line = YamlLine(
                parent_yaml_file=self,
                line_raw=line_raw,
                leading_comment=comments if comments else None,
            )

            comments = ""
            self.lines.append(line)


class YamlCommentInjector:
    def __init__(self, yaml: str, model: BaseSettings | BaseModel):
        self.yaml: str = yaml
        self.model: BaseSettings = model

    def inject_field_headers(self) -> str:
        self._iter_model_and_inject_field_headers(
            self.yaml, current_obj=self.model, parent_path=[]
        )

    def _iter_model_and_inject_field_headers(
        self,
        yaml_content: str,
        current_obj: BaseSettings | BaseModel | Dict | List,
        parent_path: List[Dict[str, BaseSettings | BaseModel | Dict | List]],
    ):
        if hasattr(current_obj, "model_fields"):
            for key, field in current_obj.model_fields.items():
                if self._has_list_annotation(field):
                    parent_path.append({current_obj.__class__: key})
                    list_item_annotation = self._get_field_list_item_annotation(field)
                    parent_path.append({List: list_item_annotation})

                    self._iter_model_and_inject_field_headers(
                        yaml_content="",
                        current_obj=list_item_annotation,
                        parent_path=parent_path,
                    )

                    print("is a list", key, field.annotation)
                    # check if there is a object type in the list
                elif self._has_dict_annotation(field):
                    dict_items_annotation = self._get_field_dict_item_annotation(field)
                    print("is a dict", key, field.annotation)
                elif self._has_subclass_annotation(field):
                    print("is subclass", key, field.annotation)
                else:
                    print("is other", key, field.annotation)
                # print(key, field.annotation)
                # find field in yaml file.
                # walk annotations like list of objects etc
                # check if there are any meta data in sub objects
                # good luck
            exit()

    def _inject_comment(self, key: str, field: fields.FieldInfo, depth: int = 0):
        new_yaml = ""
        for line in self.yaml.split("\n"):
            line_no_indent = line.lstrip()
            line_depth = int((len(line) - len(line_no_indent)) / 2)
            if line_depth != depth or not line_no_indent.startswith(
                key, field, depth=depth
            ):
                new_yaml += line + "\n"
            elif line_no_indent.startswith(key, field, depth=depth):
                new_yaml += self.get_field_comment(
                    key,
                )
                new_yaml += line + "\n"
        self.yaml = new_yaml

    def get_field_comment(self, key: str, field: fields.FieldInfo, depth=0):
        line_indent = f"{' '*depth}"
        comment_lines = []
        comment_lines.append(f"### {key} {' - '+field.title if field.title else ''}")

        return "\n" + "\n".join([f"{line_indent}{line}" for line in comment_lines])

    def _has_list_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, list):
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
            return True
        return False

    def _get_field_list_item_annotation(self, field: fields.FieldInfo) -> Tuple[Any]:
        if field.annotation == list:
            return tuple()
        else:
            return field.annotation.__args__

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
