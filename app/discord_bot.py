import asyncio
import os
from datetime import datetime
from logging import getLogger
from typing import Optional

import discord
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import app_commands
from dotenv import load_dotenv
from fastapi import FastAPI

from custom_logger import setup_logging
from reminder import cancel_reminder as __cancel_reminder, reminder as __reminder
from wordle_statistics import wordle_stats as __wordle_stats, monthly_wordle_statistic

setup_logging()
logger = getLogger('inDiaHunter_bot')

# for debugging purposes when running outside of container
if os.path.exists('../.secrets'):
    load_dotenv('../.secrets')
if os.path.exists('../.env'):
    load_dotenv('../.env')
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
SERVER_ID = os.getenv('SERVER_ID')
if SERVER_ID:
    SERVER_ID = int(SERVER_ID)
    MY_GUILD = discord.Object(id=SERVER_ID)  # replace with your guild id
else:
    MY_GUILD = None


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self) -> None:
        # This copies the global commands over to your guild.
        if MY_GUILD:
            self.tree.copy_global_to(guild=MY_GUILD)
            await self.tree.sync(guild=MY_GUILD)
        else:
            await self.tree.sync()


intents = discord.Intents.default()
client = MyClient(intents=intents)
scheduler = AsyncIOScheduler()

# Health server setup
app = FastAPI()

@app.get('/health')
async def __health():
    if client.is_ready():
        return {'status': 'healthy'}
    logger.error('Client is unhealthy')
    return {'status': 'unhealthy'}, 503


async def __run_health_server():
    config = uvicorn.Config(app, host='0.0.0.0', port=8080, loop='asyncio', log_config=None)
    server = uvicorn.Server(config)
    await server.serve()


# Month autocomplete
async def __month_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    return [
        app_commands.Choice(name=month, value=month)
        for month in months if current.lower() in month.lower()
    ]


# Year autocomplete (e.g., 2020–2030)
async def __year_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    this_year = datetime.now().year
    years = [str(y) for y in range(this_year - 5, this_year + 6)]
    return [
        app_commands.Choice(name=year, value=year)
        for year in years if current in year
    ]


@client.tree.command(name='wordle_stats', description='Provides monthly wordle statistic from the wordle channel')
@app_commands.describe(
    month='(optional) The month for which the statistic should be given',
    year='(optional) The year for which the statistic should be given',
    users='(optional) The users for which the statistic should be given'
)
@app_commands.autocomplete(month=__month_autocomplete, year=__year_autocomplete)
async def wordle_stats(
        interaction: discord.Interaction,
        month: Optional[str] = None,
        year: Optional[str] = None,
        users: Optional[str] = None,
):
    channel = client.get_channel(CHANNEL_ID)
    await __wordle_stats(interaction, channel, month, year, users)


@client.tree.command(name='reminder', description='Let the bot remind you')
@app_commands.describe(
    time='When should the reminder remind you?',
    message='what is the reminder for?'
)
async def reminder(
        interaction: discord.Interaction,
        time: str,
        message: str = 'something',
        voice: bool = False
):
    await __reminder(interaction, time, message, voice)


@client.tree.command(name='cancel_reminder', description='Cancel your active reminder.')
async def cancel_reminder(interaction: discord.Interaction):
    await __cancel_reminder(interaction)


@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user}')
    # Schedule to run on the 1st of every month at 00:05
    channel = client.get_channel(CHANNEL_ID)
    # Only add the job if it doesn't already exist
    if not scheduler.get_job('monthly_wordle'):
        scheduler.add_job(
            monthly_wordle_statistic,
            'cron',
            day=1,
            hour=0,
            minute=5,
            kwargs={'channel': channel},
            id='monthly_wordle'
        )
    if not scheduler.running:
        scheduler.start()
    asyncio.create_task(__run_health_server())


client.run(TOKEN, log_handler=None)
