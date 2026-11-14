"""Settings models that cover the ways env var names are built (see test_env_roundtrip.py)."""
from __future__ import annotations

from typing import Annotated, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- deep nesting -------------------------------------------------------
class Server(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Database(BaseModel):
    name: str = "db"
    server: Server = Server()
    tags: List[str] = []


class Deep(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    database: Database = Database()


# --- nested BaseSettings with its own prefix ----------------------------
class SubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUB_", env_nested_delimiter="__")
    host: str = "subhost"
    port: int = 1


class WithSubSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    sub: SubSettings = SubSettings()


# --- collections --------------------------------------------------------
class Item(BaseModel):
    name: str
    size: int = 1


class Collections(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    tags: List[str] = ["a", "b"]
    numbers: List[int] = [1, 2]
    items: List[Item] = [Item(name="i0"), Item(name="i1")]
    labels: Dict[str, str] = {"env": "prod"}
    item_map: Dict[str, Item] = {"first": Item(name="f")}


# --- optional / union / annotated ---------------------------------------
class Cache(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379


class OtherBackend(BaseModel):
    url: str = "x://"


class Edge(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    cache: Optional[Cache] = None
    cache2: Optional[Cache] = Cache()
    backend: Union[Cache, OtherBackend] = Cache()
    annotated: Annotated[Cache, Field(description="annotated sub-model")] = Cache()
    pipe_opt: Cache | None = None


# --- no nested delimiter -------------------------------------------------
class NoDelim(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")
    database: Database = Database()
    tags: List[str] = ["a"]


# --- case sensitive ------------------------------------------------------
class CaseSens(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_nested_delimiter="__", case_sensitive=True
    )
    log_level: str = "INFO"
    database: Database = Database()


# --- single underscore delimiter with max split ---------------------------
class LlmCfg(BaseModel):
    llm_provider: str = "none"


class MaxSplit(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_nested_delimiter="_", env_nested_max_split=1
    )
    generation: LlmCfg = LlmCfg()
