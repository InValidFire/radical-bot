from pathlib import Path
import subprocess
import logging
import traceback

from discord.ext import commands
import discord

from .config import load_config
from .git import align_tag_version, get_version_hash
from .playerdata import PlayerData

logger = logging.getLogger(__name__)


class MainBot(commands.Bot):
    def __init__(self, config_file: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = load_config(self, config_file)
        self.server_process: subprocess.Popen | None = None
        self.player_data = PlayerData(Path("data/playerdata.json"), self.config.minecraft.rcon)
        if not Path("data").exists():
            Path("data").mkdir()

    async def load_cogs(self):
        cogs_dir = Path(__file__).parent.joinpath("cogs")
        if cogs_dir.is_dir():
            for cog_file in cogs_dir.glob("*.py"):
                if cog_file.stem == "__init__":
                    continue
                cog_name = cog_file.stem
                cog_module = f"{__package__}.cogs.{cog_name}"
                try:
                    await self.load_extension(cog_module)
                    logger.info("Loaded cog: %s", cog_module)
                except discord.DiscordException as e:
                    logger.error("Failed to load cog: %s", cog_module)
                    logger.error(e)
                    if isinstance(e, commands.ExtensionFailed):
                        traceback_str = "".join(traceback.format_tb(e.original.__traceback__))
                    else:
                        traceback_str = "".join(traceback.format_tb(e.__traceback__))
                    logger.error(traceback_str)
        else:
            print("No cogs directory found.")

    async def on_ready(self):
        # this is to refresh the config with object references from discord.py
        self.config = load_config(self, Path.cwd().joinpath("config.jsonc"))
        try:
            await self.load_cogs()
        except commands.ExtensionAlreadyLoaded:
            logger.info("Cogs already loaded.")
        logger.info("Bot is ready. Logged in as %s", self.user.name)
        embed = discord.Embed(title="Bot is ready", color=discord.Color.green())
        was_aligned = await align_tag_version(self)
        if was_aligned:
            embed.description = "Bot was aligned with the latest tag. Restarting..."
            self.close()  # restart the bot, as the version was updated.
            return
        embed.set_footer(text=f"Version: {await get_version_hash(self)}")
        await self.config.discord.bot_channel.send(embed=embed)

    async def on_disconnect(self):
        logger.info("Bot disconnected.")
