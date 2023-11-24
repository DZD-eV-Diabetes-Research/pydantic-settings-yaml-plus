from pydantic import BaseModel, fields
from pydantic_settings import BaseSettings
from typing import List, Dict, Any, get_args, Annotated


class YamlCommentInjector:
    def __init__(self, yaml: str, model: BaseSettings | BaseModel):
        self.yaml: str = yaml
        self.model: BaseSettings = model

    def inject_field_headers(self) -> str:
        self._inject_field_headers(yaml_content=self.yaml, parent_path=[])

    def _inject_field_headers(
        self,
        yaml_content: str,
        parent_path: Dict[str, BaseSettings | BaseModel | Dict | List],
    ):
        for key, field in self.model.model_fields.items():
            if self._has_list_annotation(field):
                print("is a list", key, field.annotation)
                # check if there is a object type in the list
            elif self._has_dict_annotation(field):
                print("is a dict", key, field.annotation)
            else:
                print("is other", key, field.annotation)
            # print(key, field.annotation)
            # find field in yaml file.
            # walk annotations like list of objects etc
            # check if there are any meta data in sub objects
            # good luck
        exit()

    def _has_list_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, list):
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is Annotated:
            # i am pretty sure this code is not needed. if so i will get a error. if i never raise this error during all my tests this branch can be deleted
            raise NotImplemented("HA, YOU NEED THIS BRANCH")
            args = get_args(annotation)
            for arg in args:
                if self._has_list_annotation(arg):
                    return True
        return False

    def _has_dict_annotation(self, field: fields.FieldInfo):
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, dict):
            return True
        elif hasattr(annotation, "__origin__") and annotation.__origin__ is dict:
            return True
        return False
