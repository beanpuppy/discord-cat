import asyncio
import os
import requests
import json
import discord

from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SRV_STAT_URL = "https://api.mcsrvstat.us/2/"
JSON_FILE = "data/data.json"

TOKEN = os.environ["DISCORD_TOKEN"]
STATUS_CHANNEL_ID = os.environ["STATUS_CHANNEL_ID"]
SERVER_IP = os.environ["MC_SERVER_IP"]

NOTIFY_STAFF_IDS = os.getenv("NOTIFY_STAFF_IDS", "").split(",")
NOTIFY_STRING = ", ".join([f"<@{id}>" for i in NOTIFY_STAFF_IDS if i])

client = discord.Client()

status_channel = None
stats_message_task = None

data = {
    "stats_message_id": None,
}


def load_data():
    global data

    try:
        with open(JSON_FILE, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        pass


def save_data():
    global data

    with open(JSON_FILE, "w") as file:
        json.dump(data, file)


async def schedule_func(timeout, stuff):
    while True:
        await asyncio.sleep(timeout)
        await stuff()


def get_server_stats():
    return requests.get(SRV_STAT_URL + SERVER_IP).json()


def format_server_stat_message(stats):
    now = datetime.utcnow()
    now_formatted = now.strftime("%Y-%m-%d %H:%M:%S")

    message = f"My status report for Minecraft server on {SERVER_IP}\n"
    message += f"Last updated on {now_formatted} UTC+00:00\n\n"

    if stats["online"] is False:
        message += ":red_circle: Server offline :(\n"
        message += "Please let staff know if it is down for a long time."
        return message

    players = stats["players"]
    p_online = players["online"]

    message += ":green_circle: Server online! Have fun!\n\n"

    if p_online:
        message += f"{p_online}/{players['max']} friends online:\n"
        message += "\n".join(["- " + p for p in players["list"]])
    else:
        message += "Nobody has joined yet :(\n"

    return message


def create_stats_message():
    stats = get_server_stats()
    return format_server_stat_message(stats)


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
    data["stats_message_id"] = res.id  # type: ignore
    save_data()


def sync_send_stats_message():
    asyncio.run(send_stats_message())


@client.event
async def on_ready():
    global status_channel, stats_message_task

    print(f"{client.user} has connected to Discord!")

    status_channel = client.get_channel(int(STATUS_CHANNEL_ID))
    stats_message_task = asyncio.create_task(schedule_func(10, send_stats_message))


load_data()
client.run(TOKEN)
