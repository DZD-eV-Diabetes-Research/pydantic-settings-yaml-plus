"""Settings models with nullable fields, used to test the "or null" type and the env var null note."""
from typing import Annotated, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NullableModel(BaseSettings):
    """Without ``env_parse_none_str``: env vars can not set any field to null."""

    model_config = SettingsConfigDict(env_prefix="NUL_")

    max_age_days: Optional[int] = 30
    labels: Optional[List[str]] = ["a", "b"]
    annotated_limit: Annotated[Optional[int], Field(description="Annotated nullable.")] = 20
    null_by_default: Optional[str] = None
    not_nullable: int = 5


class NullableEnvNoneModel(NullableModel):
    """Same fields, with ``env_parse_none_str`` so env vars can set null."""

    model_config = SettingsConfigDict(env_prefix="NUL_", env_parse_none_str="null")
