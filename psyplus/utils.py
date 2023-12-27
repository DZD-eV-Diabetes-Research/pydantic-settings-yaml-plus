from typing import Any, Union, Dict, List
from pydantic import BaseModel
from pydantic_settings import BaseSettings


def nested_pydantic_to_dict(obj: Any) -> Any:
    if isinstance(obj, (BaseModel, BaseSettings)):
        return nested_pydantic_to_dict(obj.model_dump())
    elif isinstance(obj, dict):
        return {k: nested_pydantic_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [nested_pydantic_to_dict(item) for item in obj]
    else:
        return obj


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


def get_str_dict_as_table(
    d: Dict, vertical_seperator: str = "", respect_line_breaks_in_val: bool = True
) -> str:
    length_key_column = (max(len(string) for string in d.keys()) if d.keys() else 0) + 1
    result = ""
    for key, val in d.items():
        if respect_line_breaks_in_val:
            val = val.split("\n")
            result += f"{key.ljust(length_key_column)}{vertical_seperator}{val[0]}\n"
            for v in val[1:]:
                result += f"{''.ljust(length_key_column)}{vertical_seperator}{v}\n"
        else:
            result += f"{key.ljust(length_key_column)}{vertical_seperator}{val}\n"
    return result


def split_at_start(s: str, sep: str = " ") -> List[str]:
    """similar to str.split() but only split repeating seperatro from left and stops splitting when next fragment differs from separator
    e.g. `split_at_start("- - - - my-value4 - ","- ")` will result in  ` ['', '', '', '', 'my-value4 - ']`
    """
    ssplit = s.split(sep)
    result = []
    for index, fragment in enumerate(ssplit):
        if fragment != "":
            result.append(sep.join(ssplit[index:]))
            break
        result.append(fragment)
    return result
