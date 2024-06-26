from discord.ext import commands
from discord import app_commands
import discord

from ..bot import MainBot


class SystemEmbed(discord.Embed):
    """Class to set defaults for embeds within this Cog."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.color = discord.Color.dark_grey()


async def _sync_commands(bot: MainBot, guild_id: str = None, globally: bool = False):
    embed = SystemEmbed(title="Syncing commands")
    embed.description = "Syncing application commands to Discord."
    if guild_id is not None:
        try:
            guild_id = int(guild_id)
        except ValueError:
            embed.description = "Invalid guild ID."
            return embed
        guild = bot.get_guild(int(guild_id))
        if guild is None:
            embed.description = "Guild not found."
            return embed
        embed.add_field(name="Guild", value=guild.name)
        await bot.tree.sync(guild=bot.get_guild(guild_id))
    elif globally:
        await bot.tree.sync()
    return embed


class System(commands.Cog):
    def __init__(self, bot: MainBot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        embed = SystemEmbed(title="Pong!")
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Latency", value=f"{round(interaction._client.latency * 1000)}ms", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="sync", help="Sync application commands to Discord. Takes an optional guild ID.")
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guild_id: str = None,
                   globally: bool = False) -> None:
        if guild_id is None and not globally:
            guild_id = ctx.guild.id
        try:
            embed = await _sync_commands(self.bot, guild_id)
        except Exception as e:
            embed = SystemEmbed(title="Error")
            embed.description = f"An error occurred: {e}"
        embed.set_footer(text=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed, ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="bot_restart", description="Shutdown the bot.")
    async def shutdown(self, interaction: discord.Interaction) -> None:
        #  restarting is handled through systemd, we just need to shut down and clean up
        embed = SystemEmbed(title="Restarting...")
        embed.set_footer(text=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.bot.close()


async def setup(bot: MainBot) -> None:
    await bot.add_cog(System(bot), guilds=bot.guilds)
