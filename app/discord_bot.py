import asyncio
import calendar
import os
import re
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
from wordle_statistics import get_wordle_statistic

setup_logging()
logger = getLogger('wordle_statistic_bot')

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
    async def setup_hook(self):
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
async def health():
    if client.is_ready():
        return {'status': 'healthy'}
    logger.error('Client is unhealthy')
    return {'status': 'unhealthy'}, 503


async def run_health_server():
    config = uvicorn.Config(app, host='0.0.0.0', port=8080, loop='asyncio', log_config=None)
    server = uvicorn.Server(config)
    await server.serve()


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

    embed = discord.Embed(
        title=f'📊 Wordle Stats – {month_str}',
        color=0x2ecc71
    )
    for i, (user_id, user_data_dict) in enumerate(sorted_wordle_statistic_dict):
        rank = ' ' + medal_symbols[i] if i < len(medal_symbols) else ''
        block = (
            '```'
            f'🎮 Games : {user_data_dict['participation_count']}\n'
            f'✅ Wins  : {user_data_dict['success_count']}\n'
            f'❌ Fails : {user_data_dict['failure_count']}\n'
            f'📊 Avg   : {user_data_dict['average_score']}{rank}\n'
            f'🏆 Best  : {user_data_dict['best_score']} (×{user_data_dict['best_score_count']})'
            '```'
        )
        embed.add_field(name=f'**{user_data_dict["name"]}**', value=block, inline=False)

    if interaction:
        logger.info('Sending discord message to user')
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif channel:
        logger.info('Sending discord message to channel')
        await channel.send(embed=embed)


async def monthly_wordle_statistic():
    logger.info('Start monthly statistic output to channel...')
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        last_months_first, end, month_str = __build_date_range(use_previous=True)
        wordle_statistic_dict = await get_wordle_statistic(last_months_first, end, channel)
        await __send_stats_embed(wordle_statistic_dict, month_str, channel=channel)
    else:
        logger.error('Channel not found!')


async def __send_dm(ctx, message: str = None, embed: discord.Embed = None):
    try:
        await ctx.author.send(content=message, embed=embed)
    except discord.Forbidden:
        logger.error(f'Could not DM {ctx.author.name}')
        await ctx.reply('❌ I couldn\'t DM you. Please enable DMs from server members.')


# Month autocomplete
async def month_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    return [
        app_commands.Choice(name=month, value=month)
        for month in months if current.lower() in month.lower()
    ]

# Year autocomplete (e.g., 2020–2030)
async def year_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    this_year = datetime.now().year
    years = [str(y) for y in range(this_year - 5, this_year + 6)]
    return [
        app_commands.Choice(name=year, value=year)
        for year in years if current in year
    ]


@client.tree.command(name='wordle_stats', description='Provides monthly wordle statistic from the wordle channel ')
@app_commands.describe(
    month="(optional) The month for which the statistic should be given",
    year="(optional) The year for which the statistic should be given",
    users="(optional) The users for which the statistic should be given"
)
@app_commands.autocomplete(month=month_autocomplete, year=year_autocomplete)
async def wordle_stats(
        interaction: discord.Interaction,
        month: Optional[str] = None,
        year: Optional[str] = None,
        users: Optional[str] = None,
):
    logger.info('Command wordle_stats execution started...')
    user_filter = __parse_command_arg_users(users)
    start, end, month_str = __build_date_range(month=month, year=year)

    channel = client.get_channel(CHANNEL_ID)
    if channel:
        wordle_statistic_dict = await get_wordle_statistic(start, end, channel)
        if not wordle_statistic_dict:
            await interaction.response.send_message(f'📭 No stats found for {month_str}.', ephemeral=True)
            return

        # Filter for user if needed
        if user_filter:
            filtered_dict = {}
            for user_id, data in wordle_statistic_dict.items():
                for f in user_filter:
                    logger.debug(f'filter: {f}; id: {user_id}; name: {data['name']}')
                    if (f.isdigit() and int(f) == int(user_id)) or f in data['name']:
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


@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user}')
    # Schedule to run on the 1st of every month at 00:05
    scheduler.add_job(monthly_wordle_statistic, 'cron', day=1, hour=0, minute=5)
    scheduler.start()
    asyncio.create_task(run_health_server())


client.run(TOKEN, log_handler=None)
