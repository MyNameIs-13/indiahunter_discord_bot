import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import discord
from gtts import gTTS
from langdetect import detect

logger = logging.getLogger('reminder')
ACTIVE_TIMERS = {}


def __parse_time_string(time_str: str) -> int:
    time_str = time_str.strip().lower()
    logger.info(f'input time string: {time_str}')

    # Try HH:MM absolute time format
    match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)  # schedule for tomorrow
        total_seconds = int((target - now).total_seconds())
        logger.info(f'output time seconds: {total_seconds}')
        return total_seconds

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
        elif unit == 'm' or unit == '':
            total_seconds += value * 60
        elif unit == 's':
            total_seconds += value
        else:
            raise ValueError('Invalid time unit')
    logger.info(f'output time seconds: {total_seconds}')
    return total_seconds


async def __send_reminder_fallback(interaction: discord.Interaction, user: discord.User | discord.Member, message: str):
    """Tries to send a DM first, falls back to the interaction channel."""
    try:
        await user.send(f'🔔 {message}')
    except discord.Forbidden:
        logger.warning(f'Cannot send DM to {user.name}. Fallback to channel.')
        try:
            # Make sure channel is not None and is a TextChannel
            if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
                 await interaction.channel.send(f'{user.mention}, I couldn\'t DM you, so here is your reminder: {message}')
            else:
                logger.error('Cannot send fallback message, interaction channel is not a valid text channel.')
        except discord.Forbidden:
            logger.error(f'Cannot send message to channel {interaction.channel.name} either due to permissions.')
        except Exception as e:
            logger.error(f'Failed to send fallback message to channel: {e}')
    except Exception as e:
        logger.error(f'Failed to send DM to {user.name}: {e}')


async def __run_timer(interaction: discord.Interaction, seconds: int, message: str, voice: bool):
    user = interaction.user
    guild = interaction.guild
    original_message = message

    try:
        await asyncio.sleep(seconds)

        # Refresh user object to get current voice state
        member = guild.get_member(user.id)
        if not member:
            logger.warning(f'User {user.name} not found in guild, cannot send reminder.')
            return

        # Prepare localized message
        try:
            lang = detect(original_message)
        except:
            lang = 'en'  # Fallback if detection fails

        if lang == 'de':
            tts_message = f'{member.display_name}. Das ist deine Erinnerung für {original_message}'
        else:
            tts_message = f'{member.display_name}. This is your reminder for {original_message}'

        # Voice reminder logic
        if voice and member.voice and member.voice.channel:
            vc = None
            filename = f'./data/temp_speech_{user.id}.mp3'
            try:
                # Generate TTS audio file
                tts = gTTS(text=tts_message, lang=lang)
                tts.save(filename)
                if not os.path.exists(filename) or os.path.getsize(filename) == 0:
                    raise RuntimeError('TTS audio file is missing or empty.')

                # Connect to voice channel and play audio
                vc = await member.voice.channel.connect()
                playback_done = asyncio.Event()
                playback_failed = False

                def after_playback(error: Optional[Exception]):
                    nonlocal playback_failed
                    if error:
                        logger.error(f'Playback error: {error}')
                        playback_failed = True
                    playback_done.set()

                vc.play(discord.FFmpegPCMAudio(filename), after=after_playback)
                await playback_done.wait()

                if playback_failed:
                    await __send_reminder_fallback(interaction, member,
                                             '⚠️ Audio playback failed. Here\'s your reminder instead: ' + original_message)

            except Exception as e:
                logger.error(f'[Voice Playback Error] {e}')
                await __send_reminder_fallback(interaction, member,
                                         '⚠️ An error occurred during voice playback. Here\'s your reminder instead: ' + original_message)
            finally:
                if vc and vc.is_connected():
                    await vc.disconnect(force=True)
                if os.path.exists(filename):
                    os.remove(filename)
        else:
            # DM fallback if voice not requested or user not in a channel
            await __send_reminder_fallback(interaction, member, original_message)

    except asyncio.CancelledError:
        logger.info(f'Reminder for {user.name} was cancelled.')
    except Exception as e:
        logger.error(f'An unexpected error occurred in timer for {user.name}: {e}')
        await __send_reminder_fallback(interaction, user, f'⚠️ An unexpected error occurred with your reminder for "{original_message}".')
    finally:
        ACTIVE_TIMERS.pop(user.id, None)


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

    # Acknowledge the command and inform the user
    time_delta = timedelta(seconds=seconds)
    await interaction.response.send_message(f'{respond_message}⏱️ I\'ll remind you in **{time_delta}** about "**{message}**".', ephemeral=True)

    task = asyncio.create_task(__run_timer(interaction, seconds, message, voice))
    ACTIVE_TIMERS[user.id] = (task, message)


async def cancel_reminder(interaction: discord.Interaction):
    user = interaction.user
    if user.id in ACTIVE_TIMERS:
        task, message = ACTIVE_TIMERS[user.id]
        task.cancel()
        ACTIVE_TIMERS.pop(user.id, None)  # Eagerly remove
        logger.info(f'{user.name} cancelled the reminder for "{message}"')
        await interaction.response.send_message(f'❌ Your reminder for "**{message}**" has been canceled.', ephemeral=True)
    else:
        await interaction.response.send_message('⚠️ You don’t have an active reminder.', ephemeral=True)
