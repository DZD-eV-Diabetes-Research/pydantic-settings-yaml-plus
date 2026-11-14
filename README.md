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
    - [Single list elements](#single-list-elements)
  - [Development](#development)
    - [Smoke test](#smoke-test)
    - [Running tests with coverage](#running-tests-with-coverage)
    - [PDM cheat-sheet](#pdm-cheat-sheet)

---

## Features

- **Generate documented YAML** — each field gets a comment block with its type, required flag, default value, allowed enum values, corresponding environment variable, description, and examples.
- **Nested models** — `BaseModel` sub-models are rendered as indented YAML sections with full comment headers.
- **Read back with env-var override** — `load()` loads the YAML file and still applies environment variable overrides using pydantic-settings' standard machinery.
- **Single list elements from env vars:** `load()` also reads env vars like `APP_SERVERS__0__HOST` that change one element of a list from the YAML file.
- **Markdown docs** — generate a Markdown reference document straight from your settings class.
- **Zero boilerplate** — define your settings in a standard `pydantic_settings.BaseSettings` subclass; psyplus does the rest.

---

## Installation

```bash
pip install psyplus
```

**Requirements:** Python ≥ 3.11, pydantic ≥ 2.10, pydantic-settings ≥ 2.13.1, ruamel.yaml ≥ 0.17.5, PyYAML ≥ 6.0.1

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
admin_pw:

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
  #              'APP_DATABASE_SERVER__DATABASE_NAMES__<list-index>' (one element, 0 is the first; psyplus load() only)
  # Description: The names of the databases to use
  # Example:
  #  >database_names:
  #  >- mydb
  #  >- theotherdb
  database_names:

# ## init_values ###
# Type:     Dictionary of (str, str)
# Required: True
# Env-var:  'APP_INIT_VALUES'
init_values:
```

Required fields without a default are written with an empty value (`admin_pw:`, which YAML reads as null),
whatever their type. A required sub-model without a default shows its fields, so the structure is
visible, with its own required fields empty. The `Required: True` comment marks every value to fill in.
Until that is done, `load()` raises a pydantic `ValidationError` that names each empty required field,
so an app does not start with an unfilled config. (A required `Optional[...]` field is the exception:
null is a valid value for it.)

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

`load()` returns an instance of your model class itself (`type(config) is MyAppConfig`), validated once, exactly as if you had called `MyAppConfig()`. It compares equal to and pickles like any other `MyAppConfig` instance.

`load()` honours environment variable overrides through pydantic-settings' standard source priority: **env vars beat YAML values**. For example:

```bash
export APP_LOG_LEVEL=DEBUG
```

…will make `config.log_level == "DEBUG"` even if the YAML file says `INFO`.

> **Tip:** if you prefer to keep psyplus out of your runtime path, configure `yaml_file` directly in your model and add a YAML source (setting `yaml_file` alone is not enough, pydantic-settings does not read it by default):
>
> ```python
> from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
>
> class MyAppConfig(BaseSettings):
>     model_config = SettingsConfigDict(
>         yaml_file="config.yaml",
>         env_prefix="APP_",
>         env_nested_delimiter="__",
>     )
>
>     @classmethod
>     def settings_customise_sources(
>         cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
>     ):
>         return (
>             init_settings, env_settings, dotenv_settings, file_secret_settings,
>             YamlConfigSettingsSource(settings_cls),
>         )
>
> config = MyAppConfig()  # reads YAML + env vars
> ```
>
> Such a model still works with `load()`: psyplus then reads its own `file_path` in place of `yaml_file` (see [Environment variable overrides](#environment-variable-overrides)).

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

The fields of a nested model get their own sections, headed by their full path (`database.host`,
`servers[*].port`). A field that holds one of several models (`Union[Cat, Dog]`) gets one section
per model, labelled `option 1 of 2` and so on. Markdown has no headings below level 6, so deeper
fields stay at level 6 and the path in the heading shows where they belong.

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
| `load() → model` | Load `file_path`, apply env var overrides (including [single list elements](#single-list-elements)), return a validated instance of `model`. |

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
| `default_factory=lambda: …` | `# Default:` not shown (factory evaluated at generation time, its result is the value in the YAML file) |
| `default_factory=lambda data: …` | Same, the factory gets the values of the fields defined before it. If it needs a required value without a default, the field is written empty with a note to remove the key |
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

What pydantic-settings can set through env vars, and what the generated files show:

| Field | Env var example | Behaviour |
|---|---|---|
| Field of a nested model, any depth | `MYAPP_DATABASE__SERVER__HOST=db` | Sets only this value. The other values from the YAML file stay. |
| Whole nested model | `MYAPP_DATABASE='{"name": "x"}'` | JSON, merged into the values from the YAML file. |
| List (`List[str]`, `List[SubModel]`, tuple, set) | `MYAPP_HOSTS='["a", "b"]'` | JSON, replaces the whole list. |
| One list element, or a field of it | `MYAPP_HOSTS__1=b`, `MYAPP_SERVERS__0__PORT=8080` | Only with `load()`, see [Single list elements](#single-list-elements). `<list-index>` stands for the position, 0 is the first. Changes this element of the list from the YAML file, the other elements stay. |
| Dict value (`Dict[str, ...]`) | `MYAPP_LABELS__team=core` | `<dict-key>` stands for the key. Env var names are case-insensitive by default, so the key arrives in lower case, and the generated files say so next to the env var of the dict field. Keys in a JSON value keep their case. |

Only the root model's `env_prefix` and `env_nested_delimiter` count. A nested `BaseSettings`
sub-model's own `env_prefix` is not used for its fields. Without `env_nested_delimiter`, nested
fields have no env var of their own and can only be set through the JSON value of the top-level
field. With `case_sensitive=True`, the env var names keep the case of the field names. With
`env_nested_max_split`, only fields that many levels below the top-level field have an env var
(a list index counts as a level).
A sub-model that defaults to null has no fields in the YAML file, so its comment lists the env
vars of its fields under `Env-vars of the sub-fields:`. For a field that holds one of several
models (`Union[Cat, Dog]`), this list covers the fields of every model.

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

### Fields with an alias

pydantic-settings reads the YAML file and the env vars by a field's validation alias, so psyplus
uses it as the YAML key, in the YAML path and in the env var name. That covers `alias=`,
`validation_alias=` and an `alias_generator` such as `to_camel`, also with `populate_by_name=True`.
A `serialization_alias` changes nothing.

```python
class Database(BaseModel):
    host_name: str = Field("localhost", alias="hostName")

class MyConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_", env_nested_delimiter="__")

    log_level: str = Field("INFO", alias="logLevel")
    # → YAML key: logLevel, Env-var: 'LOGLEVEL'
    database: Database = Database()
    # → YAML path: database.hostName, Env-var: 'MYAPP_DATABASE__HOSTNAME'
```

| Field | YAML key | Env var |
|---|---|---|
| `alias="logLevel"` or `validation_alias="logLevel"` | `logLevel` | `LOGLEVEL` |
| `validation_alias=AliasChoices("a", "b")` | `a`, the first string choice | `A` |
| `validation_alias=AliasPath("database", "host")` | `host` inside a `database` map | none |
| `serialization_alias="x"` only | the field name | as without an alias |

* **Prefix:** pydantic-settings puts `env_prefix` in front of an alias only when the model sets
  `env_prefix_target="alias"` or `"all"`. With the default `"variable"` only field names get it.
  What counts is the top-level field: `MYAPP_DATABASE__HOSTNAME` above gets the prefix because
  `database` has no alias.
* **Case:** without `case_sensitive=True` env var names arrive in lower case, and
  pydantic-settings matches them back to a camelCase key only along plain sub-model fields. Below a
  dict, a Union of models, or an `Optional` sub-model deeper down, a key with upper case letters can
  not be set through its own env var, so none is shown there. The JSON value of the field above
  still works.
* **`populate_by_name`:** below a top-level field with an alias, the fields and dict entries have
  no env var of their own. pydantic-settings files them under the field name, which clashes with the alias key
  from the YAML file. The JSON value of the top-level field still works.
* **`AliasPath`:** a path of names is written as nested maps, which several fields may share. A
  path with a list index (`AliasPath("servers", 0)`) or one that clashes with another key is not
  written; its comment block says where to add it. No env var sets an `AliasPath` field:
  pydantic-settings would read each element of the path as an env var of its own.
* **Alias and validation alias differ:** pydantic-settings reads a top-level field from the YAML
  file only under its `alias`. When validation expects another name (`alias="a",
  validation_alias="b"`, an `alias_generator` next to an explicit `validation_alias`, or
  `validate_by_alias=False`), no key works, so the field is left out of the YAML file. A note in
  the YAML file and in the Markdown doc says so. Set it through its env var instead.

---

## Environment variable overrides

`load()` uses the same sources pydantic-settings uses for your model and adds the YAML file as the lowest priority source, just above the field defaults. For a model without its own `settings_customise_sources` the effective source priority (highest → lowest) is:

1. **Environment variables** (respects `env_prefix` / `env_nested_delimiter`)
2. **`.env` file** (if the model sets `env_file`)
3. **Secrets directory** (if the model sets `secrets_dir`)
4. **YAML file** values
5. **Model defaults**

No changes to your settings class are required.

If your model defines `settings_customise_sources`, `load()` respects it: the YAML file is added after the sources it returns, and a source it leaves out stays out. A model that drops `env_settings`, for example, ignores env vars in `load()` too. If it already returns a `YamlConfigSettingsSource`, `load()` adds no second one but reads `file_path` through it, at the position your model chose.

Command line parsing configured in `model_config` (`cli_parse_args`, `cli_settings_source`) also applies to `load()`, with the command line beating all other sources.

A missing YAML file is not an error: `load()` then returns the model defaults plus whatever the env vars, the `.env` file and the secrets directory set.

### Single list elements

pydantic-settings itself can only replace a whole list through an env var (`APP_SERVERS='[{"host": "a"}]'`). `load()` also reads env vars that address one element by its position, in the environment and in the `.env` file:

```bash
export APP_SERVERS__0__HOST=db.internal   # field of the first element
export APP_TAGS__1=beta                   # second element of a List[str]
export APP_GROUPS__admins__0=ann          # list inside a dict
export APP_MATRIX__1__0=7                 # list inside a list
```

The generated YAML comments and Markdown docs show these names with `<list-index>` in place of the position (`APP_SERVERS__<list-index>__HOST`). They work with `load()` only: a model instantiated directly (`MyAppConfig()`) reads them the way pydantic-settings does, which fails list validation.

The env var changes the list that the lower priority sources provide (usually the YAML file) instead of replacing it:

- **Index below the list length:** changes that element. The fields of an element model are merged into it (`APP_SERVERS__0__HOST` keeps the element's `port`), the same goes for a JSON object (`APP_SERVERS__0='{"host": "x"}'`). Any other value replaces the element.
- **Index equal to the list length:** adds an element. Several new elements need consecutive indices (2, 3, 4 for a list of two). A new element that is a model needs its required fields set too.
- **Index further beyond the end:** `load()` fails with an error that names the env var.
- **List not in the YAML file:** the env var changes the field's default list. A field without a default (or with `null`) starts as an empty list, so its indices start at 0.
- **Aliases:** the list is found in the YAML file under the field name or any of its aliases, and the changed list stays under that key.
- **Whole list and elements together:** an index env var changes the whole list value from the same place (`APP_TAGS='["a", "b"]'` plus `APP_TAGS__1=c` gives `["a", "c"]`). A whole value that is not a JSON list there (a comma separated string for a `NoDecode` field, for example) can not be changed this way, `load()` fails with an error. A whole list from a higher priority source replaces everything below it, as usual.
- **Not a list index:** `-1` or `01` where a list is expected is an error that names the env var. Other names (`APP_TAGS__NAME`) are left to pydantic-settings, as without psyplus.
- **Tuples and sets** work like lists. For a set, the index counts the elements in the order the YAML file lists them.

Only the env and `.env` sources that `load()` hands to your model's `settings_customise_sources` (`env_settings`, `dotenv_settings`) read list indices. A source your model builds itself (`EnvSettingsSource(settings_cls, env_prefix=...)`) works as pydantic-settings makes it, without list index support.

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

This writes two files per model (YAML config template + Markdown reference) to `smoke_output/` and prints a preview of each to the terminal. The output is committed to the repository and linked from the [Example gallery](#example-gallery) section. Re-run the script and commit the results whenever the generator logic changes.

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
