from pydantic import BaseModel, fields
from pydantic_settings import BaseSettings
from typing import List, Dict, Any, get_args, Annotated, get_type_hints
import yaml
from psyplus.field_info_container import FieldInfoContainer


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

    def _get_field_list_item_annotation(self, field: fields.FieldInfo) -> Any:
        print("field.annotation", field.annotation.__args__)
        if field.annotation == list:
            return Any
        for k, v in field.annotation.items():
            print(k, v)
        exit()
        print("annotation", field)
        type_h = get_type_hints(field)
        print("get_type_hints", type_h)
        exit()

    def _has_dict_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, dict):
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is dict:
            return True
        return False

    def _has_subclass_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(
            annotation, (BaseSettings, BaseModel)
        ):
            return True
        return False
