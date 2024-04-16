import logging

import discord

logger = logging.getLogger(__file__)


class ConfirmView(discord.ui.View):
    """A view that displays a confirmation prompt.

    Attributes:
        confirm (discord.ui.Button): The button that confirms the prompt.
        cancel (discord.ui.Button): The button that cancels the prompt.
        timeout (int): The timeout in seconds before the prompt is automatically canceled.
        confirmed (bool): Whether the prompt has been confirmed.
    """
    def __init__(self, embed: discord.Embed, timeout: int = 30, confirm_callback=None, cancel_callback=None):
        super().__init__()
        self.confirm = discord.ui.Button(style=discord.ButtonStyle.success, label="Confirm")
        self.cancel = discord.ui.Button(style=discord.ButtonStyle.danger, label="Cancel")
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback
        self.timeout = timeout
        self.embed = embed

    async def on_timeout(self) -> None:
        self.cancel.disabled = True
        self.cancel.label = "Timed Out"
        self.confirm.disabled = True
        await self.message.edit(view=self)

    async def disable(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.confirm_callback(interaction, button, self.embed)
        await self.disable()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cancel_callback(interaction, button, self.embed)
        await self.disable()
