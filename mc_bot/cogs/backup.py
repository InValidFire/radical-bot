from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
from pathlib import Path
import shutil
import logging
import asyncio
from dataclasses import fields
from typing import Literal

from discord.ext import commands, tasks
from discord import app_commands
import discord

from ..mcrcon import run_command
from ..bot import MainBot

logger = logging.getLogger(__name__)


class BackupEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.dark_gold()


async def __get_cloud_backups(bot: MainBot) -> list:
    backups_resp = await __run_aws_command(bot, ("s3", "ls", f"s3://{bot.config.cloud.bucket_name}"))
    backups = []
    if len(backups_resp[0]) == 0:
        return backups
    for backup in backups_resp[0].split("\n"):
        if not backup:  # skip empty lines
            continue
        backup_name = backup.split()[-1]
        backup_datetime = datetime.strptime(" ".join(backup_name.split("_")[1:]), "%Y-%m-%d %H-%M-%S.zip")
        backup_time = backup_datetime.strftime("%H:%M:%S")
        backup_date = backup_datetime.strftime("%Y-%m-%d")
        backup_size = round(int(backup.split()[2])/1024/1024, 2)
        backup_link = f"{bot.config.cloud.endpoint_url}/{bot.config.cloud.bucket_name}/{backup_name}"
        backup_link = f"[{backup_size} MiB]({backup_link})"
        backups.append((backup_name, backup_date, backup_time, backup_link))
    logger.info("Cloud backups [%s]: %s", len(backups), backups)
    return backups


def __get_local_backups(bot: MainBot) -> list[tuple[str, str, str, float]]:
    """Get a list of all local backups.

    Args:
        bot: The bot instance.

    Returns:
        A list of all local backups. Each item contains the name, date, time, and size of each backup."""
    backups = []
    for backup in bot.config.minecraft.backup_dir.iterdir():
        backup_datetime = datetime.strptime(" ".join(backup.stem.split("_")[1:]), "%Y-%m-%d %H-%M-%S")
        backup_time = backup_datetime.strftime("%H:%M:%S")
        backup_date = backup_datetime.strftime("%Y-%m-%d")
        backup_size = round(backup.stat().st_size/1024/1024, 2)
        backups.append((backup.name, backup_date, backup_time, backup_size))
    return backups


async def __run_aws_command(bot: MainBot, command: tuple) -> tuple[str, str, int]:
    """
    Run an AWS CLI command.

    Args:
        bot: The bot instance.
        command: The command to run.

    Returns:
        A tuple containing the stdout, stderr, and return code of the command.
    """
    class AWSException(Exception):
        pass

    process = await asyncio.create_subprocess_exec(
        "aws", *command,
        env={"AWS_ACCESS_KEY_ID": bot.config.cloud.access_key_id,
             "AWS_SECRET_ACCESS_KEY": bot.config.cloud.access_key_secret,
             "AWS_DEFAULT_REGION": bot.config.cloud.region_name,
             "AWS_ENDPOINT_URL": bot.config.cloud.endpoint_url},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    logger.info("AWS command: %s", command)
    logger.info("AWS stdout: %s", stdout.decode("utf-8").strip())
    logger.info("AWS stderr: %s", stderr.decode("utf-8").strip())
    if process.returncode != 0:
        raise AWSException(f"AWS Error: {stderr.decode('utf-8').strip()}")
    return stdout.decode("utf-8"), stderr.decode("utf-8"), process.returncode


async def _delete_backups(bot: MainBot, location: str,
                          interaction: discord.Interaction = None) -> tuple[discord.Embed, discord.ui.View]:
    """
    Handle the command to delete backups. This function will return an embed and view to be used in the command.
    It will also delete the backups from the local directory or the S3 bucket, depending on the location selected.
    """
    async def _delete_local_backup_callback(interaction: discord.Interaction,
                                            backups: list[str],
                                            embed: discord.Embed) -> discord.Embed:
        embed.description = "Deleted the following backups:"
        for backup in backups:
            bot.config.minecraft.backup_dir.joinpath(backup).unlink()
            embed.description += f"\n- **{backup}**"
        embed.set_footer(text="Local Files")
        if interaction is not None and not interaction.is_expired():
            # the interaction can only be edited once, so we remove the dropdown after the event to prevent further use
            await interaction.response.edit_message(embed=embed, view=None)
        return embed

    async def _delete_cloud_backup_callback(interaction: discord.Interaction,
                                            backups: list[str],
                                            embed: discord.Embed) -> discord.Embed:
        embed.description = "Deleting backups..."
        #  this is a separate interaction from the initial slash-command so we respond as if we haven't before.
        await interaction.response.edit_message(embed=embed, view=None)
        embed.description = "Deleted the following backups:"
        for backup in backups:
            command = ("s3", "rm", f"s3://{bot.config.cloud.bucket_name}/{backup}")
            try:
                await __run_aws_command(bot, command)
            except Exception as e:
                embed.description += f"Failed to delete backup '{backup}': {e}"
                logger.error("Failed to delete backup '%s': %s", backup, e)
            embed.description += f"\n- **{backup}**"
        embed.set_footer(text="Cloud Files")
        await interaction.edit_original_response(embed=embed, view=None)
        return embed

    embed = BackupEmbed(title="Delete Backups")
    if location == "local":
        backups = __get_local_backups(bot)
        if len(backups) == 0:
            embed.description = "No backups found."
            return embed, None
        view = DropdownView({f"{backup[1]} - {backup[2]}": backup[0] for backup in backups},
                            _delete_local_backup_callback, embed)
        if interaction is not None:
            view.message = await interaction.original_response()
        return embed, view
    elif location == "cloud":
        if interaction is not None:
            embed.description = "Fetching backups..."
            await interaction.response.send_message(embed=embed)
        backups = await __get_cloud_backups(bot)
        if len(backups) == 0:
            embed.description = "No backups found."
            return embed, None
        view = DropdownView({f"{backup[1]} - {backup[2]}": backup[0] for backup in backups},
                            _delete_cloud_backup_callback, embed)
        if interaction is not None:
            view.message = await interaction.original_response()
        embed.description = "Select the backups you would like to delete."
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
        command = ("s3", "cp", str(backup_file),
                   f"s3://{bot.config.cloud.bucket_name}/{backup_file.name}", "--acl", "public-read")
        await __run_aws_command(bot, command)
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


def _zip_directory(zip_file: Path, directory: Path):
    logger.info("Creating backup at %s of directory %s.", zip_file, directory)
    if not directory.is_dir():
        raise ValueError(directory)
    # create a zip file with compression, requires zlib to be installed
    with ZipFile(zip_file, "w", compression=ZIP_DEFLATED) as zf:
        for file in directory.rglob("*"):
            if file.is_dir():
                continue
            logger.info("Checking file: %s.", file)
            zf.write(file, str(file.relative_to(directory)))
            logger.info("Added %s to backup.", file)


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
    _zip_directory(backup_file, bot.config.minecraft.server_dir)  # create the backup of the entire server directory
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


async def _restore_backup(bot: MainBot, backup_file: Path,
                          interaction: discord.Interaction = None) -> discord.Embed:
    embed = BackupEmbed(title="Restoring Backup")
    if bot.server_process is None:
        embed.add_field(name="Status", value="restoring")
        if not backup_file.exists():
            embed.set_field_at(0, name="Status", value="file not found")
            if interaction is not None and not interaction.is_expired():
                await interaction.response.edit_message(embed=embed)
            logger.info("Backup file not found: %s", backup_file)
            return
        if interaction is not None and not interaction.is_expired():
            await interaction.response.send_message(embed=embed)
        logger.info("Restoring server backup: %s", backup_file)
        backup_zip = ZipFile(backup_file)
        shutil.rmtree(bot.config.minecraft.server_dir)
        backup_zip.extractall(bot.config.minecraft.server_dir)
        embed.set_field_at(0, name="Status", value="restored")
        if interaction is not None and not interaction.is_expired():
            await interaction.response.edit_message(embed=embed)
        logger.info("Server backup restored.")
    else:
        embed.set_field_at(0, name="Status", value="server running, aborted")
        logger.info("A backup cannot be restored while the server is running.")
    return embed


async def _get_cloud_backups(bot: MainBot, embed: discord.Embed) -> discord.Embed:
    try:
        for field in fields(bot.config.cloud):
            if getattr(bot.config.cloud, field.name) is None:
                embed.description = "Cloud storage not configured."
                return embed
        backups = await __get_cloud_backups(bot)
        embed.description = ""
        embed.set_footer(text="Cloud Files")
        if len(backups) == 0:
            embed.description = "No backups found."
            return embed
        for backup in backups:
            embed.description += f"\n- **{backup[1]}** - **{backup[2]}** - {backup[3]}"
    except Exception as e:
        logger.error("Failed to get backups: %s", e)
        embed.description = "Failed to get backups."
        embed.add_field(name="Error", value=str(e))
        raise e
    return embed


async def _get_backups(bot: MainBot, location: Literal['cloud', 'local'],
                       interaction: discord.Interaction) -> discord.Embed:
    embed = BackupEmbed(title="Backup List")
    if location == "local":
        embed.description = ""
        embed.set_footer(text="Local Files")
        backups = __get_local_backups(bot)
        if len(backups) == 0:
            embed.description = "No backups found."
            return embed
        for backup in backups:
            backup_date, backup_time, backup_size = backup[1:]
            embed.description += f"\n- **{backup_date}** - **{backup_time}** - {backup_size} MiB"
    elif location == "cloud":
        embed.description = "Fetching backups..."
        await interaction.response.send_message(embed=embed)  # defer the response to prevent timeout
        embed = await _get_cloud_backups(bot, embed)
    return embed


class Dropdown(discord.ui.Select):
    def __init__(self, *, items: dict[str, str] = None,
                 placeholder: str = None, selected_handler=None, max_values: int = 1,
                 embed: discord.Embed):
        if items is None:
            items = []
        self.embed = embed
        self.items = items
        self.selected_handler = selected_handler

        options = []
        for item in self.items:
            options.append(discord.SelectOption(label=item, value=items[item]))

        if len(options) < max_values:  # Discord requires max_values to be less than or equal to the number of options
            max_values = len(options)

        super().__init__(placeholder=placeholder, min_values=1, max_values=max_values, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.selected_handler(interaction, self.values, self.embed)


class DropdownView(discord.ui.View):
    #  TODO: Create a way to paginate the items and expose the full backup count even beyond Discord's initial limits.
    def __init__(self, items: dict[str, str], selected_handler, embed: discord.Embed, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.embed = embed
        self.add_item(Dropdown(items=items, selected_handler=selected_handler, embed=embed, max_values=25))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        self.embed.description = "This interaction has timed out."
        await self.message.edit(view=self)  # this should be set immediately after sending the interaction response.


class BackupCog(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot
        self.bot.config.minecraft.backup_dir.mkdir(parents=True, exist_ok=True)

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
        embed = await _get_backups(self.bot, location, interaction)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @backup_group.command(name="delete", description="Delete a backup.")
    async def delete_backup(self, interaction: discord.Interaction, location: Literal['cloud', 'local']) -> None:
        embed, view = await _delete_backups(self.bot, location, interaction)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @backup_group.command(name="restore", description="Restore a backup.")
    async def restore_backup(self, ctx: discord.Interaction, backup_name: str,
                             location: Literal['cloud', 'local']) -> None:
        backup = self.bot.config.minecraft.backup_dir.joinpath(backup_name)
        embed = await _restore_backup(self.bot, backup)
        await ctx.send(embed=embed, ephemeral=True)

    @tasks.loop(hours=24)
    async def backup_loop(self) -> None:
        logger.info("Starting routine backup process.")
        embed = await _create_backup(self.bot)
        await self.bot.config.discord.bot_channel.send(embed=embed)


async def setup(bot: MainBot) -> None:
    await bot.add_cog(BackupCog(bot), guilds=bot.guilds)
