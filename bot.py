import asyncio
import os
import json
import discord
import random

# import requests

from mcstatus import MinecraftServer
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

server = MinecraftServer.lookup(SERVER_IP)
client = discord.Client()

presence_task = None
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


def get_server_status():
    try:
        return server.status()
    except Exception as e:
        print(e)
        return None


def format_server_stat_message(status):
    now = datetime.utcnow()
    now_formatted = now.strftime("%Y-%m-%d %H:%M:%S")

    message = "@here is my server status report!\n"
    message += f"`updated at {now_formatted} UTC`\n\n"

    if status is None:
        message += ":red_circle: Server offline :(\n"
        message += "Please let staff know if it is down for a long time."
        return message

    players = status.players
    p_online = players.online

    message += ":green_circle: Server online! Have fun!\n\n"

    if p_online > 0:
        message += f"{p_online} friend{'s' if p_online > 1 else ''} online:\n"
        message += "\n".join(["- " + p.name for p in players.sample])
    else:
        message += "Nobody is online now :("

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
    data["stats_message_id"] = res.id  # type: ignore
    save_data()


async def change_presence():
    song = random.choice([
        "Alberto Balsam", "Nyan Cat", "Heartbeat", "Puppy Linux Song", "Kid A",
        "#1F1e33", "Lateralus"
    ])

    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, name=song
        )
    )


@client.event
async def on_ready():
    global status_channel, stats_message_task, presence_task

    print(f"{client.user} has connected to Discord!")

    status_channel = client.get_channel(int(STATUS_CHANNEL_ID))
    stats_message_task = asyncio.create_task(schedule_func(30, send_stats_message))

    # Change each 30 mins
    await change_presence()
    presence_task = asyncio.create_task(schedule_func(1800, change_presence))


load_data()
client.run(TOKEN)
