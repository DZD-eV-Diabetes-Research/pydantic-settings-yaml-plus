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
    nested_dict_str: Dict[str, Dict[str, str]] = {
        "DictkeyA": {
            "InnerStrDictA1": "StrinA1",
            "InnerStrDictA2": "StrinA2",
        }
    }
    nested_dict_obj: Dict[str, Dict[str, SimpleObject]] = {
        "DictkeyA": {
            "InnerDictA1": SimpleObject(a_string_val="Damn these other typed"),
            "InnerDictA2": SimpleObject(a_string_val="Being a string the only way"),
        }
    }
