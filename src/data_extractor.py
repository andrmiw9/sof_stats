""" Extract data from list of questions """
from typing import List

import loguru


async def extract_info(tag_questions: dict, tags: List[str] = None) -> dict | None:
    """
    Извлекает инфу из входного словаря вопросов по тегам и возвращает статистику в формате dict.
    """
    logger: loguru.Logger = loguru.logger.bind(object_id='Data extractor')

    # if not tag_questions:
    #
    #     return None

    try:
        questions = tag_questions['items']
    except TypeError as te:
        logger.error(f'Got None input tag_questions: {te}. Returning...')
        return None
    except KeyError as ke:
        logger.error(f'Can not get items (questions) from SOF response: {ke}. Returning...')
        return None

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
            logger.error(f'{ke}')
    if tags:
        logger.debug(f'Tags {tags}: extracted info from {len(questions)} questions!')
    else:
        logger.debug(f'Extracted info from {len(questions)} questions!')
    return stats
