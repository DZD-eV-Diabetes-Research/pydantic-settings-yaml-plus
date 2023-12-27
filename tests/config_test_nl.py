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


class ListObject(BaseSettings):
    a_string_list: List[str] = Field(
        default=["listInObitemA1-0,0", "listInObitemA2-0,1", "listInObitemA3-0,2"],
        description="This is a mofo object with list of string baby",
    )


class TestConfig(BaseSettings):
    # works !
    nested_list_str: List[List[str]] = [
        ["lisitemA1-0,0", "listitemA2-0,1", "listitemA3-0,2"],
        ["lisitemB1-1,0", "listitemB2-1,1"],
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
    nested_list_obj_list: List[ListObject] = [
        ListObject(
            a_string_list=[
                "listInObitemA1-0,0",
                "listInObitemA2-0,1",
                "listInObitemA3-0,2",
            ]
        ),
        ListObject(
            a_string_list=[
                "listInObitemB1-1,0",
                "listInObitemB2-1,1",
                "listInObitemB3-1,2",
            ]
        ),
    ]
