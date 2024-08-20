from typing import (
    Any,
    Union,
    Dict,
    List,
    get_origin,
    Literal,
    get_args,
    Generator,
)
from pydantic_core import PydanticUndefined
from pydantic import BaseModel
from pydantic_settings import BaseSettings


import datetime
from pydantic import (
    PastDate,
    FutureDate,
    PastDatetime,
    FutureDatetime,
    AwareDatetime,
    NaiveDatetime,
)


def python_annotation_to_generic_readable(
    annotation,
) -> str:
    # https://docs.pydantic.dev/2.5/api/json_schema/#pydantic.json_schema.GenerateJsonSchema
    JSON_BASIC_TYPES = Literal["boolean", "number", "string", "array", "object"]

    # https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1
    JSON_SUBSCHEMAS = Literal["allOf", "anyOf", "oneOf", "not"]

    PYTHON_SCALAR_TYPES = [
        int,
        float,
        str,
        bool,
        datetime.time,
        datetime.date,
        datetime.datetime,
        PastDate,
        FutureDate,
        PastDatetime,
        FutureDatetime,
        AwareDatetime,
        NaiveDatetime,
    ]

    def stringifiy_annotation(annot) -> str:
        if type(annot) == tuple:
            res = []
            for item in annot:
                res.append(stringifiy_annotation(item))
            if res:
                return ",".join(res)
        if is_typingOptional(annot):
            return stringifiy_annotation(get_typingOptionalArg(annot))
        elif annot == Any:
            return None
        elif annot in PYTHON_SCALAR_TYPES:
            return annot.__name__
        elif get_origin(annot) == list or annot == list:
            list_annotation_args = get_args(annot)
            if list_annotation_args:
                return "List of " + stringifiy_annotation(list_annotation_args)
            else:
                return "List"
        elif get_origin(annot) == dict or annot == dict:
            dict_annotation_args = get_args(annot)
            if dict_annotation_args:
                return f"Dictionary of ({stringifiy_annotation(get_args(annot))})"
            else:
                return "Dictionary"
        elif get_origin(annot) == Literal:
            return "Enum"
        else:
            return "Object"

    return stringifiy_annotation(annotation)


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
    """extract actual type annotation from field annotations like typing.Optional,...

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


def nested_pydantic_to_dict(obj: Any) -> Any:
    if isinstance(obj, (BaseModel, BaseSettings)):
        return nested_pydantic_to_dict(obj.model_dump())
    elif isinstance(obj, dict):
        return {k: nested_pydantic_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [nested_pydantic_to_dict(item) for item in obj]
    else:
        return obj


def get_dict_val_key_insensitive(
    dictionary: Dict, key: str, default: Any = PydanticUndefined
):
    for k in dictionary.keys():
        if k.upper() == key.upper():
            return dictionary[k]
    if default != PydanticUndefined:
        raise KeyError(f"Can not find key '{key}' in {dictionary.keys()}")
    return default


def env_to_nested_dict(key: str | List[str], val: Any, delimiter: str = "__") -> Dict:
    """Convert a env var key to a nestesd dict.
    e.g.
    `MYDICT__NEXTKEY__WHATEVER=val111` -> `{'MYDICT': {'NEXTKEY': {'WHATEVER': 'val111'}}}`

    Returns:
        Dict:
    """

    if isinstance(key, str):
        fragments = key.split(delimiter)
    elif isinstance(key, list):
        fragments = key
    else:
        raise ValueError(f"key must be str or list but is {type(key)}")
    result = {}
    temp = result

    for frag in fragments[:-1]:
        temp = temp.setdefault(frag, {})
    temp[fragments[-1]] = val

    return result


def get_str_dict_as_table(
    d: Dict, vertical_seperator: str = "", respect_line_breaks_in_val: bool = True
) -> str:
    length_key_column = (max(len(string) for string in d.keys()) if d.keys() else 0) + 1
    result = ""
    for key, val in d.items():
        if respect_line_breaks_in_val:
            val = str(val).split("\n")
            result += f"{key.ljust(length_key_column)}{vertical_seperator}{val[0]}\n"
            for v in val[1:]:
                result += f"{''.ljust(length_key_column)}{vertical_seperator}{v}\n"
        else:
            result += f"{key.ljust(length_key_column)}{vertical_seperator}{val}\n"
    return result


def indent_multilines(
    text: List[str],
    indent_depth: int = 0,
    line_prefix: str = "",
    line_suffix: str = "",
    extra_indent_depth_after_prefix: int = 0,
    add_extra_indent_for_subsequent_lines_after_line_prefix: bool = False,
    indent: str = "  ",
) -> Generator[str, None, None]:
    indent = f"{indent_depth*indent}"
    inner_indent = f"{extra_indent_depth_after_prefix*indent}"
    for index, line in enumerate(text):
        line_prefix_real = f"{line_prefix}{inner_indent}"
        if index != 0 and add_extra_indent_for_subsequent_lines_after_line_prefix:
            line_prefix_real = f"{line_prefix_real}{indent}"
        yield f"{indent}{line_prefix_real}{line}{line_suffix}"
