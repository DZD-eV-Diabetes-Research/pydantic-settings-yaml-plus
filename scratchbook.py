def annofields():
    from typing import Dict

    from pydantic import BaseModel, Field
    from typing import Any, List, Dict, Set, Tuple, get_type_hints
    import typing

    class myClass(BaseModel):
        test: Any
        test_string: str = Field(
            max_length=123, min_length=2, alias="ba", validate_default=""
        )
        test_int: int
        test_float: float
        # test_complex: complex
        test_simple_list: list
        test_list: List[str]
        test_simple_dict: dict
        test_dict: Dict[int, str]
        test_simple_set: set
        test_set: Set[int]
        test_simple_tuple: tuple
        test_tuple: Tuple[int, int]

    for key, field in myClass.model_fields.items():
        print("---------", key)
        print(field.metadata)

        """
        if hasattr(annotation, "__origin__"):
            print(key, annotation.__origin__())
        elif type(annotation) == type:
            # we have a basic type
            print(key, annotation())
        """


def envtest():
    import os
    from typing import List
    import pydantic

    print("pydantic.__version__:", pydantic.__version__)
    from pydantic import BaseModel

    import pydantic_settings

    print("pydantic_settings.__version__:", pydantic_settings.__version__)
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class RedisSettings(BaseModel):
        host: str = "localhost"
        port: int = 9874

    class Config(BaseSettings):
        redis: List[RedisSettings] = []
        model_config = SettingsConfigDict(env_nested_delimiter="__")

        # class Config:
        #    env_nested_delimiter: str = "__"

    os.environ["REDIS__0__PORT"] = "1234"
    os.environ["redis__0__host"] = "horst"
    print(Config().model_dump())
    # > {'redis': {'host': 'localhost', 'port': 6379}}


# envtest()  #


def intend_test():
    import yaml

    print(yaml.dump({"l1": [1, 2, 3]}, default_flow_style=True))


# intend_test()


def list_replace_test():
    l1 = ["A", "b", "c"]
    itemb = l1[1]
    print(itemb)
    itemb = None
    print(l1, itemb)


def remove_ml_indi():
    import re

    YAML_BLOCK_SCALAR_INDICATOR = (">", "|", ">-", "|-", ">+", "|+")
    teststrings = ["> sdafeas fwef we", ">- asdiohweuifguewfhdsfsd", "+ safd aesdfe"]
    for t in teststrings:
        tr = re.sub(
            f"^(?:{'|'.join(map(re.escape, YAML_BLOCK_SCALAR_INDICATOR))})",
            "",
            t,
        )
        print(tr)


# remove_ml_indi()


def anno_exploder():
    from typing import get_args, get_origin, _GenericAlias, Union, Dict, List, Any
    from pydantic import BaseModel

    def explode_field_annotation(annotation) -> List[Any]:
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
            annotation_path.extend(explode_field_annotation(arg))

        return annotation_path
        if (
            hasattr(annotation, "__origin__")
            and hasattr(annotation, "__args__")
            and 1 == 2
        ):
            if annotation.__origin__ == list:
                return [annotation.__origin__] + [
                    arg
                    for arg in annotation.__args__
                    for t in explode_field_annotation(arg)
                ]
            return [annotation.__origin__] + [
                t for t in explode_field_annotation(annotation.__args__[0])
            ]
        else:
            return [annotation]

    class SomeModel(BaseModel):
        a: int = 1

    annotation = Dict[str, List[int]]
    annotation2 = Dict[str, list]
    annotation1 = Union[List[int], List[str]]
    print(explode_field_annotation(annotation=annotation))


anno_exploder()
