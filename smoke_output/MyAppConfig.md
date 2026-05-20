# Configuration Reference — `MyAppConfig`

This document is auto-generated from the pydantic-settings model. All settings can be provided via the YAML config file or overridden with environment variables.

---

## `log_level`

| Property | Value |
|---|---|
| Type | Enum |
| Required | No |
| Default | `"INFO"` |
| Allowed values | `INFO` · `DEBUG` |
| Environment variable | `APP_LOG_LEVEL` |

---

## `app_name`

The display name of the app

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Default | `"THE APP"` |
| Environment variable | `APP_APP_NAME` |

**Examples:**

*Example 1:*

```yaml
app_name: THAT APP
```

*Example 2:*

```yaml
app_name: THIS APP
```

---

## `storage_dir`

A directory to store files for the app.

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Environment variable | `APP_STORAGE_DIR` |

---

## `admin_pw`

The init password for the admin account

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `APP_ADMIN_PW` |

---

## `database_server`

The settings for the database server

| Property | Value |
|---|---|
| Type | Object (DatabaseServerSettings) |
| Required | **Yes** |
| Environment variable | `APP_DATABASE_SERVER` |

**Examples:**

```yaml
database_server:
  host: db.company.org
  port: 1234
  database_names:
  - db1
  - db2
```

---

### `database_server.host`

The hostname the database will be available at

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Default | `"localhost"` |
| Environment variable | `APP_DATABASE_SERVER__HOST` |

---

### `database_server.port`

The port to connect to the database

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `5678` |
| Environment variable | `APP_DATABASE_SERVER__PORT` |

---

### `database_server.database_names`

The names of the databases to use

| Property | Value |
|---|---|
| Type | List of str |
| Required | **Yes** |
| Environment variable | `APP_DATABASE_SERVER__DATABASE_NAMES` |

**Examples:**

```yaml
database_names:
- mydb
- theotherdb
```

---

## `init_values`

| Property | Value |
|---|---|
| Type | Dictionary of (str, str) |
| Required | **Yes** |
| Environment variable | `APP_INIT_VALUES` |

---
