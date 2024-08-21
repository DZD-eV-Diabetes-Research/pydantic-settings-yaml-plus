from pydantic import BaseModel, fields
from pydantic_settings import BaseSettings
from typing import List, get_args, Any


from psyplus.utils import clean_annotation


from ruamel.yaml import YAML, CommentedMap, CommentedSeq
from io import StringIO

from psyplus.field_container import FieldInfoContainer, ListIndex, DictKey


class YamlFileGenerator:
    def __init__(
        self, settings_instance: BaseSettings | BaseModel, indent_size: int = 2
    ):
        self.indent_size = indent_size
        self.yaml = YAML()

        # https://yaml.readthedocs.io/en/latest/detail/#indentation-of-block-sequences
        # > It is best to always have sequence >= offset + 2 but this is not enforced. Depending on your structure, not following this advice might lead to invalid output.
        self.yaml.indent(sequence=indent_size + 2, offset=indent_size)
        self.settings = settings_instance

    def parse_pydantic_model(self):
        self.model: CommentedMap = self._parse_pydantic_model(
            self.settings, parent_path=[]
        )

    def get_yaml(self) -> str:
        stream = StringIO()
        self.yaml.dump(self.model, stream)

        return stream.getvalue()

    def _parse_pydantic_model(
        self,
        setting_inst: BaseSettings | BaseModel,
        parent_path: List[ListIndex | DictKey | str],
    ) -> CommentedMap:
        level = len(parent_path)
        result: CommentedMap = CommentedMap()
        for key, field_info in setting_inst.model_fields.items():
            path = parent_path.copy() + [key]
            field_value = getattr(setting_inst, key)
            if isinstance(field_value, (BaseSettings, BaseModel)):
                result[key] = self._parse_pydantic_model(field_value, path)
            elif isinstance(field_value, dict):
                result[key] = self._parse_dict(field_value, field_info.annotation, path)
            elif isinstance(field_value, list):
                result[key] = self._parse_list(field_value, field_info.annotation, path)
            else:
                result[key] = field_value
            header_comment = FieldInfoContainer(
                path=path,
                field_name=key,
                field_info=field_info,
                root_settings_model=self.settings,
            ).get_field_comment_header()
            result.yaml_set_comment_before_after_key(
                key=key,
                before="\n" + "\n".join(header_comment),
                indent=level * self.indent_size,
            )
        return result

    def _parse_dict(
        self,
        value,
        field_annotation: Any,
        parent_path: List[ListIndex | DictKey | str],
    ) -> CommentedMap:
        level = len(parent_path)
        result: CommentedMap = CommentedMap()
        if isinstance(value, dict):
            if field_annotation is not None:
                dict_annotation_args = get_args(clean_annotation(field_annotation))
                if dict_annotation_args:
                    dict_key_annotation, dict_val_annotation = dict_annotation_args
            for key, val in value.items():
                path = parent_path.copy() + [DictKey(key=key)]
                if isinstance(val, (BaseSettings, BaseModel)):
                    result[key] = self._parse_pydantic_model(val, parent_path=path)
                elif isinstance(val, dict):
                    result[key] = self._parse_dict(
                        val, dict_val_annotation, parent_path=path
                    )
                elif isinstance(val, list):
                    result[key] = self._parse_list(
                        val, dict_val_annotation, parent_path=path
                    )
                else:
                    result[key] = val
                header_comment = FieldInfoContainer(
                    path=path,
                    field_name=key,
                    annotation=field_annotation,
                    root_settings_model=self.settings,
                ).get_field_comment_header()
                result.yaml_set_comment_before_after_key(
                    key=key,
                    before="\n" + "\n".join(header_comment),
                    indent=level * self.indent_size,
                )
        return result

    def _parse_list(
        self,
        value,
        field_annotation: Any,
        parent_path: List[ListIndex | DictKey | str],
    ) -> CommentedSeq:
        level = len(parent_path)
        result: CommentedSeq = CommentedSeq()
        if isinstance(value, list):
            list_val_annotation = get_args(clean_annotation(field_annotation))
            for index, item in enumerate(value):
                path = parent_path.copy() + [ListIndex(index=index)]
                if isinstance(item, (BaseSettings, BaseModel)):
                    result.append(self._parse_pydantic_model(item, parent_path=path))
                elif isinstance(item, dict):
                    result.append(
                        self._parse_dict(item, list_val_annotation, parent_path=path)
                    )
                elif isinstance(item, list):
                    result.append(
                        self._parse_list(item, list_val_annotation, parent_path=path)
                    )
                else:
                    result.append(item)

                header_comment = FieldInfoContainer(
                    path=path,
                    field_name=f"List[{index}]",
                    annotation=list_val_annotation,
                    root_settings_model=self.settings,
                ).get_field_comment_header(overwrite_required=False)
                result.yaml_set_comment_before_after_key(
                    key=index,
                    before="\n" + "\n".join(header_comment),
                    indent=level * self.indent_size,
                )
        return result
