import json
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger('wordle_statistic_bot')

def __get_wordle_data(text: str) -> tuple[str, int]:
    match = re.search(r'Wordle\s([\d,\\. ]+)\s([1-6X])/6', text)
    if match:
        wordle_id = match.group(1).replace(',', '').replace('.', '').replace(' ', '')  # Remove commas and convert to int
        wordle_score = int(match.group(2).replace('X', '8'))  # This will be a string, can be '1'-'6' or 'X'
        logger.debug('ID: %s, SCORE: %s' % (wordle_id, wordle_score))
        return wordle_id, wordle_score
    else:
        return '', 0

def __get_users_wordle_statistic(user_data_dict: dict) -> tuple[int, int, float, int, int]:
    failure_count, success_count, average_score, best_score = 0, 0, 0, 8
    for score in user_data_dict.values():
        average_score += score
        if score < best_score:
            best_score = score
        if score == 8:
            failure_count += 1
        else:
            success_count += 1

    average_score = round(average_score / len(user_data_dict), 2)
    best_score_count = list(user_data_dict.values()).count(best_score)
    return failure_count, success_count, average_score, best_score, best_score_count

async def get_wordle_statistic(start: datetime, end: datetime, channel) -> dict:
    statistics_folderpath = './statistics'
    statistics_filepath = os.path.join(statistics_folderpath, f'statistics_{start.strftime("%Y_%m")}.json')
    wordle_raw_data_filepath = os.path.join(statistics_folderpath, f'wordle_raw_data_{start.strftime("%Y_%m")}.json')
    load_messages = True
    now = datetime.now()

    try:
        logger.info(f'Try to get {start.month} {start.year} messages from file...')
        with open(wordle_raw_data_filepath, 'r', encoding='utf-8') as f:
            wordle_raw_data_dict = json.load(f)
    except:
        wordle_raw_data_dict = {}

    if wordle_raw_data_dict.get('last_save'):
        last_save = datetime.strptime(wordle_raw_data_dict['last_save'], "%Y-%m-%d %H:%M:%S")

        if last_save >= end:
            # Data from 'end' to somewhere before now is already saved
            load_messages = False
        elif now.month == last_save.month:
            start = last_save

    if load_messages:
        logger.info(f'Start fetching messages from: {start} to {end}...')
        try:
            async for msg in channel.history(after=start, before=end, limit=None, oldest_first=True):
                wordle_id, wordle_score = __get_wordle_data(msg.content)
                if wordle_id:
                    wordle_raw_data_dict.setdefault(str(msg.author.id), {'name': msg.author.name}).setdefault(wordle_id, wordle_score)
            logger.info('All messages fetched...')
        except Exception as e:
            logger.error(f'Messages could not be fetched...\n{e}')

        try:
            # Save to file (or database)
            wordle_raw_data_dict['last_save'] = now.strftime("%Y-%m-%d %H:%M:%S") # Save in file
            with open(wordle_raw_data_filepath, 'w', encoding='utf-8') as f:
                json.dump(wordle_raw_data_dict, f, ensure_ascii=False, indent=4)
            logger.info('Message file saved...')
        except Exception as e:
            logger.error(f'Wordle raw data could not be saved...\n{e}')

    logger.info('Calculate statistics...')
    wordle_raw_data_dict.pop('last_save')  # not needed for statistics (and already saved in file)
    wordle_statistic_dict = {}
    for user_id, user_data_dict in wordle_raw_data_dict.items():
        name = user_data_dict.pop('name')
        failure_count, success_count, average_score, best_score, best_score_count = __get_users_wordle_statistic(
            user_data_dict)
        wordle_statistic_dict[user_id] = {
            'name': name,
            'participation_count': len(user_data_dict),
            'failure_count': failure_count,
            'success_count': success_count,
            'average_score': average_score,
            'best_score': best_score,
            'best_score_count': best_score_count
        }
    if logger.getEffectiveLevel() == logging.DEBUG:
        try:
            with open(statistics_filepath, 'w', encoding='utf-8') as f:
                json.dump(wordle_statistic_dict, f, ensure_ascii=False, indent=4)
            logger.info('Statistics file saved...')
        except Exception as e:
            logger.error(f'Statistics could not be saved...\n{e}')

    return wordle_statistic_dict
