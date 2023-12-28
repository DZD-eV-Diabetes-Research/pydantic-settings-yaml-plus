from typing import Tuple, List, Dict, Any, get_args, get_origin
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import os
from inspect import isclass
from psyplus.field_container import FieldInfoContainer
from psyplus.utils import clean_annotation, get_dict_val_key_insensitive


class ListitemPlaceholder:
    pass


class EnvVarHandler:
    def __init__(self, settings: BaseSettings | BaseModel):
        self.settings: BaseSettings | BaseModel = settings
        self.env_var_delimiter, self.env_var_prefix = self._get_env_var_seps()
        self.env_vars: Dict[str, str] = self._get_env_vars()

    def _get_env_vars(self) -> Dict[str, str]:
        print("os.environ.items()", os.environ.items())
        return {
            k: v for k, v in os.environ.items() if k.startswith(self.env_var_prefix)
        }

    def _get_env_var_seps(self) -> Tuple[str, str]:
        env_var_delimiter: str = (
            self.settings.model_config["env_nested_delimiter"]
            if self.settings.model_config["env_nested_delimiter"]
            else "__"
        )
        env_prefix: str = (
            self.settings.model_config["env_prefix"]
            if self.settings.model_config["env_prefix"]
            else ""
        )
        return env_var_delimiter, env_prefix

    def get_value_dict_by_env_var_key(self, env_var_key: str):
        env_var_splitted = self._split_env_var(env_var_key)
        result = self._get_value_dict_by_env_var_key(
            env_var_key_splitted=env_var_splitted,
            settings=self.settings,
            value=self.env_vars[env_var_key],
        )

    def _get_value_dict_by_env_var_key(
        self,
        env_var_key_splitted: List[str],
        settings: BaseSettings | BaseModel | Dict | List = None,
        annotation: Any = None,
        value: Any = None,
    ) -> Dict:
        if len(env_var_key_splitted) == 0:
            return value

        print("--------")
        print("annotation", annotation)
        print("env_var_key", env_var_key_splitted)
        print("settings.__class__", settings.__class__)

        env_var_fragment = env_var_key_splitted[0]
        print("path_fragment", env_var_fragment)

        print("+++++")

        annotation = clean_annotation(annotation)
        next_annotation = None

        if annotation is None or (
            isclass(annotation) and issubclass(annotation, (BaseSettings, BaseModel))
        ):
            if annotation is None:
                annotation = settings
            key = next(
                k
                for k in annotation.model_fields.keys()
                if k.upper() == env_var_fragment.upper()
            )
            next_annotation = annotation.model_fields[key].annotation
            next_settings_instance = getattr(settings, key, None)
            result = {}
            result[key] = self._get_value_dict_by_env_var_key(
                env_var_key_splitted=env_var_key_splitted[1:],
                settings=next_settings_instance,
                annotation=next_annotation,
                value=value,
            )
        elif get_origin(annotation) == dict:
            next_annotation = get_args(annotation)[1]

            next_settings_instance = get_dict_val_key_insensitive(
                settings, env_var_fragment, None
            )
            result = {}
            result[env_var_fragment.lower()] = self._get_value_dict_by_env_var_key(
                env_var_key_splitted=env_var_key_splitted[1:],
                settings=next_settings_instance,
                annotation=next_annotation,
                value=value,
            )
        elif get_origin(annotation) == list:
            print("JEP LIST")
            next_annotation = get_args(annotation)[0]
            # fill up list with placeholder to respect the env vars given index
            result = [ListitemPlaceholder] * int(env_var_fragment)
            try:
                print("settings", settings)
                next_settings_instance = (
                    settings[int(env_var_fragment)] if settings is not None else None
                )
            except IndexError:
                next_settings_instance = None

            result.append(
                self._get_value_dict_by_env_var_key(
                    env_var_key_splitted=env_var_key_splitted[1:],
                    settings=next_settings_instance,
                    annotation=next_annotation,
                    value=value,
                )
            )
        print("RESULT", result)
        return result

    def _get_setting_dict_by_env_var(self, env_var_key: str) -> Dict:
        self._get_value_dict_by_env_var_key(env_var_key)

    def get_field_info_by_env_var(self, env_var_key: str) -> FieldInfoContainer:
        for path_fragment in self._split_env_var(env_var_key):
            if path_fragment in self.settings.model_fields:
                field_info = self.settings.model_fields[path_fragment]
                return FieldInfoContainer(
                    path=path_fragment,
                    field_name=path_fragment,
                    field_info=field_info,
                )

    def _split_env_var(self, env_var_key: str) -> List[str]:
        return env_var_key.split(self.env_var_delimiter)
