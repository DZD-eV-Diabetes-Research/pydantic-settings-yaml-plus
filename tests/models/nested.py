"""Nested settings model used in tests — covers BaseModel sub-models and lists of sub-models."""
from pathlib import Path, PurePath
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(description="Database name (required)")
    tags: List[str] = []


class CacheConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379


class NestedModel(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")

    app_name: str = Field(default="My App", description="Display name of the application")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database: DatabaseConfig = Field(description="Primary database settings")
    cache: Optional[CacheConfig] = None
    storage_dir: str = Field(
        default_factory=lambda: str(Path(PurePath(Path().home(), ".config/app/"))),
        description="Directory for application state.",
    )
    admin_password: Annotated[
        str,
        Field(description="Initial admin password (required)"),
    ]  # required


class ServerItem(BaseModel):
    host: str
    port: int = 80


class MultiNestedModel(BaseSettings):
    """A model with list-of-BaseModel and dict-of-BaseModel fields."""

    model_config = SettingsConfigDict(env_prefix="MULTI_", env_nested_delimiter="__")

    servers: List[ServerItem] = [ServerItem(host="a.example.com"), ServerItem(host="b.example.com")]
    server_map: Dict[str, ServerItem] = {
        "primary": ServerItem(host="primary.example.com", port=443)
    }
