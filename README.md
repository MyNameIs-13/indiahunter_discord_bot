# inDiaHunter Discord Bot

combines several functions:

- reads shared wordle data from specified channel and returns statistics about it.
Post the monthly statistic to a channel once each new month
Reacts to the command `wordle_stats <month> <year> <users>` to provide statistic
![](Screenshot_2025-05-18_00-08-34.png)
- keeps tracks of reminder and notifies users when they are due `/reminder`

## Requirements

- docker: <https://docs.docker.com/engine/install/>
  - or rootless docker: <https://docs.docker.com/engine/security/rootless/>
- docker compose: <https://docs.docker.com/compose/install/>
- discord server with a discord bot: <https://discord.com/developers/docs/quick-start/getting-started#configuring-your-bot>

## Preparation

- crate a `.secrets` file (example values)
  ```text
  DISCORD_TOKEN=ABCDEF123456
  ```
- create a folder for `data` and add their path to the `.env` file as `DATA_PATH`
  - the used folder require access right for anybody when the `nobody` user is used to run the container
    ```shell
    mkdir /your/path/data
    sudo chown -R 65534:65534 /your/path/data
    chmod -R u+rw /your/path/data
    ```  
- crate a `.env` file (example values)
  ```text
  TAG=0.0.6
  UID=65534
  GID=65534
  LOG_LEVEL=INFO
  CHANNEL_ID=1234567890
  SERVER_ID=1234567890
  LOG_PATH=./logs
  DATA_PATH=./data
  ```
- (optional) create a folder (and give access permissions) for `logs`
  - when an accessible `/app/logs` mount is created, and LOG_LEVEL=DEBUG, log files will be written into this folder. Otherwise they are written to stdout
- (optional) define UID (UserId) and GID (GroupId) for the user which should be used inside the container (default is nobody)

### Build & run docker container

navigate to folder (`cd /your/path`), then:
```shell
docker compose up
```

to update the image use:
````shell
docker compose up --build
````

## Misc

- The following environment variables can be passed to the docker container:
  - LOG_LEVEL - optional - {INFO, WARNING, ERROR, CRITICAL} (everything else defaults to DEBUG)
  - DISCORD_TOKEN - required - token from your discord bot
  - CHANNEL_ID - required - id from your discord channel where wordle data is shared
  - SERVER_ID - optional - id from your discord server (makes the command available faster)
- Trivy
  - using on machine where image is located
    ```shell
    trivy image indiahunter-discord-bot:<TAG>
    ```
  - when using a different machine
    ```shell
    # on machine with image
    docker save -o /save/path/indiahunter-discord-bot.tar indiahunter-discord-bot:<TAG>
    # -> transfer image cp, scp, rsync, smb, ...
    # on machine with trivy
    trivy image --input /path/to/indiahunter-discord-bot.tar
    ```
  - current output
    ```text
    /path/to/indiahunter-discord-bot.tar (alpine 3.21.2)
    Total: 0 (UNKNOWN: 0, LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0)
    ```
