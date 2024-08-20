import os, sys

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(
        os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
    )
    MODULE_ROOT_DIR = os.path.join(SCRIPT_DIR, "..")

    sys.path.insert(0, os.path.normpath(MODULE_ROOT_DIR))

from psyplus import YamlSettingsPlus
from psyplus.env_var_handler import EnvVarHandlerExtended

# from tests.config_test import TestConfig
from tests.config_readme_example import TestConfig

settings_wrapper = YamlSettingsPlus(TestConfig, "config.yaml")
os.environ["EXTERNAL_SUBCONFIG_LIST_WITH_EG__0__TEST_SIMPLE_LIST__0"] = (
    "ValueExtravgante"
)
os.environ["EXTERNAL_SUBCONFIG_LIST_WITH_EG__0__TEST_SIMPLE_LIST__1"] = (
    "ValueExtravgante2"
)
os.environ["EXTERNAL_SUBCONFIG_LIST_WITH_EG__0__TEST_SIMPLE_LIST1__2"] = (
    "ValueExtravgante5"
)
os.environ["EXTERNAL_SUBCONFIG_DICT2__DYNAMICDIC"] = "dictval1"
os.environ["EXTERNAL_SUBCONFIG_DICT2__0__TEST_SIMPLE_LIST1__3"] = "ValueExtravgante6"
settings = settings_wrapper.generate_config_file_with_examples_values()
e = EnvVarHandlerExtended(settings=settings)
import yaml

print("settings", yaml.dump(e.settings.model_dump()))
settings = YamlSettingsPlus(TestConfig, "test.config.yaml")
settings.generate_config_file(overwrite_existing=True)
exit()

from psyplus import YamlSettingsPlus

from tests.config_test import TestConfig

# from tests.config_complex_test import TestConfig


settings.generate_config_file_with_examples_values(overwrite_existing=True)


# settings_com = YamlSettings(TestConfigCom, "configCom.yaml")

# settings_com.generate_config_file_with_examples_values(overwrite_existing=True)
