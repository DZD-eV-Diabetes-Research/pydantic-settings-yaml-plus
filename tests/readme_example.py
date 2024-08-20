from typing import List, Dict, Optional, Literal, Annotated

from pydantic import Field
from pydantic_settings import BaseSettings

from pathlib import Path, PurePath


class DatabaseServerSettings(BaseSettings):
    host: Optional[str] = Field(
        default="localhost",
        description="The Hostname the database will be available at",
    )
    port: Optional[int] = Field(
        default=5678, description="The port to connect to the database"
    )
    database_names: List[str] = Field(
        description="The names of the databases to use",
        examples=[["mydb", "theotherdb"]],
    )


class MyAppConfig(BaseSettings):
    log_level: Optional[Literal["INFO", "DEBUG"]] = "INFO"
    app_name: Optional[str] = Field(
        default="THE APP",
        description="The display name of the app",
        examples=["THAT APP", "THIS APP"],
    )
    storage_dir: Optional[str] = Field(
        description="A directory to store the file of the apps.",
        default_factory=lambda: str(Path(PurePath(Path().home(), ".config/myapp/"))),
    )
    admin_pw: Annotated[str, Field(description="The init password the admin account")]
    database_server: DatabaseServerSettings = Field(
        description="The settings for the database server",
        examples=[
            DatabaseServerSettings(
                host="db.company.org", port=1234, database_names=["db1", "db2"]
            )
        ],
    )
    init_values: Dict[str, str]


from psyplus import YamlSettingsPlus


yaml_handler = YamlSettingsPlus(MyAppConfig, "test.config.yaml")
yaml_handler.generate_config_file(overwrite_existing=True)

import os

# set env vars
# emulate:
# `export DATABASE_SERVER__DATABASE_NAMES__0=DB01`
# `export DATABASE_SERVER__DATABASE_NAMES__0=DB02`
os.environ["DATABASE_SERVER__ADMIN_PW"] = "xxxxx"
os.environ["DATABASE_SERVER__DATABASE_SERVER"] = "server.com"
os.environ["DATABASE_SERVER__INIT_VALUES"] = "{}"
os.environ["DATABASE_SERVER__DATABASE_NAMES__0"] = "DB01"
os.environ["DATABASE_SERVER__DATABASE_NAMES__1"] = "DB02"
from psyplus import YamlSettingsPlus, EnvVarHandlerExtended


app_config = MyAppConfig()
EnvVarHandlerExtended(app_config)
print(app_config.database_server.database_names)
