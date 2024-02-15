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
import typing
from datetime import datetime, timedelta
from typing import List

import httpx
import loguru
import uvicorn
from fastapi import FastAPI, Query
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.config import get_settings, logger_set_up, Settings
from src.data_extractor import extract_info
from src.requester import search_sof_questions


# TODO: set default values in Swagger documentation
# TODO: test limit connections with Postman somehow


async def process_tag(tag) -> dict:
    """
    Обработать тег
    :param tag:
    :return:
    """
    global aclient
    global settings
    logger: loguru.Logger = loguru.logger.bind(object_id='Process tag')
    logger.info(f'Working with tag "{tag}"...')
    tag_answers = await search_sof_questions(query_tag=tag, aclient=aclient, _settings=settings)
    tag_stats = await extract_info(tag_answers)
    return tag_stats


# region FastAPI
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
        logger: loguru.Logger = loguru.logger.bind(object_id='test2')
        if not is_running:
            s = f'Error: service is shutting down!'
            logger.error(s)
            return s

        # TODO!: переделать так, чтобы поиск был не по одному тегу, а по 2 сразу
        results = []
        for tg in tag:
            results.append(await process_tag(tg))
        # return f'Requested: {tag}, answers: {results}'
        return results

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
            "res": "ok",
            "app": f'{settings.service_name}',
            "version": f'{settings.version}',
            "uptime": delta,
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
    logger: loguru.Logger = loguru.logger.bind(object_id='Run main')
    logger.info("SETTINGS PARSED", f"data: {settings}")
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
