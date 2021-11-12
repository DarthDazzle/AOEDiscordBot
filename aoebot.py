import os
from datetime import datetime
import discord
from discord.ext import commands
from os import walk
from threading import Timer
import time
import asyncio
TOKEN = 'OTA0MDQwODE3OTY1MDMxNDY0.YX1vnw.Lufg5d0TqGZWbsr2VbwMFIs-2jM'
#https://discord.com/api/oauth2/authorize?client_id=904040817965031464&permissions=2172928&scope=bot
client = discord.Client()

async def deevee(message):
    #time.sleep(36)
    #await message.channel.send("<:nolove:908730069936132178>")
    #time.sleep(30)
    #await message.channel.send("<:dignified:908735166510411776>")
    print("lol")

user_timeouts = {}
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

class Taunter(commands.Cog):
    def __init__(self, bot, files):
        self.bot = bot
        self.vc = None
        self.files = files
        


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
                self.vc.play(discord.FFmpegPCMAudio(self.files[message.content]))
                if(message.content == str(422)):
                    await asyncio.create_task(deevee(message)) 
                user_timeouts[username] = datetime.today().timestamp() + 10
            await message.delete()

bot = commands.Bot(command_prefix='!', help_command=None)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

f = []
dir_path = os.path.dirname(os.path.realpath(__file__))
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
async def taunts(context):
    context.channel.send('Aunts. Aunts. Aunts:', {
        files: [
            "./aunts.jpg"
        ]
    });
bot.add_cog(Taunter(bot, files))
bot.run(TOKEN)