from typing import Tuple, List, Dict, Any
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import os

from psyplus.field_container import FieldInfoContainer
from psyplus.utils import clean_annotation


class EnvVarHandler:
    def __init__(self, settings: BaseSettings | BaseModel):
        self.settings: BaseSettings | BaseModel = settings

        self.env_var_delimiter, self.env_var_prefix = self._get_env_var_seps()
        self.env_vars: Dict[str, str] = self._get_env_vars()

    def _get_env_vars(self) -> Dict[str, str]:
        self.env_vars = {
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
        self._get_value_dict_by_env_var_key(
            env_var_key=self._split_env_var(env_var_key), settings=self.settings
        )

    def _get_value_dict_by_env_var_key(
        self,
        env_var_key: List[str],
        settings: BaseSettings | BaseModel = None,
        annotation: Any = None,
    ) -> Dict:
        result = {}
        annotation = clean_annotation(annotation)
        next_annotation = None
        print("env_var_key", env_var_key)

        for index, path_fragment in enumerate(env_var_key[0]):
            next_settings_instance = settings

            if path_fragment in settings.model_fields:
                next_annotation = settings.model_fields[path_fragment].annotation
            elif annotation is not None and hasattr(annotation, "__origin__"):
                if annotation.__origin__ == dict:
                    next_annotation = annotation.__args__[1]
                elif annotation.__origin__ == list:
                    next_annotation = annotation.__args__[0]
                    path_fragment = int(path_fragment)
                    result = []
            if (
                next_annotation is not None
                and hasattr(next_annotation, "__origin__")
                and next_annotation.__origin__ in [BaseSettings, BaseModel]
            ):
                next_settings_instance = getattr(settings, path_fragment)
            result[path_fragment] = self._get_value_dict_by_env_var_key(
                env_var_key=env_var_key[index + 1 :],
                settings=next_settings_instance,
                annotation=next_annotation,
            )
        print("result", result)
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
