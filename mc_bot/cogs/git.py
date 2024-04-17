import logging
from pathlib import Path

from discord.ext import commands
from discord import app_commands
import discord

from ..bot import MainBot
from ..git import update, get_version_hash, get_commit_info, switch_branch, get_branches, GitError

logger = logging.getLogger(__name__)


class GitEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.dark_teal()


class Git(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot

    git_group = app_commands.Group(name="git", description="Commands for updating the bot via Git.",
                                   default_permission=discord.Permissions(administrator=True))

    @git_group.command(name="update", description="Update the bot via Git.")
    async def update_cmd(self, interaction: discord.Interaction, branch: str = "main") -> None:
        embed = GitEmbed(title="Updating...")
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            output = await update(self.bot.config.general.update_mode, branch)
        except GitError as e:
            embed.title = "Update failed."
            embed.color = discord.Color.red()
            embed.description = "Failed to update from Git."
            embed.add_field(name="Error", value=str(e))
            embed.add_field(name="Output", value=e.output[1])
            await interaction.edit_original_response(embed=embed)
            return
        logger.info("Bot updated.")
        embed.title = "Bot updated."
        embed.description = f"Output:\n```\n{output[0]}\n```restarting..."
        await interaction.edit_original_response(embed=embed)
        await self.bot.close()  # restart the bot, systemd will handle the rest

    @git_group.command(name="branches", description="Get all branches in the repository.")
    async def branches(self, interaction: discord.Interaction) -> None:
        embed = GitEmbed(title="Branches")
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        try:
            branches = await get_branches()
        except GitError as e:
            embed.title = "Failed to get branches."
            embed.color = discord.Color.red()
            embed.description = "Failed to get branches."
            embed.add_field(name="Error", value=str(e))
            embed.add_field(name="Output", value=e.output[1])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.description = "\n".join(branches)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @git_group.command(name="checkout", description="Checkout a branch.")
    async def checkout(self, interaction: discord.Interaction, branch: str) -> None:
        embed = GitEmbed(title=f"Checking out branch {branch}.")
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            stdout = await switch_branch(branch)
            embed.description = f"Output:\n```\n{stdout}\n```restarting..."
        except GitError as e:
            embed.title = "Checkout failed."
            embed.color = discord.Color.red()
            embed.description = "Failed to checkout branch."
            embed.add_field(name="Error", value=str(e))
            embed.add_field(name="Output", value=e.output)
            logger.exception("Failed to checkout branch.")
            logger.exception(e)
            await interaction.edit_original_response(embed=embed)
            return
        logger.info(f"Branch {branch} checked out.")
        embed.title = f"Branch {branch} checked out."
        await interaction.edit_original_response(embed=embed)
        await self.bot.close()  # restart the bot, systemd will handle the rest

    @git_group.command(name="version", description="Get the current version of the bot.")
    async def version(self, interaction: discord.Interaction) -> None:
        embed = GitEmbed(title="Bot Version")
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Version", value=await get_version_hash(self.bot))
        if self.bot.config.general.update_mode == "commits":
            embed.description = (await get_commit_info())[1]
        else:
            embed.description = Path.cwd().joinpath("VERSION").read_text()
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: MainBot):
    await bot.add_cog(Git(bot), guilds=bot.guilds)
