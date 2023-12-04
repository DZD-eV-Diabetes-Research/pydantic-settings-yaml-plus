from pydantic import BaseModel, fields
from pydantic_settings import BaseSettings
from typing import (
    List,
    Dict,
    Any,
    get_args,
    Annotated,
    get_type_hints,
    Tuple,
    Generator,
)
from typing_extensions import Self
import yaml
from psyplus.field_info_container import FieldInfoContainer
from dataclasses import dataclass


class YamlNullVal:
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
        if self_index > 0 and self_index + 1 <= len(self.parent_yaml_file.lines):
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

    """UNUSED. REMOVE LATER
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
    def leading_list_siblings(self) -> Self | None:
        # if self is a list item, return all other items of the list that are in front of self

        raise NotImplementedError()

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
    def object_leading_top_sibling(self) -> Self | None:
        # the first attr of parent object
        raise NotImplementedError()

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
    def line_scalar_value(self) -> str | None:
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

    def _parse_yaml(self):
        comments_and_emptylines = ""
        for line_raw in self.input_yaml.split("\n"):
            if line_raw.strip().startswith("#") or line_raw.strip() == "":
                # just a comment line. store it to attach it to next comming line as leading_comment
                # and continue
                comments_and_emptylines += line_raw
                continue
            line = YamlLine(
                parent_yaml_file=self,
                line_raw=line_raw,
                leading_comment=comments_and_emptylines
                if comments_and_emptylines
                else None,
            )

            comments_and_emptylines = ""
            self.lines.append(line)


class YamlCommentInjector:
    def __init__(self, yaml: str, model: BaseSettings | BaseModel):
        self.yaml: YamlFile = YamlFile(yaml)
        self.model: BaseSettings = model

    def inject_field_headers(self) -> str:
        print("model", self.model)
        for line in self.yaml.lines:
            model_chapter = self.model
            for path_fragment in line.path:
                if (
                    not isinstance(path_fragment, ListIndex)
                    and path_fragment in model_chapter.model_fields
                ):
                    print(model_chapter.model_fields[path_fragment])
                else:
                    print("Catch list", path_fragment)
                ### TODO you are here. match yaml line path to model path and extract metadat from model for comments generation
        exit()

    def _iter_model_and_inject_field_headers(
        self,
        yaml_content: str,
        current_obj: BaseSettings | BaseModel | Dict | List,
        parent_path: List[Dict[str, BaseSettings | BaseModel | Dict | List]],
    ):
        # propably obsolete func. remove later
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
