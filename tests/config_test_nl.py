from typing import List, Dict, Optional, Annotated, Literal, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import inspect
from pathlib import Path, PurePath


class ExternalSubClass(BaseSettings):
    test: Any
    test_simple_list: List[str]
    test_simple_dict: Dict[int, str]


class TestConfig(BaseSettings):
    external_subconfig_dict_with_eg: Annotated[
        Dict[str, ExternalSubClass],
        Field(
            title="A dict field with example",
            examples=[
                {
                    "a": ExternalSubClass(
                        test="a value",
                        test_simple_list=["a", "b", "c"],
                        test_simple_dict={1: "a"},
                    )
                },
            ],
        ),
    ]
