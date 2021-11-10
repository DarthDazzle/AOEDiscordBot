import os
from datetime import datetime
import discord
from discord.ext import commands
from os import walk

TOKEN = 'OTA0MDQwODE3OTY1MDMxNDY0.YX1vnw.Lufg5d0TqGZWbsr2VbwMFIs-2jM'
#https://discord.com/api/oauth2/authorize?client_id=904040817965031464&permissions=2172928&scope=bot
client = discord.Client()

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
                user_timeouts[username] = datetime.today().timestamp() + 10
            await message.delete()

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"),
                   description='Wololo')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

f = []
dir_path = os.path.dirname(os.path.realpath(__file__))
files = {}
for (dirpath, dirnames, filenames) in walk(dir_path):
    
    for f in filenames:
        if f.split(".")[1] == "ogg":
            number = f.split("_")[0]
            files[number] = f

bot.add_cog(Taunter(bot, files))
bot.run(TOKEN)