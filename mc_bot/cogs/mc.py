import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..mcrcon import run_command
from ..bot import MainBot

logger = logging.getLogger(__file__)


class MCEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.green()


class MC(commands.Cog):
    """Contains player-accessible commands for interacting with the Minecraft server.

    Attributes:
        bot (MainBot): The bot instance.

        Args:
            bot (MainBot): The bot instance.
    """
    def __init__(self, bot: MainBot):
        self.bot = bot

    mc_group = app_commands.Group(name="mc", description="Minecraft commands.")

    @mc_group.command(name="status", description="Get the status of the Minecraft server.")
    async def status(self, interaction: discord.Interaction) -> None:
        """Get the status of the Minecraft server.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        if self.bot.server_process is None:
            embed = MCEmbed(title="The server is not running.")
        else:
            embed = MCEmbed(title="The server is running.")
        embed.description = "You can quickly see this by looking at the status of the bot.\n\n" \
                            "If the bot is offline **or** away, the server is __offline__.\n" \
                            "If the bot is online **and** playing Minecraft, the server is __online__."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    @mc_group.command(name="list", description="List the players on the Minecraft server.")
    async def list(self, interaction: discord.Interaction) -> None:
        """List the players on the Minecraft server.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        if self.bot.server_process is None:
            embed = MCEmbed(title="The server is not running.")
            embed.description = "There are no players online."
        else:
            embed = MCEmbed(title="Players online:")
            try:
                players = await run_command("list", self.bot.config.minecraft.rcon)
            except Exception as e:
                embed.add_field(name="Error", value=e)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            player_data = players.split(":")
            logger.debug(f"player_data: {player_data}")
            pre_text = player_data[0].strip()
            logger.debug(f"pre_text: {pre_text}")
            if player_data[1] == " ":
                players = []
            else:
                players = player_data[1].split(", ")
            logger.debug(f"players: {players}")
            if len(players) == 0:
                embed.description = "There are no players online."
            else:
                embed.description = f"{pre_text}\n -" + "\n -".join(players)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return


async def setup(bot: MainBot):
    await bot.add_cog(MC(bot), guilds=bot.guilds)
