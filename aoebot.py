import os
from datetime import datetime
import discord
from discord.ext import commands
from os import walk
from threading import Timer
import time
import asyncio
import random

TOKEN = 'OTA0MDQwODE3OTY1MDMxNDY0.YX1vnw.Lufg5d0TqGZWbsr2VbwMFIs-2jM'
#https://discord.com/api/oauth2/authorize?client_id=904040817965031464&permissions=2172928&scope=bot
client = discord.Client()


user_timeouts = {}
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')



class Taunter(commands.Cog):
    def __init__(self, bot, files, suntzus):
        self.bot = bot
        self.vc = None
        self.files = files
        self.suntzus = suntzus
        


    @commands.Cog.listener()
    async def on_message(self, message):
        if(message.content.isdigit()):
            if message.author.voice == None:
                await message.author.send("Joina en voice channel din tönt!")
                await message.delete()
                return
            if not self.vc:
                self.vc = await message.author.voice.channel.connect()
            elif(self.vc.channel != message.author.voice.channel):
                if self.vc:
                    await self.vc.disconnect()
                self.vc = await message.author.voice.channel.connect()
            username = str(message.author).split('#')[0]
            if username in user_timeouts:
                if user_timeouts[username] < datetime.today().timestamp():
                    user_timeouts.pop(username)
                else:
                    await message.author.send("Chilla fan")
            if username not in user_timeouts:
                self.vc.play(discord.FFmpegPCMAudio("taunts/" + self.files[message.content]))
                user_timeouts[username] = datetime.today().timestamp() + 5
            await message.delete()
        if "sun tzu" in message.content:
            if message.author.voice == None:
                await message.author.send("Joina en voice channel din tönt!")
                await message.delete()
                return
            if not self.vc:
                self.vc = await message.author.voice.channel.connect()
            elif(self.vc.channel != message.author.voice.channel):
                if self.vc:
                    await self.vc.disconnect()
                self.vc = await message.author.voice.channel.connect()
            username = str(message.author).split('#')[0]
            if username in user_timeouts:
                if user_timeouts[username] < datetime.today().timestamp():
                    user_timeouts.pop(username)
                else:
                    await message.author.send("Chilla fan")
            if username not in user_timeouts:
                self.vc.play(discord.FFmpegPCMAudio("suntzu/" + random.choice(self.suntzus)))
                user_timeouts[username] = datetime.today().timestamp() + 10

bot = commands.Bot(command_prefix='!', help_command=None)

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
            for j in range(4-len(numb)):
                numb = numb + " "
            text +=  numb  + command + "\n"
    await context.author.send(text + "```")

@bot.command()
async def aunts(context):
    with open('aunts.jpg', 'rb') as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)

@bot.command()
async def AUNTS(context):
    with open('aunts.jpg', 'rb') as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)
        
@bot.command()
async def Aunts(context):
    with open('aunts.jpg', 'rb') as f:
        picture = discord.File(f)
        await context.channel.send(file=picture)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

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
            #print(f)

f = []
dir_path = os.getcwd() + "/taunts/"
print(dir_path)
files = {}
for (dirpath, dirnames, filenames) in walk(dir_path):
    for f in filenames:
        try:
            if f.split(".")[1] == "ogg":
                number = f.split("_")[0]
                files[number] = f
        except:
            f = f
            #print(f)

bot.add_cog(Taunter(bot, files, suntzu))

bot.run(TOKEN)