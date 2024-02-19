"""
Основной скрипт для запуска
SOF_stats - Маркин Андрей, 02.2024

Задача:
1. Обслуживать HTTP запросы по URL "/search". В параметрах запроса передается
параметр "tag", содержащий ключевой тэг для поиска. Параметров может быть
несколько, в этом случае мы работаем с несколькими ключевыми тэгами. Пример
"http://localhost:8080/search?tag=clojure&tag=scala". Предполагаем, что клиент будет
передавать только алфавитно-цифровые запросы в ASCII. Однако, наличие
корректной поддержки русского языка в кодировке UTF-8 будет плюсом.
2. Сервис должен обращаться к REST API StackOverflow для поиска (документация по
API https://api.stackexchange.com/docs/search). В случае, если ключевых слов
передано больше одного, запросы должны выполняться параллельно (по одному
HTTP запросу на ключевое слово). Должно быть ограничение на максимальное
количество одновременных HTTP-соединений, это значение нельзя превышать. Если
ключевых слов больше, нужно организовать очередь обработки так, чтобы более
указанного количество соединений не открывалось.
3. По каждому тэгу ищем только первые 100 записей, отсортированных по дате
создания. Пример запроса к API: https://api.stackexchange.com/2.2/search?
pagesize=100&order=desc&sort=creation&tagged=clojure&site=stackoverflow. Можно
использовать любые дополнительные параметры запроса, если это необходимо.
4. В результатах поиска интересует полный список тегов (поле tags) по каждому
вопросу, а также был ли дан на вопрос ответ.
5. В результате работы запроса должна быть возвращена суммарная статистика по
всем тэгам - сколько раз встречался тег во всех вопросах и сколько раз на вопрос,
содержащий тэг, был дан ответ.
6. Результат должен быть представлен в формате JSON. Выдача ответа с человекочитаемым форматированием (pretty print)
будет рассматриваться как плюс. Пример
ответа:
{
"clojure": { "total": 173, "answered": 54},
"python": { "total": 100, "answered": 9}
"scala": { "total": 193, "answered": 193}
}

тестовый запрос:
http://127.0.0.1:7006/search?tag=closure&tag=python&smth=foo&tag=Русский2
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, List

import httpx
import loguru
import orjson
import uvicorn
from fastapi import FastAPI, Query
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse
from asyncio import BoundedSemaphore

from src.config import Settings, get_settings, logger_set_up
from src.data_extractor import extract_info
from src.requester import RequestError, search_sof_questions


# TODO list:
# TODO!: collect requests after 1000 quota
# TODO!: add quota check
# TODO: set up order of tests to test logger init
# TODO: add tests for api responses
# TODO: check async client status once in several seconds
# TODO?: Use uvloop instead of asyncio default loop (5 times faster, but doesnt support Windows, so no testing in Win)
# TODO?: display only statistics in last several minutes, if highload is expected
# TODO?: write specification for Swagger documentation
# TODO?: check in /search request contains smth diff from alphabet-numeric chars
# TODO?: graceful shutdown + задержка закрытия docker-контейнера
# TODO?: make custom class with Exception from requester
# TODO?: add constraints to config model (use pydantic_settings)
# TODO?: replace some logger.error funcs with logger.exception for tracebacks (mb only in TEST env_mode)

class ORJSONPrettyResponse(JSONResponse):
    """
    Класс для возврата FastAPI Response JSON с человекочитаемым форматированием
    """

    def render(self, content: Any) -> bytes:
        """
        Вернуть ответ от orjson.dumps с человекочитаемым форматированием
        """
        return orjson.dumps(
            content,
            option=orjson.OPT_NON_STR_KEYS
                   | orjson.OPT_SERIALIZE_NUMPY
                   | orjson.OPT_INDENT_2,
        )


async def concat_tags(tags: list[str]) -> dict[str, list]:
    """
    Объединить теги в один словарь с общим полем items
    В одиночной версии: {'items':[...], 'has_more': True, 'quota_max': 300, 'quota_remaining': 294}
    :param tags: список тегов
    :return: словарь с полем items где лежат 100 ответов на каждый из переданных тегов
    """
    global aclient
    global settings
    logger: loguru.Logger = loguru.logger.bind(object_id='Concat tags')
    logger.info(f'Working with tags: len:{len(tags)}, data: "{tags}"...')

    tags_answers: dict[str, list] = {'items': list()}
    for tag in tags:
        try:
            res = await search_sof_questions(query_tag=tag, aclient=aclient, _settings=settings)
            # logger.trace(f'Result: {res}')
        except RequestError as e:  # base error for requester.py
            logger.warning(f"Request to SOF wrong with tag {tag}: {e}")
        if not res:
            logger.trace(f'Tag: {tag} - empty response!')
            continue

        try:
            tags_answers['items'].extend(res['items'])
        except Exception as e:
            logger.error(f"Smth wrong with tag {tag}: {e}")
    return tags_answers


# region FastAPI
async def app_startup():
    """Signal from fastapi"""
    global loop
    log: loguru.Logger = loguru.logger.bind(object_id='Startup')
    log.info("app_startup")
    loop = asyncio.new_event_loop()  # start new async loop for asyncio
    loop.set_debug(True if settings.debug_mode else False)  # for more precise errors and tracebacks


async def app_shutdown():
    """ Shutdown signal from FastAPI """
    logger.info("app_shutdown")
    global is_running
    is_running = False
    global loop
    await asyncio.sleep(settings.stop_delay)
    await aclient.aclose()  # close httpx.AsyncClient
    loop.close()  # close asyncio AbstractEventLoop


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
        logger: loguru.Logger = loguru.logger.bind(object_id='Middleware')
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
        """ Returns all settings of service. Work in TEST env_mode only! """
        if settings.env_mode == 'TEST':
            return settings
        else:
            return f'Unauthorized access to config'

    @fastapi_app.post('/search', response_class=ORJSONPrettyResponse)
    async def search(tag: List[str] = Query()):
        """
        Standard stackoverflow for received tags
        :param tag:
        :return:
        """
        logger: loguru.Logger = loguru.logger.bind(object_id='Search endpoint')

        # region Checks

        if not is_running:
            s = f'Error: service is shutting down!'
            logger.error(s)
            return s

        if not tag or len(tag) == 0:
            s = f'Error: empty tag list!'
            logger.error(s)
            return s

        for _tag in tag:
            if not _tag.isalnum():
                s = f'Error: tag "{_tag}" is not alphanumeric!'
                logger.error(s)
                return s
        # endregion

        # if len(tag) < 2:  # для единичного тега
        #     tag_answers = await search_sof_questions(query_tag=tag[0], aclient=aclient, _settings=settings)
        # else:
        #     tag_answers = await concat_tags(tags=tag)

        if len(tag) < 2:  # для единичного тега:
            tag = [tag]  # create list
        tag_answers = await concat_tags(tags=tag)  # uniform func

        if not tag_answers:
            s = f'Error: something went wrong with request / response!'
            logger.error(s)
            return s

        # logger.trace(f'tag_answers: {tag_answers}')  # словарь с полем items

        tag_stats = await extract_info(tag_answers, tag)

        # time1 = time.perf_counter()
        logger.success(f'Request with tags {tag} done!')
        # using custom Response to avoid calling json.dumps in FastAPI JSONResponse
        return ORJSONPrettyResponse(tag_stats,
                                    media_type='application/json')
        # all_time = time.perf_counter() - time1
        # logger.log("HL", f"{all_time}")
        # return t

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
    settings = get_settings()

    logger_set_up(settings)
    # logger.bind(object_id=os.path.basename(__file__))
    _logger: loguru.Logger = loguru.logger.bind(object_id='Run main')
    _logger.info("SETTINGS PARSED", f"data: {settings}")
    # logger.log("HL", "Test highlighting!")

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
    proxy = os.getenv('HTTP_PROXY')
    if proxy:
        aclient = httpx.AsyncClient(limits=limits, proxy=proxy, verify=False)
    else:
        aclient = httpx.AsyncClient(limits=limits)

    global semaphore
    semaphore = BoundedSemaphore(value=settings.max_requests)

    try:
        # disabled duplicate logs (uvicorn logs)
        # uvicorn_log_config = uvicorn.config.LOGGING_CONFIG
        # del uvicorn_log_config["loggers"]
        _logger.trace(f'Main passed, launching uvicorn...')

        uvicorn.run(app=f'__main__:app',
                    host=settings.self_api_host,
                    port=settings.self_api_port,
                    log_level="debug", access_log=False)

    except KeyboardInterrupt:
        _logger.info("KEYBOARD INTERRUPT MAIN")
    except Exception as e:
        _logger.error("MAIN ERROR", f"e: {e}")


if __name__ == '__main__':
    # global variables declaration (just to list them and also keep track of them)
    start_time: datetime = None  # just time when service started
    settings: Settings = None  # app settings
    app: FastAPI = None

    # could be redundant, since it looks like FastAPI stops handling incoming requests immediately
    is_running: bool = None

    loop: asyncio.AbstractEventLoop = None
    limits: httpx.Limits = None  # limits for httpx, uses config stop_delay setting
    aclient: httpx.AsyncClient = None  # one async client for all requests for optimizaitons
    semaphore: asyncio.BoundedSemaphore = None  # semaphore for manual limiting number of concurrent requests
    main()
