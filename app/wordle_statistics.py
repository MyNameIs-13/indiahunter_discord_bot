import calendar
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

import discord

logger = logging.getLogger('wordle_statistic_bot')

SCORE_TO_POINTS = {1: 19, 2: 11, 3: 5, 4: 3, 5: 2, 6: 1, 8: 0 }
REFERENCE_WORDLE_ID = {'id': 1337, 'date': datetime(2025, 2, 15)}


def __get_wordle_data(text: str) -> tuple[str, int]:
    match = re.search(r'Wordle\s([\d,\\. ]+)\s([1-6X])/6', text)
    if match:
        wordle_id = match.group(1).replace(',', '').replace('.', '').replace(' ', '')  # Remove commas and convert to int
        wordle_score = int(match.group(2).replace('X', '8'))  # This will be a string, can be '1'-'6' or 'X'
        logger.debug('ID: %s, SCORE: %s' % (wordle_id, wordle_score))
        return wordle_id, wordle_score
    else:
        return '', 0

def __get_users_wordle_statistic(user_data_dict: dict, game_ids_set: set) -> tuple[int, int, int, float, int, int]:
    points, failure_count, success_count, average_score, best_score = 0, 0, 0, 0, 8
    for game_id, score in user_data_dict.items():
        game_ids_set.remove(int(game_id))
        score = int(score)
        points += SCORE_TO_POINTS[score]
        average_score += score
        if score < best_score:
            best_score = score
        if score == 8:
            failure_count += 1
        else:
            success_count += 1

    average_score = round(average_score / len(user_data_dict), 2)
    best_score_count = list(user_data_dict.values()).count(best_score)
    points -= len(game_ids_set)
    return points, failure_count, success_count, average_score, best_score, best_score_count


def __get_wordle_numbers_for_month(start: datetime, end: datetime) -> set:
    day_range = (end - start).days + 1

    # Calculate the difference in days
    delta_days = (start - REFERENCE_WORDLE_ID['date']).days
    # Compute the wordle id
    wordle_id = REFERENCE_WORDLE_ID['id'] + delta_days

    wordle_ids_set = set()
    for i in range(day_range):
        wordle_ids_set.add(wordle_id + i)

    return wordle_ids_set


async def __get_wordle_statistic(start: datetime, end: datetime, channel: discord.TextChannel) -> dict:
    statistics_folderpath = './data'
    statistics_filepath = os.path.join(statistics_folderpath, f'statistics_{start.strftime("%Y_%m")}.json')
    wordle_raw_data_filepath = os.path.join(statistics_folderpath, f'wordle_raw_data_{start.strftime("%Y_%m")}.json')
    load_messages = True
    now = datetime.now()

    wordle_ids_set = __get_wordle_numbers_for_month(start, end if now > end else now)

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
                if wordle_id and int(wordle_id) in wordle_ids_set:
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

    logger.info('Calculate data...')
    wordle_raw_data_dict.pop('last_save')  # not needed for data (and already saved in file)
    wordle_statistic_dict = {}
    for user_id, user_data_dict in wordle_raw_data_dict.items():
        name = user_data_dict.pop('name')
        points, failure_count, success_count, average_score, best_score, best_score_count = __get_users_wordle_statistic(
            user_data_dict, wordle_ids_set.copy())
        wordle_statistic_dict[user_id] = {
            'name': name,
            'points': points,
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


def __build_date_range(month: Optional[str] = None, year: Optional[str] = None, use_previous: bool = False) -> tuple[
    datetime, datetime, str]:
    now = datetime.now()

    year_num = int(year) if year and year.isdigit() else now.year

    # Determine base month and year
    if month:
        month_num = datetime.strptime(month, '%B').month
    else:
        month_num = now.month - 1 if use_previous else now.month
        if month_num == 0:
            month_num = 12
            year_num -= 1  # Decrement year if wrapping to December

    start_date = datetime(year=year_num, month=month_num, day=1)
    _, days_in_month = calendar.monthrange(year=year_num, month=month_num)
    end_date = datetime(year=year_num, month=month_num, day=days_in_month, hour=23, minute=59, second=59)
    month_str = start_date.strftime('%B %Y')

    return start_date, end_date, month_str


def __parse_command_arg_users(users: Optional[str]) -> list:
    user_filter = []
    logger.debug(f'users: {users}')
    if users:
        users_list = [t.strip() for t in re.split(r'[,\s]+', users) if t.strip()]
        for user in users_list:
            normalized = user.lower().strip()
            mention_match = re.fullmatch(r'<@!?(\d+)>', normalized)
            # Check for user mention (e.g., <@123456>) (with or without '!')
            if mention_match:
                user_filter.append(mention_match.group(1))
            # Check for username
            elif re.fullmatch(r'\w+', normalized):
                user_filter.append(normalized)
    logger.debug(f'user_filter: {user_filter}')
    return user_filter


async def __send_stats_embed(wordle_statistic_dict: dict, month_str: str, channel: discord.TextChannel = None,
                             interaction: discord.Interaction = None):
    """
    Send a pretty embed with monthly stats.
    """
    # Medals for top 3
    medal_symbols = ['🥇', '🥈', '🥉']
    # Sort users by average score (descending)
    sorted_wordle_statistic_dict = sorted(wordle_statistic_dict.items(), key=lambda x: x[1]['average_score'])
    sorted_wordle_statistic_dict = sorted(
        wordle_statistic_dict.items(),
        key=lambda x: (-x[1]["points"], x[1]["average_score"])  # descending points, ascending average
    )

    embed = discord.Embed(
        title=f'📊 Wordle Stats – {month_str}',
        color=0x2ecc71
    )
    for i, (user_id, user_data_dict) in enumerate(sorted_wordle_statistic_dict):
        rank = ' ' + medal_symbols[i] if i < len(medal_symbols) else ''
        block = (
            '```'
            f'🎯 Points : {user_data_dict['points']}{rank}\n'
            f'🎮 Games  : {user_data_dict['participation_count']}\n'
            f'✅ Wins   : {user_data_dict['success_count']}\n'
            f'❌ Fails  : {user_data_dict['failure_count']}\n'
            f'📊 Avg    : {user_data_dict['average_score']}\n'
            f'🏆 Best   : {user_data_dict['best_score']} (×{user_data_dict['best_score_count']})'
            '```'
        )
        embed.add_field(name=f'**{user_data_dict["name"]}**', value=block, inline=False)

    if interaction:
        logger.info('Sending discord message to user')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif channel:
        logger.info('Sending discord message to channel')
        await channel.send(embed=embed)


async def monthly_wordle_statistic(channel: discord.TextChannel):
    logger.info('Start monthly statistic output to channel...')
    if channel:
        last_months_first, end, month_str = __build_date_range(use_previous=True)
        wordle_statistic_dict = await __get_wordle_statistic(last_months_first, end, channel)
        await __send_stats_embed(wordle_statistic_dict, month_str, channel=channel)
    else:
        logger.error('Channel not found!')


async def wordle_stats(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        month: Optional[str] = None,
        year: Optional[str] = None,
        users: Optional[str] = None,
):
    logger.info(f'Command wordle_stats execution started by {interaction.user.name}...')
    user_filter = __parse_command_arg_users(users)
    start, end, month_str = __build_date_range(month=month, year=year)

    if channel:
        wordle_statistic_dict = await __get_wordle_statistic(start, end, channel)
        if not wordle_statistic_dict:
            await interaction.response.send_message(f'📭 No stats found for {month_str}.', ephemeral=True)
            return

        # Filter for user if needed
        if user_filter:
            filtered_dict = {}
            for user_id, data in wordle_statistic_dict.items():
                for f in user_filter:
                    logger.debug(f'filter: {f}; id: {user_id}; name: {data['name']}')
                    if (f.isdigit() and f == user_id) or f in data['name']:
                        filtered_dict[user_id] = data
                        break
            wordle_statistic_dict = filtered_dict

            if not wordle_statistic_dict:
                await interaction.response.send_message(f'🙅 No stats found for that user in {month_str}.', ephemeral=True)
                return

        await __send_stats_embed(wordle_statistic_dict, month_str, interaction=interaction)
    else:
        logger.error('Channel not found!')
        await interaction.response.send_message('Channel not found!', ephemeral=True)
