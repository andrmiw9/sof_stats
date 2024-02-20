""" Extract data from list of questions """
from typing import List

import loguru


class ExtractionError(Exception):
    """ Something went wrong when parsing StackOverflow Response"""
    pass


async def extract_info(tag_questions: dict, tags: List[str] = None) -> dict:
    """
    Извлекает инфу из входного словаря вопросов по тегам и возвращает статистику в формате dict.
    :param tag_questions: dict of questions with q in list under 'items' field
    :param tags: Optional tags for more precise logging
    :return: calculated statistics based on tag_questions
    """
    logger: loguru.Logger = loguru.logger.bind(object_id='Data extractor')

    try:
        questions = tag_questions['items']
    except TypeError as te:
        msg = f'Got None input tag_questions: {te}. Returning...'
        logger.error(msg)
        raise ExtractionError(msg)
    except KeyError as ke:
        msg = f'Can not get items (questions) from SOF response: {ke}. Returning...'
        logger.error(msg)
        raise ExtractionError(msg)

    stats: dict[dict[str:int]] = dict()
    for question in questions:
        # logger.trace(f"{question}")
        try:
            # logger.trace(f"q_id {question['question_id']} in consideration")

            # just to not catch error here. Hopefully this would not go so wrong that is_answered is missing
            answered = question.get('is_answered', False)
            for tag in question['tags']:
                if tag in stats:
                    stats[tag]['total'] += 1
                else:  # create new dict if this is new tag in our stats
                    stats[tag] = {'total': 1, 'answered': 0}

                if answered:  # rise up counter if question was given
                    stats[tag]['answered'] += 1
        except KeyError as ke:
            logger.debug(f'Skipping question: {question}, Error: {ke}')

    if tags:
        logger.debug(f'Tags {tags}: extracted info from {len(questions)} questions!')
    else:
        logger.debug(f'Extracted info from {len(questions)} questions!')

    if not stats:
        msg = f'Gathered statistics is empty!'
        logger.error(msg)
        raise ExtractionError(msg)

    return stats
