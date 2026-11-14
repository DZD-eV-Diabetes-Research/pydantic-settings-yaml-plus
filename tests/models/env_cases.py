"""Settings models that cover the ways env var names are built (see test_env_roundtrip.py)."""
from __future__ import annotations

from typing import Annotated, Dict, List, Optional, Union

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
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


# --- aliases: the YAML key and the env var name are the validation alias ---
class AliasSub(BaseModel):
    sub_field: str = Field("d", alias="subAlias")
    plain: int = 1
    choice_field: str = Field("c", validation_alias=AliasChoices("subChoice", "sub_choice_2"))


class AliasItem(BaseModel):
    item_name: str = Field("n", alias="itemName")
    size: int = Field(1, alias="item_size")


class Aliases(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    my_field: str = Field("x", alias="MY_ALIAS")
    v_field: int = Field(1, validation_alias="V_ALIAS")
    c_field: str = Field("x", validation_alias=AliasChoices("C_ONE", "C_TWO"))
    cp_field: str = Field("x", validation_alias=AliasChoices(AliasPath("o", "i"), "C_STR"))
    p_field: str = Field("x", validation_alias=AliasPath("outer", "inner"))
    s_field: str = Field("x", serialization_alias="SER")
    plain: str = "p"
    sub: AliasSub = AliasSub()
    asub: AliasSub = Field(AliasSub(), alias="theSub")
    opt_sub: Optional[AliasSub] = AliasSub()
    items: List[AliasItem] = [AliasItem()]
    item_map: Dict[str, AliasItem] = {"first": AliasItem()}
    required_field: str = Field(alias="REQ")


class AliasesPrefixAlias(Aliases):
    model_config = SettingsConfigDict(env_prefix_target="alias")


class AliasesPrefixAll(Aliases):
    model_config = SettingsConfigDict(env_prefix_target="all")


class AliasesCaseSens(Aliases):
    model_config = SettingsConfigDict(case_sensitive=True)


class AliasesByName(Aliases):
    model_config = SettingsConfigDict(populate_by_name=True)


# --- alias_generator: every field gets a camelCase alias ------------------
class CamelLeaf(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    inner_value: str = "d"
    count: int = 1


class CamelMid(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    mid_value: str = "m"
    leaf_model: CamelLeaf = CamelLeaf()
    opt_leaf: Optional[CamelLeaf] = CamelLeaf()


class Camel(BaseSettings):
    model_config = SettingsConfigDict(
        alias_generator=to_camel, env_prefix="APP_", env_nested_delimiter="__"
    )
    log_level: str = "INFO"
    port: int = 8080
    mid_model: CamelMid = CamelMid()
    leaves: List[CamelLeaf] = [CamelLeaf()]
    leaf_map: Dict[str, CamelLeaf] = {"k": CamelLeaf()}


class CamelPrefixAll(Camel):
    model_config = SettingsConfigDict(env_prefix_target="all")


class CamelCaseSens(Camel):
    model_config = SettingsConfigDict(case_sensitive=True)


# --- aliases on a Union of models and on a dict ----------------------------
class AliasCache(BaseModel):
    host_name: str = Field("h", alias="hostName")
    port: int = Field(1, alias="cache_port")


class AliasOther(BaseModel):
    url: str = Field("u", alias="the_url")


class UnionAliases(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    backend: Union[AliasCache, AliasOther] = Field(AliasCache(), alias="theBackend")
    opt: Optional[Union[AliasCache, AliasOther]] = Field(None, alias="optU")
    labels: Dict[str, str] = Field({"a": "b"}, alias="theLabels")
    plain_labels: Dict[str, str] = {"a": "b"}


class UnionAliasesByName(UnionAliases):
    model_config = SettingsConfigDict(populate_by_name=True)
