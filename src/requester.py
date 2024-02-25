"""
Вынес в отдельный модуль, тк это часть взаимодействующая с сетью
"""

from ast import literal_eval
from typing import Any

import httpx
import loguru

from src.settings_model import Settings


class RequestError(Exception):
    """ Base class for all exceptions that occur at the level of the requester.py """

    def __init__(self, message, error_code=500):  # default 500 - Internal Server Error
        self.message = message
        self.error_code = error_code

    def __repr__(self):
        return f'Code {self.error_code}, {self.message}'

    def __str__(self):
        return f'Code {self.error_code}, {self.message}'


class BadRequest(RequestError):
    """ Wrong request - incorrect params for example """

    def __init__(self, message):
        super().__init__(message, 400)  # bad request


class UnsuccessfulRequest(RequestError):
    """Something wrong while sending request to SOF server OR any wrong (not 200 OK) response from StackOverflow """

    def __init__(self, message, error_code=502):
        # 502 Bad Gateway - проблема в коммуникации между серверами
        # (ошибка в ответе от вышестоящего сервиса, которым для нас является StackOverflow)
        super().__init__(message, error_code)


async def search_sof_questions(aclient: httpx.AsyncClient,
                               query_tag: str,
                               _settings: Settings) -> Any:
    """
    Search stackoverflow questions
    :param _settings: Pydantic модель с настройками приложения
    :param aclient: httpx.AsyncClient object для переиспользования keep-alive соединений и прочих оптимизаций
    :param query_tag: тег, по которому нужно совершить поиск
    :return: None если ошибка, JSON с ответом в случае успеха
    """
    # bind logger extra obj for more intuitive logging
    logger: loguru.Logger = loguru.logger.bind(object_id='Requester')

    if not _settings:
        msg = 'Settings not found!'
        logger.error(msg)
        raise FileNotFoundError(msg)

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
        logger.error(f"HTTPStatusError: {e}")
        # usually this is like:
        # {"error_id":502,"error_message":"too many requests from this IP, more requests available in 82235 seconds",
        # "error_name":"throttle_violation"}

        # TODO!: NEEDS TESTING
        try:
            if not response.status_code == 400:
                logger.warning(f'Tag "{query_tag}": response status_code is not 400!')
            dict_str = response.content.decode("UTF-8")
            mydata: dict = literal_eval(dict_str)
            sof_code = mydata.get('error_id')
            if sof_code == 502:
                # 429 Too Many Requests - SOF забанил IP сервера на 24ч скорее всего
                er_msg = response.json()['error_message']
                logger.warning(f'Raising 429 error...')
                raise UnsuccessfulRequest(f'StackOverflow error: {er_msg}', error_code=429) from e
            else:
                logger.warning(f'Tag: "{query_tag}", failed to fetch response.status_code')
                # 502 Bad Gateway - проблема в коммуникации между серверами
                raise UnsuccessfulRequest(e) from e
        except ValueError as e2:
            logger.exception(f'Caught exception while trying to deal with first one! :( {e2}')
            logger.trace(f'Raising  error...')
            raise UnsuccessfulRequest(e) from e

    except httpx.PoolTimeout as e:
        msg = f"Try increasing httpx limits! httpx.PoolTimeout: {e}. "
        log_out(msg)  # requests are waiting for several seconds
        # for httpx.pool free slot for them. If there are waiting more than timeout time - error raises
        # must be not raised since the moment asyncio.Semaphore is implemented in my code
        raise UnsuccessfulRequest(msg, error_code=503) from e  # 503 Service Unavailable, то есть мой сервис перегружен
    except httpx.TimeoutException as e:
        log_out(f"TimeoutException: {e.__repr__()}")
        raise UnsuccessfulRequest("Probably wrong network configuration. " + str(e.__repr__()),
                                  error_code=504) from e  # 504 Gateway Timeout - SOF не успел выдать ответ
    except httpx.TransportError as e:
        log_out(f"TransportError: {e.__repr__()}")
        raise UnsuccessfulRequest(e.__repr__()) from e  # 502 Bad Gateway - проблема в коммуникации между сервами
    except httpx.RequestError as e:
        log_out(f"RequestError: {e.__repr__()}")
        raise UnsuccessfulRequest(e.__repr__()) from e  # 502 Bad Gateway
    except httpx.HTTPError as e:
        log_out(f"HTTPError: {e.__repr__()}")
        raise UnsuccessfulRequest(e.__repr__()) from e  # 502 Bad Gateway
    except Exception as e:
        # use exception to traceback since we must have caught all request-related errors already
        logger.exception(f"Exception: {e}")
        raise UnsuccessfulRequest(e, error_code=500) from e  # 500 Internal Server Error

    else:  # no errors
        logger.debug(f'Tag {query_tag}: request to SOF went good!')
        # logger.trace(f'Good request response: {response.json()}')
        result = response.json()

        items = result['items']  # just additional check
        if not items:
            msg = f'Tag: {query_tag} - empty response!'
            logger.warning(msg)
            raise UnsuccessfulRequest(msg)

        return result
    # logger.warning(f'Bad request response for tag "{query_tag}"')
    # return None
