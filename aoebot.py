import logging
import pathlib
import os
import random
from datetime import datetime
from os import walk

import discord
import openai
import requests
from discord import Message
from discord.ext import commands
from dotenv import load_dotenv
from craiyon import Craiyon
from io import BytesIO
import base64

# https://discord.com/api/oauth2/authorize?client_id=904040817965031464&permissions=2172928&scope=bot
client = discord.Client()

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("DISCORD_API")

user_timeouts = {}


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")


class Taunter(commands.Cog):
    def __init__(self, bot, files, suntzus) -> None:
        self.bot = bot
        self.vc = None
        self.files = files
        self.suntzus = suntzus

    async def check_user_eligible(self, message: Message) -> bool:
        """
        Check if user is eligble to send a command to the bot and manage the users
        timeout between sending commands
        """

        if message.author.voice == None:
            await message.author.send("Joina en voice channel din tönt!")
            await message.delete()
            return False

        username = str(message.author).split("#")[0]
        if username in user_timeouts:
            if user_timeouts[username] < datetime.today().timestamp():
                user_timeouts.pop(username)
            else:
                await message.author.send("Chilla fan")
                await message.delete()
                return False

        user_timeouts[username] = datetime.today().timestamp() + 5
        return True

    async def play_taunt(self, message: Message) -> None:
        if message.content not in self.files:
            await message.delete()
            return

        self.vc.play(discord.FFmpegPCMAudio("taunts/" + self.files[message.content]))
        await message.delete()

    async def play_suntzu(self, message: Message) -> None:
        self.vc.play(discord.FFmpegPCMAudio("suntzu/" + random.choice(self.suntzus)))
        await message.delete()

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        # Dont reply to ourselves or other bots
        if message.author.bot or message.channel.type.name == "private":
            return

        try:
            # If the bot is not connected to the same voice channel, we connect it
            if not self.vc and message.author.voice:
                self.vc = await message.author.voice.channel.connect()
            elif self.vc not in bot.voice_clients and message.author.voice:
                self.vc = await message.author.voice.channel.connect()

            # Execute the command
            if message.content.isdigit() and await self.check_user_eligible(message):
                await self.play_taunt(message)

            elif "sun tzu" in message.content and await self.check_user_eligible(
                message
            ):
                await self.play_suntzu(message)

        except Exception as e:
            logging.getLogger(__name__).exception("Got an exception: ")
            await message.channel.send(e)


bot = commands.Bot(command_prefix="!", help_command=None)


@bot.command()
async def taunts(context):
    text = "Available Taunts: \n ```"
    for i in range(999):
        if str(i) in files:

            if len(text + files[str(i)]) > 2000:
                await context.author.send(text + "```")
                text = "```"
            command = files[str(i)].split(".")[0].split("_")[1]
            numb = files[str(i)].split("_")[0] + ":"
            for j in range(4 - len(numb)):
                numb = numb + " "
            text += numb + command + "\n"
    await context.author.send(text + "```")


@bot.command()
async def aunts(context):
    with open("aunts.jpg", "rb") as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)


@bot.command()
async def taints(context):
    with open("taints.mp4", "rb") as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)


@bot.command()
async def AUNTS(context):
    with open("aunts.jpg", "rb") as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)


@bot.command()
async def Aunts(context):
    with open("aunts.jpg", "rb") as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)


@bot.command()
async def peckel(context, args):

    p = pathlib.Path("peckel.txt")
    if not p.exists():
        p.touch()

    with p.open("r") as f:
        prev = f.readlines()
        peckel = args.replace('"', "").replace(" ", "")
        if peckel:
            peckel = f"{peckel}\n"
            prev.append(peckel)

    with p.open("w") as f:
        f.writelines(prev)

    await context.author.send(f"La till ord: {peckel}")


@bot.command()
async def peckel_remove(context):
    # ANTI OLAV
    if context.author.id == 268484310992945153:
        await context.author.send("SCHAS")
        return

    p = pathlib.Path("peckel.txt")
    p.unlink(missing_ok=True)

    await context.author.send("peckel.txt borttagen")


@bot.command()
async def peckel_status(context):
    # ANTI OLAV
    if context.author.id == 268484310992945153:
        await context.author.send("SCHAS")
        return

    p = pathlib.Path("peckel.txt")
    if not p.exists():
        await context.author.send("peckel.txt finns inte!")
        return

    with p.open("r") as f:
        peckels = f.read()
        await context.author.send("Följande peckels finns:")
        await context.author.send(peckels)


@bot.command()
async def skapa(context, args):
    try:
        p = pathlib.Path("peckel.txt")
        if p.exists():
            with p.open("r") as f:
                forbidden_words = f.readlines()
                for w in forbidden_words:
                    if w.replace("\n", "") in args.lower():
                        await context.author.send("INGET JÄVLA ÄCKELPÄCKEL")
                        return

        await context.channel.send(
            "Skapar Fantastiska Bilder! Använder input: \n{0}".format(args)
        )

        generator = Craiyon()  # Instantiates the api wrapper
        result = await generator.async_generate(args)  # Generate 9 images
        images = result.images  # A list containing image data as base64 encoded strings
        for i in images:
            image = BytesIO(base64.decodebytes(i.encode("utf-8")))
            # Use the PIL's Image object as per your needs
            await context.channel.send(file=discord.File(image, "dalle.png"))

    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception: ")
        await context.channel.send(e)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


@bot.event
async def on_disconnect():
    print("Disconnected")


f = []
dir_path = os.getcwd() + "/suntzu/"
suntzu = {}
i = 0
for (dirpath, dirnames, filenames) in walk(dir_path):

    for f in filenames:
        try:
            if f.split(".")[1] == "mp3":
                suntzu[i] = f
                i += 1
        except:
            f = f
            # print(f)

f = []
dir_path = os.getcwd() + "/taunts/"
print(dir_path)
files = {}
for (dirpath, dirnames, filenames) in walk(dir_path):
    for f in filenames:
        try:
            if f.split(".")[1] == "ogg" or f.split(".")[1] == "mp3":
                number = f.split("_")[0]
                files[number] = f
        except:
            f = f
            # print(f)

bot.add_cog(Taunter(bot, files, suntzu))

bot.run(TOKEN)
