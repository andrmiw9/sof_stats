"""
Tests for config, version, logger, settings, etc.
"""
import asyncio
import time
import pytest

import src.constants as constants
from src.config import get_settings, logger_set_up
from loguru import logger


def test_passes():
    assert True


# def test_logger_right(app_settings):
#     # disable this if use of fixture is intended
#     logger_set_up(app_settings)


def test_config(logger_ready):
    logger.info("Start of Config test main!", f"\n")
    config_path: str = '../configs/config_win.toml'
    version_path: str = '../version'
    stgs = get_settings(config_path, version_path)
    logger.info("test_config got settings", f"{stgs}")
    time.sleep(1)  # ждем секунду, чтобы сохранить порядок логов и принтов
    logger.info("\nEnd of Config test main!", f".")


@pytest.fixture(scope='module')
def app_settings():
    # print(f'Fixture working!')
    app_settings: dict = get_settings(constants.TEST_CONFIG_PATH, constants.TEST_VERSION_PATH)
    yield app_settings
    # print(f'Fixture ended!')


@pytest.fixture(scope='module')
def logger_ready(app_settings):
    logger_set_up(app_settings)
