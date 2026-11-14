# Configuration Reference: `MultiNestedModel`

This document is auto-generated from the pydantic-settings model. All settings can be provided via the YAML config file or overridden with environment variables.

---

## `servers`

| Property | Value |
|---|---|
| Type | List of Object (ServerItem) |
| Required | No |
| Default | `[{"host": "a.example.com", "port": 80}, {"host": "b.example.com", "port": 80}]` |
| Environment variable | `MULTI_SERVERS` |

---

### `servers[*]`: `ServerItem` schema

---

### `servers[*].host`

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |

---

### `servers[*].port`

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `80` |

---

## `server_map`

| Property | Value |
|---|---|
| Type | Dictionary of (str, Object (ServerItem)) |
| Required | No |
| Default | `{"primary": {"host": "primary.example.com", "port": 443}}` |
| Environment variable | `MULTI_SERVER_MAP` (`MULTI_SERVER_MAP__<dict-key>` sets one entry, its key arrives in lower case) |

---

### `server_map[*]`: `ServerItem` schema

---

### `server_map[*].host`

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `MULTI_SERVER_MAP__<dict-key>__HOST` |

---

### `server_map[*].port`

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `80` |
| Environment variable | `MULTI_SERVER_MAP__<dict-key>__PORT` |

---
