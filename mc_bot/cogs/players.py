import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import MainBot
from ..views.page_view import PageView

logger = logging.getLogger(__file__)


class PlayersEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.magenta()


class Players(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot

    @app_commands.default_permissions(manage_guild=True)
    @app_commands.group(name="players", description="Commands for managing players.")
    async def players(self, interaction: discord.Interaction) -> None:
        pass

    @players.command(name="info", description="Get information about a player.")
    async def info(self, interaction: discord.Interaction, user: discord.Member) -> None:
        embed = PlayersEmbed(title="Player Information")
        try:
            player = self.bot.player_data.get(user.id)
        except ValueError as e:
            embed.description = f"Error: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.add_field(name="Discord ID", value=user.id)
        embed.add_field(name="Minecraft Username", value=player.mc_username)
        embed.add_field(name="Whitelisted", value="Yes" if player.is_whitelisted else "No")
        embed.add_field(name="Trusted", value="Yes" if player.is_trusted else "No")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="list", description="List the players on the Minecraft server.")
    async def list(self, interaction: discord.Interaction) -> None:
        embed = PlayersEmbed(title="All Known Players")
        players = self.bot.player_data.get_all()
        if not players:
            embed = PlayersEmbed(title="No players found.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        view = PageView(players)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @players.command(name="link", description="Link a Discord account to a Minecraft account.")
    async def link(self, interaction: discord.Interaction, user: discord.Member, mc_username: str) -> None:
        try:
            await self.bot.player_data.add(user.id, mc_username)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Linking Player")
            embed.description = f"User {user.mention} could not be linked: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Linked", description=f"{user.mention} is now linked to {mc_username}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="unlink", description="Unlink a Discord account from a Minecraft account.")
    async def unlink(self, interaction: discord.Interaction, user: discord.Member) -> None:
        try:
            await self.bot.player_data.remove(user.id)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Unlinking Player")
            embed.description = f"User {user.mention} could not be unlinked: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Unlinked", description=f"{user.mention} is no longer linked.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="whitelist", description="Whitelist a player on the Minecraft server.")
    async def whitelist(self, interaction: discord.Interaction, user: discord.Member) -> None:
        try:
            await self.bot.player_data.whitelist(user.id)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = f"User {user.mention} could not be whitelisted: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Whitelisted", description=f"{user.mention} is now whitelisted.")
        await user.add_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="unwhitelist", description="Unwhitelist a player on the Minecraft server.")
    async def unwhitelist(self, interaction: discord.Interaction, user: discord.Member) -> None:
        try:
            await self.bot.player_data.unwhitelist(user.id)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = f"User {user.mention} could not be unwhitelisted: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Unwhitelisted", description=f"{user.mention} is no longer whitelisted.")
        await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="trust", description="Trust a player on the Minecraft server.")
    async def trust(self, interaction: discord.Interaction, user: discord.Member) -> None:
        try:
            await self.bot.player_data.trust(user.id)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = f"User {user.mention} could not be trusted: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Trusted", description=f"{user.mention} is now trusted.")
        await user.add_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="untrust", description="Untrust a player on the Minecraft server.")
    async def untrust(self, interaction: discord.Interaction, user: discord.Member) -> None:
        try:
            await self.bot.player_data.untrust(user.id)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Untrusting")
            embed.description = f"User {user.mention} could not be untrusted: {e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Untrusted", description=f"{user.mention} is no longer trusted.")
        await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: MainBot) -> None:
    await bot.add_cog(Players(bot), guilds=bot.guilds)
