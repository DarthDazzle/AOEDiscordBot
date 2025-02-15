import asyncio
import base64
import concurrent.futures
import logging
import os
import pathlib
import random
import time
import threading
import requests
import subprocess
import pickle
import aiohttp

from datetime import datetime
from functools import partial
from io import BytesIO
from os import walk
from typing import List

import discord
from discord import Message
from discord import Member
from discord.ext import commands
from discord import app_commands
#import interactions

from craiyon import Craiyon
from dotenv import load_dotenv
from PIL import Image
import psutil

euphemisms = ["a solo game", "with oneself", "a one-person sport", "a private symphony", "a tantalizing one-man show", "stealthy solo escapade", "sensuous solo tango", "an intimate rendezvous with oneself", "the one-handed piano", "tug of war with the cyclops"] 

lazyDict = {
    "dirtydazzle": "<:vik:1061396237200404542>",
    "ixuue": "<:ff:895743538166366249>",
    "darthdazzle": "<:axl:898278404661596180>",
    "mrseal1993": "<:seb:895744495310733344>",
    "knastatur": "<:hurr:898280606138527824>",
    "tehbaldeagle": "<:broken:896724301435265044>",
    "sjudin": "<:jak:934386916487479326>",
    "AOE_Taunts": "<:burk:895723401090588692>",
    "emil0x": "<:emil:895751124580200508>",
    "paltis_": "<:koks:1201622535805075516>",
    "mangeee": "<:hajp:896056974905602049>",
    "amandasofia9485": "<:mandy:1206331809604837476>",
    ".tenex": "<:caaaarl:1208752788318847027>",
    "sarazodd": "<:zod:1296168810511990854>"
}

lazyDict2 = {
    "dirtydazzle": "50",
    "ixuue": "667",
    "darthdazzle": "89",
    "mrseal1993": "137",
    "knastatur": "30",
    "tehbaldeagle": "111",
    "sjudin": "73",
    "AOE_Taunts": "",
    "emil0x": "8",
    "paltis_": "96",
    "mangeee": "669",
    "amandasofia9485": "101",
    ".tenex": "55",
    "sarazodd": "132"
}

intents = discord.Intents.default()
intents.members = True
intents.guilds  = True
intents.voice_states = True
intents.typing = True
intents.messages = True
intents.message_content = True

files = {}

tsm = "<:tillsammans:908711034511044618>"
allt= "<:alltid:908711034632683593>"
cats = {tsm, allt}

bot = commands.Bot(command_prefix="/", help_command=None, intents=intents)
#tree= app_commands.CommandTree(bot)


load_dotenv()

TOKEN = os.getenv("DISCORD_API")

user_timeouts = {}


def checkIfProcessRunning(processName):
    '''
    Check if there is any running process that contains the given name processName.
    '''
    #Iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            if processName.lower() in proc.name().lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def merge_images(image_buffers: List[BytesIO]) -> BytesIO:
    """
    Merges 9 images together into a 3x3 grid, assumes that the incoming
    images have the same size
    Returns a BytesIO object containing the merged image buffer
    """
    images = [Image.open(b) for b in image_buffers]
    width, height = images[0].size

    result_width = width * 3
    result_height = height * 3

    result = Image.new("RGB", (result_width, result_height))

    for idx in range(0, 3):
        result.paste(im=images[idx * 3 + 0], box=(width * 0, height * idx))
        result.paste(im=images[idx * 3 + 1], box=(width * 1, height * idx))
        result.paste(im=images[idx * 3 + 2], box=(width * 2, height * idx))

    image_binary = BytesIO()
    result.save(image_binary, format="PNG")
    image_binary.seek(0)
    return image_binary



class Taunter(commands.Cog):
    def __init__(self, bot, files, suntzus, taunt_counts) -> None:
        self.bot = bot
        self.vc = None
        self.files = files
        self.taunt_counts = taunt_counts
        self.task = None
        self.cat = None
        self.suntzus = suntzus
        self.lastMessage = None
        self.save_task = asyncio.create_task(self.periodic_save())

    async def save_counts(self):
        try:
            with open("taunt_counts.pickle", 'wb') as f:
                pickle.dump(self.taunt_counts, f)
            logging.info("Saved taunt counts")
        except Exception as e:
            logging.error(f"Error saving taunt counts: {e}")

    async def periodic_save(self):
        while True:
            await asyncio.sleep(600)  # 10 minutes
            await self.save_counts()

    async def check_user_eligible(self, author: Member) -> bool:
        """
        Check if user is eligble to send a command to the bot and manage the users
        timeout between sending commands
        """
        if author.voice == None:
            await author.send("Joina en voice channel din tönt!")
            return False

        # If the bot is not connected to the same voice channel, we connect it
        if not self.vc and author.voice:
            self.vc = await author.voice.channel.connect()
        elif self.vc not in bot.voice_clients and author.voice:
            self.vc = await author.voice.channel.connect()

        username = str(author).split("#")[0]
        if username in user_timeouts:
            if user_timeouts[username] < datetime.today().timestamp():
                user_timeouts.pop(username)
            else:
                await author.send("Chilla fan")
                return False

        user_timeouts[username] = datetime.today().timestamp() + 0.5
        return True
      
    async def play_taunt(self, taunt, pitch) -> None:

        if taunt not in self.files:
            return
        if pitch:
            self.vc.play(discord.FFmpegPCMAudio("taunts/" + self.files[taunt], options=f"-af asetrate=44100*{pitch},aresample=44100,atempo=1/{pitch}"))
        else:
            self.vc.play(discord.FFmpegPCMAudio("taunts/" + self.files[taunt]))

    async def play_suntzu(self, message: Message) -> None:
        self.vc.play(discord.FFmpegPCMAudio("suntzu/" + random.choice(self.suntzus)))
        await message.delete()

    async def disconnect_self_if_lonely(self, message: Message):
        if message.content == "<:burk:895723401090588692>":
            self.vc = await self.vc.disconnect() 

    async def handle_cats(self, message: Message):
        if self.task == None:
            self.cat = cats.difference({self.cat}).pop()
            self.channel = message.channel
            self.task = asyncio.create_task(self.send_cat_response(message))
            return
        if message.content == self.cat:
            self.task.cancel()
            self.task = None



    async def send_cat_response(self, message):
        await asyncio.sleep(5)
        await message.channel.send("Ingen svarade, skäms!")
        await message.channel.send(self.cat)
        self.task = None

    @commands.Cog.listener()
    async def on_message(self, message):
        # Dont reply to ourselves or other bots
        if message is None:
            return
        if message.author.bot == True:
            await self.disconnect_self_if_lonely(message)
            return
        if  message.channel.type.name == "private":
            await message.delete()
            return
        try:
            if message.content in cats:
                await self.handle_cats(message)
            # Execute the command
            split_msg = message.content.split(" ")
            if split_msg[0].isdigit() and await self.check_user_eligible(message.author):
                if len(split_msg) == 2:
                    try:
                        float(split_msg[1])
                    except:
                        return
                    
                taunt = split_msg[0]
                pitch = None
                try:
                  pitch = float(split_msg[1])
                  if pitch > 0:
                      pitch = max(0.5, min(pitch, 2.0))
                  else:
                      pitch = random.random() + 0.5
                except IndexError:
                  pass
                except ValueError:
                  logging.getLogger(__name__).exception("Pitch must be floatable, <0 for random pitch")

                if int(taunt) < 0 or int(taunt) > 999:
                    return
                self.taunt_counts[int(taunt)] += 1

                await self.play_taunt(taunt, pitch)
                await message.delete()

            elif "sun tzu" in message.content and await self.check_user_eligible(
                message.author
            ):
                await self.play_suntzu(message)

        except Exception as e:
            logging.getLogger(__name__).exception("Got an exception: ")
            await message.channel.send(e)
            if message is not None:
                    await message.delete()




    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        names = ""
        if before.channel == after.channel:
            return
        
        if after.channel is None:
            channelToCheck = before.channel
        else:
            channelToCheck = after.channel

        members = channelToCheck.members
        for mem in members:
            if mem.name in lazyDict:
                names = names + lazyDict.get(mem.name)

        if names == "":
            return
        try:
            #await after.channel.edit(status=names) # TYP något sånt när apin uppdateras
            channel = bot.get_channel(895733929808650311)
            if self.lastMessage != None:
                await self.lastMessage.delete()
                self.lastMessage = None
                
            self.lastMessage = await channel.send(names)

            # If member joined
            if after.channel is None:
                return
            if not await self.check_user_eligible(member):
                return
            taunt = lazyDict2.get(member.name)
            if taunt == None:
                return
            pitch = random.random() + 0.5
            await self.play_taunt(taunt, pitch)
            
        except Exception as e:
            print(e)
            logging.getLogger(__name__).exception("Got an exception: ")
            
    def cog_unload(self):
        self.save_task.cancel()
        asyncio.create_task(self.save_counts())  # Final save on unload

@bot.tree.command(name = "taunts", description="Sends you a message with all available taunts")
async def taunts(context):
    
    try:
        text = "Available Taunts: \n ```"
        for i in range(999):
            if str(i) in files:

                if len(text + files[str(i)]) > 2000:
                    await context.response.send_message(text + "```", ephemeral=True)
                    text = "```"
                command = files[str(i)].split(".")[0].split("_")[1]
                numb = files[str(i)].split("_")[0] + ":"
                for j in range(4 - len(numb)):
                    numb = numb + " "
                text += numb + command + "\n"
                
        await context.response.send_message(text + "```", ephemeral=True)
    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception: ")
        await context.channel.send(e)


@bot.tree.command(name = "aunts", description="Sends you a message with two very nice aunts")
async def aunts(context):
    with open("aunts.jpg", "rb") as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)
        await context.response.send_message("Fina tanter.", ephemeral=True)


@bot.tree.command(name = "taints", description="Sends you a message with all available taints")
async def taints(context):
    with open("taints.mp4", "rb") as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)
        await context.response.send_message("Fin stjärt.", ephemeral=True)

async def update_status():
    try:
        txt = "server host for: "
        anyRunning = False

        if checkIfProcessRunning('VRising'):
            txt = txt + "Vrising ,"
            anyRunning = True
        if checkIfProcessRunning('java'):
            txt = txt + "Minecraft ,"
            anyRunning = True
        if checkIfProcessRunning('valheim'):
            txt = txt + "Valheim ,"
            anyRunning = True
        if checkIfProcessRunning('Main Thread'):
            txt = txt + "Terraria ,"
            anyRunning = True
        txt = txt[:-1]
        
        if anyRunning == False:
            txt = random.choice(euphemisms)
        activ = discord.Game(txt)

        await bot.change_presence(status=discord.Status.online, activity=activ)
        return txt
    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception in update_status: ")
        return "Error"

@bot.tree.command(name = "status_update", description="Updates the status of the servers")
async def status_update(context):
    try:
        await update_status()
        await context.response.send_message("Updated Server Status", ephemeral=True)
    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception: ")
        await context.channel.send(e)

@bot.tree.command(name = "start", description="Start the specified server, hosted in docker")
async def start(context, server: str):
    # We want to use docker compose to check for new images. They have their individual docker-compose.yml location 
    # specified in the environment variable COMPOSE_FILE_#SERVERNAME#
    composeFile = os.getenv("COMPOSE_FILE_" + server.upper())
    if composeFile == None:
        await context.response.send_message("Server not found", ephemeral=True)
        return
    # Check if the server is already running
    if checkIfProcessRunning(server):
        await context.response.send_message(server + " is already running", ephemeral=True)
        return
    try:
        subprocess.run("docker compose -f " + composeFile + "/docker-compose.yml"+ " up -d", shell=True)
        message = server + "server booting up, might take a minute to start"
        await context.response.send_message(message, ephemeral=True)
    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception: ")
        await context.channel.send(e)

@bot.tree.command(name="top_taunts", description="Shows the most and least used taunts")
async def top_taunts(context):
    try:
        # Get taunts with non-zero counts
        active_taunts = [(i, count) for i, count in enumerate(bot.get_cog('Taunter').taunt_counts) if count > 0]
        
        if not active_taunts:
            await context.response.send_message("No taunts have been used yet!", ephemeral=True)
            return

        # Sort by count
        sorted_taunts = sorted(active_taunts, key=lambda x: x[1], reverse=True)
        total_uses = sum(count for _, count in active_taunts)

        # Format message
        message = "**Top 5 Most Used Taunts:**\n```"
        for taunt_id, count in sorted_taunts[:5]:
            percentage = (count / total_uses) * 100
            message += f"#{taunt_id}: {count} uses ({percentage:.1f}%)\n"

        message += "```\n**Least Used Taunts:**\n```"
        for taunt_id, count in sorted_taunts[-5:]:
            percentage = (count / total_uses) * 100
            message += f"#{taunt_id}: {count} uses ({percentage:.1f}%)\n"
        message += "```"

        await context.response.send_message(message, ephemeral=False)

    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception: ")
        await context.response.send_message(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name = "skapa", description="Creates very nice images through Craiyon")
async def skapa(context, args: str):
    try:
        await context.channel.send(
            "Skapar Fantastiska Bilder! Använder input: \n{0}".format(args)
        )
        await context.response.send_message("Bra request, smart tänkt! Roligt att ha dig här!", ephemeral=True)

        generator = Craiyon()  # Instantiates the api wrapper
        result = await generator.async_generate(args)  # Generate 9 images
        images = [
            requests.get(link, allow_redirects=True).content
            for link in result.images
        ]
        image_buffers = [
            BytesIO(image)
            for image in images
        ]

        loop = asyncio.get_running_loop()

        # Creating the 3x3 image takes some time and is CPU bound, therefore we run
        # it in another process and await it
        with concurrent.futures.ProcessPoolExecutor():
            big_image_buf = await loop.run_in_executor(
                None, partial(merge_images, image_buffers)
            )
        await context.channel.send(file=discord.File(big_image_buf, "dalle.png"))

    except Exception as e:
        logging.getLogger(__name__).exception("Got an exception: ")
        await context.channel.send(e)


@bot.event
async def on_ready():
    await bot.tree.sync()
    await update_status()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


@bot.event
async def on_disconnect():
    print("Disconnected")

async def do_stuff_every_x_seconds(timeout):
    while True:
        await asyncio.sleep(timeout)
        await update_status()

async def check_internet():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://8.8.8.8', timeout=5) as response:
                return response.status == 200
    except:
        return False

async def wait_for_internet(max_attempts=50, delay=5):
    for attempt in range(max_attempts):
        if await check_internet():
            logging.info("Internet connection established")
            return True
        logging.warning(f"Waiting for internet... attempt {attempt + 1}/{max_attempts}")
        await asyncio.sleep(delay)
    raise ConnectionError("Could not establish internet connection")

async def main():
    # Load Sun Tzu quotes
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

    dir_path = os.getcwd() + "/taunts/"
    for (dirpath, dirnames, filenames) in walk(dir_path):
        for f in filenames:
            try:
                if f.split(".")[1] == "ogg" or f.split(".")[1] == "mp3":
                    number = f.split("_")[0]
                    files[number] = f
            except:
                f = f

        # Add pickle file handling
    PICKLE_FILE = os.path.join(os.getcwd(), "taunt_counts.pickle")
    try:
        with open(PICKLE_FILE, 'rb') as f:
            taunt_counts = pickle.load(f)
    except FileNotFoundError:
        taunt_counts = [0] * 999
        with open(PICKLE_FILE, 'wb') as f:
            pickle.dump(taunt_counts, f)
        logging.info("Created new taunt_counts.pickle file")
    except Exception as e:
        logging.error(f"Error loading taunt counts: {e}")
        taunt_counts = [0] * 999

    try:
        await wait_for_internet()
    except ConnectionError as e:
        logging.error(f"Failed to connect to internet: {e}")
        return
    
    task = asyncio.create_task(do_stuff_every_x_seconds(60))
    async with bot:
        await bot.add_cog(Taunter(bot, files, suntzu, taunt_counts))
        await bot.start(TOKEN)

asyncio.run(main())

