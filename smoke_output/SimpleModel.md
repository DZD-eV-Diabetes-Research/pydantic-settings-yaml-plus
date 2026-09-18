# Configuration Reference — `SimpleModel`

This document is auto-generated from the pydantic-settings model. All settings can be provided via the YAML config file or overridden with environment variables.

---

## `a_string`

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Default | `"hello"` |
| Environment variable | `SIMPLE_A_STRING` |

---

## `an_int`

| Property | Value |
|---|---|
| Type | int |
| Required | No |
| Default | `42` |
| Environment variable | `SIMPLE_AN_INT` |

---

## `a_float`

| Property | Value |
|---|---|
| Type | float |
| Required | No |
| Default | `3.14` |
| Environment variable | `SIMPLE_A_FLOAT` |

---

## `a_bool`

| Property | Value |
|---|---|
| Type | bool |
| Required | No |
| Default | `true` |
| Environment variable | `SIMPLE_A_BOOL` |

---

## `optional_none`

| Property | Value |
|---|---|
| Type | str or null |
| Required | No |
| Default | `null` |
| Environment variable | `SIMPLE_OPTIONAL_NONE` |

---

## `literal_field`

| Property | Value |
|---|---|
| Type | Enum |
| Required | No |
| Default | `"A"` |
| Allowed values | `A` · `B` · `C` |
| Environment variable | `SIMPLE_LITERAL_FIELD` |

---

## `string_list`

| Property | Value |
|---|---|
| Type | List of str |
| Required | No |
| Default | `["x", "y"]` |
| Environment variable | `SIMPLE_STRING_LIST` |

---

## `string_dict`

| Property | Value |
|---|---|
| Type | Dictionary of (str, int) |
| Required | No |
| Default | `{"one": 1}` |
| Environment variable | `SIMPLE_STRING_DICT` |

---

## `required_string`

| Property | Value |
|---|---|
| Type | str |
| Required | **Yes** |
| Environment variable | `SIMPLE_REQUIRED_STRING` |

---

## `required_list`

| Property | Value |
|---|---|
| Type | List of str |
| Required | **Yes** |
| Environment variable | `SIMPLE_REQUIRED_LIST` |

---

## `fully_documented`

*Great String*

A fully documented optional string field.

| Property | Value |
|---|---|
| Type | str or null |
| Required | No |
| Default | `"default_value"` |
| Constraints | MaxLen(max_length=100) |
| Environment variable | `SIMPLE_FULLY_DOCUMENTED` (can not set null, use `null` in the YAML file) |

**Examples:**

*Example 1:*

```yaml
fully_documented: ex1
```

*Example 2:*

```yaml
fully_documented: ex2
```

---

## `with_factory`

Uses a default_factory lambda.

| Property | Value |
|---|---|
| Type | str |
| Required | No |
| Environment variable | `SIMPLE_WITH_FACTORY` |

---
