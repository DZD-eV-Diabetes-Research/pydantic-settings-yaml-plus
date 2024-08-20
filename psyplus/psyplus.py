import typing

from typing import (
    List,
    Any,
    Dict,
    Union,
    Type,
)
import inspect

from pydantic import BaseModel, fields


from pydantic_settings import BaseSettings
from pydantic_core import PydanticUndefined
from pathlib import Path

import yaml


from psyplus.yaml_pydantic_metadata_comment_injector import YamlFileGenerator
from psyplus.env_var_handler import EnvVarHandlerExtended


class YamlSettingsPlus:
    def __init__(
        self,
        model: Type[BaseSettings],
        file_path: Union[str, Path] = None,
        parse_finde_grained_env_var: bool = True,
    ):
        self.parse_finde_grained_env_var = parse_finde_grained_env_var
        self.config_file: Path = (
            file_path if isinstance(file_path, Path) else Path(file_path)
        )
        self.model: Type[BaseSettings] = model
        self._settings_cache: BaseSettings = None

    def get_config(self) -> BaseSettings:
        with open(self.config_file) as file:
            raw_yaml_object = file.read()
        obj: Dict = yaml.safe_load(raw_yaml_object)
        if self.parse_finde_grained_env_var:
            env_var_handler = EnvVarHandlerExtended(self.model)
            obj = env_var_handler.settings_as_dict
        self._settings_cache = self.model.model_validate(obj)
        return

    def generate_config_file(self, overwrite_existing: bool = False, exists_ok=True):
        null_placeholder = "NULL_PLACEHOLDER_328472384623746012386389621948"
        dummy_values = self._get_fields_filler(
            required_only=False,
            use_example_values_if_exists=False,
            fallback_fill_value=null_placeholder,
        )
        # print("dummy_values", dummy_values)
        config = self.model.model_validate(dummy_values)
        self._generate_file(
            config,
            overwrite_existing=overwrite_existing,
            generate_with_example_values=True,
            exists_ok=exists_ok,
            replace_pattern={null_placeholder: "null"},
        )

    def generate_config_file_with_examples_values(
        self, overwrite_existing: bool = False
    ):
        dummy_values = self._get_fields_filler(
            required_only=True, use_example_values_if_exists=True
        )
        print("dummy_values", dummy_values)
        config = self.model.model_validate(dummy_values)
        return config
        filegen = YamlFileGenerator(config)
        filegen.parse_pydantic_model()
        print(filegen.get_yaml())
        exit()
        self._generate_file(
            config,
            generate_with_example_values=True,
            overwrite_existing=overwrite_existing,
        )

    def generate_config_file_from_config_object(self, config: BaseSettings):
        self._generate_file(config)

    def generate_config_file_with_only_required_keys(self):
        config = self.model.model_validate(
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
        yaml_content: str = yaml.dump(config.model_dump(), sort_keys=False)
        from psyplus.yaml_pydantic_metadata_comment_injector import YamlFileGenerator

        y = YamlFileGenerator(settings_instance=config)
        y.parse_pydantic_model()
        yaml_content = y.get_yaml()
        for key, val in replace_pattern.items():
            yaml_content = yaml_content.replace(key, val)

        with open(self.config_file, "w") as file:
            file.write(yaml_content)

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

        def parse_model_class(m_cls: Type[BaseSettings | BaseModel]) -> Dict:
            result: Dict = {}
            for key, field in m_cls.model_fields.items():
                if key == "only_for_groupnames_starting_with":
                    print(
                        "only_for_groupnames_starting_with.is_required()",
                        field.is_required(),
                    )
                # if not required_only or field.is_required():
                if True:
                    if use_example_values_if_exists and field.examples:
                        example = field.examples[0]
                        # We want to generate a example models and there are examples in the annotation
                        # if it is a real config object we pass it to as a values else we try to create a json compatible string

                        result[key] = example
                        """
                        if inspect.isclass(field.annotation) and issubclass(
                            field.annotation, BaseModel
                        ):
                            result[key] = example
                        else:
                            result[key] = self.jsonfy_example(example)
                        """
                    elif inspect.isclass(field.annotation) and issubclass(
                        field.annotation, BaseModel | BaseSettings
                    ):
                        if field.default is not PydanticUndefined:
                            result[key] = field.default
                        elif field.default_factory is not None:
                            print("field.default_factory", field.default_factory)
                            result[key] = field.default_factory()
                        else:
                            result[key] = parse_model_class(field.annotation)
                    elif field.annotation == Any:
                        result[key] = ""
                    elif type(field.annotation) in (typing._GenericAlias, type):
                        # This is a basic type. we can provide some reasonable sane default values like 0 for int or "" for str
                        if hasattr(field.annotation, "__origin__"):
                            result[key] = field.annotation.__origin__()
                        elif type(field.annotation) == type:
                            # we have a basic type
                            result[key] = field.annotation()

                    elif (
                        isinstance(field, fields.FieldInfo)
                        and field.default_factory is not None
                    ):
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
        elif val is not None:
            return str(val)
        else:
            return None
