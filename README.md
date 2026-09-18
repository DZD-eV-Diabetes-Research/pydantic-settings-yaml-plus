# pydantic-settings-yaml-plus

A helper library that builds upon [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to **generate**, **read**, and **document** YAML config files — with comment headers that explain every setting's type, default value, allowed values, environment variable override, and description.

- [pydantic-settings-yaml-plus](#pydantic-settings-yaml-plus)
  - [Features](#features)
  - [Installation](#installation)
  - [Quick start](#quick-start)
    - [1 — Define your settings model](#1--define-your-settings-model)
    - [2 — Generate the YAML config file](#2--generate-the-yaml-config-file)
  - [Generated YAML output](#generated-yaml-output)
  - [Reading the config](#reading-the-config)
  - [Generating Markdown documentation](#generating-markdown-documentation)
  - [Example gallery](#example-gallery)
  - [API reference](#api-reference)
    - [`YamlSettingsPlus(model, file_path=None)`](#yamlsettingsplusmodel-file_pathnone)
      - [Methods](#methods)
    - [`YamlFileGenerator(settings_class, indent_size=2)`](#yamlfilegeneratorsettings_class-indent_size2)
    - [`MarkdownDocGenerator(settings_class)`](#markdowndocgeneratorsettings_class)
  - [Defining your settings model](#defining-your-settings-model)
    - [Useful `Field()` kwargs](#useful-field-kwargs)
    - [Configuring env vars](#configuring-env-vars)
  - [Environment variable overrides](#environment-variable-overrides)
  - [Development](#development)
    - [Smoke test](#smoke-test)
    - [Running tests with coverage](#running-tests-with-coverage)
    - [PDM cheat-sheet](#pdm-cheat-sheet)

---

## Features

- **Generate documented YAML** — each field gets a comment block with its type, required flag, default value, allowed enum values, corresponding environment variable, description, and examples.
- **Nested models** — `BaseModel` sub-models are rendered as indented YAML sections with full comment headers.
- **Read back with env-var override** — `load()` loads the YAML file and still applies environment variable overrides using pydantic-settings' standard machinery.
- **Markdown docs** — generate a Markdown reference document straight from your settings class.
- **Zero boilerplate** — define your settings in a standard `pydantic_settings.BaseSettings` subclass; psyplus does the rest.

---

## Installation

```bash
pip install psyplus
```

**Requirements:** Python ≥ 3.12, pydantic ≥ 2.0, pydantic-settings ≥ 2.3

---

## Quick start

### 1 — Define your settings model

```python
# config.py
from typing import Annotated, Dict, List, Literal, Optional
from pathlib import Path, PurePath

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    host: Optional[str] = Field(
        default="localhost",
        description="The hostname the database will be available at",
    )
    port: Optional[int] = Field(
        default=5678,
        description="The port to connect to the database",
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
```

> **Note on `model_config`:** use `SettingsConfigDict` (pydantic-settings v2 style) rather than the old inner `class Config`. Both work, but `SettingsConfigDict` is preferred.

### 2 — Generate the YAML config file

```python
from psyplus import YamlSettingsPlus
from config import MyAppConfig

handler = YamlSettingsPlus(MyAppConfig, "config.yaml")
handler.generate_config_file()                       # silently skips if file exists (default)
handler.generate_config_file(on_exists="overwrite")  # replace existing file
handler.generate_config_file(on_exists="error")      # raise FileExistsError if file exists
```

---

## Generated YAML output

The command above creates `config.yaml` with a comment block above every key:

```yaml
# ## log_level ###
# Type:         Enum or null
# Required:     False
# Default:      "INFO"
# Allowed vals: ['INFO', 'DEBUG']
# Env-var:      'APP_LOG_LEVEL' (can not set null, use null in the YAML file)
log_level: INFO

# ## app_name ###
# Type:        str or null
# Required:    False
# Default:     "THE APP"
# Env-var:     'APP_APP_NAME' (can not set null, use null in the YAML file)
# Description: The display name of the app
# Example No. 1:
#  >app_name: THAT APP
# Example No. 2:
#  >app_name: THIS APP
app_name: THE APP

# ## storage_dir ###
# Type:        str or null
# Required:    False
# Env-var:     'APP_STORAGE_DIR' (can not set null, use null in the YAML file)
# Description: A directory to store files for the app.
storage_dir: /home/user/.config/myapp

# ## admin_pw ###
# Type:        str
# Required:    True
# Env-var:     'APP_ADMIN_PW'
# Description: The init password for the admin account
admin_pw: ''

# ## database_server ###
# Type:        Object (DatabaseServerSettings)
# Required:    True
# Env-var:     'APP_DATABASE_SERVER'
# Description: The settings for the database server
# Example:
#  >database_server:
#  >  host: db.company.org
#  >  port: 1234
#  >  database_names:
#  >  - db1
#  >  - db2
database_server:

  # ## host ###
  # YAML-path:   database_server.host
  # Type:        str or null
  # Required:    False
  # Default:     "localhost"
  # Env-var:     'APP_DATABASE_SERVER__HOST' (can not set null, use null in the YAML file)
  # Description: The hostname the database will be available at
  host: localhost

  # ## port ###
  # YAML-path:   database_server.port
  # Type:        int or null
  # Required:    False
  # Default:     5678
  # Env-var:     'APP_DATABASE_SERVER__PORT' (can not set null, use null in the YAML file)
  # Description: The port to connect to the database
  port: 5678

  # ## database_names ###
  # YAML-path:   database_server.database_names
  # Type:        List of str
  # Required:    True
  # Env-var:     'APP_DATABASE_SERVER__DATABASE_NAMES'
  # Description: The names of the databases to use
  # Example:
  #  >database_names:
  #  >- mydb
  #  >- theotherdb
  database_names: []

# ## init_values ###
# Type:     Dictionary of (str, str)
# Required: True
# Env-var:  'APP_INIT_VALUES'
init_values: {}
```

Required fields without defaults are written with an empty placeholder (`''`, `[]`, `{}`).  
The `Required: True` comment tells the user they must fill these in before the app will validate.

---

## Reading the config

```python
from psyplus import YamlSettingsPlus
from config import MyAppConfig

handler = YamlSettingsPlus(MyAppConfig, "config.yaml")
config: MyAppConfig = handler.load()

print(config.database_server.host)   # → "localhost" (or whatever is in the YAML)
print(config.log_level)              # → "INFO"
```

`load()` honours environment variable overrides through pydantic-settings' standard source priority: **env vars beat YAML values**. For example:

```bash
export APP_LOG_LEVEL=DEBUG
```

…will make `config.log_level == "DEBUG"` even if the YAML file says `INFO`.

> **Tip:** if you prefer to keep psyplus out of your runtime path, configure `yaml_file` directly in your model and call it without psyplus:
>
> ```python
> from pydantic_settings import BaseSettings, SettingsConfigDict
>
> class MyAppConfig(BaseSettings):
>     model_config = SettingsConfigDict(
>         yaml_file="config.yaml",
>         env_prefix="APP_",
>         env_nested_delimiter="__",
>     )
>
> config = MyAppConfig()  # reads YAML + env vars automatically
> ```

---

## Generating Markdown documentation

Write a Markdown reference document to disk:

```python
from psyplus import YamlSettingsPlus
from config import MyAppConfig

YamlSettingsPlus(MyAppConfig).generate_markdown_doc("SETTINGS.md")
```

Or get the Markdown as a string (e.g. to post to a wiki API):

```python
md = YamlSettingsPlus(MyAppConfig).render_markdown()
```

Both produce a document with a property table for every field: type, required flag, default, allowed values, environment variable, description, and examples.

---

## Example gallery

The table below links the bundled test models to their pre-generated output so you can see exactly what psyplus produces before writing a single line of your own config.

| Model | Source | What it demonstrates | YAML output | Markdown output |
|---|---|---|---|---|
| `SimpleModel` | [tests/models/simple.py](tests/models/simple.py) | Flat settings: scalars, Optional, Literal, List, Dict, Annotated metadata, `default_factory` | [SimpleModel.yaml](smoke_output/SimpleModel.yaml) | [SimpleModel.md](smoke_output/SimpleModel.md) |
| `NestedModel` | [tests/models/nested.py](tests/models/nested.py) | Nested `BaseModel` sub-field, optional sub-model, env-var path generation with `env_nested_delimiter` | [NestedModel.yaml](smoke_output/NestedModel.yaml) | [NestedModel.md](smoke_output/NestedModel.md) |
| `MultiNestedModel` | [tests/models/nested.py](tests/models/nested.py) | `List[BaseModel]` and `Dict[str, BaseModel]` fields — YAML renders each item, Markdown recurses into the item schema | [MultiNestedModel.yaml](smoke_output/MultiNestedModel.yaml) | [MultiNestedModel.md](smoke_output/MultiNestedModel.md) |
| `MyAppConfig` | [tests/models/readme_example.py](tests/models/readme_example.py) | The full README quick-start model with nested database settings and field examples | [MyAppConfig.yaml](smoke_output/MyAppConfig.yaml) | [MyAppConfig.md](smoke_output/MyAppConfig.md) |

These files are regenerated automatically by the smoke script (`pdm run smoke`) and committed to the repository, so they are always in sync with the current code.

---

## API reference

### `YamlSettingsPlus(model, file_path=None)`

| Parameter   | Type                    | Description                              |
|-------------|-------------------------|------------------------------------------|
| `model`     | `Type[BaseSettings]`    | The pydantic-settings class to work with |
| `file_path` | `str \| Path \| None`   | Path of the YAML config file             |

#### Methods

| Method | Description |
|---|---|
| `generate_config_file(on_exists="skip")` | Write a documented YAML template to `file_path`. `on_exists` controls what happens when the file already exists: `"skip"` (default) does nothing, `"overwrite"` replaces it, `"error"` raises `FileExistsError`. |
| `generate_markdown_doc(output_path)` | Write a Markdown reference document to `output_path`. |
| `render_yaml() → str` | Render the documented YAML as a string without touching the filesystem. |
| `render_markdown() → str` | Render the Markdown reference document as a string without touching the filesystem. |
| `load() → BaseSettings` | Load `file_path`, apply env var overrides, return a validated settings instance. |

### `YamlFileGenerator(settings_class, indent_size=2)`

Low-level generator for the YAML string. Useful if you want to customise output without using `YamlSettingsPlus`.

```python
from psyplus import YamlFileGenerator
from config import MyAppConfig

gen = YamlFileGenerator(MyAppConfig)
gen.parse()
print(gen.get_yaml())
```

### `MarkdownDocGenerator(settings_class)`

Low-level generator for the Markdown string.

```python
from psyplus import MarkdownDocGenerator
from config import MyAppConfig

doc = MarkdownDocGenerator(MyAppConfig).generate()
```

---

## Defining your settings model

psyplus works with any standard `pydantic_settings.BaseSettings` subclass. The richer the metadata you provide on your fields, the more informative the generated YAML/Markdown will be.

### Useful `Field()` kwargs

| Kwarg | Shown in output as |
|---|---|
| `description="…"` | `# Description:` comment row |
| `title="…"` | Appended to the `## field_name - Title ###` header |
| `examples=[…]` | `# Example:` block with rendered YAML |
| `default=…` | `# Default:` comment row |
| `default_factory=lambda: …` | `# Default:` not shown (factory evaluated at generation time) |
| `max_length=…` / `gt=…` / etc. | `# Constraints:` comment row |

### Configuring env vars

Set `env_prefix` and `env_nested_delimiter` in `model_config` so that psyplus can generate correct `Env-var:` hints:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class MyConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_",
        env_nested_delimiter="__",
    )

    database_host: str = "localhost"
    # → Env-var: 'MYAPP_DATABASE_HOST'
```

For nested models the env var path is built as:
```
{env_prefix}{parent_key}{env_nested_delimiter}{child_key}
# e.g. MYAPP_DATABASE__HOST  (prefix="MYAPP_", delimiter="__")
```

#### Nullable fields

A nullable field (`Optional[int]`, `int | None`) shows its type as `int or null`. By default,
pydantic-settings can not set such a field to null through an env var: an `int` or `bool` field
fails validation, a `str` field gets the literal text `null`, and a list, dict or model field
silently keeps its default. Only the YAML file can set null then. Set `env_parse_none_str` to name
the env var value that means null:

```python
class MyConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_", env_parse_none_str="null")

    max_age_days: Optional[int] = 30
    # → Type:    int or null
    # → Env-var: 'MYAPP_MAX_AGE_DAYS' ('null' sets null)
```

For a nullable field whose default is not null, the `Env-var:` hint says which case applies:
`('null' sets null)` with `env_parse_none_str`, or `(can not set null, use null in the YAML file)`
without it. A field that defaults to null gets no hint, since leaving the env var unset already
gives null.

---

## Environment variable overrides

`load()` creates a thin dynamic subclass that adds the YAML file as a pydantic-settings source while keeping the normal env var source with higher priority. The effective source priority (highest → lowest) is:

1. **Environment variables** (respects `env_prefix` / `env_nested_delimiter`)
2. **YAML file** values
3. **Model defaults**

No changes to your settings class are required.

---

## Development

This project uses [PDM](https://pdm-project.org/) for dependency management.

```bash
git clone https://github.com/DZD-eV-Diabetes-Research/pydantic-settings-yaml-plus
cd pydantic-settings-yaml-plus
pdm install -G test
pdm run pytest
```

If you prefer plain pip (no PDM):

```bash
pip install -e ".[test]"
pytest
```

### Smoke test

To visually inspect the generated YAML and Markdown for all built-in test models, run:

```bash
pdm run smoke
```

This writes four files per model (YAML config template + Markdown reference) to `smoke_output/` and prints a preview of each to the terminal. The output is committed to the repository and linked from the [Example gallery](#example-gallery) section — re-run the script and commit the results whenever the generator logic changes.

```
smoke_output/
├── SimpleModel.yaml
├── SimpleModel.md
├── NestedModel.yaml
├── NestedModel.md
├── MultiNestedModel.yaml
├── MultiNestedModel.md
├── MyAppConfig.yaml
└── MyAppConfig.md
```

### Running tests with coverage

```bash
pdm run pytest tests/ --cov=psyplus --cov-report=term-missing
```

### PDM cheat-sheet

| Task | Command |
|---|---|
| Install all deps incl. test extras | `pdm install -G test` |
| Add a runtime dependency | `pdm add <package>` |
| Add a test-only dependency | `pdm add -G test <package>` |
| Update lock file | `pdm update` |
| Run any command in the PDM venv | `pdm run <command>` |
| Show installed packages | `pdm list` |

Tests are in `tests/` and cover utilities, field metadata, YAML generation, Markdown generation, and the full `YamlSettingsPlus` API. They run in CI against Python 3.12, 3.13, and 3.14.
