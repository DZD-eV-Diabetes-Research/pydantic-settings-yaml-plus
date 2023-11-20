import os, sys

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(
        os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
    )
    MODULE_ROOT_DIR = os.path.join(SCRIPT_DIR, "..")

    sys.path.insert(0, os.path.normpath(MODULE_ROOT_DIR))
from psyplus import YamlSettings
from tests.config_test import TestConfig

settings = YamlSettings(TestConfig, "config.yaml")

settings.generate_example_config_file(overwrite_existing=True)
