# Configuration Reference — `MultiNestedModel`

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

### `servers[*]` — `ServerItem` schema

---

### `servers[*].host`

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `MULTI_SERVERS[*]__HOST` |

---

### `servers[*].port`

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `80` |
| Environment variable | `MULTI_SERVERS[*]__PORT` |

---

## `server_map`

| Property | Value |
|---|---|
| Type | Dictionary of (str, Object (ServerItem)) |
| Required | No |
| Default | `{"primary": {"host": "primary.example.com", "port": 443}}` |
| Environment variable | `MULTI_SERVER_MAP` |

---

### `server_map[*]` — `ServerItem` schema

---

### `server_map[*].host`

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `MULTI_SERVER_MAP[*]__HOST` |

---

### `server_map[*].port`

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `80` |
| Environment variable | `MULTI_SERVER_MAP[*]__PORT` |

---
