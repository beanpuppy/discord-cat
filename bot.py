import asyncio
import os
import json
import discord
import random
import logging

from discord.ext import commands
from discord_slash import SlashCommand
from dateutil import parser, tz
from mcstatus import MinecraftServer
from datetime import datetime, timedelta
from dotenv import load_dotenv

from lib.db import db, create_db, SessionHistory, DowntimeHistory

load_dotenv()

JSON_FILE = "data/data.json"
LOG_FILE = "data/data.log"
SONGS_FILE = "songs.json"

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
STATUS_CHANNEL_ID = os.environ["STATUS_CHANNEL_ID"]
SERVER_IP = os.environ["MC_SERVER_IP"]

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
PING_INTERVAL = int(os.getenv("PING_INTERVAL", "30"))
GRACE_PERIOD = int(os.getenv("GRACE_PERIOD", "5"))
DEFAULT_ROLES = os.getenv("DEFAULT_ROLES", "").split(",")
STAFF_IDS = os.getenv("STAFF_IDS", "").split(",")
NOTIFY_STRING = ", ".join([f"<@{id}>" for i in STAFF_IDS if i])

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

intents = discord.Intents.all()
bot = commands.Bot(intents=intents, command_prefix="/")
slash = SlashCommand(bot, sync_commands=True)

with open(SONGS_FILE, "r") as file:
    songs = json.load(file)

presence_task = None
stats_message_task = None
save_data_task = None

status_channel = None

data = {"stats_message_id": None, "players": {}, "downtime_started": None}


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

        db.connect()

        try:
            await func()
        except Exception as e:
            if ENVIRONMENT == "dev":
                print(e)
                raise e

            logger.error(e)
        finally:
            db.close()


def get_server_status():
    global data

    now = datetime.utcnow()

    try:
        status = server.status()

        # Server is up, measure the time if it was down
        if data["downtime_started"] is not None:
            downtime_started = parse_date(data["downtime_started"])

            # Let's be nice and give a grace period
            grace_period = downtime_started + timedelta(minutes=GRACE_PERIOD)

            if now > grace_period:  # type: ignore
                DowntimeHistory.insert(
                    {"start": format_date(downtime_started), "end": format_date(now)}
                )

            data["downtime_started"] = None

        return [now, status]
    except Exception as e:
        # Exception raised means server is down
        logger.error(e)

        if data["downtime_started"] is None:
            data["downtime_started"] = format_date(now)

        return [now, None]


def set_player_sessions(now_formatted, sample):
    global data

    online_names = [s.name for s in sample or []]

    for p in online_names:
        player = data["players"].get(p, {})
        online = player.get("online")

        player["last_seen"] = now_formatted

        if online is None:
            player["online"] = now_formatted

        data["players"][p] = player

    for name, value in data["players"].items():
        if value.get("online") is not None and name not in online_names:
            SessionHistory.insert(
                {"player": name, "start": value["online"], "end": now_formatted}
            )

            data["players"][name]["online"] = None


def format_server_stat_message(now, status):
    now_formatted = format_date(now)

    message = "@here is my server status report!\n"
    message += f"`updated at {now_formatted} UTC`\n\n"

    # Server status
    if status is None:
        message += ":red_circle: Server offline :(\n"
        message += "Please let staff know if it has been down for a long time."
        set_player_sessions(now_formatted, [])
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
        message += "I haven't seen any friends online in the past day"

    # Player session history
    set_player_sessions(now_formatted, players.sample)

    return message


def create_stats_message():
    now, status = get_server_status()
    message = format_server_stat_message(now, status)

    save_data()

    return message


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

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name=song)
    )


@bot.event
async def on_member_join(member):
    for role_id in DEFAULT_ROLES:
        role = discord.utils.get(member.guild.roles, id=int(role_id))
        await member.add_roles(role)


@bot.event
async def on_ready():
    global status_channel, stats_message_task, presence_task

    logger.info(f"{bot.user} has connected to Discord!")

    status_channel = bot.get_channel(int(STATUS_CHANNEL_ID))
    stats_message_task = asyncio.create_task(
        schedule_func(PING_INTERVAL, send_stats_message)
    )

    # Change each 30 mins
    if ENVIRONMENT == "prod":
        await change_presence()
        presence_task = asyncio.create_task(schedule_func(1800, change_presence))


@slash.slash(
    name="modpack",
    description="Displays the Minecraft modpack link",
    guild_ids=[GUILD_ID],
)
async def modpack(ctx):
    await ctx.send("https://www.curseforge.com/minecraft/modpacks/rule-breakers")


if __name__ == "__main__":
    create_db()
    load_data()
    bot.run(TOKEN)
