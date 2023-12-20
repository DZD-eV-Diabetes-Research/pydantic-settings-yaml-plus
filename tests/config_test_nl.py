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


class ExternalSubClass(BaseSettings):
    test: Any
    test_simple_list: List[str]
    test_simple_dict: Dict[int, str]
    datetime_today: datetime.datetime = Field(
        default_factory=datetime.datetime.now, description="The time and date of now"
    )
    day: datetime.date = Field(
        default_factory=lambda: datetime.datetime.now().date(),
        description="The day of now",
    )
    past_date: PastDate = Field(
        default_factory=lambda: (
            datetime.datetime.now() - datetime.timedelta(1)
        ).date(),
        description="The day of just",
    )
    nested_list: List[List[str]] = [["A", "B", "C"], ["D", "E", "F"]]
    nested_list_obj: List[List[SimpleObject]] = [
        [SimpleObject(), SimpleObject(a_string_val="I am just a normal string")],
        [SimpleObject(a_string_val="Am i a string? sometimes im in doubt")],
    ]
    nested_dict: Dict[str, Dict[str, int]] = {
        "DictkeyA": {"InnerDictA1": 1, "InnerDictA2": 2},
        "DictkeyB": {"InnerDictB1": 1, "InnerDictB2": 2},
        "DictkeyC": {"InnerDictC1": 1, "InnerDictC2": 2},
    }
    nested_dict_obj: Dict[str, Dict[str, SimpleObject]] = {
        "DictkeyA": {
            "InnerDictA1": SimpleObject(a_string_val="Damn these other typed"),
            "InnerDictA2": SimpleObject(a_string_val="Being a string the only way"),
        },
        "DictkeyB": {
            "InnerDictB1": SimpleObject(a_string_val="We are the worst"),
            "InnerDictB2": SimpleObject(a_string_val="I hate being a string"),
        },
        "DictkeyC": {
            "InnerDictC1": SimpleObject(
                a_string_val="Chill the f out about being a string"
            ),
            "InnerDictC2": SimpleObject(a_string_val="Why argue about being a string?"),
        },
    }


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
