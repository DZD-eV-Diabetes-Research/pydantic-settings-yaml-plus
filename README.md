# pydantic-settings-yaml-plus
A helper module that builds upon [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to generate, read and comment a config file in yaml ~~and improve ENV var capabilities~~  
 
> [!WARNING]  
> work in progress. please ignore this repo for now


- [pydantic-settings-yaml-plus](#pydantic-settings-yaml-plus)
  - [Target use cases](#target-use-cases)
  - [Features](#features)
  - [Known Issues](#known-issues)
  - [Goals](#goals)
    - [ToDo / ToInvestigate](#todo--toinvestigate)
    - [Ideas/Roadmap](#ideasroadmap)
  - [How to use](#how-to-use)


## Target use cases

* **Config File Provisioning** The idea is to use this module during the build/release- (deploy on pypi.org) or init(First start)-process of your python module to generate a documented yaml file the user can understand.
* ~~**Extended Nested Env Var Parsing** Provide complex configs via env var without the need to write json~~ Needs a rewrite with pydantic-settings 2.x



## Features

* Generate a commented/documented yaml file based on your `pydantic-settings`.`BaseSettings` class
* ~~Support for nested listed and dict and var. E.g. `MYLIST__0__MYKEY=val` -> `config`.`MYLIST``[0]`.`MYKEY`=`val`~~ Needs a rewrite with pydantic-settings 2.x

## Known Issues
* Multiline values are crippled

## Goals

* Have a single source of truth for config and all its meta-data/documentation (type, descpription, examples)
* ~~All keys/values are addressable by env vars~~

### ToDo / ToInvestigate
* What about date(times) support?
* Make indexed env vars work again!
* Remove debug prints
* Write some more test
* Make pypi package

### Ideas/Roadmap
* Generate a mark down doc of all settings
* Generate template (minimal with required values only or maximum with all values listed) and example config files (all YAML only!)
* generate diff betwen current config and config model (when config model changed after update)
* update existing config files metadata
  * Update info, descs
  * Add missing/new required values
  



## How to use

Lets have the following examplary pydantic-settings config.py file:
  
```python
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
```
  
With the help of psyplus we can generate a fully documented  
  

```python
from psyplus import YamlSettingsPlus
from config import MyAppConfig

yaml_handler = YamlSettingsPlus(MyAppConfig, "test.config.yaml")
yaml_handler.generate_config_file(overwrite_existing=True)
```
  
which will generate a yaml file `./test.config.yaml` that looks like the following:
  
```yaml
# ## log_level ###
# Type:          Enum
# Required:      False
# Default:       '"INFO"'
# Allowed vals:  ['INFO', 'DEBUG']
# Env-var:       'LOG_LEVEL'
log_level: INFO

# ## app_name ###
# Type:         str
# Required:     False
# Default:      '"THE APP"'
# Env-var:      'APP_NAME'
# Description:  The display name of the app
# Example No. 1:
#  >app_name: THAT APP
#  >
# Example No. 2:
#  >app_name: THIS APP
app_name: THE APP

# ## storage_dir ###
# Type:         str
# Required:     False
# Env-var:      'STORAGE_DIR'
# Description:  A directory to store the file of the apps.
storage_dir: /home/tim/.config/myapp

# ## admin_pw ###
# Type:         str
# Required:     True
# Env-var:      'ADMIN_PW'
# Description:  The init password the admin account
admin_pw: ''

# ## database_server ###
# Type:         Object
# Required:     True
# Env-var:      'DATABASE_SERVER'
# Description:  The settings for the database server
# Example:
#  >database_server:
#  >  database_names:
#  >  - db1
#  >  - db2
#  >  host: db.company.org
#  >  port: 1234
database_server:

  # ## host ###
  # YAML-path:    database_server.host
  # Type:         str
  # Required:     False
  # Default:      '"localhost"'
  # Env-var:      'DATABASE_SERVER__HOST'
  # Description:  The Hostname the database will be available at
  host: localhost

  # ## port ###
  # YAML-path:    database_server.port
  # Type:         int
  # Required:     False
  # Default:      '5678'
  # Env-var:      'DATABASE_SERVER__PORT'
  # Description:  The port to connect to the database
  port: 5678

  # ## database_names ###
  # YAML-path:    database_server.database_names
  # Type:         List of str
  # Required:     True
  # Env-var:      'DATABASE_SERVER__DATABASE_NAMES'
  # Description:  The names of the databases to use
  # Example:
  #  >database_names:
  #  >- mydb
  #  >- theotherdb
  database_names: []
```
  
To use this yaml file you just psyplus: need to parse it and validate on your pydantic-setting model.
  
```python
from psyplus import YamlSettingsPlus

yaml_handler = YamlSettingsPlus(MyAppConfig, "test.config.yaml")
config: MyAppConfig = yaml_handler.get_config()
print(config.database_server.host)
```
  
Alternativly you can parse and validate the pydantic-settings model yourself:
  
```python
import yaml  # pip install PyYAML

with open("test.config.yaml") as file:
    raw_yaml_str = file.read()
obj: Dict = yaml.safe_load(raw_yaml_str)
config: MyAppConfig = MyAppConfig.model_validate(obj)

```