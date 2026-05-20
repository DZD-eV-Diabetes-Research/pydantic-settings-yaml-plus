"""Flat settings model used in tests — covers basic scalar types and field metadata."""
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimpleModel(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIMPLE_")

    a_string: str = "hello"
    an_int: int = 42
    a_float: float = 3.14
    a_bool: bool = True
    optional_none: Optional[str] = None
    literal_field: Literal["A", "B", "C"] = "A"
    string_list: List[str] = ["x", "y"]
    string_dict: Dict[str, int] = {"one": 1}
    required_string: str  # required — no default
    required_list: List[str]  # required — no default
    fully_documented: Annotated[
        Optional[str],
        Field(
            title="Great String",
            description="A fully documented optional string field.",
            examples=["ex1", "ex2"],
            max_length=100,
        ),
    ] = "default_value"
    with_factory: str = Field(
        default_factory=lambda: "from_factory",
        description="Uses a default_factory lambda.",
    )
