import typing
import asyncio
from typing import (
    List,
    Any,
    Dict,
    Union,
    Literal,
    Tuple,
    Type,
    Generator,
    get_type_hints,
    Optional,
    Mapping,
    Awaitable,
)
import inspect
from functools import singledispatch
from pydantic import BaseModel, fields
import pydantic
from pydantic_settings import BaseSettings
from pathlib import Path, PurePath
import yaml
from dataclasses import dataclass


# ToDo: Wrap that class up and migrate that into a proper selfcontained python module
# * Add generate markdown function
# * complete _generate_file() with all parameters


# https://docs.pydantic.dev/2.5/api/json_schema/#pydantic.json_schema.GenerateJsonSchema
JSON_BASIC_TYPES = Literal["boolean", "number", "string", "array", "object"]

# https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1
JSON_SUBSCHEMAS = Literal["allOf", "anyOf", "oneOf", "not"]


class YamlSettings:
    @dataclass
    class FieldInfoContainer:
        field_name: str
        field_schema: fields.FieldInfo = None
        container_model: BaseModel = None
        env_var_name: str = None

        @property
        def field_value_type_name(
            self,
        ) -> JSON_BASIC_TYPES | Dict[JSON_SUBSCHEMAS, JSON_BASIC_TYPES] | None:
            """The type the value has to be. based on https://docs.pydantic.dev/2.5/api/json_schema/#pydantic.json_schema.GenerateJsonSchema and https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1

            Returns:
                str: name of the field type based on https://json-schema.org/draft/2020-12/json-schema-core#name-instance-data-model
            """
            if self.field_schema is None:
                return None
            # https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-00#section-10.2.1
            json_subscheme_type = next(
                (
                    json_subs in ["allOf", "anyOf", "oneOf", "not"]
                    for json_subs in self.container_model.model_json_schema()[
                        "properties"
                    ][self.field_name]
                ),
                None,
            )
            if json_subscheme_type:
                return json_subscheme_type
            # default types
            return self.container_model.model_json_schema()["properties"][
                self.field_name
            ]["type"]

        @property
        def field_value_enum(
            self,
        ) -> List[Any] | None:
            """If the value has a fixed list of allowed values, this return the list of these values

            Returns:
                List[Any]: List of allowed values for the field
            """
            if (
                self.field_schema is None
                or "enum"
                not in self.container_model.model_json_schema()["properties"][
                    self.field_name
                ]
            ):
                return None

            return self.container_model.model_json_schema()["properties"][
                self.field_name
            ]["enum"]

        @classmethod
        def from_base_model(
            cls,
            key: str,
            base_settings_model: Type[BaseSettings],
            nested_container_path: List[str] = [],
        ) -> "YamlSettings.FieldInfoContainer":
            field_info_container = cls(
                field_name=key,
            )

            field_info_container.container_model = base_settings_model
            field_info_container.field_schema = base_settings_model
            # generate env var name incl parent path
            env_var_delimiter: str = (
                base_settings_model.model_config["env_nested_delimiter"]
                if base_settings_model.model_config["env_nested_delimiter"]
                else "__"
            )
            # Todo: you are here!!!!! You try to iterate the base model to find the given "key" so you can construct the env path and attach a "container_model" to the field

            for parent_key in nested_container_path + [key]:
                if isinstance(field_info_container.field_schema, fields.FieldInfo):
                    if (
                        inspect.isclass(field_info_container.field_schema.type_)
                        and issubclass(
                            field_info_container.field_schema.type_, BaseModel
                        )
                        and parent_key
                        in field_info_container.field_schema.type_.__fields__
                    ):
                        field_info_container.container_model = (
                            field_info_container.field_schema.type_
                        )
                        field_info_container.field_schema = (
                            field_info_container.field_schema.type_.__fields__[
                                parent_key
                            ]
                        )
                    else:
                        return None
                else:
                    field_info_container.container_model = (
                        field_info_container.field_schema
                    )
                    field_info_container.field_schema = (
                        field_info_container.field_schema.__fields__[parent_key]
                    )
                field_info_container.env_var_name = env_var_delimiter.join(
                    [env_var_prefix + k.upper() for k in path + [key]]
                )

            def get_parent_env_var(field: base_settings_model):
                print("model", base_settings_model)
                exit

            env_var_prefix: str = base_settings_model.model_config["env_prefix"]

    def __init__(self, model: Type[BaseSettings], file_path: Union[str, Path] = None):
        self.config_file: Path = (
            file_path if isinstance(file_path, Path) else Path(file_path)
        )
        self.model: Type[BaseSettings] = model

    def get_config(self):
        with open(self.config_file) as file:
            raw_yaml_object = file.read()
        obj: Dict = yaml.safe_load(raw_yaml_object)
        return self.model.parse_obj(obj)

    def generate_config_file(self, overwrite_existing: bool = False, exists_ok=True):
        null_placeholder = "NULL_PLACEHOLDER_328472384623746012386389621948"
        dummy_values = self._get_fields_filler(
            required_only=False,
            use_example_values_if_exists=False,
            fallback_fill_value=null_placeholder,
        )
        config = self.model.parse_obj(dummy_values)
        self._generate_file(
            config,
            overwrite_existing=overwrite_existing,
            generate_with_example_values=True,
            exists_ok=exists_ok,
            replace_pattern={null_placeholder: "null"},
        )

    def generate_example_config_file(self):
        dummy_values = self._get_fields_filler(
            required_only=True, use_example_values_if_exists=True
        )
        print(dummy_values)
        config = self.model.model_validate(dummy_values)
        self._generate_file(config, generate_with_example_values=True)

    def generate_existing_config_file(self, config: BaseSettings):
        self._generate_file(config)

    def generate_minimal_config_file(self):
        config = self.model.parse_obj(
            self._get_fields_filler(
                required_only=True,
                use_example_values_if_exists=True,
            )
        )
        self._generate_file(config, generate_with_optional_fields=False)

    def generate_markdown_doc(self):
        raise NotImplementedError()

    def _generate_file(
        self,
        config: BaseSettings,
        overwrite_existing: bool = False,
        exists_ok: bool = False,
        generate_with_optional_fields: bool = True,
        comment_out_optional_fields: bool = True,
        generate_with_comment_desc_header: bool = True,
        generate_with_example_values: bool = False,
        replace_pattern: Dict = None,
    ):
        self.config_file.parent.mkdir(exist_ok=True, parents=True)
        if self.config_file.is_file() and not overwrite_existing:
            if exists_ok:
                return
            else:
                raise FileExistsError(
                    f"Can not generate config file at {self.config_file}. File allready exists."
                )
        if replace_pattern is None:
            replace_pattern = {}
        yaml_content: str = yaml.dump(config.dict(), sort_keys=False)
        yaml_content_with_comment: List[str] = []
        previous_depth = 0
        previous_key: str = None
        current_path: List[str] = []
        in_multiline_block: bool = False
        for line in yaml_content.split("\n"):
            line_no_indent = line.lstrip()

            depth = int((len(line) - len(line_no_indent)) / 2)
            if previous_depth < depth:
                current_path.append(previous_key)
            elif depth < previous_depth:
                for i in range(depth, previous_depth):
                    generate_field_header
                pass

            elif ": " in line:
                key, val = line.split(": ")
                key = key.strip()
                field = self._get_field_info_from_model_by_name(key, current_path)
                if field:
                    comment = self.generate_field_header(
                        field,
                        indent_size=depth * 2,
                    )
                    if comment:
                        yaml_content_with_comment.append(comment)
                previous_key = key
            elif line.endswith(":"):
                key = line.split(":")[0].strip()
                field = self._get_field_info_from_model_by_name(key, current_path)
                if field:
                    comment = self.generate_field_header(
                        field,
                        indent_size=depth * 2,
                    )
                    if comment:
                        yaml_content_with_comment.append(comment)
                # sub chapter or line start
                previous_key = key
            previous_depth = depth
            yaml_content_with_comment.append(line)
        with open(self.config_file, "w") as file:
            lines = []
            for line in yaml_content_with_comment:
                for key, val in replace_pattern.items():
                    lines.append(f"{line.replace(key, val)}\n")
            file.writelines(lines)

    def _get_field_info_from_model_by_name(
        self, key: str, path: List[str]
    ) -> FieldInfoContainer | None:
        """Get a `YamlSettings.FieldInfoContainer` instance by a the field name and its path (parent container names)

        Args:
            key (str): _description_
            path (List[str]): _description_

        Returns:
            FieldInfoContainer | None: _description_
        """
        YamlSettings.FieldInfoContainer.from_base_model(
            key,
        )
        info = YamlSettings.FieldInfoContainer(field_name=key)
        info.container_model = self.model
        info.field_schema = self.model
        env_var_delimiter: str = (
            self.model.model_config["env_nested_delimiter"]
            if self.model.model_config["env_nested_delimiter"]
            else "__"
        )
        env_var_prefix: str = self.model.model_config["env_prefix"]
        for parent_key in path + [key]:
            if isinstance(info.field_schema, fields.FieldInfo):
                if (
                    inspect.isclass(info.field_schema.type_)
                    and issubclass(info.field_schema.type_, BaseModel)
                    and parent_key in info.field_schema.type_.__fields__
                ):
                    info.container_model = info.field_schema.type_
                    info.field_schema = info.field_schema.type_.__fields__[parent_key]
                else:
                    return None
            else:
                info.container_model = info.field_schema
                info.field_schema = info.field_schema.__fields__[parent_key]
        info.env_var_name = env_var_delimiter.join(
            [env_var_prefix + k.upper() for k in path + [key]]
        )
        return info

    def generate_field_header(
        self, field: FieldInfoContainer, indent_size: int = 0
    ) -> str:
        if not isinstance(field.field_schema, fields.FieldInfo):
            return None

        indent = f"{' '*indent_size}"
        """
        print("--------field.field_schema---------")
        for attr in dir(field.field_schema):
            try:
                print(attr, getattr(field.field_schema, attr))
            except:
                print(attr, "NOT_PRINTABL")
        print("-----")
        """
        # schema.model_schema(field.container_model)
        # parent_model = field.container_model

        field_schema = field.field_schema
        """ value examples
        field: name='server_name' type=Optional[ConstrainedStrValue] required=False default=None
        field_info: description="Synapse's public facing domain https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name" max_length=100 extra={'example': 'company.org'}
        field_schema: {'title': 'Server Name', 'description': "Synapse's public facing domain https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name", 'maxLength': 100, 'example': 'company.org', 'type': 'string'}
        """
        """
        if field.name == "synapse_server":
            print("field:", field)
            print("field_info:", field_info)
            print("field_schema:", field_schema)
        """
        # YOU ARE HERE. seems all good :)
        header_lines: List[str] = []
        header_lines.append(
            f"### '{field.field_name}' {' - '+field_schema.title if field_schema.title else ''} - ###"
        )
        if field.field_value_type_name:
            header_lines.append(f"# Type: {field.field_value_type_name}")
        if field_schema.description:
            desc = field_schema.description.replace("\n", f"\n{indent}#   ")
            header_lines.append(f"# Description: {desc}")

        header_lines.append(f"# Required: {field.field_schema.is_required}")

        if field.field_value_enum:
            header_lines.append(f"# Allowed values: {field.field_value_enum}")
        if field.field_schema.default:
            header_lines.append(f"# Defaults to {field.field_schema.default}")
        header_lines.append(f"# EnvVar name to override: '{field.env_var_name}'")
        if field_schema.examples:
            exmpl = f"\n" + yaml.dump(
                {field.field_name: self.jsonfy_example(field_schema.examples[0])}
            )
            exmpl = exmpl.rstrip("\n")
            exmpl = exmpl.replace("\n", f"\n{indent}# >{indent}")
            header_lines.append(f"# Example: {exmpl}")

        return "\n" + "\n".join([f"{indent}{line}" for line in header_lines])

    def _get_fields_filler(
        self,
        required_only: bool = True,
        use_example_values_if_exists: bool = False,
        fallback_fill_value: Any = "",
    ) -> Dict:
        """Needed for creating dummy values for non nullable values. Otherwise we are not able to initialize a living config from the model

        Args:
            required_only (bool, optional): _description_. Defaults to True.
            use_example_values_if_exists (bool, optional): _description_. Defaults to False.
            fallback_fill_value (Any, optional): _description_. Defaults to None.

        Returns:
            Dict: _description_
        """

        def parse_model_class(m_cls: Type[BaseModel]) -> Dict:
            result: Dict = {}
            for key, field in m_cls.model_fields.items():
                if not required_only or field.is_required():
                    if use_example_values_if_exists and field.examples:
                        example = field.examples[0]
                        # We want to generate a example models and there are examples in the annotation
                        # if it is a real config object we pass it to as a values else we try to create a json compatible string
                        if inspect.isclass(field.annotation) and issubclass(
                            field.annotation, BaseModel
                        ):
                            result[key] = example
                        else:
                            result[key] = self.jsonfy_example(example)

                    elif inspect.isclass(field.annotation) and issubclass(
                        field.annotation, BaseModel
                    ):
                        if field.default is not fields._Unset:
                            result[key] = field.default
                        elif field.default_factory is not None:
                            result[key] = field.default_factory()
                        else:
                            result[key] = parse_model_class(field.annotation)
                    elif isinstance(
                        field.annotation,
                        (str, int, float, complex, list, dict, set, tuple),
                    ):
                        result[key] = self.jsonfy_example(field.annotation())
                    elif (
                        isinstance(field, fields.FieldInfo)
                        and field.default_factory is not None
                    ):
                        val = self.jsonfy_example(field.default_factory())
                        result[key] = self.jsonfy_example(field.default_factory())
                    else:
                        result[key] = (
                            fallback_fill_value
                            if field.is_required()
                            else self.jsonfy_example(field.default)
                        )
            return result

        return parse_model_class(self.model)

    def jsonfy_example(self, val: Any) -> List | Dict:
        if isinstance(val, dict):
            result: Dict = {}
            for k, v in val.items():
                result[k] = self.jsonfy_example(v)
            return result
        elif isinstance(val, (list, set, tuple)):
            return [self.jsonfy_example(i) for i in val]
        elif isinstance(val, BaseModel):
            return val.model_dump_json()
        else:
            return str(val)
