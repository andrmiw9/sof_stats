""" Вынес в отдельный модуль, тк это часть взаимодействующая с сетью """
from typing import Any
import httpx

import loguru

from src.config import get_settings
from src.settings_model import Settings


async def search_sof_questions(aclient: httpx.AsyncClient,
                               query_tag: str,
                               _settings: Settings = get_settings()) -> Any | None:
    """ Search stackoverflow questions
    :param _settings: Pydantic модель с настройками приложения
    :param aclient: httpx.AsyncClient object для переиспользования keep-alive соединений и прочих оптимизаций
    :param query_tag: тег, по которому нужно совершить поиск
    :return: None если ошибка, JSON с ответом в случае успеха
    """
    logger: loguru.Logger = loguru.logger.bind(object_id='Search')  # bind logger extra obj for more intuitive logging
    try:
        if not query_tag:
            raise ValueError('query_tag cannot be empty or null')

        response = await aclient.get("https://api.stackexchange.com/2.3/search",
                                     params={
                                         "pagesize": 100,
                                         "order": "desc",
                                         "sort": "creation",
                                         "intitle": query_tag,
                                         "site": "stackoverflow"
                                     })
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError: {e}")
    except httpx.RequestError as e:
        logger.error(f"RequestError: {e}")
    except httpx.HTTPError as e:
        logger.error(f"HTTPError: {e}")
    except ValueError as e:
        logger.error(f"ValueError: {e}")
    except Exception as e:
        logger.error(f"Exception: {e}")
    else:  # no errors
        logger.debug(f'Request to SOF went good, resp: {response}')
        return response.json()
    return None
