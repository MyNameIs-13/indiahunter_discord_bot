FROM docker.io/python:3.13.3-alpine3.21

WORKDIR /app

COPY app/ .

RUN pip install --no-cache-dir -r /app/requirements.txt \
  ; mkdir /app/logs \
  ; mkdir /app/statistics \
  ; chmod 0444 /app/discord_bot.py \
  ; chmod 0444 /app/custom_logger.py \
  ; chmod 0444 /app/wordle_statistics.py

ENTRYPOINT [ "python", "discord_bot.py" ]