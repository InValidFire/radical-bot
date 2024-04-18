"""
This module provides functionality for the Minecraft server.
"""

import logging
from pathlib import Path
import subprocess
import shutil

import aiohttp
import aiohttp.web
import aiofiles
import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..views.confirm_view import ConfirmView
from ..properties import Properties
from ..mcrcon import run_command
from ..bot import MainBot

logger = logging.getLogger(__name__)


class MinecraftEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.dark_green()


async def _download_file(url: str, file_path: Path):
    chunk_size = 1048576
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(file_path, "wb") as file:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        await file.write(chunk)
                return file_path
            else:
                return None


async def _delete_server(bot: MainBot, interaction: discord.Interaction):
    async def _cancel_callback(interaction: discord.Interaction, button: discord.ui.Button, embed: discord.Embed):
        embed.description = "Server directory deletion canceled."
        logger.info("Server directory deletion canceled.")
        await interaction.response.edit_message(embed=embed)

    async def _delete_server_callback(interaction: discord.Interaction, button: discord.ui.Button,
                                      embed: discord.Embed):
        embed.description = "Deleting server directory.."
        await interaction.response.edit_message(embed=embed)
        logger.info("Deleting server directory..")
        try:
            shutil.rmtree(bot.config.minecraft.server_dir)
            embed.description = "Server directory deleted."
            logger.info("Server directory deleted.")
        except OSError as e:
            embed.description = f"Failed to delete server directory: {e}"
            logger.error("Failed to delete server directory: %s", e)
        await interaction.edit_original_response(embed=embed)

    embed = MinecraftEmbed(title="Delete Server Directory")
    if bot.server_process is not None and bot.server_process.poll() is None:
        embed.description = "Server is running. Please stop the server before deleting the server directory."
        logger.error("Server is running. Please stop the server before deleting the server directory.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if bot.config.minecraft.server_dir.exists():
        view = ConfirmView(embed=embed, confirm_callback=_delete_server_callback, cancel_callback=_cancel_callback)
        embed.description = "Are you sure you want to delete the server directory?"
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
    else:
        embed.description = "Server directory not found."
        logger.error("Server directory not found.")


async def _start_server(bot: MainBot, interaction: discord.Interaction = None) -> discord.Embed:
    # too many stairs, refactor this
    embed = MinecraftEmbed(title="Server Status")
    if bot.server_process is None or bot.server_process.poll() is not None:
        if not Path(bot.config.minecraft.server_dir.joinpath("server.jar")).exists():
            embed.description = "Server file not found."
            logger.error("Server file not found.")
            if interaction is not None and not interaction.is_expired():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return embed
        if bot.config.minecraft.server_dir.joinpath("server.properties").exists():
            properties = Properties(bot.config.minecraft.server_dir.joinpath("server.properties"))
            logger.log(logging.DEBUG, "Properties: %s", properties)
            if properties['enable-rcon'] is not True:
                embed.description = "RCON is not enabled. Please enable RCON with the '/server_init' command."
                if interaction is not None and not interaction.is_expired():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return embed
        if bot.config.minecraft.server_dir.joinpath("eula.txt").exists():
            eula = Properties(bot.config.minecraft.server_dir.joinpath("eula.txt"))
            if eula["eula"] is not True:
                embed.description = "EULA not signed. Please sign the EULA with the '/server_init' command."
                logger.error("EULA not signed.")
                if interaction is not None and not interaction.is_expired():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return embed
        else:
            embed.description = "Initializing server... Please run the '/server_init' command."
        bot.server_process = subprocess.Popen(
            ["java", f"-Xmx{bot.config.minecraft.server_ram}",
             f"-Xms{bot.config.minecraft.server_ram}",
             "-jar", "server.jar", "nogui"], cwd=bot.config.minecraft.server_dir)
        embed.description = "Server started successfully."
        logger.info("Server started.")
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return embed
    else:
        embed.description = "Server is already running."
        logger.info("Server is already running.")
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed, ephemeral=True)
    return embed


async def _setup(bot: MainBot) -> discord.Embed:
    embed = MinecraftEmbed(title="Server Setup")
    eula_path = bot.config.minecraft.server_dir.joinpath("eula.txt")
    if eula_path.exists():
        eula = Properties(eula_path)
        eula["eula"] = "true"
        eula.save()
        logger.info("EULA signed.")
        embed.add_field(name="EULA", value="signed")
    if bot.config.minecraft.server_dir.joinpath("server.properties").exists():
        properties = Properties(bot.config.minecraft.server_dir.joinpath("server.properties"))
        properties["enable-rcon"] = "true"
        properties["rcon.password"] = bot.config.minecraft.rcon.password
        properties["rcon.port"] = str(bot.config.minecraft.rcon.port)
        try:
            properties.save()
        except Exception as e:
            embed.add_field(name="RCON", value="failed")
            logger.error("Failed to enable RCON: %s", e)
            return embed
        logger.info("RCON enabled.")
        embed.add_field(name="RCON", value="enabled")
    return embed


async def _run_command(bot: MainBot, command: str) -> discord.Embed:
    embed = MinecraftEmbed(title="Command Status")
    if bot.server_process is not None and bot.server_process.poll() is None:
        response = await run_command(command, bot.config.minecraft.rcon)
        if len(response) == 0:
            response = "No response."
        embed.description = f"Sent command: {command}\n\nResponse: {response}"
        logger.info("Sent command: '%s', response: '%s'", command, response)
    else:
        embed.description = "The server is not running. Command was not sent."
        logger.info("The server is not running.")
    return embed


async def _stop_server(bot: MainBot, interaction: discord.Interaction = None) -> discord.Embed:
    embed = MinecraftEmbed(title="Server Status")
    if bot.server_process is not None and bot.server_process.poll() is None:
        logger.info("Stopping server..")
        embed.description = "Stopping server.."
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await _run_command(bot, "stop")
            return_code = bot.server_process.wait()
            bot.server_process = None
            embed.description = f"Server stopped with return code {return_code}."
            logger.info("Server stopped with return code %s.", return_code)
            await bot.change_presence(status=discord.Status.idle, activity=discord.Game(name="with your heart."))
        except ConnectionRefusedError:
            embed.description = "Server is not responding. Is the server running?"
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        return embed
    else:
        if interaction is not None and not interaction.is_expired():
            embed.description = "Server is not running."
            logger.info("Server is not running.")
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
    return embed


async def _update_server(bot: MainBot, url: str, interaction: discord.Interaction) -> discord.Embed:
    embed = MinecraftEmbed(title="Update Status")
    embed.add_field(name="URL", value=f"[link]({url})")
    if bot.server_process is not None and bot.server_process.poll() is None:
        embed.description = "Server is running. Please stop the server before updating."
        logger.info("Server is running. Please stop the server before updating.")
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return embed
    embed.description = "Updating server.."
    if interaction is not None and not interaction.is_expired():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    if not url.endswith(".jar"):
        embed.description = "Update failed. Invalid file type."
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        logger.error("Update failed. Invalid file type.")
        return embed
    logger.info("Downloading server file from url: %s.", url)
    try:
        file_path = await _download_file(url, bot.config.minecraft.server_dir.joinpath("server.jar"))
    except aiohttp.web.HTTPException:
        embed.description = "Update failed. Failed to download server file."
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
    if file_path is None:
        embed.description = "Update failed. Failed to download server file."
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        logger.error("Update failed. Failed to download server file.")
    else:
        embed.description = "Server updated."
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        logger.info("Server updated.")
    return embed


class MinecraftServer(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot
        self.bot.config.minecraft.server_dir.mkdir(parents=True, exist_ok=True)
        self.check_server.start()

    @app_commands.default_permissions(manage_guild=True)
    @app_commands.command(name="server_start", description="Start the Minecraft server.")
    async def start_server(self, interaction: discord.Interaction) -> None:
        embed = await _start_server(self.bot)
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.default_permissions(manage_guild=True)
    @app_commands.command(name="server_stop", description="Stop the Minecraft server.")
    async def stop_server(self, interaction: discord.Interaction) -> None:
        await _stop_server(self.bot, interaction)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="server_run", description="Send a command to the Minecraft server.")
    async def run_command(self, interaction: discord.Interaction, command: str) -> None:
        embed = await _run_command(self.bot, command)
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @run_command.error
    async def run_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        embed = MinecraftEmbed(title="Command Error", color=discord.Color.red())
        if isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, ConnectionRefusedError):
            embed.description = "Connection refused. Is the server running?"
        else:
            embed.description = f"An error occurred while executing a command.\n\nError: {error}"
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="server_update", description="Update the Minecraft server.")
    async def update_server(self, interaction: discord.Interaction, url: str) -> None:
        embed = await _update_server(self.bot, url, interaction)
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        await interaction.edit_original_response(embed=embed)

    @app_commands.default_permissions(manage_guild=True)
    @app_commands.command(name="server_restart", description="Restart the Minecraft server.")
    async def restart_server(self, interaction: discord.Interaction) -> None:
        stop_embed = await _stop_server(self.bot)
        start_embed = await _start_server(self.bot)
        embed = MinecraftEmbed(title="Server Status", color=discord.Color.green())
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        embed.description = f"{stop_embed.description}\n{start_embed.description}"
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="server_init", description="Initialize the Minecraft server.")
    async def setup_server(self, interaction: discord.Interaction) -> None:
        embed = await _setup(self.bot)
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="server_delete", description="Delete the Minecraft server directory.")
    async def delete_server(self, interaction: discord.Interaction) -> None:
        await _delete_server(self.bot, interaction)

    async def cog_load(self):
        embed = await _start_server(self.bot)
        embed.title = "Loading Server Cog - Starting Server"
        await self.bot.config.discord.bot_channel.send(embed=embed)

    async def cog_unload(self):
        if self.bot.server_process is not None and self.bot.server_process.poll() is None:
            embed = await _stop_server(self.bot)
            embed.title = "Unloading Server Cog - Stopping Server"
            await self.bot.config.discord.bot_channel.send(embed=embed)
        self.check_server.cancel()

    @tasks.loop(seconds=5)
    async def check_server(self):
        if self.bot.server_process is not None and self.bot.server_process.poll() is None:
            await self.bot.change_presence(status=discord.Status.online, activity=discord.Game(name="Minecraft"))
        else:
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game(name="with your heart."))


async def setup(bot: MainBot) -> None:
    await bot.add_cog(MinecraftServer(bot), guilds=bot.guilds)
