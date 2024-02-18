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


@pytest.mark.asyncio
def test_db_com_stop_unusual():
    """ Запустить корутины из start_up() и закенселить все"""
    # TEST start_up()
    # !!! DONT FORGET TO PRESS CTRL+C OR STOP BUTTON !!!

    settings = get_settings(constants.TEST_CONFIG_PATH, constants.TEST_VERSION_PATH)
    print(f"Settings OK!")
    logger_set_up(settings)
    logger.info(f"Logger OK!")
    db_communicator = DbCommunicator(settings, q_p, q_s)
    loop = asyncio.new_event_loop()
    logger.info(f"Got to try section!")
    try:
        loop.create_task(db_communicator.start_up())
        loop.run_forever()
    except KeyboardInterrupt as ke:
        logger.warning(f'Closed by CTRL+C: {ke}')
    finally:
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            logger.info(f"canceled task {task}")
        task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()


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
