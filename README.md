sof_stats

Сервис sof_stats предоставляет endpoint /search для отправки запроса на поиск ответов по переданному тегу (тегам).
Сервис обрабатывает запрос и получает первые 100 релевантных ответов c с сайта StackOverflow, собирая по ним статистику.
После этого статистика возвращается отправителю запроса.
Если происходит какая-либо ошибка, то возвращается соотв-ий статус запроса (не 200 OK) и сообщение об ошибке в формате
JSON.
Пример возврата при ошибке:
{
  "detail": "Code 429, StackOverflow error: too many requests from this IP, more requests available in 83506 seconds"
}

Пример возврата без ошибок:
{
  "rust": {
    "total": 27,
    "answered": 16
  },
  "rusqlite": {
    "total": 1,
    "answered": 0
  }
}

Если по какому-то из тегов приходит пустой или плохой ответ, то он пропускается,
ошибка в запросе не выдается - если есть другие теги, которые сработали нормально

В папке configs лежат 2 конфига - один для тестов на Windows (config_win.toml), один для PROD запуска (config_war.toml).
В корне проекта лежит Dockerfile и скрипт для пересобрания образа и запуска контейнера.
Если вы хотите изменить порт работы приложения, то сделать это надо в 2-ух местах: в конфиге и
в dockerfile (и так же в build_and_run.sh, если вы его используете)
В папке tests шаблоны для написания тестов с готовыми фикстурами.
Файл version используется для версионирования.

Страница Swagger динамической документации (при локальном запуске):
http://127.0.0.1:7006/docs (ip и port задаются в конфиге)

Endpoint-ы (ручки):
/diag - возвращает несколько полей статистики: имя сервиса, версию, время работы.
/search - осуществляет поиск по StackOverflow и подсчет статистики ответа, если все ок.
/config - работает только в среде TEST (env_mode в конфиге). Возвращает экземпляр использующихся настроек.

Заметки:

- Если /search передали 2 тега, то результаты их статистики по тегам обьединяются
- 5 пункт задания - сколько раз на вопрос был дан ответ. Предполагаю, что имеется в виду is_answered.
- Мой сервис поддерживает русский язык, но вот StackOverflow не поддерживает русские теги, насколько я понял.
- Если один из тегов не буквы-цифры, то выкидывается ошибка. Альтернатива - выкинуть тег и искать по всем остальным
  тегам, если они нормальные, но из-за формата ответа я не знаю как передать сообщение о неправильном теге =>
  тот, кто запрашивал, даже не узнает, что в теге была ошибка.
- Если в переменных окружения (среды) есть HTTP_PROXY, то для запросов будет использоваться она.
- Если в переменных окружения (среды) есть SOF_STATS_CONFIG (внутри контейнера), то этот путь
  будет использоваться для получения конфига
- Вверху run_sof_stats.py есть список TODO
- Для ограничения в 1000 запросов я использовал httpx.limits. Однако при превышении лимита просто вызывается исключение
  httpx.PoolTimeout (то есть реквесты ожидают освобождения места какое-то время - таймаут). Так как этого оказалось  
  недостаточно я ввел также asyncio.BoundedSemaphore(1000) (1000 - задается в конфиге переменной max_requests)
- Максимальный тест доступный в Postman - 100 клиентов одновременно, он прошел. На 1000 не протестировано.
  Сам семафор протестирован, просто на меньших значениях.
- Для ускорения ответа используется либа orjson взамен стандартной json. (~ в 5 раз быстрее для моего приложения)