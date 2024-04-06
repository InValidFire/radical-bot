import logging.config
from pathlib import Path
import logging
import traceback

from discord import Intents, Interaction, app_commands, Embed
from discord.ext import commands

logging.config.fileConfig(Path.cwd().joinpath("logging.ini"))

from mc_bot.bot import MainBot  # noqa

logger = logging.getLogger("radical_bot")

bot = MainBot(config_file=Path.cwd().joinpath("config.jsonc"), command_prefix="!", intents=Intents.all())


@bot.before_invoke
async def before_invoke(ctx: commands.Context):
    logger.info("Command invoked: %s, by %s", ctx.command.name, ctx.author.name)


@bot.tree.error
async def on_app_command_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    embed = Embed(title="You broke it!", color=0xFF0000)
    embed.description = "Just kidding!\nThough please contact the bot owner."
    embed.add_field(name="Command Invoked", value=interaction.command.name)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    embed = Embed(title="Command Error!", color=0xFF0000)
    embed.description = "An error occurred while executing a command."
    embed.add_field(name="Command Invoked", value=interaction.command.name)
    embed.add_field(name="User", value=f"{interaction.user.mention}")
    embed.add_field(name="Guild", value=f"{interaction.guild.name}")
    embed.add_field(name="Channel", value=f"{interaction.channel.mention}")
    logger.log(logging.ERROR, "Error occurred while executing command %s", interaction.command.name)
    logger.error(error)
    try:
        if isinstance(error, app_commands.CommandInvokeError):
            embed.add_field(name="Error", value=str(error.original), inline=False)
            traceback_str = "".join(traceback.format_tb(error.original.__traceback__))
        else:
            embed.add_field(name="Error", value=str(error), inline=False)
            traceback_str = "".join(traceback.format_tb(error.__traceback__))
        if len(traceback_str) > 1000:
            logger.info(traceback_str)
            logger.info("Truncating error traceback...")
            traceback_str = traceback_str[:1000]
        embed.add_field(name="Traceback", value=f'```txt\n{traceback_str}```', inline=False)
        await bot.config.discord.error_channel.send(embed=embed)
    except Exception as e:
        logger.info("Error sending error message to bot owner.")
        logger.error(e)

bot.run(bot.config.discord.bot_token)
