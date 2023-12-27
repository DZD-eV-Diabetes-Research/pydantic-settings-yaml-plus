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


# anno_exploder()


def pydantic_to_dict_nested():
    from typing import Any, List, Dict
    from pydantic import BaseModel
    from pydantic_settings import BaseSettings
    import yaml

    def pydantic_to_dict(obj: Any) -> Any:
        if isinstance(obj, (BaseModel, BaseSettings)):
            return pydantic_to_dict(obj.dict())
        elif isinstance(obj, dict):
            return {k: pydantic_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [pydantic_to_dict(item) for item in obj]
        else:
            return obj

    class ExternalSubClass(BaseModel):
        test: Any
        test_simple_list: List[str]
        test_simple_dict: Dict[int, str]

    v = {
        "a": ExternalSubClass(
            test="a value",
            test_simple_list=["a", "b", "c"],
            test_simple_dict={1: "a"},
        )
    }
    print(yaml.dump(pydantic_to_dict(v), sort_keys=False))


# pydantic_to_dict_nested()


def ruamel_yaml_test():
    import sys
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap

    yaml = YAML()
    raw_yaml = """
external_subconfig_dict_with_eg:
  a:

    ### test ###
    # YAML-path:  external_subconfig_dict_with_eg.a.test
    # Required:   True
    # Env-var:    'EXTERNAL_SUBCONFIG_DICT_WITH_EG__<DICTKEY>__TEST'
    test: a value
    """
    data: CommentedMap = yaml.load(raw_yaml)

    # mh is see no way of inserting a comment UNDER a key without having a leading '#' in a actual yaml line

    data.yaml_add_eol_comment(
        "\n\n#This does not work", "external_subconfig_dict_with_eg", column=5
    )

    print(data)
    yaml.dump(data, sys.stdout)


ruamel_yaml_test()


def nested_lists():
    import yaml

    yaml_raw = """
uneven_nesting:
  - item1
    - sub_item1
      - sub_sub_item1
  - item2
    - sub_item2
      - sub_sub_item2
      - sub_sub_item3
"""
    d = yaml.safe_load(yaml_raw)
    print(d)


# nested_lists()


def split_start_dash():
    import re

    test_vals = [
        "- - my-value2 - ",
        "  - - my-value2 - ",
        "- - - - my-value4 - ",
        "- my-value1 - ",
        "  - my-value1 - ",
    ]

    def split_at_start(s: str, sep: str = " "):
        ssplit = s.split(sep)
        result = []
        for index, fragment in enumerate(ssplit):
            if fragment != "":
                result.append(sep.join(ssplit[index:]))
                break
            result.append(fragment)
        return result

        parts = s.split("-")
        result = [" " * (len(s) - len(s.lstrip())) + parts[0]]
        if len(parts) > 1:
            result.append("-" + "-".join(parts[1:]))
        return result

    for val in test_vals:
        print("#-#-INPUT", val)
        print("RESULT:", split_at_start(val.lstrip(), "- "))
        print(split_at_start(val.lstrip(), "- ")[:-1])
        print("")


# split_start_dash()
