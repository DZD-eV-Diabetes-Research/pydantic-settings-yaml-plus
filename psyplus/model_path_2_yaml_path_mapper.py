from dataclasses import dataclass
from pydantic import fields, BaseModel
from pydantic_settings import BaseSettings
from typing import (
    List,
    Any,
    Dict,
    Type,
    Literal,
    get_origin,
    get_args,
    Optional,
    get_type_hints,
)


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
class ModelPathMap:
    fragments: List["ModelPathFragment"]
    root_settings: BaseSettings
    yaml_path: List[str | ListIndex]

    def append(self, fragment: "ModelPathFragment"):
        fragment.source_path = self
        self.fragments.append(fragment)

    @property
    def enditem(self):
        return self.fragments[-1]

    @property
    def rootitem(self):
        return self.fragments[0]

    def __len__(self):
        return len(self.fragments)


@dataclass
class ModelPathFragment:
    yaml_path_key: str
    yaml_path_index: int
    content: BaseModel | BaseSettings | Dict | List
    annotation_fragment: Any = None
    source_path: ModelPathMap = None

    @property
    def parent_path_fragment(self) -> "ModelPathFragment":
        selfindex = self.source_path.fragments.index(self)
        if selfindex > 0:
            self.source_path.fragments[selfindex - 1]
        else:
            return None

    @property
    def parent_content(self) -> BaseModel | BaseSettings | Dict | List:
        if self.parent_path_fragment:
            return self.parent_path_fragment.content
        # we are the root path fragment. lets return the root settings content
        return self.source_path.root_settings

    @property
    def field_info(self) -> fields.FieldInfo | None:
        if self.key_raw in self.parent_content.model_fields:
            return self.parent_content.model_fields[self.key_raw]
        return None

    @property
    def source_field_info(self) -> fields.FieldInfo | None:
        """If fragment does not have a direct pydantic-settings field, but is part of it as nested annotation lets return the field where this annotation comes from."""
        current_path_fragment = self
        while True:
            if current_path_fragment.field_info:
                return current_path_fragment.field_info
            else:
                current_path_fragment = current_path_fragment.parent_path_fragment

    @property
    def source_pydantic_model(self) -> BaseModel | BaseSettings:
        current_path_fragment = self
        while True:
            if current_path_fragment == None:
                # we are at the root. we can only return the root settings
                return self.source_path.root_settings

            if isinstance(current_path_fragment.content, (BaseModel, BaseSettings)):
                return current_path_fragment.content
            else:
                current_path_fragment = current_path_fragment.parent_path_fragment

    def get_next_annotation_fragment(self) -> Any:
        annon_args = get_args(self.annotation_fragment)
        if get_origin(self.annotation_fragment) == dict:
            return get_args(self.annotation_fragment)[1]
        elif annon_args:
            return get_args(self.annotation_fragment)[0]
        else:
            return None

    @property
    def key_raw(self):
        if isinstance(self.yaml_path_key, str):
            return self.yaml_path_key
        try:
            return self.yaml_path_key.index
        except:
            return self.yaml_path_key.key


def map_pydantic_settings_to_yaml_path(
    pydantic_settings: BaseSettings,
    yaml_path: List[str | ListIndex],
) -> ModelPathMap:
    ######
    print("##########", yaml_path)
    model_path: ModelPathMap = ModelPathMap(
        fragments=[], yaml_path=yaml_path, root_settings=pydantic_settings
    )
    for index, path_fragment in enumerate(yaml_path):
        print("-#-#-path_fragment", path_fragment)

        if len(model_path) == 0:
            # root item
            model_path.append(
                ModelPathFragment(
                    content=getattr(model_path.root_settings, path_fragment),
                    yaml_path_key=path_fragment,
                    yaml_path_index=index,
                    annotation_fragment=pydantic_settings.model_fields[
                        path_fragment
                    ].annotation,
                )
            )
        else:
            parent_path_fragment = model_path.enditem
            print(
                "parent_path_fragment.annotation_fragment",
                parent_path_fragment.annotation_fragment,
            )
            print(
                "get_origin(parent_path_fragment.annotation_fragment)",
                get_origin(parent_path_fragment.annotation_fragment),
            )
            print("parent_path_fragment", parent_path_fragment)

            if get_origin(parent_path_fragment.annotation_fragment) == dict:
                # a dict key could be int value but from the yaml path it always comes as string. we need to evaluate the type to cast it into the right type..
                key_type: Type[int] | Type[str] = get_args(
                    parent_path_fragment.annotation_fragment
                )[0]
                model_path.append(
                    ModelPathFragment(
                        content=parent_path_fragment.content[key_type(path_fragment)],
                        yaml_path_key=DictKey(path_fragment),
                        yaml_path_index=index,
                        annotation_fragment=parent_path_fragment.get_next_annotation_fragment(),
                    )
                )
            elif get_origin(
                parent_path_fragment.annotation_fragment
            ) == list and not isinstance(path_fragment, ListIndex):
                print("yaml_path", yaml_path)
                print("path_fragment", path_fragment)
                print(
                    "type(path_fragment)",
                    type(path_fragment),
                )
                raise ValueError(
                    "got a list item but no list index. something went wrong"
                )
            elif get_origin(parent_path_fragment.annotation_fragment) == list:
                print("yaml_path", yaml_path)
                print("parent_path_fragment.content", parent_path_fragment.content)
                print(
                    "parent_path_fragment.annotation_fragment",
                    parent_path_fragment.annotation_fragment,
                )
                print("path_fragment", path_fragment)
                print("path", yaml_path)
                print("path_fragment.index", path_fragment.index)

                model_path.append(
                    ModelPathFragment(
                        content=parent_path_fragment.content[path_fragment.index],
                        yaml_path_key=path_fragment,
                        yaml_path_index=index,
                        annotation_fragment=parent_path_fragment.get_next_annotation_fragment(),
                    )
                )
            elif get_origin(parent_path_fragment.annotation_fragment) in (
                BaseModel,
                BaseSettings,
            ) or issubclass(
                parent_path_fragment.annotation_fragment, (BaseModel, BaseSettings)
            ):
                model_path.append(
                    ModelPathFragment(
                        content=getattr(parent_path_fragment.content, path_fragment),
                        yaml_path_key=path_fragment,
                        yaml_path_index=index,
                        annotation_fragment=parent_path_fragment.content.model_fields[
                            path_fragment
                        ].annotation,
                    )
                )
            else:
                print("I AM DOING SHIT", path_fragment)
                exit()

    return model_path
