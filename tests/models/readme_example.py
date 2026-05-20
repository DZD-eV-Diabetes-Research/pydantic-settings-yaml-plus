"""The exact model from the README — used in integration tests."""
from pathlib import Path, PurePath
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    host: Optional[str] = Field(
        default="localhost",
        description="The hostname the database will be available at",
    )
    port: Optional[int] = Field(
        default=5678, description="The port to connect to the database"
    )
    database_names: List[str] = Field(
        description="The names of the databases to use",
        examples=[["mydb", "theotherdb"]],
    )


class MyAppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")

    log_level: Optional[Literal["INFO", "DEBUG"]] = "INFO"
    app_name: Optional[str] = Field(
        default="THE APP",
        description="The display name of the app",
        examples=["THAT APP", "THIS APP"],
    )
    storage_dir: Optional[str] = Field(
        description="A directory to store files for the app.",
        default_factory=lambda: str(Path(PurePath(Path().home(), ".config/myapp/"))),
    )
    admin_pw: Annotated[str, Field(description="The init password for the admin account")]
    database_server: DatabaseServerSettings = Field(
        description="The settings for the database server",
        examples=[
            DatabaseServerSettings(
                host="db.company.org", port=1234, database_names=["db1", "db2"]
            )
        ],
    )
    init_values: Dict[str, str]
