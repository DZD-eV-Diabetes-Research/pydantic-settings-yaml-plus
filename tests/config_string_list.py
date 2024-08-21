from typing import List, Dict, Optional, Annotated, Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import inspect
from pathlib import Path, PurePath


class TestConfig(BaseSettings):
    log_level: Optional[List[str]] = ["ListEntryA", "ListEntryB"]

    # this generated a "# Required:   True" for every list entyr which is wrong
    class Config:
        # (meta)config class for pydantic-settings https://docs.pydantic.dev/latest/usage/settings/
        env_prefix: str = "TEST_"
        env_nested_delimiter: str = "__"
