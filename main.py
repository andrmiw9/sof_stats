"""
Основной скрипт для запуска
SOF_stats - Маркин Андрей, 02.2024
тестовый запрос:
http://127.0.0.1:7006/search?tag=closure&tag=python&smth=foo&tag=Русский2

requirements:
annotated-types==0.6.0
anyio==4.2.0
certifi==2024.2.2
click==8.1.7
colorama==0.4.6
fastapi==0.109.2
h11==0.14.0
httpcore==1.0.2
httpx==0.26.0
idna==3.6
loguru==0.7.2
pydantic==2.6.1
pydantic_core==2.16.2
sniffio==1.3.0
starlette==0.36.3
typing_extensions==4.9.0
uvicorn==0.27.0.post1
win32-setctime==1.1.0

config_default:
[app]
#project_path = 'opt/vox_message'
self_api_port = 7006 # порт фаст апи
self_api_host = "127.0.0.1" # адрес фаст апи бэка
env_mode = "TEST" # окружение для запуска
stop_delay = 4 # задержка перед закрытием

[network]
max_requests = 1 # максимальное количество запросов к stackoverflow
max_alive_requests = 1  # максимальное количество активных (keep-alive) запросов к stackoverflow
keep_alive = 5 # время в секундах для keep-alive

[logger]
log_console = true # дублировать логи в консоль
debug_mode = true # выводить уровень DEBUG (или TRACE)
rotation_size = "250 MB" # размер лога для начала ротации
retention_time = 5 # время в днях до начала ротации

"""
import asyncio
import os
import tomllib
import typing

import httpx
import loguru
import uvicorn
from json import JSONDecodeError
from asyncio import Queue
from typing import List
from datetime import datetime, timedelta
from colorama import Fore, Back, Style  # colors for custom logger level
from functools import cache  # cache decorator for get_settings()
from sys import stderr  # for setting up logger
from pydantic import BaseModel
from fastapi import FastAPI, Query
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

DEFAULT_CONFIG_PATH = 'config_default.toml'  # путь к файлу конфига
TEST_CONFIG_PATH = 'test_config.toml'  # путь к тестовому файлу конфига
WAR_CONFIG_PATH = 'config.toml'  # путь к боевому файлу конфига
SOF_URL = "https://api.stackexchange.com/2.2/search?pagesize=100&order=desc&sort=creation&tagged={0}&site=stackoverflow"
VERSION_PATH = 'version'  # путь к файлу версии


# TODO: set default values in Swagger documentation
# TODO: test limit connections with Postman somehow
# region Config ready

class Settings(BaseModel):
    """ Модель pydantic, валидирующая конфиг """
    # TODO: add constraints? (use pydantic_settings)
    # TODO: add timeouts for requests
    service_name: str = 'StackOverFlow_stats'  # захардкожено
    version: str  # из файла с версией в корне проекта (подтягивается в config.py)

    # формат и цвета логов
    log_format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>[<level>{level}</level>]" \
                      "<cyan>[{extra[object_id]}]</cyan>" \
                      "<magenta>{function}</magenta>:" \
                      "<cyan>{line}</cyan> - <level>{message}</level>"

    # app
    # project_path: str = 'opt/StackOverFlow_stats' # путь проекта от корня внутри будущего докер контейнера
    self_api_port: int  # порт для FastAPI сервера
    self_api_host: str = '127.0.0.1'  # адрес для FastAPI сервера
    env_mode: str = 'TEST'  # среда в которой запускается проект
    stop_delay: int = 10  # задержка перед закрытием

    # network
    max_requests: int = 1  # максимальное количество запросов к stackoverflow
    max_alive_requests: int = 1  # максимальное количество активных (keep-alive) запросов к stackoverflow
    keep_alive: int = 5  # время в секундах для keep-alive

    # logger
    log_console: bool = True  # выводить ли лог в консоль
    debug_mode: bool = True  # в дебаг режиме логи хранятся 3 дня по умолчанию и пишется лог уровня debug
    rotation_size: str = "500 MB"  # размер в МБ для начала ротации - то есть замены записываемого файла
    retention_time: int = 5  # время для начала ротации в днях


@cache
def get_settings(_config_path: str = DEFAULT_CONFIG_PATH,
                 _version_path: str = VERSION_PATH) -> Settings:
    """
    Cacheable function (for each module actually runs only once) that returns dict of settings,
    read from .toml file and transformed into one - level dict.
    """
    print(f'Зарегистрирован вызов get_settings(), cache info: {get_settings.cache_info()}')
    if not _config_path:
        if os.name == 'nt':  # WINDOWS
            _config_path = DEFAULT_CONFIG_PATH
        else:  # UNIX
            _config_path = WAR_CONFIG_PATH

    config = Config(_config_path, _version_path)
    return config.settings


class ConfigError(OSError):
    """Raised when smth in config.toml is wrong"""
    pass


def load_toml(config_path, use_env: bool = False) -> dict:
    """ TOML config file related stuff """

    # путь переменной из окружения имеет приоритет (if use_env is True)
    if use_env and "SOF_STATS_CONFIG" in os.environ:
        config_path = os.environ["SOF_STATS_CONFIG"]
        print(f"Переменная окружения SOF_STATS_CONFIG найдена, значение: {config_path}")

    if not os.path.isfile(config_path):  # если не валидный путь, то выйти
        print(f"Конфигурационный файл {config_path} не найден, выхожу...")
        # Raise error and just quit the app. There is no best solution here - the alternative would be to use
        # hard-coded values of settings
        raise FileNotFoundError

    print(f"Использую конфигурационный файл: {config_path}")
    config = {}
    with open(config_path, mode='rb') as f:  # binary mode is required for TOML, but it may be unsafe
        data = tomllib.load(f)
        # print("LOADED TOML", f"data: {data}")
        if data is None or len(data) == 0:
            raise ConfigError('Empty config!')

        config.update({k: v for subdict in data.values() for k, v in subdict.items()})

    print("load_toml result", f"data: {config}")
    return config


class Config:
    """Представляет обьект, парсящий настройки из TOML, версию и хранящий поле settings с полученными данными"""

    def __init__(self, config_path: str = '', version_path: str = ''):
        # load to self.config dict of settings
        self.config = load_toml(config_path)

        # parse project version from version file and add to config
        self.config['version'] = self.get_project_version(version_path)

        # validate settings
        self.settings = Settings(**self.config)

    def get_project_version(self, version_file_path: str = '') -> str:
        """ Возврат номера версии приложения """
        if not version_file_path:
            # try to find version in project root. Mb actually unsafe
            version_file_path = os.path.join(self.settings.project_path, "version")

        try:
            with open(version_file_path, "r") as file:
                version = file.readline().strip()
        except FileNotFoundError as fnfe:
            err = f"Ошибка: не найден файл с номером версии по пути: {version_file_path}. Ошибка: {fnfe}. Выхожу... "
            print(err)
            raise FileNotFoundError(err) from fnfe
        except BaseException as e:
            err = f"Ошибка: {e}. Выхожу... "
            print(err)
            raise Exception(err) from e

        if version is None or version == '':
            err = f'Ошибка: найден файл {version_file_path}, но не найдена версия! Выхожу...'
            print(err)
            raise ValueError(err)

        print(f'Найден файл {version_file_path} с версией {version}. Без ошибок.')
        return version


def logger_set_up(_settings, logs_path: str = "logs/vox_message.log"):
    """Loguru set up"""
    # TODO: разделить 3 этапа выполнения по цветам, близким к белому
    logger.configure(extra={"object_id": "None"})  # Default values if not bind extra variable
    logger.remove()  # this removes duplicates in the console if we use the custom log format
    logger.level("HL", no=38, color=Back.MAGENTA, icon="🔺")
    logger.level(f"TRACE", color="<fg #1b7c80>")  # выставить цвет
    logger.level(f"SUCCESS", color="<bold><fg #2dd644>")  # выставить цвет

    if _settings.log_console:
        # for output log in console
        logger.add(sink=stderr,
                   format=_settings.log_format,
                   colorize=True,
                   enqueue=True,  # for better work of async
                   level='TRACE')

    logger.add(sink=logs_path,
               rotation=_settings.rotation_size,
               compression='gz',
               retention=_settings.retention_time,
               format=_settings.log_format,
               enqueue=True,  # for better work of async
               level='TRACE' if _settings.env_mode == 'TEST' else 'DEBUG')
    # level='INFO')


# endregion

# region Requests
async def search_sof_questions(query_tag: str) -> typing.Any | None:
    """ Search stackoverflow questions """
    try:
        if not query_tag:
            raise ValueError('query_tag cannot be empty or null')

        global aclient
        response = await aclient.get("https://api.stackexchange.com/2.3/search",
                                     params={
                                         "pagesize": 100,
                                         "order"   : "desc",
                                         "sort"    : "creation",
                                         "intitle" : query_tag,
                                         "site"    : "stackoverflow"
                                     })
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError: {e}")
    except httpx.HTTPError as e:
        logger.error(f"HTTPError: {e}")
    except ValueError as e:
        logger.error(f"ValueError: {e}")
    except Exception as e:
        logger.error(f"Exception: {e}")
    else:  # no errors
        return response.json()
    return None
    # return f'{{{query_tag}: Error({e})}}'  # default answer


# endregion

# region Extraction
async def extract_info(tag_answers: list):
    pass


# endregion

# region FastAPI main not ready
async def app_startup():
    """Signal from fastapi"""
    global loop
    log: loguru.Logger = loguru.logger.bind(object_id='Startup')
    log.info("app_startup")
    loop = asyncio.new_event_loop()


async def app_shutdown():
    """ Shutdown signal from FastAPI """
    # TODO: graceful shutdown
    # TODO: переделать так, чтобы docker-контейнер не закрывался раньше правильного закрытия сервиса
    logger.info("app_shutdown")
    global is_running
    is_running = False
    # loop = asyncio.get_running_loop()

    # if hasattr(app, 'db_communicator') and isinstance(app.db_communicator, DbCommunicator):
    #     await app.db_communicator.close_up()
    # if hasattr(app, 'vox_communicator') and isinstance(app.vox_communicator, VoxCommunicator):
    #     await app.vox_communicator.close_up()

    await asyncio.sleep(settings.stop_delay)
    loop.close()


def normal_app() -> FastAPI:
    """ FastAPI settings and endpoints. Mb move to class? """
    fastapi_app = FastAPI(version=settings.version, title=settings.service_name)

    fastapi_app.add_event_handler(event_type='startup', func=app_startup)
    fastapi_app.add_event_handler(event_type='shutdown', func=app_shutdown)

    @fastapi_app.middleware('http')
    async def mdlwr(request: Request, call_next):
        """
        Middleware это предобработчик запросов
        :param request: Запрос входящий (или мб исходящий)
        :param call_next: Следующий ендпоинт, куда в оригинале шел запрос
        """
        req_start_time = datetime.now()
        # вывести адрес ручки без адреса и порта сервиса
        logger.info(f"Incoming request: /{''.join(str(request.url).split('/')[3:])}")
        response = await call_next(request)
        process_time = (datetime.now() - req_start_time)
        response.headers["X-Process-Time"] = str(process_time)
        logger.debug(f'Request time took {process_time} seconds')
        return response

    @fastapi_app.get("/config")
    async def config() -> Settings | str:
        """ Returns all settings of service """
        if settings.env_mode == 'TEST':
            return settings
        else:
            return f'Unauthorized access to config'

    @fastapi_app.post('/search')
    async def search(tag: List[str] = Query()):
        """
        Standard stackoverflow for received tags
        :param tag:
        :return:
        """
        if not is_running:
            s = f'Error: service is shutting down!'
            logger.error(s)
            return s
        results = []
        for tg in tag:
            tag_answers = await search_sof_questions(tg)
            # await extract_info(tag_answers)
            results.append(tag_answers)
        return f'Requested: {tag}, answers: {results}'

    @fastapi_app.get("/diag")
    async def diag() -> dict:  #
        """Standard /diag route"""
        delta = datetime.now() - start_time
        if delta.days < 0:  # for midnight
            delta = timedelta(
                days=0,
                seconds=delta.seconds,
                microseconds=delta.microseconds
            )

        # uptime calculations
        td_sec = delta.seconds  # getting seconds field of the timedelta
        hour_count, rem = divmod(td_sec, 3600)  # calculating the total hours
        minute_count, second_count = divmod(rem, 60)  # distributing the remainders
        delta = f"{delta.days}:{hour_count}:{minute_count}:{second_count}"

        response = {
            "res"       : "ok",
            "app"       : f'{settings.service_name}',
            "version"   : f'{settings.version}',
            "uptime"    : delta,
            "is_running": is_running
        }
        return response

    @fastapi_app.exception_handler(404)
    async def custom_404_handler(request: Request, _):
        """Собственный обработчик 404 ошибки"""

        content = {
            "res": "Error",
            "msg": f"Not found {request.method} API handler for {request.url}"
        }
        logger.warning(f"content={content}")
        return JSONResponse(content=content,
                            status_code=404)

    return fastapi_app


# endregion

def main():
    """ Initialize globals, such as settings and FastAPI app, do some preparations like logger bind and run uvicorn"""

    global settings  # use a global type of link
    # _win_config = constants.DEFAULT_CONFIG_PATH
    # _win_version = constants.DEFAULT_VERSION_PATH
    settings = get_settings()
    # settings = get_settings()

    logger_set_up(settings)
    # logger.bind(object_id=os.path.basename(__file__))
    logger: loguru.Logger = loguru.logger.bind(object_id='Run main')
    logger.info("SETTINGS PARSED", f"data: {settings}")
    logger.log("HL", "Test highlighting!")

    global app  # use global variable
    app = normal_app()

    global is_running  # shows if service is alive
    is_running = True  # ATM actually IDK if its needed

    global start_time
    start_time = datetime.now()

    global limits
    limits = httpx.Limits(max_connections=settings.max_requests,
                          max_keepalive_connections=settings.max_alive_requests,
                          keepalive_expiry=settings.keep_alive)
    global aclient
    aclient = httpx.AsyncClient(limits=limits)

    try:
        # disabled duplicate logs (uvicorn logs)
        # uvicorn_log_config = uvicorn.config.LOGGING_CONFIG
        # del uvicorn_log_config["loggers"]

        uvicorn.run(app=f'__main__:app',
                    host=settings.self_api_host,
                    port=settings.self_api_port,
                    log_level="debug", access_log=False)

    except KeyboardInterrupt:
        logger.info("KEYBOARD INTERRUPT MAIN")
    except Exception as e:
        logger.error("MAIN ERROR", f"e: {e}")


if __name__ == '__main__':
    # global variables declaration
    start_time: datetime = None
    settings: Settings = None
    app: FastAPI = None
    is_running: bool = None
    loop: asyncio.AbstractEventLoop = None
    limits: httpx.Limits = None
    aclient: httpx.AsyncClient = None
    main()
