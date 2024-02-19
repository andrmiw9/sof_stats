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
    # bind logger extra obj for more intuitive logging
    logger: loguru.Logger = loguru.logger.bind(object_id='Requester')
    logger.debug(f'Working with tag "{query_tag}"...')
    try:
        if not query_tag:
            raise ValueError('query_tag cannot be empty or null')

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
        logger.error(f"HTTPStatusError: {e}")
    except httpx.RequestError as e:
        logger.error(f"RequestError: {e}")
    except httpx.HTTPError as e:
        logger.error(f"HTTPError: {e}")
    except ValueError as e:
        logger.error(f"ValueError: {e}")
    except Exception as e:
        logger.exception(f"Exception: {e}")
    else:  # no errors
        logger.debug(f'Tag {query_tag}: request to SOF went good!')
        # logger.trace(f'Good request response: {response.json()}')
        result = response.json()

        items = result['items']  # just additional check
        if not items:
            logger.warning(f'Tag: {query_tag} - empty response!')
            return None

        return result
    logger.warning(f'Bad request response: {response.json()}')
    return None
