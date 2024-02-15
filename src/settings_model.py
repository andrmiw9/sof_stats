from pydantic import BaseModel


class Settings(BaseModel):
    """ Модель pydantic, валидирующая конфиг """

    # TODO?: add constraints? (use pydantic_settings)
    # TODO: add timeouts for requests

    service_name: str = 'StackOverFlow_stats'  # захардкожено
    version: str  # из файла с версией в корне проекта (подтягивается в config.py)

    # формат и цвета логов
    log_format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>[<level>{level}</level>]" \
                      "<cyan>[{extra[object_id]}]</cyan>" \
                      "<magenta>{function}</magenta>:" \
                      "<cyan>{line}</cyan> - <level>{message}</level>"

    # app - общие настройки
    # project_path: str = 'opt/StackOverFlow_stats' # путь проекта от корня внутри будущего докер контейнера
    self_api_port: int  # порт для FastAPI сервера
    self_api_host: str = '127.0.0.1'  # адрес для FastAPI сервера
    env_mode: str = 'TEST'  # среда в которой запускается проект
    stop_delay: int = 10  # задержка перед закрытием

    # logger - настройки логгера
    log_console: bool = True  # выводить ли лог в консоль
    debug_mode: bool = True  # в дебаг режиме логи хранятся 3 дня по умолчанию и пишется лог уровня debug
    rotation_size: str = "500 MB"  # размер в МБ для начала ротации - то есть замены записываемого файла
    retention_time: int = 5  # время для начала ротации в днях

    # network
    max_requests: int = 1  # максимальное количество запросов к stackoverflow
    max_alive_requests: int = 1  # максимальное количество активных (keep-alive) запросов к stackoverflow
    keep_alive: int = 5  # время в секундах для keep-alive
    timeout: int = 10  # тайм-аут в секундах для запросов к stackoverflow

    # stackoverflow - вынесены в настройки с предположением что они будут изменяться в будущем
    url: str = "https://api.stackexchange.com/2.3/search"  # url-адрес для запросов к stackoverflow
    pagesize: int = 100  # кол-во вопросов по тегу
    order: str = "desc"  # порядок
    sort: str = "creation"  # сортировка
    site: str = "stackoverflow"  # название внутреннего домена для поиска
