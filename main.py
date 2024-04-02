from pathlib import Path
from discord.ext import commands
from discord import Intents
from mc_bot.bot import MainBot
import os

from dotenv import load_dotenv

# This program wraps the Minecraft server, and can be manipulated by the Discord bot.
# The bot can start, stop, and restart the server, and can also create backups of the server.
# This program will be able to handle updating the server, and its plugins.

# Load the environment variables from the .env file.
load_dotenv(".env")
if os.getenv("DISCORD_TOKEN") is None:
    print("DISCORD_TOKEN environment variable not found.")
    exit(1)

# Create the bot instance and run it.
MainBot(command_prefix="!", intents=Intents.all()).run(os.getenv("DISCORD_TOKEN"))