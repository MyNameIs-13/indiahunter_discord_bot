# inDiaHunter Discord Bot

combines several functions:

- reads shared wordle data from specified channel and returns statistics about it.
Post the monthly statistic to a channel once each new month
Reacts to the command `wordle_stats <month> <year> <users>` to provide statistic
![](Screenshot_2025-05-18_00-08-34.png)
- keeps tracks of reminder and notifies users when they are due `/reminder`

## Requirements

- Python 3.13
- `ffmpeg`, `opus`, `libsodium` (voice playback for `/reminder`'s voice-channel option)
- discord server with a discord bot: <https://discord.com/developers/docs/quick-start/getting-started#configuring-your-bot>

## Setup

- install dependencies:
  ```shell
  pip install -r app/requirements.txt
  ```
- create a `data` folder next to `app/` (wordle-statistics and reminder-TTS
  temp files are written there, as `./data`) and make sure it's writable by
  the user running the bot
- export the required environment variables (or place them in a `.env`
  file in `app/`, picked up automatically):
  ```text
  DISCORD_TOKEN=ABCDEF123456
  CHANNEL_ID=1234567890
  SERVER_ID=1234567890
  LOG_LEVEL=INFO
  ```

## Run

```shell
cd app
python discord_bot.py
```

## Environment variables

- `DISCORD_TOKEN` - required - token from your discord bot
- `CHANNEL_ID` - required - id from your discord channel where wordle data is shared
- `SERVER_ID` - optional - id from your discord server (makes the command available faster)
- `LOG_LEVEL` - optional - `{INFO, WARNING, ERROR, CRITICAL}` (everything else defaults to `DEBUG`); logs always go to stdout
