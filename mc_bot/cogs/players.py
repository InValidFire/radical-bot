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

    @commands.Cog.listener()
    async def on_member_leave(self, member: discord.Member) -> None:
        logger.info("Member %s left the server, removing player data.", member.name)
        embed = PlayersEmbed(title="Player Data Removed")
        player = self.bot.player_data.get(str(member.id))
        embed.description = f"Player data for {member.name} has been removed."
        embed.set_footer(text=member.name, icon_url=member.avatar.url)
        embed.add_field(name="Minecraft Username", value=player.mc_username, inline=False)
        embed.add_field(name="Whitelisted", value="Yes" if player.is_whitelisted else "No")
        embed.add_field(name="Trusted", value="Yes" if player.is_trusted else "No")
        if player.is_owner:
            embed.add_field(name="Owner", value="Yes")
        if player.is_staff:
            embed.add_field(name="Staff", value="Yes")
        try:
            await self.bot.player_data.remove(str(member.id))
        except ValueError:
            embed.description = f"Player data for {member.mention} could not be removed."
        await self.bot.get_channel(self.bot.config.discord.bot_channel).send(embed=embed)

    staff_group = app_commands.Group(name="staff", description="Commands for managing staff members.",
                                     default_permissions=discord.Permissions(administrator=True))

    @staff_group.command(name="add", description="Add a staff member to the Minecraft server.")
    async def add_staff(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not check_if_guild_has_role(interaction, "Staff"):
            embed = PlayersEmbed(title="Error Adding Staff")
            embed.description = "The Staff role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if check_if_user_has_role(interaction, user, "Staff"):
            embed = PlayersEmbed(title="Error Adding Staff")
            embed.description = f"User {user.mention} is already staff."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            await self.bot.player_data.add_staff(str(user.id))
            embed = PlayersEmbed(title="You've been promoted!",
                                 description="You are now a staff member on the Minecraft Server.")
            await user.send(embed=embed)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Adding Staff")
            embed.description = f"User {user.mention} could not be added as staff.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Staff Added", description=f"{user.mention} is now staff.")
        member: discord.Member | None = discord.utils.get(interaction.guild.members, id=user.id)
        if member is not None:
            await member.add_roles(discord.utils.get(interaction.guild.roles, name="Staff"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staff_group.command(name="remove", description="Remove a staff member from the Minecraft server.")
    async def remove_staff(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not check_if_guild_has_role(interaction, "Staff"):
            embed = PlayersEmbed(title="Error Removing Staff")
            embed.description = "The Staff role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not check_if_user_has_role(interaction, user, "Staff"):
            embed = PlayersEmbed(title="Error Removing Staff")
            embed.description = f"User {user.mention} is not staff."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            await self.bot.player_data.remove_staff(str(user.id))
            embed = PlayersEmbed(title="You need to file for unemployment!",
                                 description="You are no longer a staff member on the Minecraft Server.")
            await user.send(embed=embed)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Removing Staff")
            embed.description = f"User {user.mention} could not be removed as staff.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Staff Removed", description=f"{user.mention} is no longer staff.")
        member: discord.Member | None = discord.utils.get(interaction.guild.members, id=user.id)
        if member is not None:
            await member.remove_roles(discord.utils.get(interaction.guild.roles, name="Staff"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    players = app_commands.Group(name="players", description="Commands for managing players.",
                                 default_permissions=discord.Permissions(manage_guild=True))

    @players.command(name="profile", description="Get information about a player.")
    async def info(self, interaction: discord.Interaction, user: discord.User) -> None:
        embed = PlayersEmbed(title=f"{user.name}'s Player Profile")
        try:
            player = self.bot.player_data.get(str(user.id))
        except ValueError:
            embed.description = f"User {user.mention}'s player data could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.add_field(name="Minecraft Username", value=player.mc_username, inline=False)
        embed.add_field(name="Whitelisted", value="Yes" if player.is_whitelisted else "No")
        embed.add_field(name="Trusted", value="Yes" if player.is_trusted else "No")
        if player.is_owner:
            embed.add_field(name="Owner", value="Yes")
        if player.is_staff:
            embed.add_field(name="Staff", value="Yes")
        embed.set_footer(text=user.name, icon_url=user.avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="list", description="List all known players on the Minecraft server.")
    async def list(self, interaction: discord.Interaction) -> None:
        embed = PlayersEmbed(title="All Known Players")
        players = self.bot.player_data.get_all()
        if len(players) == 0:
            embed = PlayersEmbed(title="No players found.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        players = [f"{self.bot.get_user(discord_id).mention} ({player.mc_username})"
                   for discord_id, player in players]
        logger.debug("Players: %s", players)
        view = PageView(players, embed)
        await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @players.command(name="link", description="Link a Discord account to a Minecraft account.")
    async def link(self, interaction: discord.Interaction, user: discord.Member, mc_username: str) -> None:
        try:
            await self.bot.player_data.add(str(user.id), mc_username)
            app_info = await self.bot.application_info()
            if app_info.owner.id == user.id:
                await self.bot.player_data.add_owner(str(user.id))
        except ValueError as e:
            embed = PlayersEmbed(title="Error Linking Player")
            embed.description = f"User {user.mention} could not be linked.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Linked", description=f"{user.mention} is now linked to {mc_username}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        embed.description = f"Your account has been linked to {mc_username}."
        await user.send(embed=embed)

    @players.command(name="unlink", description="Unlink a Discord account from a Minecraft account.")
    async def unlink(self, interaction: discord.Interaction, user: discord.User) -> None:
        try:
            if check_if_user_has_role(interaction, user, "Whitelisted"):
                await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
            if check_if_user_has_role(interaction, user, "Trusted"):
                await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
            player = self.bot.player_data.get(str(user.id))
            player_name = player.mc_username
            await self.bot.player_data.remove(str(user.id))
        except Exception as e:
            embed = PlayersEmbed(title="Error Unlinking Player")
            embed.description = f"User {user.name} could not be unlinked.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Unlinked",
                             description=f"{user.name} is no longer linked to {player_name}.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        embed.description = f"Your account has been unlinked from {player_name}."
        await user.send(embed=embed)

    @players.command(name="whitelist", description="Whitelist a player on the Minecraft server.")
    async def whitelist(self, interaction: discord.Interaction, user: discord.User) -> None:
        if self.bot.server_process is None:
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = "The Minecraft server is not running."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not check_if_guild_has_role(interaction, "Whitelisted"):
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = "The Whitelisted role could not be found."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if check_if_user_has_role(interaction, user, "Whitelisted"):
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = f"User {user.mention} is already whitelisted."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            embed = PlayersEmbed(title="Player Whitelisted")
            player_data = self.bot.player_data.get(str(user.id))
            embed.description = f"You are now whitelisted on the Minecraft server as '{player_data.mc_username}'."
            await self.bot.player_data.whitelist(str(user.id))
            await user.send(embed=embed)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Whitelisting")
            embed.description = f"User {user.mention} could not be whitelisted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Whitelisted", description=f"{user.mention} is now whitelisted.")
        member: discord.Member | None = discord.utils.get(interaction.guild.members, id=user.id)
        if member is not None:
            await member.add_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="unwhitelist", description="Unwhitelist a player on the Minecraft server.")
    async def unwhitelist(self, interaction: discord.Interaction, user: discord.User) -> None:
        if self.bot.server_process is None:
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = "The Minecraft server is not running."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
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
        if check_if_user_has_role(interaction, user, "Trusted"):
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = f"User {user.mention} is trusted and cannot be unwhitelisted."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            embed = PlayersEmbed(title="Player Unwhitelisted")
            embed.description = "You are no longer whitelisted on the Minecraft server."
            await self.bot.player_data.unwhitelist(str(user.id))
            await user.send(embed=embed)
        except Exception as e:
            embed = PlayersEmbed(title="Error Unwhitelisting")
            embed.description = f"User {user.mention} could not be unwhitelisted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Unwhitelisted", description=f"{user.mention} is no longer whitelisted.")
        member: discord.Member | None = discord.utils.get(interaction.guild.members, id=user.id)
        if member is not None:
            await member.remove_roles(discord.utils.get(interaction.guild.roles, name="Whitelisted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="trust", description="Trust a player on the Minecraft server.")
    async def trust(self, interaction: discord.Interaction, user: discord.User) -> None:
        if self.bot.server_process is None:
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = "The Minecraft server is not running."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
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
        if check_if_user_has_role(interaction, user, "Trusted"):
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = f"User {user.mention} is already trusted."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            embed = PlayersEmbed(title="Player Trusted")
            embed.description = "You are now trusted on the Minecraft server."
            await self.bot.player_data.trust(str(user.id))
            await user.send(embed=embed)
        except Exception as e:
            embed = PlayersEmbed(title="Error Trusting")
            embed.description = f"User {user.mention} could not be trusted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Trusted", description=f"{user.mention} is now trusted.")
        member: discord.Member | None = discord.utils.get(interaction.guild.members, id=user.id)
        if member is not None:
            await member.add_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @players.command(name="untrust", description="Untrust a player on the Minecraft server.")
    async def untrust(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if self.bot.server_process is None:
            embed = PlayersEmbed(title="Error Untrusting")
            embed.description = "The Minecraft server is not running."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
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
            embed = PlayersEmbed(title="Player Untrusted")
            embed.description = "You are no longer trusted on the Minecraft server."
            await self.bot.player_data.untrust(str(user.id))
            await user.send(embed=embed)
        except ValueError as e:
            embed = PlayersEmbed(title="Error Untrusting")
            embed.description = f"User {user.mention} could not be untrusted.\n{e}"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = PlayersEmbed(title="Player Untrusted", description=f"{user.mention} is no longer trusted.")
        member: discord.Member | None = discord.utils.get(interaction.guild.members, id=user.id)
        if member is not None:
            await user.remove_roles(discord.utils.get(interaction.guild.roles, name="Trusted"))
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: MainBot) -> None:
    await bot.add_cog(Players(bot), guilds=bot.guilds)
