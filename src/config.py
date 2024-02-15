import os
import tomllib  # parse toml config
from functools import cache  # @cache decorator
from sys import stderr  # for setting up logger

from colorama import Back
from loguru import logger

from src import constants
from src.settings_model import Settings


@cache
def get_settings(_config_path: str = constants.DEFAULT_CONFIG_PATH,
                 _version_path: str = constants.VERSION_PATH) -> Settings:
    """
    Cacheable function (for each module actually runs only once) that returns dict of settings,
    read from .toml file and transformed into one - level dict.
    """

    if not _config_path:
        if os.name == 'nt':  # WINDOWS
            _config_path = constants.DEFAULT_CONFIG_PATH
        else:  # UNIX
            _config_path = constants.WAR_CONFIG_PATH

    config = Config(_config_path, _version_path)
    if config.settings.env_mode == 'TEST':
        print(f'Был зарегистрирован вызов get_settings(), cache info: {get_settings.cache_info()}')
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
            version_file_path = os.path.join(self.settings.project_path, "../version")

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
