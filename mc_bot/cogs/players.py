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


def check_if_guild_has_role(interaction: discord.Interaction, role_name: str) -> bool:
    """Check if a role exists in a guild.

    Args:
        interaction (discord.Interaction): The interaction object.
        role_name (str): The name of the role to check.

    Returns:
        bool: True if the role exists, False otherwise.
    """
    return discord.utils.get(interaction.guild.roles, name=role_name) is not None


def check_if_user_has_role(interaction: discord.Interaction, user: discord.Member, role_name: str) -> bool:
    """Check if a user has a role in a guild.

    Args:
        interaction (discord.Interaction): The interaction object.
        user (discord.Member): The user to check.
        role_name (str): The name of the role to check.

    Returns:
        bool: True if the user has the role, False otherwise.
    """
    return discord.utils.get(user.roles, name=role_name) is not None


class Players(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot

    players = app_commands.Group(name="players", description="Commands for managing players.",
                                 default_permissions=discord.Permissions(manage_guild=True))

    @players.command(name="info", description="Get information about a player.")
    async def info(self, interaction: discord.Interaction, user: discord.Member) -> None:
        embed = PlayersEmbed(title="Player Information")
        try:
            player = self.bot.player_data.get(str(user.id))
        except ValueError:
            embed.description = f"User {user.mention}'s player data could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.add_field(name="Minecraft Username", value=player.mc_username, inline=False)
        embed.add_field(name="Whitelisted", value="Yes" if player.is_whitelisted else "No")
        embed.add_field(name="Trusted", value="Yes" if player.is_trusted else "No")
        embed.set_footer(text=user.name, icon_url=user.avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="list", description="List the players on the Minecraft server.")
    async def list(self, interaction: discord.Interaction) -> None:
        embed = PlayersEmbed(title="All Known Players")
        players = self.bot.player_data.get_all()
        if len(players) == 0:
            embed = PlayersEmbed(title="No players found.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        players = [f"{discord.utils.get(interaction.guild.members, id=discord_id).mention} ({player.mc_username})"
                   for discord_id, player in players]
        logger.debug("Players: %s", players)
        view = PageView(players, embed)
        await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @players.command(name="link", description="Link a Discord account to a Minecraft account.")
    async def link(self, interaction: discord.Interaction, user: discord.Member, mc_username: str) -> None:
        try:
            await self.bot.player_data.add(str(user.id), mc_username)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Linking Player")
            embed.description = f"User {user.mention} could not be linked.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Linked", description=f"{user.mention} is now linked to {mc_username}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="unlink", description="Unlink a Discord account from a Minecraft account.")
    async def unlink(self, interaction: discord.Interaction, user: discord.Member) -> None:
        try:
            await self.bot.player_data.remove(str(user.id))
        except ValueError as e:
            embed = PlayersEmbed(title="Error Unlinking Player")
            embed.description = f"User {user.mention} could not be unlinked.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Unlinked", description=f"{user.mention} is no longer linked.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="whitelist", description="Whitelist a player on the Minecraft server.")
    async def whitelist(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not check_if_guild_has_role(interaction, "Whitelisted"):
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = "The Whitelisted role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            await self.bot.player_data.whitelist(str(user.id))
        except ValueError as e:
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = f"User {user.mention} could not be whitelisted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Whitelisted", description=f"{user.mention} is now whitelisted.")
        await user.add_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="unwhitelist", description="Unwhitelist a player on the Minecraft server.")
    async def unwhitelist(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not check_if_guild_has_role(interaction, "Whitelisted"):
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = "The Whitelisted role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not check_if_user_has_role(interaction, user, "Whitelisted"):
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = f"User {user.mention} is not whitelisted."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            await self.bot.player_data.unwhitelist(str(user.id))
        except Exception as e:
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = f"User {user.mention} could not be unwhitelisted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Unwhitelisted", description=f"{user.mention} is no longer whitelisted.")
        await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="trust", description="Trust a player on the Minecraft server.")
    async def trust(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not check_if_guild_has_role(interaction, "Trusted"):
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = "The Trusted role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not check_if_user_has_role(interaction, user, "Whitelisted"):
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = f"User {user.mention} is not whitelisted."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            await self.bot.player_data.trust(str(user.id))
        except Exception as e:
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = f"User {user.mention} could not be trusted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Trusted", description=f"{user.mention} is now trusted.")
        await user.add_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="untrust", description="Untrust a player on the Minecraft server.")
    async def untrust(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not check_if_guild_has_role(interaction, "Trusted"):
            embed = PlayersEmbed(title="Error Untrusting")
            embed.description = "The Trusted role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not check_if_user_has_role(interaction, user, "Trusted"):
            embed = PlayersEmbed(title="Error Untrusting")
            embed.description = f"User {user.mention} is not trusted."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            await self.bot.player_data.untrust(str(user.id))
        except ValueError as e:
            embed = PlayersEmbed(title="Error Untrusting")
            embed.description = f"User {user.mention} could not be untrusted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Untrusted", description=f"{user.mention} is no longer trusted.")
        await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: MainBot) -> None:
    await bot.add_cog(Players(bot), guilds=bot.guilds)
