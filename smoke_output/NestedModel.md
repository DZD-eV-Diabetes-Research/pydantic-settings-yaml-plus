# Configuration Reference — `NestedModel`

This document is auto-generated from the pydantic-settings model. All settings can be provided via the YAML config file or overridden with environment variables.

---

## `app_name`

Display name of the application

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Default | `"My App"` |
| Environment variable | `APP_APP_NAME` |

---

## `log_level`

| Property | Value |
|---|---|
| Type | Enum |
| Required | No |
| Default | `"INFO"` |
| Allowed values | `DEBUG` · `INFO` · `WARNING` · `ERROR` |
| Environment variable | `APP_LOG_LEVEL` |

---

## `database`

Primary database settings

| Property | Value |
|---|---|
| Type | Object (DatabaseConfig) |
| Required | **Yes** |
| Environment variable | `APP_DATABASE` |

---

### `database.host`

Database host

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Default | `"localhost"` |
| Environment variable | `APP_DATABASE__HOST` |

---

### `database.port`

Database port

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `5432` |
| Environment variable | `APP_DATABASE__PORT` |

---

### `database.name`

Database name (required)

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `APP_DATABASE__NAME` |

---

### `database.tags`

| Property | Value |
|---|---|
| Type | List of str |
| Required | No |
| Default | `[]` |
| Environment variable | `APP_DATABASE__TAGS` |

---

## `cache`

| Property | Value |
|---|---|
| Type | Object (CacheConfig) or null |
| Required | No |
| Default | `null` |
| Environment variable | `APP_CACHE` |

---

### `cache.host`

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Default | `"127.0.0.1"` |
| Environment variable | `APP_CACHE__HOST` |

---

### `cache.port`

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `6379` |
| Environment variable | `APP_CACHE__PORT` |

---

## `storage_dir`

Directory for application state.

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Environment variable | `APP_STORAGE_DIR` |

---

## `admin_password`

Initial admin password (required)

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `APP_ADMIN_PASSWORD` |

---
