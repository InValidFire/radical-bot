from zipfile import ZipFile
from datetime import datetime, timezone, time
from pathlib import Path
import shutil
import logging
from dataclasses import fields
from typing import Literal

from discord.ext import commands, tasks
from discord import app_commands
import discord

from ..views.select_view import SelectView
from ..views.page_view import PageView
from ..filesystem import zip_directory, delete_local_backup, get_local_backups
from ..aws import upload_backup, get_cloud_backups, delete_cloud_backup, download_backup
from ..mcrcon import run_command
from ..bot import MainBot

logger = logging.getLogger(__name__)


class BackupEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.dark_gold()


async def _delete_backups(bot: MainBot, location: str,
                          interaction: discord.Interaction = None) -> tuple[discord.Embed, discord.ui.View]:
    """
    Handle the command to delete backups. This function will return an embed and view to be used in the command.
    It will also delete the backups from the local directory or the S3 bucket, depending on the location selected.
    """
    async def _delete_local_backup_callback(interaction: discord.Interaction,
                                            backups: list[str],
                                            embed: discord.Embed) -> discord.Embed:
        """
        Delete backups from the local filesystem. This function is called when the user selects a backup to delete.
        It will delete the selected backups from the filesystem and update the embed with the results.

        Worthy note: the interaction here is not the same as the one that triggered the command, so the response
        is a new one which uses `interaction.response.edit_message()` rather than `interaction.edit_original_response()`
        """
        embed.description = "Deleted the following backups:"
        for backup in backups:
            delete_local_backup(bot.config.minecraft.backup_dir.joinpath(backup))
            embed.description += f"\n- **{backup}**"
        embed.set_footer(text="Local Files")
        if interaction is not None and not interaction.is_expired():
            # the interaction can only be edited once, so we remove the dropdown after the event to prevent further use
            await interaction.response.edit_message(embed=embed, view=None)
        return embed

    async def _delete_cloud_backup_callback(interaction: discord.Interaction,
                                            backups: list[str],
                                            embed: discord.Embed) -> discord.Embed:
        """
        Delete backups from the S3 bucket. This function is called when the user selects a backup to delete.
        It will delete the selected backups from the S3 bucket and update the embed with the results.

        Worthy note: the interaction here is not the same as the one that triggered the command, so the response
        is a new one which uses `interaction.response.edit_message()` rather than `interaction.edit_original_response()`
        """
        embed.description = "Deleting backups..."
        #  this is a separate interaction from the initial slash-command so we respond as if we haven't before.
        await interaction.response.edit_message(embed=embed, view=None)
        embed.description = "Deleted the following backups:"
        for backup in backups:
            await delete_cloud_backup(bot.config.cloud, backup)
            embed.description += f"\n- **{backup}**"
        embed.set_footer(text="Cloud Files")
        await interaction.edit_original_response(embed=embed, view=None)
        return embed

    embed = BackupEmbed(title="Delete Backups")
    if interaction is not None:
        embed.description = "Fetching backups..."
        await interaction.response.send_message(embed=embed, ephemeral=True)
    if location == "local":
        backups = get_local_backups(bot.config.minecraft)
        view = SelectView({f"{backup[1]} - {backup[2]}": backup[0] for backup in backups},
                          embed, _delete_local_backup_callback, multi_select=True)
    elif location == "cloud":
        backups = await get_cloud_backups(bot.config.cloud)
        view = SelectView({f"{backup[1]} - {backup[2]}": backup[0] for backup in backups},
                          embed, _delete_cloud_backup_callback, multi_select=True)
    if len(backups) == 0:
        embed.description = "No backups found."
    else:
        embed.description = "Select the backups you would like to delete."
    await interaction.edit_original_response(embed=embed)
    if interaction is not None:
        view.message = await interaction.original_response()
    return embed, view


async def _upload_backup(bot: MainBot, backup_file: Path,
                         embed: discord.Embed, interaction: discord.Interaction = None) -> str:
    """
    Upload a backup to an S3 bucket.

    Args:
        bot: The bot instance.
        backup_file: The backup file to upload.
        embed: The embed to update with the upload status.
        interaction: The interaction to edit with the upload status.
        chunk_size: The size of the chunks to upload.

    Returns:
        The embed with the updated upload status."""
    field_count = len(embed.fields)
    embed.add_field(name="Upload Status", value="pending")
    for field in fields(type(bot.config.cloud)):  # if any of the cloud fields are not set, disable uploading
        if getattr(bot.config.cloud, field.name) is None:
            embed.set_field_at(field_count, name="Upload Status", value="Not Configured")
            if interaction is not None and not interaction.is_expired():
                await interaction.edit_original_response(embed=embed)
            return embed

    embed.set_field_at(field_count, name="Upload Status", value="uploading")
    if interaction is not None and not interaction.is_expired():
        await interaction.edit_original_response(embed=embed)
    logger.info("Uploading backup to S3: %s", backup_file.name)
    try:
        await upload_backup(bot.config.cloud, backup_file)
        logger.info("Backup uploaded to S3.")
        embed.set_field_at(field_count, name="Upload Status", value="complete")
        url_text = f"[Download Backup]({bot.config.cloud.endpoint_url}/{bot.config.cloud.bucket_name}/\
{backup_file.name})"
        embed.add_field(name="Backup URL", value=url_text, inline=False)
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        return embed
    except Exception as e:
        logger.error("Failed to upload backup to S3: %s", e)
        embed.set_field_at(field_count, name="Upload Status", value="failed")
        embed.add_field(name="Error", value=str(e))
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        return embed


async def _create_backup(bot: MainBot, interaction: discord.Interaction = None, upload: bool = True) -> discord.Embed:
    """Create a backup of the Minecraft server."""
    async def _error_embed(embed: discord.Embed, error: Exception) -> discord.Embed:
        logger.error("Failed to create backup: %s", error)
        embed.title = "Backup Failed"
        embed.set_field_at(0, name="Status", value="failed")
        embed.add_field(name="Error", value=str(error))
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return embed

    embed = BackupEmbed(title="Creating Backup")
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = bot.config.minecraft.backup_dir.joinpath(f"backup_{current_time}.zip")
    embed.add_field(name="Status", value="creating")
    logger.info("Creating backup at %s.", backup_file)
    embed.set_footer(text=backup_file.name)
    if bot.server_process is not None:
        try:  # allows us to respond when the connection is refused (maybe the server is off or starting up?)
            await run_command("say Starting backup process. Auto-save is disabled.", bot.config.minecraft.rcon)
            await run_command("save-off", bot.config.minecraft.rcon)
            await run_command("save-all", bot.config.minecraft.rcon)
        except ConnectionRefusedError as e:
            return await _error_embed(embed, e)
    if interaction is not None and not interaction.is_expired():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    zip_directory(backup_file, bot.config.minecraft.server_dir)  # create the backup of the entire server directory
    if bot.server_process is not None:
        try:
            await run_command("save-on", bot.config.minecraft.rcon)
            await run_command("say Backup process complete. Auto-save is enabled.", bot.config.minecraft.rcon)
        except ConnectionRefusedError as e:
            return await _error_embed(embed, e)
    logger.info("Backup complete. Filesize: %s MiB.", round(backup_file.stat().st_size/1024/1024, 2))
    embed.set_field_at(0, name="Status", value="complete")
    embed.add_field(name="Filesize", value=f"{round(backup_file.stat().st_size/1024/1024, 2)}MiB")
    if interaction is not None and not interaction.is_expired():
        await interaction.edit_original_response(embed=embed)
    if upload:
        embed.title = "Uploading Backup"
        embed = await _upload_backup(bot, backup_file, embed, interaction)
        embed.title = "Backup Complete"
    return embed


async def _restore_backup(bot: MainBot, location: str,
                          interaction: discord.Interaction = None) -> tuple[discord.Embed, discord.ui.View]:
    """Restore a backup of the Minecraft server."""
    async def _restore_local_backup(interaction: discord.Interaction, value: list[Path],
                                    embed: discord.Embed) -> discord.Embed:
        await view.disable()
        if len(value) != 1:  # should only ever be one value, what would it mean to restore multiple backups?
            raise ValueError("Invalid backup selection.")
        value = Path(value[0])
        if bot.config.minecraft.backup_dir not in value.parents:  # ensure the path is in the backup directory
            value = bot.config.minecraft.backup_dir.joinpath(value)
        value: Path
        if not value.exists():  # ensure the backup file exists, this should never happen logically
            embed.set_field_at(0, name="Status", value="file not found")
            if interaction is not None and not interaction.is_expired():
                await interaction.edit_original_response(embed=embed)
            logger.info("Backup file not found: %s", value)
            return embed

        embed.set_field_at(0, name="Status", value="restoring")
        embed.description = "This may take a bit."
        embed.set_footer(text=value.name)
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed)
        logger.info("Restoring server backup: %s", value)
        try:
            backup_zip = ZipFile(value)
            if bot.config.minecraft.server_dir.exists():
                shutil.rmtree(bot.config.minecraft.server_dir)
            bot.config.minecraft.server_dir.mkdir()
            backup_zip.extractall(bot.config.minecraft.server_dir)
            embed.set_field_at(0, name="Status", value="restored")
            embed.description = "Thanks for waiting! The backup has been restored."
        except Exception as e:
            logger.error("Failed to restore backup: %s", e)
            embed.set_field_at(0, name="Status", value="failed")
            embed.add_field(name="Error", value=str(e))
        if interaction is not None and not interaction.is_expired():
            await interaction.edit_original_response(embed=embed)
        logger.info("Server backup restored.")

    async def _restore_cloud_backup(interaction: discord.Interaction, value: list[str],
                                    embed: discord.Embed) -> discord.Embed:
        await view.disable()
        if len(value) != 1:  # should only ever be one value, doesn't make sense to have more
            raise ValueError("Invalid backup selection.")
        value = value[0]
        logger.info("Restoring backup from S3: %s", value)
        backup_file = bot.config.minecraft.backup_dir.joinpath(value)
        if not backup_file.exists():
            embed.set_field_at(0, name="Status", value="downloading")
            if interaction is not None and not interaction.is_expired():
                await interaction.response.edit_message(embed=embed)
            await download_backup(bot.config.cloud, value, backup_file)
        embed = await _restore_local_backup(interaction, [backup_file], embed)  # efficiency baby :)
        return embed

    view = None
    embed = BackupEmbed(title="Restoring Backup")
    if bot.server_process is not None:
        embed.description = "A backup cannot be restored while the server is running."
        logger.info("A backup cannot be restored while the server is running.")
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed, view=None, ephemeral=True)
        return embed, view
    embed.add_field(name="Status", value="fetching")
    if interaction is not None:
        await interaction.response.send_message(embed=embed, ephemeral=True)
    if location == "local":
        embed.set_footer(text="Local Files")
        backups = get_local_backups(bot.config.minecraft)
        view = SelectView({f"{backup[1]} - {backup[2]}": backup[0] for backup in backups},
                          embed, _restore_local_backup)
    elif location == "cloud":
        embed.set_footer(text="Cloud Files")
        backups = await get_cloud_backups(bot.config.cloud)
        view = SelectView({f"{backup[1]} - {backup[2]}": backup[0] for backup in backups},
                          embed, _restore_cloud_backup)
    if len(backups) == 0:
        embed.description = "No backups found."
    else:
        embed.description = "Select the backup you would like to restore."
        embed.set_field_at(0, name="Status", value="ready")
    if interaction is not None:
        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()
    return embed, view


async def _get_cloud_backups(bot: MainBot, embed: discord.Embed) -> tuple[discord.Embed, discord.ui.View]:
    try:
        for field in fields(bot.config.cloud):
            if getattr(bot.config.cloud, field.name) is None:
                if logger.isEnabledFor(logging.WARN):
                    logger.warn("Cloud storage not configured.")
                embed.description = "Cloud storage not configured."
                return embed, None
        backups = await get_cloud_backups(bot.config.cloud)
        view = PageView([f"**{backup[1]}** - **{backup[2]}** - {backup[3]}" for backup in backups], embed)
        embed.description = ""
        if len(backups) == 0:
            embed.description = "No backups found."
            return embed, None
        for backup in backups:  # have this set in the view so we don't have to write this twice
            embed.description += f"\n- **{backup[1]}** - **{backup[2]}** - {backup[3]}"
    except Exception as e:
        logger.error("Failed to get backups: %s", e)
        embed.description = "Failed to get backups."
        embed.add_field(name="Error", value=str(e))
        raise e
    return embed, view


async def _get_backups(bot: MainBot, location: Literal['cloud', 'local'],
                       interaction: discord.Interaction) -> tuple[discord.Embed, discord.ui.View]:
    embed = BackupEmbed(title="Backup List")
    if location == "local":
        embed.description = ""
        embed.set_footer(text="Local Files")
        backups = get_local_backups(bot.config.minecraft)
        view = PageView([f"**{backup[1]}** - **{backup[2]}** - {backup[3]}" for backup in backups], embed)
        if len(backups) == 0:
            embed.description = "No backups found."
            return embed, None
        for backup in backups:
            backup_date, backup_time, backup_size = backup[1:]
            embed.description += f"\n- **{backup_date}** - **{backup_time}** - {backup_size} MiB"
    elif location == "cloud":
        embed.description = "Fetching backups..."
        embed.set_footer(text="Cloud Files")
        await interaction.response.send_message(embed=embed, ephemeral=True)  # defer the response to prevent timeout
        embed, view = await _get_cloud_backups(bot, embed)
    return embed, view


class BackupCog(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot
        self.bot.config.minecraft.backup_dir.mkdir(parents=True, exist_ok=True)

    backup_time = time(hour=4, minute=0, second=0, tzinfo=timezone.utc)  # midnight EST

    backup_group = app_commands.Group(name="backups", description="Backup commands.",
                                      default_permissions=discord.Permissions(manage_guild=True))

    @backup_group.command(name="create", description="Create a backup of the Minecraft server.")
    async def create_backup(self, interaction: discord.Interaction, upload: bool = True) -> None:
        """
        This command creates a backup of the Minecraft server.
        """
        embed = await _create_backup(self.bot, interaction, upload)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @backup_group.command(name="list", description="Get a list of all backups.")
    async def get_backups(self, interaction: discord.Interaction, location: Literal['cloud', 'local']) -> None:
        embed, view = await _get_backups(self.bot, location, interaction)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @backup_group.command(name="delete", description="Delete a backup.")
    async def delete_backup(self, interaction: discord.Interaction, location: Literal['cloud', 'local']) -> None:
        embed, view = await _delete_backups(self.bot, location, interaction)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @backup_group.command(name="restore", description="Restore a backup.")
    async def restore_backup(self, interaction: discord.Interaction, location: Literal['cloud', 'local']) -> None:
        await _restore_backup(self.bot, location, interaction)

    @tasks.loop(time=backup_time)
    async def backup_loop(self) -> None:
        logger.info("Starting routine backup process.")
        embed = await _create_backup(self.bot)
        await self.bot.config.discord.bot_channel.send(embed=embed)


async def setup(bot: MainBot) -> None:
    await bot.add_cog(BackupCog(bot), guilds=bot.guilds)
