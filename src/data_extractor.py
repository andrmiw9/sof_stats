"""

"""
import loguru


async def extract_info(tag_questions):
    """
    4. В результатах поиска интересует полный список тегов (поле tags) по каждому
    вопросу, а также был ли дан на вопрос ответ.
    5. В результате работы запроса должна быть возвращена суммарная статистика по
    всем тэгам (всем найденным по вопросу) - сколько раз встречался тег во всех вопросах и сколько раз на вопрос,
    содержащий тэг, был дан ответ.
    6. Результат должен быть представлен в формате JSON. Выдача ответа с человекочитаемым форматированием (pretty print)
    будет рассматриваться как плюс. Пример
    ответа:
    {
    "clojure": { "total": 173, "answered": 54},
    "python": { "total": 100, "answered": 9}
    "scala": { "total": 193, "answered": 193}
    }
    """
    logger: loguru.Logger = loguru.logger.bind(object_id='Data extraction')
    try:
        questions = tag_questions['items']
    except KeyError as ke:
        logger.error(f'Can not get items (questions) from SOF response: {ke}')
        return None

    stats: dict[dict[str:int]] = {}
    for question in questions:
        # logger.debug(f"{question}")
        try:
            logger.trace(f"q_id {question['question_id']} in consideration")
            answered = question['is_answered']
            for tag in question['tags']:
                if tag in stats:
                    stats[tag]['total'] += 1
                else:  # create new dict if this is new tag in our stats
                    stats[tag] = {'total': 1, 'answered': 0}

                if answered:  # rise up counter if question was given
                    stats[tag]['answered'] += 1
        except KeyError as ke:
            logger.error(f'{ke}')
    return stats
