"""
Pydantic модель, валидирующая конфиг и динамические
настройки (например версию проекта, которая подтягивается из файлика)
"""
from pydantic import BaseModel


class Settings(BaseModel):
    """ Модель pydantic, валидирующая конфиг """

    service_name: str = 'sof_stats'  # захардкожено
    version: str  # из файла с версией в корне проекта (подтягивается в config.py)

    # формат и цвета логов
    log_format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>[<level>{level}</level>]" \
                      "<cyan>[{extra[object_id]}]</cyan>" \
                      "<magenta>{function}</magenta>:" \
                      "<cyan>{line}</cyan> - <level>{message}</level>"

    # app - общие настройки
    project_path: str = 'opt/sof_stats'  # путь проекта от корня внутри будущего докер контейнера
    self_api_port: int = 7006  # порт для FastAPI сервера
    self_api_host: str = '0.0.0.0'  # адрес для FastAPI сервера
    env_mode: str = 'TEST'  # среда в которой запускается проект
    stop_delay: int = 5  # задержка перед закрытием

    # logger - настройки логгера
    # уровень логирования. По умолчанию: TRACE если env_mode TEST, иначе DEBUG
    log_level: str = 'TRACE' if env_mode == 'TEST' else 'DEBUG'
    log_console: bool = True  # выводить логи в консоль
    console_lvl: str = 'DEBUG'  # уровень логирования в консоль, по умолчанию DEBUG
    rotation_size: str = "500 MB"  # размер в МБ для начала ротации - то есть замены записываемого файла
    retention_time: int = 5  # время в днях до начала ротации

    # network
    max_requests: int = 1000  # максимальное количество запросов к stackoverflow
    max_alive_requests: int = 1000  # максимальное количество активных (keep-alive) запросов к stackoverflow
    keep_alive: int = 15  # время в секундах для keep-alive
    timeout: int = 10  # тайм-аут в секундах для запросов к stackoverflow

    # stackoverflow - вынесены в настройки с предположением что они будут изменяться в будущем
    url: str = "https://api.stackexchange.com/2.3/search"  # url-адрес для запросов к stackoverflow
    pagesize: int = 100  # кол-во вопросов по тегу
    order: str = "desc"  # порядок
    sort: str = "creation"  # сортировка
    site: str = "stackoverflow"  # название внутреннего домена для поиска
