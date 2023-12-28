import os, sys

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(
        os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
    )
    MODULE_ROOT_DIR = os.path.join(SCRIPT_DIR, "..")

    sys.path.insert(0, os.path.normpath(MODULE_ROOT_DIR))

from psyplus import YamlSettingsPlus
from psyplus.env_var_handler import EnvVarHandler

from tests.config_test import TestConfig

settings = YamlSettingsPlus(TestConfig, "config.yaml")
e = EnvVarHandler(settings=settings.generate_config_file_with_examples_values())
print(
    e.get_value_dict_by_env_var_key(
        "EXTERNAL_SUBCONFIG_LIST_WITH_EG__0__TEST_SIMPLE_LIST__0"
    )
)
exit()

from psyplus import YamlSettingsPlus

from tests.config_test import TestConfig

# from tests.config_complex_test import TestConfig

settings = YamlSettingsPlus(TestConfig, "config.yaml")

settings.generate_config_file_with_examples_values(overwrite_existing=True)


# settings_com = YamlSettings(TestConfigCom, "configCom.yaml")

# settings_com.generate_config_file_with_examples_values(overwrite_existing=True)
