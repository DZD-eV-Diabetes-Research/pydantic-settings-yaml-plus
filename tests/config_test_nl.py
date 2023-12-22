from typing import List, Dict, Optional, Annotated, Literal, Any, Type
import datetime
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import inspect
from pathlib import Path, PurePath
from pydantic import (
    PastDate,
    FutureDate,
    PastDatetime,
    FutureDatetime,
    AwareDatetime,
    NaiveDatetime,
)


class SimpleObject(BaseSettings):
    a_string_val: str = Field(
        default="I am a mofo string baby", description="This is a mofo string baby"
    )


class TestConfig(BaseSettings):
    # works !
    nested_list_str: List[List[str]] = [
        ["lisitemA1", "listitemA2"],
        ["lisitemB1", "listitemB2"],
    ]
    # DOES NOT works ! A list index gets lost in YamlLine.path
    nested_list_obj: List[List[SimpleObject]] = [
        [
            SimpleObject(a_string_val="ListObjA1"),
            SimpleObject(a_string_val="ListObjA2"),
        ],
        [
            SimpleObject(a_string_val="ListObjB1"),
            SimpleObject(a_string_val="ListObjB2"),
        ],
    ]
