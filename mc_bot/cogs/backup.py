from zipfile import ZipFile
from datetime import datetime
from pathlib import Path

from discord.ext import commands, tasks
from discord import app_commands
from ..mcrcon import run_command
from ..bot import MainBot

class BackupCog(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot

    async def create_backup(self) -> None:
        await run_command("say Starting backup process. Auto-save is disabled.")
        await run_command("save-off")
        await run_command("save-all")
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = f"backup_{current_time}.zip"
        with ZipFile(backup_file, "w") as zip:
            zip.write("server.properties")
            worlds = Path.glob("world*")
            for world in worlds:
                zip.write(world)
                await run_command("say Backup of world '{world}' complete.")
        await run_command("save-on")
        await run_command("say Backup process complete. Auto-save is enabled.")

    @app_commands.command(name="backup", description="Create a backup of the Minecraft server.")
    async def backup(self, ctx: commands.Context) -> None:
        ctx.send("Creating backup of the server.")
        await self.create_backup()
        ctx.send("Backup complete.")

    @tasks.loop(hours=24)
    async def backup_loop(self) -> None:
        await self.backup()

async def setup(bot: MainBot) -> None:
    await bot.add_cog(BackupCog(bot), guilds=bot.guilds)