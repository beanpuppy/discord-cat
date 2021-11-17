import asyncio
import os
import json
import discord
import random
import logging

from dateutil import parser, tz
from mcstatus import MinecraftServer
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

JSON_FILE = "data/data.json"
LOG_FILE = "data/data.log"
SONGS_FILE = "songs.json"

TOKEN = os.environ["DISCORD_TOKEN"]
STATUS_CHANNEL_ID = os.environ["STATUS_CHANNEL_ID"]
SERVER_IP = os.environ["MC_SERVER_IP"]

NOTIFY_STAFF_IDS = os.getenv("NOTIFY_STAFF_IDS", "").split(",")
NOTIFY_STRING = ", ".join([f"<@{id}>" for i in NOTIFY_STAFF_IDS if i])

EMOJIS = {
    "beanplush": "<:beanplush:899476921002373130>",
    "pikachu": "<:pikachu:909111043886833684>",
    "eevee": "<:eevee:910222072385531945>",
}

logger = logging.getLogger("discord-mc-status")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

server = MinecraftServer.lookup(SERVER_IP)
client = discord.Client()

with open(SONGS_FILE, "r") as file:
    songs = json.load(file)

presence_task = None
stats_message_task = None
save_data_task = None

status_channel = None

data = {"stats_message_id": None, "players": {}, "downtime": []}


def parse_date(date):
    dt = parser.parse(date)
    dt.astimezone(tz.UTC)
    return dt


def format_date(date):
    return date.strftime("%Y-%m-%d %H:%M:%S")


def load_data():
    global data

    try:
        with open(JSON_FILE, "r") as file:
            data.update(json.load(file))
    except FileNotFoundError:
        pass


def save_data():
    global data

    with open(JSON_FILE, "w") as file:
        json.dump(data, file)


async def schedule_func(timeout, func):
    while True:
        await asyncio.sleep(timeout)

        try:
            await func()
        except Exception as e:
            logger.error(e)


def get_server_status():
    try:
        return server.status()
    except Exception as e:
        logger.error(e)
        return None


def format_server_stat_message(status):
    now = datetime.utcnow()
    now_formatted = format_date(now)

    message = "@here is my server status report!\n"
    message += f"`updated at {now_formatted} UTC`\n\n"

    # Server status

    if status is None:
        message += ":red_circle: Server offline :(\n"
        message += "Please let staff know if it is down for a long time."
        return message

    players = status.players
    p_online = players.online

    message += ":green_circle: Server online! Have fun!\n\n"

    # Players online

    if p_online > 0:
        message += (
            f"{p_online} friend{'s' if p_online > 1 else ''} "
            f"are online now! {EMOJIS['eevee']}\n"
        )
        message += "\n".join(["- " + p.name for p in players.sample])

        for p in players.sample:
            data["players"][p.name] = {"last_seen": now_formatted}
    else:
        message += f"Nobody is online right now {EMOJIS['pikachu']}"

    # Num players online past day

    message += "\n\n"
    data_players = data["players"].items()
    now_delta = now - timedelta(hours=24)

    if len(data_players) > 0:
        count = len(
            [
                p_data
                for _, p_data in data_players
                if now_delta <= parse_date(p_data["last_seen"]) <= now
            ]
        )

        message += (
            f"{EMOJIS['beanplush']} I've seen {count} friend{'s' if count > 1 else ''} "
            f"online in the past day"
        )
    else:
        message += "I've seen no friends online in the past day"

    return message


def create_stats_message():
    status = get_server_status()
    return format_server_stat_message(status)


async def send_stats_message():
    global data, status_channel

    message = create_stats_message()

    if data["stats_message_id"]:
        try:
            msg = await status_channel.fetch_message(data["stats_message_id"])
            await msg.edit(content=message)
            return
        except discord.errors.NotFound:
            pass

    res = await status_channel.send(message)
    data["stats_message_id"] = res.id
    save_data()


async def change_presence():
    song = random.choice(songs)

    await client.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name=song)
    )

    # Piggybacking off this function to periodically save data to disk
    save_data()


@client.event
async def on_ready():
    global status_channel, stats_message_task, presence_task

    logger.info(f"{client.user} has connected to Discord!")

    status_channel = client.get_channel(int(STATUS_CHANNEL_ID))
    stats_message_task = asyncio.create_task(schedule_func(30, send_stats_message))

    # Change each 30 mins
    await change_presence()
    presence_task = asyncio.create_task(schedule_func(1800, change_presence))


if __name__ == "__main__":
    load_data()
    client.run(TOKEN)
