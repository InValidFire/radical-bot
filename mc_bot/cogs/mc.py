import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..mcrcon import get_players
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
        embed.description = "You can quickly see this by looking at my status!\n\n" \
                            "If I am offline **or** away, the server is __offline__.\n" \
                            "If I am online **and** playing Minecraft, the server is __online__."
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
            embed.description = ""
            try:
                players = await get_players(self.bot.config.minecraft.rcon)
            except Exception as e:
                embed.description = "An error occurred while fetching the players."
                embed.description += f"\n{e}"
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if len(players[0]) == 1:
                embed.description = "No players online."
                players = []
            for player in players:
                embed.description += f"- {player}\n"
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    @mc_group.command(name="whois-mc",
                      description="Identify the Discord user associated with a Minecraft account.")
    async def whois_mc(self, interaction: discord.Interaction, mc_username: str) -> None:
        """Get the player data for a specified Minecraft user.

        Args:
            interaction (discord.Interaction): The interaction object.
            username (str): The Minecraft username to get data for.
        """
        embed = MCEmbed(title=f"Player Profile: {mc_username}")
        try:
            discord_id = None
            player_data = self.bot.player_data.get_all()
            for player in player_data:
                if player[1].mc_username.lower() == mc_username.lower():
                    player_data = player[1]
                    discord_id = player[0]
                    break
        except ValueError:
            embed.description = "Player not found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        user = self.bot.get_user(discord_id)
        if user is not None:
            embed.add_field(name="Discord Account", value=user.mention, inline=False)
            embed.add_field(name="Minecraft Username", value=player_data.mc_username, inline=False)
        else:
            embed.description = "The Discord account associated with this Minecraft player no longer exists!"
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    @mc_group.command(name="whois-discord",
                      description="Identify the Minecraft account associated with a Discord user.")
    async def whois_discord(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Identify the Minecraft account associated with a Discord user.

        Args:
            interaction (discord.Interaction): The interaction object.
            user (discord.User): The Discord user to get data for.
        """
        embed = MCEmbed(title=f"Who is {user.display_name} in Minecraft?")
        try:
            player_data = self.bot.player_data.get(str(user.id))
        except ValueError:
            embed.description = "I don't have any data for this user."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.description = f"They are associated with the following Minecraft account: {player_data.mc_username}."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    @mc_group.command(name="profile", description="Get your player profile.")
    async def profile(self, interaction: discord.Interaction) -> None:
        """Get the player data for the user who invoked the command.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        embed = MCEmbed(title="Your Player Profile")
        try:
            player_data = self.bot.player_data.get(str(interaction.user.id))
        except ValueError:
            embed.description = "You are not in the player data. Ask a staff member to add you."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.add_field(name="Minecraft Username", value=player_data.mc_username, inline=False)
        embed.add_field(name="Whitelisted", value="Yes" if player_data.is_whitelisted else "No")
        embed.add_field(name="Trusted", value="Yes" if player_data.is_trusted else "No")
        if player_data.is_staff:
            embed.add_field(name="Staff", value="Yes")
        if player_data.is_owner:
            embed.add_field(name="Owner", value="Yes")
        embed.set_footer(text=interaction.user.name, icon_url=interaction.user.avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return


async def setup(bot: MainBot):
    await bot.add_cog(MC(bot), guilds=bot.guilds)
