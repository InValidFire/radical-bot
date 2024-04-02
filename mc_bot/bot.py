from discord.ext import commands
from pathlib import Path

class MainBot(commands.Bot):
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
                    print(f"Loaded cog: {cog_module}")
                except Exception as e:
                    print(f"Failed to load cog: {cog_module}")
                    print(e)
        else:
            print("No cogs directory found.")

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        await self.load_cogs()