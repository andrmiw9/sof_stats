"""
Вынес в отдельный модуль, тк это часть взаимодействующая с сетью
Вводная информация:
У меня запущен Python скрипт, который реализует FastAPI и uvicorn сервер. Я обращаюсь к нему по POST запросу по
адресу http://127.0.0.1:7006/search и в теле запроса передаю один или несколько тегов для поиска. После этого мой
сервис делает запрос с помощью httpx на сайт StackOverflow и ищет там ответы на вопросы, содержащие полученные теги
или теги.
Важное примечание: мой сервис использует один общий httpx.AsyncClient для всех запросов, чтобы оптимизировать затраты
на его создание и выделения памяти вместе httpx.limits: limits = httpx.Limits(max_connections=1,
                          max_keepalive_connections=1,
                          keepalive_expiry=5), которые ограничивают количество одновременных запросов и подключений.
Все работает при ручных тестах.
Однако сейчас я провел автоматизированное нагрузочное тестирование с помощью Postman и в некоторых случаях получил
ошибку.
Когда я делал 1 запрос одновременно, все работало.
Когда я делал 2 запроса одновременно тоже все работало.
Однако если я делаю 3 запроса одновременно, то получаю ошибку. ЗАДАНИЕ: Помоги разобрать в ней.
Вот сокращенный лог ошибки:
"""

from typing import Any

import httpx
import loguru

from src.config import get_settings
from src.settings_model import Settings


class RequestError(Exception):
    """ Base class for all exceptions that occur at the level of the requester.py """

    def __init__(self, message):
        self.message = message


class BadRequest(RequestError):
    """ Wrong request - incorrect params for example """

    def __init__(self, message):
        super().__init__(message)
        self.error_code = 400  # bad request


class BadNetwork(RequestError):
    """ Something wrong while sending request to SOF server """

    def __init__(self, message):
        super().__init__(message)
        self.error_code = 500  # server related problem


class BadResponse(Exception):
    """ Any wrong (not 200 OK) response from StackOverflow """

    def __init__(self, message):
        super().__init__(message)
        self.error_code = 502  # SOF server related problem (hopefully)


async def search_sof_questions(aclient: httpx.AsyncClient,
                               query_tag: str,
                               _settings: Settings = get_settings()) -> Any:
    """
    Search stackoverflow questions
    :param _settings: Pydantic модель с настройками приложения
    :param aclient: httpx.AsyncClient object для переиспользования keep-alive соединений и прочих оптимизаций
    :param query_tag: тег, по которому нужно совершить поиск
    :return: None если ошибка, JSON с ответом в случае успеха
    """
    # bind logger extra obj for more intuitive logging
    logger: loguru.Logger = loguru.logger.bind(object_id='Requester')
    logger.debug(f'Working with tag "{query_tag}"...')

    if not query_tag:
        msg = 'query_tag cannot be empty or null'
        logger.error(msg)
        raise BadRequest(msg)

    if _settings.env_mode == 'TEST':
        log_out = logger.exception  # with traceback
    else:
        log_out = logger.error  # simple

    try:
        response = await aclient.get(_settings.url,
                                     params={
                                         "pagesize": _settings.pagesize,
                                         "order"   : _settings.order,
                                         "sort"    : _settings.sort,
                                         "intitle" : query_tag,
                                         "site"    : _settings.site
                                     })
        response.raise_for_status()

    except httpx.HTTPStatusError as e:
        # do not use exception traceback since its just status error
        logger.error(f"HTTPStatusError: {e}")  # usually this is like:
        # {"error_id":502,"error_message":"too many requests from this IP, more requests available in 82235 seconds",
        # "error_name":"throttle_violation"}
        raise BadResponse(e) from e
    except httpx.PoolTimeout as e:
        msg = 'Try increasing httpx limits!'
        log_out(f"{msg}  httpx.PoolTimeout: {e}. ")  # requests are waiting for several seconds
        # for httpx.pool free slot for them. If there are waiting more than timeout time - error raises
        raise BadNetwork(e) from e
    except httpx.TransportError as e:
        log_out(f"TransportError: {e}")
        raise BadNetwork(e) from e
    except httpx.RequestError as e:
        log_out(f"RequestError: {e}")
        raise BadNetwork(e) from e
    except httpx.HTTPError as e:
        log_out(f"HTTPError: {e}")
        raise BadNetwork(e) from e
    except Exception as e:
        log_out(f"Exception: {e}")
        raise Exception(e) from e

    else:  # no errors
        logger.debug(f'Tag {query_tag}: request to SOF went good!')
        # logger.trace(f'Good request response: {response.json()}')
        result = response.json()

        items = result['items']  # just additional check
        if not items:
            msg = f'Tag: {query_tag} - empty response!'
            logger.warning(msg)
            raise BadResponse(msg)

        return result
    logger.warning(f'Bad request response for tag "{query_tag}"')
    return None
