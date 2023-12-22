from dataclasses import dataclass
from pydantic import fields, BaseModel
from pydantic_settings import BaseSettings
import yaml
import datetime
from typing import (
    List,
    Any,
    Dict,
    Type,
    Literal,
    get_origin,
    get_args,
    Optional,
    get_type_hints,
)
from operator import itemgetter
from psyplus.utils import is_typingOptional, get_typingOptionalArg

# from psyplus.yaml_pydantic_metadata_comment_injector import ListIndex, DictKey
import datetime
from pydantic import (
    PastDate,
    FutureDate,
    PastDatetime,
    FutureDatetime,
    AwareDatetime,
    NaiveDatetime,
)

from psyplus.model_path_2_yaml_path_mapper import (
    map_pydantic_settings_to_yaml_path,
    ModelPathMap,
)

# https://docs.pydantic.dev/2.5/api/json_schema/#pydantic.json_schema.GenerateJsonSchema
JSON_BASIC_TYPES = Literal["boolean", "number", "string", "array", "object"]

# https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1
JSON_SUBSCHEMAS = Literal["allOf", "anyOf", "oneOf", "not"]

PYTHON_SCALAR_TYPES = [
    int,
    float,
    str,
    bool,
    datetime.time,
    datetime.date,
    datetime.datetime,
    PastDate,
    FutureDate,
    PastDatetime,
    FutureDatetime,
    AwareDatetime,
    NaiveDatetime,
]

ENV_VAR_LISTINDEX_PLACEHOLDER: str = "<LISTINDEX>"
ENV_VAR_DICTKEY_PLACEHOLDER: str = "<DICTKEY>"


@dataclass
class FieldInfoContainer:
    """A wrapper class to simplify access to certain (meta-)informations in/of a `pydantic.fields.FieldInfo` instance.
    Intended for internal use only"""

    field_name: str
    yaml_path_2_pydantic_settings_map: ModelPathMap

    def get_env_var_scheme(
        self, env_var_delimiter: str = "__", prefix: str = ""
    ) -> str:
        result = []
        for member in self.yaml_path_2_pydantic_settings_map.fragments:
            if isinstance(member.parent_content, (BaseModel, BaseSettings)):
                result.append(member.yaml_path_key.upper())
            elif type(member.parent_content) == list:
                result.append(ENV_VAR_LISTINDEX_PLACEHOLDER)
            elif type(member.parent_content) == dict:
                result.append(ENV_VAR_DICTKEY_PLACEHOLDER)
            else:
                # unsupported type; we can not generate a env var
                return None
        return prefix + env_var_delimiter.join(result)

    @property
    def pydantic_field_info(self):
        return self.yaml_path_2_pydantic_settings_map.enditem.field_info

    @property
    def parent_container_model(self) -> BaseSettings | BaseModel:
        """The pydantic settings model that contains the field"""
        return self.yaml_path_2_pydantic_settings_map.enditem.parent_content
        print("self.container_model_hierachy", self.yaml_path_2_pydantic_settings_map)
        for parent_obj in reversed(self.yaml_path_2_pydantic_settings_map):
            if isinstance(parent_obj.model_instance, (BaseSettings, BaseModel)):
                return parent_obj.model_instance
        # return list(self.container_model_hierachy[-1].keys())[0]

    @property
    def root_container_model(self) -> BaseSettings | BaseModel:
        """The root model that contains the container with the field. Can be the same as 'parent_container_model'"""
        return self.yaml_path_2_pydantic_settings_map.rootitem.source_pydantic_model

    @property
    def path(self) -> List[str]:
        """If the field has parent containers, return the tfield name of the parent container and its parens.

        Returns:
            str: The path as a list of strings
        """
        return [
            list(parent_field.values())[0]
            for parent_field in self.yaml_path_2_pydantic_settings_map
        ]

    @property
    def env_var_name(self) -> str:
        env_var_delimiter: str = self.root_container_model.model_config.get(
            "env_nested_delimiter", "__"
        )
        if env_var_delimiter is None:
            env_var_delimiter = "__"
        print("env_var_delimiter", env_var_delimiter)
        env_prefix: str = self.root_container_model.model_config.get("env_prefix", "__")
        if env_prefix is None:
            env_prefix = ""
        return self.get_env_var_scheme(
            env_var_delimiter=env_var_delimiter, prefix=env_prefix
        )

    @property
    def json_model_schema(self) -> Dict:
        return self.parent_container_model.model_json_schema()["properties"][
            self.field_name
        ]

    @property
    def field_value_type_name(
        self,
    ) -> str:
        def stringifiy_annotation(annotation) -> str:
            if type(annotation) == tuple:
                res = []
                for item in annotation:
                    res.append(stringifiy_annotation(item))
                if res:
                    return ",".join(res)
            if is_typingOptional(annotation):
                return stringifiy_annotation(get_typingOptionalArg(annotation))
            elif annotation == Any:
                return None
            elif annotation in PYTHON_SCALAR_TYPES:
                return annotation.__name__
            elif get_origin(annotation) == list or annotation == list:
                list_annotation_args = get_args(annotation)
                if list_annotation_args:
                    return "List of " + stringifiy_annotation(list_annotation_args)
                else:
                    return "List"
            elif get_origin(annotation) == dict or annotation == dict:
                dict_annotation_args = get_args(annotation)
                if dict_annotation_args:
                    return (
                        f"Dictonary of ({stringifiy_annotation(get_args(annotation))})"
                    )
                else:
                    return "Dictonary"
            elif get_origin(annotation) == Literal:
                return "Enum"
            else:
                return "Object"

        return stringifiy_annotation(self.pydantic_field_info.annotation)

    @property
    def field_value_json_type_name(
        self,
    ) -> JSON_BASIC_TYPES | Dict[JSON_SUBSCHEMAS, JSON_BASIC_TYPES] | None:
        """The type the value has to be. based on https://docs.pydantic.dev/2.5/api/json_schema/#pydantic.json_schema.GenerateJsonSchema and https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1
        e.g.
            "String"
            "oneOf("type":"String", "type": "Int")
        Returns:
            str: name of the field type based on https://json-schema.org/draft/2020-12/json-schema-core#name-instance-data-model
        """

        # https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1

        json_schemas_initiators = {
            "allOf",
            "anyOf",
            "oneOf",
            "not",
        }

        if not json_schemas_initiators.isdisjoint(self.json_model_schema.keys()):
            # {'anyOf': [{'type': 'string'}, {'type': 'null'}]}
            if (
                "anyOf" in self.json_model_schema
                and len(self.json_model_schema["anyOf"]) == 2
                and {"type": "null"} in self.json_model_schema["anyOf"]
            ):
                # this is just a "<some type> or None"-case. we can simplfiy this, as the "or None" Information is covered by "self.field_info.is_required()"
                return next(
                    (
                        item["type"]
                        for item in self.json_model_schema["anyOf"]
                        if item.get("type") != "null"
                    ),
                    None,
                )
            else:
                # we have a more complex type case here
                json_subscheme_type = {}
                for jsi in json_schemas_initiators:
                    if jsi in self.json_model_schema:
                        json_subscheme_type[jsi] = self.json_model_schema[jsi]
                return json_subscheme_type
        # default types
        if "type" in self.json_model_schema:
            return self.json_model_schema["type"]
        return None

    @property
    def field_value_enum(
        self,
    ) -> List[Any] | None:
        """If the value has a fixed list of allowed values, this return the list of these values

        Returns:
            List[Any]: List of allowed values for the field
        """
        print("self.parent_container_model", self.parent_container_model)
        if self.pydantic_field_info is None or (
            self.field_name
            in self.parent_container_model.model_json_schema()["properties"]
            and "enum"
            not in self.parent_container_model.model_json_schema()["properties"][
                self.field_name
            ]
        ):
            return None

        return self.parent_container_model.model_json_schema()["properties"][
            self.field_name
        ]["enum"]

    @classmethod
    def from_base_model_and_key(
        cls,
        key: str,
        base_settings_model: Type[BaseSettings],
        parents_key_path: List[str] = [],
    ) -> "FieldInfoContainer":
        field_info_container = cls(
            field_name=key,
            field_info=None,
            container_model_hierachy=[],
        )
        model_walking_current = base_settings_model
        for parent_key in list(reversed((parents_key_path))) + [key]:
            field_info_container.yaml_path_2_pydantic_settings_map.append(
                {model_walking_current: parent_key}
            )
            if (
                hasattr(model_walking_current, "model_fields")
                and key in model_walking_current.model_fields
            ):
                # we are reached the direct parent container
                field_info_container.pydantic_field_info = (
                    model_walking_current.model_fields[key]
                )
            elif key != parent_key and key in parents_key_path:
                # we are still in a grand-*-parent container
                model_walking_current = model_walking_current.model_fields[
                    parent_key
                ].annotation

        return field_info_container
