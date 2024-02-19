"""
ASYNC TESTS file
Здесь находятся асинхронные тесты, в основном глобальные - на целый этап

"""

import asyncio

import pytest
from loguru import logger

import src.constants as constants
from src.config import get_settings, logger_set_up
from src.settings_model import Settings


# region Fixtures

@pytest.fixture(scope='module')
def logger_ready(settings):
    """
    Означает что логгер должен быть инициализирован
    :param settings:
    """
    logger_set_up(settings)


@pytest.fixture(scope='module')
def settings():
    """ Означает что должен быть экземпляр настроек """
    # print(f'Fixture working!')
    app_settings: Settings = get_settings(constants.TEST_CONFIG_PATH, constants.TEST_VERSION_PATH)
    yield app_settings
    # print(f'Fixture ended!')


@pytest.fixture(scope="session")
def loop():
    # Настройка
    # loop = asyncio.new_event_loop()
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Очистка
    loop.close()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.WindowsSelectorEventLoopPolicy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    res._close = res.close
    res.close = lambda: None

    yield res

    res._close()

# endregion
