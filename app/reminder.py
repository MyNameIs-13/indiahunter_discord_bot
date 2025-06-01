import asyncio
import logging
import os
import re
from datetime import datetime, timedelta

import discord
from gtts import gTTS
from langdetect import detect

logger = logging.getLogger('reminder')
ACTIVE_TIMERS = {}


def __parse_time_string(time_str: str) -> int:
    time_str = time_str.strip().lower()
    logger.debug(f'input time string: {time_str}')

    # Try HH:MM absolute time format
    match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)  # schedule for tomorrow
        return int((target - now).total_seconds())

    # Fallback: parse relative time (e.g. 1h30m)
    total_seconds = 0
    pattern = re.compile(r'(\d+)(h|m|s)?')
    matches = pattern.findall(time_str)

    if not matches:
        raise ValueError('Invalid time format')

    for value, unit in matches:
        value = int(value)
        if unit == 'h':
            total_seconds += value * 3600
        elif unit == 'm':
            total_seconds += value * 60
        elif unit == 's' or unit == '':
            total_seconds += value
        else:
            raise ValueError('Invalid time unit')
    logger.debug(f'output time seconds: {total_seconds}')
    return total_seconds


async def __run_timer(interaction: discord.Interaction, seconds: int, message: str, voice: bool):
    user = interaction.user
    try:
        await asyncio.sleep(seconds)
        # Check if user is in a voice channel
        guild = interaction.guild
        user = guild.get_member(interaction.user.id)
        logger.info(f'reminder for {user.name} will be announced')
        try:
            lang = detect(message)  # Auto-detect language (e.g., 'en', 'fr', 'de')
        except:
            lang = 'en'  # Fallback if detection fails

        if lang == 'de':
            message = f'{user.name}. Das ist deine Erinnerung für {message}'
        else:
            message = f'{user.name}. This is your reminder for {message}'

        channel = user.voice.channel
        if (voice and user and user.voice and user.voice.channel) or (channel and len(channel.members) == 1):
            vc = await user.voice.channel.connect()

            tts = gTTS(text=message, lang=lang)
            tts.save(f'./data/temp_speech_{user.id}.mp3')

            vc.play(discord.FFmpegPCMAudio(f'./data/temp_speech_{user.id}.mp3'))
            while vc.is_playing():
                await asyncio.sleep(1)

            await vc.disconnect()
            os.remove(f'./data/temp_speech_{user.id}.mp3')
        else:
            # DM fallback
            try:
                dm = await user.create_dm()
                await dm.send(message)
            except Exception:
                try:
                    await interaction.followup.send(message, ephemeral=True)
                except:
                    pass

    except asyncio.CancelledError:
        pass
    finally:
        ACTIVE_TIMERS.pop(user.id, None)
        if os.path.exists(f'./data/temp_speech_{user.id}.mp3'):
            os.remove(f'./data/temp_speech_{user.id}.mp3')


async def reminder(
        interaction: discord.Interaction,
        time: str,
        message: str = 'something',
        voice: bool = False
):
    user = interaction.user
    respond_message = ''
    logger.info(f'Command reminder execution started by {user.name}...')

    try:
        seconds = __parse_time_string(time)
        if seconds < 1 or seconds > 86400:
            await interaction.response.send_message('❌ Please enter a time between 1 second and 24 hours from now.', ephemeral=True)
            return
    except ValueError as verr:
        await interaction.response.send_message(f'❌ {verr}. Try `5m`, `1h30m`, or `15:45`.', ephemeral=True)
        return

    # Cancel existing timer if present
    if user.id in ACTIVE_TIMERS:
        task, last_reminder_message = ACTIVE_TIMERS[user.id]
        task.cancel()
        respond_message = f'⏹️ Your previous reminder for "**{last_reminder_message}**" was canceled.\n'

    await interaction.response.send_message(f'{respond_message}⏱️ I\'ll remind you in {seconds} seconds.', ephemeral=True)

    task = asyncio.create_task(__run_timer(interaction, seconds, message, voice))
    ACTIVE_TIMERS[user.id] = (task, message)


async def cancel_reminder(interaction: discord.Interaction):
    user = interaction.user
    if user.id in ACTIVE_TIMERS:
        task, message = ACTIVE_TIMERS[user.id]
        task.cancel()
        logger.info(f'{user.name} cancelled the reminder')
        await interaction.response.send_message(f'❌ Your reminder for "**{message}**" has been canceled.', ephemeral=True)
    else:
        await interaction.response.send_message('⚠️ You don’t have an active reminder.', ephemeral=True)
