import os, sys

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(
        os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
    )
    MODULE_ROOT_DIR = os.path.join(SCRIPT_DIR, "..")

    sys.path.insert(0, os.path.normpath(MODULE_ROOT_DIR))
from psyplus import YamlSettings
from tests.config_test_nl import TestConfig
from tests.config_complex_test import TestConfigCom

settings = YamlSettings(TestConfig, "config.yaml")

settings.generate_config_file_with_examples_values(overwrite_existing=True)


# settings_com = YamlSettings(TestConfigCom, "configCom.yaml")

# settings_com.generate_config_file_with_examples_values(overwrite_existing=True)
