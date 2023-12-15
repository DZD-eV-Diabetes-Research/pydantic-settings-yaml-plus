from typing import Any
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
