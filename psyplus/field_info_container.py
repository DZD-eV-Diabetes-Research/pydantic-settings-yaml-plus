from dataclasses import dataclass
from pydantic import fields
from pydantic_settings import BaseSettings
import yaml
from typing import List, Any, Dict, Type, Literal
from operator import itemgetter

# https://docs.pydantic.dev/2.5/api/json_schema/#pydantic.json_schema.GenerateJsonSchema
JSON_BASIC_TYPES = Literal["boolean", "number", "string", "array", "object"]

# https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1
JSON_SUBSCHEMAS = Literal["allOf", "anyOf", "oneOf", "not"]


@dataclass
class FieldInfoContainer:
    """A wrapper class to simplify access to certain (meta-)informations in/of a `pydantic.fields.FieldInfo` instance.
    Intended for internal use only"""

    field_name: str
    field_info: fields.FieldInfo
    container_model_hierachy: List[Dict[Type[BaseSettings], str]]
    # env_var_name: str

    @property
    def parent_container_model(self) -> BaseSettings:
        """The pydantic settings model that contains the field"""
        return list(self.container_model_hierachy[-1].keys())[0]

    @property
    def base_container_model(self) -> BaseSettings:
        """The root model that contains the container with the field. Can be the same as 'parent_container_model'"""
        return list(self.container_model_hierachy[0].keys())[0]

    @property
    def path(self) -> List[str]:
        """If the field has parent containers, return the field name of the parent container and its parents.

        Returns:
            str: The path as a list of strings
        """
        return [
            list(parent_field.values())[0]
            for parent_field in self.container_model_hierachy
        ]

    @property
    def env_var_name(self) -> str:
        env_var_delimiter: str = (
            self.base_container_model.model_config["env_nested_delimiter"]
            if self.base_container_model.model_config["env_nested_delimiter"]
            else "__"
        )
        env_prefix: str = (
            self.base_container_model.model_config["env_prefix"]
            if self.base_container_model.model_config["env_prefix"]
            else ""
        )
        keys: List[str] = [
            list(parent_model.values())[0]
            for parent_model in self.container_model_hierachy
        ]
        return env_var_delimiter.join([env_prefix + k.upper() for k in keys])

    @property
    def json_model_schema(self) -> Dict:
        return self.parent_container_model.model_json_schema()["properties"][
            self.field_name
        ]

    @property
    def field_value_type_name(
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
                # this is just a "<some type> or None"-case. we can simplfiy this, as the "or None" parts is covered by "is_requiried"
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

        return self.json_model_schema["type"]

    @property
    def field_value_enum(
        self,
    ) -> List[Any] | None:
        """If the value has a fixed list of allowed values, this return the list of these values

        Returns:
            List[Any]: List of allowed values for the field
        """
        if (
            self.field_info is None
            or "enum"
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
            field_info_container.container_model_hierachy.append(
                {model_walking_current: parent_key}
            )

            if key in model_walking_current.model_fields:
                # we are reached the direct parent container
                field_info_container.field_info = model_walking_current.model_fields[
                    key
                ]
            elif key != parent_key:
                # we are still in a grand-*-parent container
                model_walking_current = model_walking_current.model_fields[
                    parent_key
                ].annotation

        return field_info_container
