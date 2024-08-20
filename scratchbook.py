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
  l: 
  - A
  - B
    """
    data: CommentedMap = yaml.load(raw_yaml)

    # mh is see no way of inserting a comment UNDER a key without having a leading '#' in a actual yaml line

    # data.yaml_add_eol_comment(
    #    "\n\n#This does not work", "external_subconfig_dict_with_eg", column=5
    # )
    # data.yaml_set_start_comment(comment=indent=)
    # data.yaml_end_comment_extend(comment=,clear=)
    # data.yaml_add_eol_comment(comment=,key=,column=)
    data["external_subconfig_dict_with_eg"].yaml_set_comment_before_after_key(
        "a", before="KEY COMMETN BITCHES", indent=2
    )
    # print(list(data.items()))

    # print(data)
    data["external_subconfig_dict_with_eg"]["l"].yaml_set_start_comment("Cooment000", 0)
    data["external_subconfig_dict_with_eg"]["l"][1].yaml_set_start_comment(
        "Cooment111", 1
    )
    yaml.dump(data, sys.stdout)


# ruamel_yaml_test()


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


def test_clean_annot():
    from pydantic import Field
    from typing import (
        Annotated,
        Optional,
        Dict,
        Any,
        Union,
        get_type_hints,
        get_args,
        List,
    )
    from dataclasses import dataclass

    def is_typingOptional(annotation: Any) -> bool:
        return (
            hasattr(annotation, "__origin__")
            and annotation.__origin__ is Union
            and annotation.__args__[1] is type(None)
        )

    def get_typingOptionalArg(annotation) -> Any:
        if is_typingOptional(annotation):
            return annotation.__args__[0]
        return annotation

    def clean_annotation(annotation) -> Any:
        """remove any

        Args:
            annotation (_type_): _description_

        Returns:
            Any: _description_
        """
        if is_typingOptional(annotation=annotation):
            annotation = get_typingOptionalArg(annotation=annotation)
            return clean_annotation(annotation=annotation)
        return annotation

    @dataclass
    class Test:
        test: Annotated[
            Optional[Dict[str, str]],
            Field(description="Bla"),
        ] = None
        testlist: Annotated[Optional[List[str]], Field(description="Bla")] = None

    print(get_args((get_type_hints(Test)["testlist"])))
    print(get_args(clean_annotation(get_type_hints(Test)["testlist"])))


# test_clean_annot()


def ruamelyaml_debug():
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    from io import StringIO

    yaml = YAML()
    yaml.indent(sequence=2, offset=2)
    m0 = CommentedMap()
    l0 = CommentedSeq()
    m1 = CommentedMap()
    l1 = CommentedSeq()
    m0["OuterMap"] = l0
    l0.append(m1)
    m1["innerMapSimpleVal"] = "Somevalue"
    m1.yaml_set_comment_before_after_key(
        key="innerMapSimpleVal", before="###MyComment###", indent=2
    )
    m1["innerMapListVal"] = l1
    m1.yaml_set_comment_before_after_key(
        key="innerMapListVal", before="###MyComment2###", indent=2
    )
    l1.extend(["A", "B"])
    """
    l0_0 = CommentedSeq()
    l0_1 = CommentedSeq()

    l0_0.extend(["0|0"])
    l0_0.yaml_set_start_comment("Comment")

    m1["A"] = l0_0
    l0_1.extend([m1])
    l0.append(m1)
    l0.append(l0_1)
    m0["OuterMap"] = l0_1
    """
    stream = StringIO()

    yaml.dump(m0, stream)

    print(stream.getvalue())


# ruamelyaml_debug()


def get_literal_annot():
    from pydantic import Field
    from typing import (
        Annotated,
        Optional,
        Dict,
        Any,
        Union,
        get_type_hints,
        get_args,
        List,
        Literal,
    )
    from dataclasses import dataclass

    def is_typingOptional(annotation: Any) -> bool:
        return (
            hasattr(annotation, "__origin__")
            and annotation.__origin__ is Union
            and annotation.__args__[1] is type(None)
        )

    def get_typingOptionalArg(annotation) -> Any:
        if is_typingOptional(annotation):
            return annotation.__args__[0]
        return annotation

    def clean_annotation(annotation) -> Any:
        """remove any

        Args:
            annotation (_type_): _description_

        Returns:
            Any: _description_
        """
        if is_typingOptional(annotation=annotation):
            annotation = get_typingOptionalArg(annotation=annotation)
            return clean_annotation(annotation=annotation)
        return annotation

    def has_literal(annotation: Any) -> bool:
        clean_annot = clean_annotation(annotation=annotation)
        if hasattr(clean_annot, "__origin__"):
            return clean_annot.__origin__ == Literal

    def get_literal_list(annotation: Any) -> List[Any] | None:
        clean_annot = clean_annotation(annotation=annotation)
        if hasattr(clean_annot, "__origin__") and clean_annot.__origin__ == Literal:
            return list(clean_annot.__args__)
        return None

    @dataclass
    class Test:
        test: Annotated[
            Optional[Literal["A", "B", "C"]],
            Field(description="Bla"),
        ] = None
        testlist: Annotated[
            Optional[Literal["1A", "2B", "3C"]], Field(description="Bla")
        ] = None

    print(get_literal_list((get_type_hints(Test)["test"])))
    print(get_literal_list((get_type_hints(Test)["testlist"])))
    # print(get_args(clean_annotation(get_type_hints(Test)["testlist"])))
    # has_literal(get_type_hints(Test)["testlist"])
    return
    print(get_args((get_type_hints(Test)["testlist"])))
    print(get_args(clean_annotation(get_type_hints(Test)["testlist"])))


# get_literal_annot()


def env_to_dict():
    import os

    key = "MYDICT__NEXTKEY__WHATEVER"
    val = "val111"

    parts = key.split("__")
    result = {}
    temp = result

    for part in parts[:-1]:
        temp = temp.setdefault(part, {})
    temp[parts[-1]] = val

    print(result)
    return result


def get_seperators():
    from pydantic_settings import BaseSettings

    class Conf(BaseSettings):
        val: int = 1

        class Config:
            # (meta)config class for pydantic-settings https://docs.pydantic.dev/latest/usage/settings/
            env_prefix: str = "ONBOT_"
            env_nested_delimiter: str = "__"

    Conf.Config.env_prefix
