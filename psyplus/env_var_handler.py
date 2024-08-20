from typing import Tuple, List, Dict, Any, get_args, get_origin
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_core import PydanticUndefined
import os
from inspect import isclass
from psyplus.field_container import FieldInfoContainer
from psyplus.utils import (
    clean_annotation,
    get_dict_val_key_insensitive,
    env_to_nested_dict,
)
import logging

log = logging.getLogger(__name__)
######
# WIP - needs total rewrite
######
# This is gargabe atm.
# pydantic-settings 2.x does most the thing now i tried to achieve here.
# todo: only thing left is indexes env var e.g. `MY_LIST__0=1`,`MY_DICT__KEY1=2`, `MY_OBJ_LIST__0__OBJ0_ATTR=Hello`
#


class ListitemPlaceholder:
    pass


class EnvVarHandler:
    def __init__(self, settings: BaseSettings | BaseModel):
        self.settings: BaseSettings | BaseModel = settings
        self.settings_as_dict: BaseSettings | BaseModel = settings.model_dump()
        self.env_var_delimiter, self.env_var_prefix = self._get_env_var_seps()
        self.env_vars: Dict[str, str] = self._get_env_vars()
        for key in self.env_vars.keys():
            val_dic = self.get_value_dict_by_env_var_key(key)
            if val_dic:
                self._deep_merge(self.settings_as_dict, val_dic)
        self.settings = settings.__class__.model_validate(self.settings_as_dict)

    def get_value_dict_by_env_var_key(
        self, env_var_key: str, default: Any = PydanticUndefined
    ) -> Dict | None:
        try:
            val = self.env_vars[env_var_key]
        except KeyError:
            prefix_hint = ""
            if self.env_var_prefix and env_var_key.startswith(self.env_var_prefix):
                prefix_hint = f" Did you exclude the prefix? If no, try it whithout the prefix `{self.env_var_prefix}`."
            raise ValueError(
                f"No environment var with key `{env_var_key}` found.{prefix_hint}"
            )
        env_var_splitted = self._split_env_var(env_var_key)
        try:
            result = self._get_value_dict_by_env_var_key(
                env_var_key_splitted=env_var_splitted,
                settings=self.settings,
                value=val,
            )
        except KeyError:
            return None
        return result

    def _get_env_vars(self) -> Dict[str, str]:
        """Collect env vars. if applicable filter by prefix and remove prefix for internal use."""
        result = {}
        for key, val in os.environ.items():
            if key.startswith(self.env_var_prefix):
                non_prefixed_key = key.replace(self.env_var_prefix, "", 1)
                result[non_prefixed_key] = val
        return result

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

    def _get_value_dict_by_env_var_key(
        self,
        env_var_key_splitted: List[str],
        settings: BaseSettings | BaseModel | Dict | List = None,
        annotation: Any = None,
        value: Any = None,
        parent_keys: List[str] = None,
    ) -> Dict:
        if len(env_var_key_splitted) == 0:
            return value

        env_var_fragment = env_var_key_splitted[0]

        annotation = clean_annotation(annotation)
        next_annotation = None
        if annotation is None or (
            isclass(annotation) and issubclass(annotation, (BaseSettings, BaseModel))
        ):
            if annotation is None:
                annotation = settings
            try:
                key = next(
                    k
                    for k in annotation.model_fields.keys()
                    if k.upper() == env_var_fragment.upper()
                )
            except StopIteration:
                # we found no setting key that matches the env var key.
                # this env var propably has nothing to do with the settings here
                raise KeyError(
                    f"Attr/Key `{env_var_fragment}` not found in `{annotation.__class__}`"
                )
            next_annotation = annotation.model_fields[key].annotation
            next_settings_instance = getattr(settings, key, None)
            result = {}
            result[key] = self._get_value_dict_by_env_var_key(
                env_var_key_splitted=env_var_key_splitted[1:],
                settings=next_settings_instance,
                annotation=next_annotation,
                value=value,
                parent_keys=env_var_key_splitted,
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
                parent_keys=env_var_key_splitted,
            )
        elif annotation == dict:
            # omg, we are in the wildlands. any dict is allowed.
            # we just make our best guess by creating a nested dict based on the path fragments
            if not os.getenv("PSYPLUS_SUPRESS_MISSING_TYPE_WARNING", None) in [
                "yes",
                "true",
                "1",
            ]:
                log.warning(
                    f"Env var key `{self.env_var_delimiter.join(parent_keys)}` is mapped to a simple `dict` annotation (subkey: '{env_var_key_splitted[0]}', value: `{value}`) in the config model `{self.settings.__class__.__name__}`. This is not recommended. "
                    + "Please use a `Dict[<type>]` annotation."
                    + "PsYplus is now creating a nested dict based on the path fragments, which maybe is not what you expected."
                    + "Set env var 'PSYPLUS_SUPRESS_MISSING_TYPE_WARNING=true' to supress this warning."
                )

            result = env_to_nested_dict(env_var_key_splitted, value)

        elif get_origin(annotation) == list:
            next_annotation = get_args(annotation)[0]
            # fill up list with placeholder to respect the env vars given index
            result = [ListitemPlaceholder] * int(env_var_fragment)
            try:
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
                    parent_keys=env_var_key_splitted,
                )
            )
        elif annotation == list:
            # omg, any list is allowed.
            # this is stupid. lets output a warning and just make a simple list the value
            if not os.getenv("PSYPLUS_SUPRESS_MISSING_TYPE_WARNING", None) in [
                "yes",
                "true",
                "1",
            ]:
                log.warning(
                    f"Env var key `{self.env_var_delimiter.join(parent_keys)}` is mapped to a simple `list` annotation. This is not recommended. "
                    + "Please use a `List[<type>]` annotation. "
                    + "We are just creating a list with the value and ignoring following env path fragments, which is possibly not what you expected."
                    + "Set env var 'PSYPLUS_SUPRESS_MISSING_TYPE_WARNING=true' to supress this warning."
                )
            result = [value]

        return result

    def _get_setting_dict_by_env_var(self, env_var_key: str) -> Dict:
        self._get_value_dict_by_env_var_key(env_var_key)

    def _split_env_var(self, env_var_key: str) -> List[str]:
        return env_var_key.split(self.env_var_delimiter)

    def _deep_merge(self, base: Dict | List, update: Dict | List):
        """Deep merge a complex nested dict/list object. Lists can have `ListitemPlaceholder` which will be recessive while merging

        Args:
            base (Dict | List): _description_
            update (Dict | List): _description_

        Raises:
            ValueError: _description_
        """
        if (isinstance(base, dict) or base in (None, PydanticUndefined)) and isinstance(
            update, dict
        ):
            if base in (None, PydanticUndefined):
                base = {}
            for key in set(base.keys()).union(update.keys()):
                if key in base and key in update:
                    # we have both keys. we need to go deeper
                    base[key] = self._deep_merge(base[key], update[key])
                elif key in update:
                    base[key] = update[key]
        elif (
            isinstance(base, list) or base in (None, PydanticUndefined)
        ) and isinstance(update, list):
            if base in (None, PydanticUndefined):
                base = []
            length = max(len(base), len(update))
            # Pad the base list, if its shorter
            base.extend([ListitemPlaceholder] * (length - len(base)))
            # iter through items and merge them
            for index, item in enumerate(update):
                if item != ListitemPlaceholder:
                    if isinstance(item, (dict, list)):
                        base[index] = self._deep_merge(base[index], update[index])
                    else:
                        base[index] = update[index]
        elif update is None:
            pass
        else:
            raise ValueError(
                "Source and update obj are too divergent in structure to be merged."
            )
        return base
