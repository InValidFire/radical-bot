import logging
from math import ceil

import discord

logger = logging.getLogger(__file__)


class PageView(discord.ui.View):
    """A view that paginates a list of items in an embed.

    This view is intended to be used with a message that contains an embed.

    Attributes:
        embed (discord.Embed): The embed that will be updated with the items.
        page_size (int): The number of items to display on each page.
        page_count (int): The total number of pages.
        page_index (int): The current page index.
        items (list[str]): The list of items to paginate.
    """
    def __init__(self, items: list[str], embed: discord.Embed):
        super().__init__()
        self.embed = embed
        self.page_size = 10
        self.page_count = max(ceil(len(items) / self.page_size), 1)  # ensure at least one page
        self.page_index = 0
        self.items = items

        if self.page_count > 1:
            self.embed.set_footer(text=f"Page {self.page_index + 1}/{self.page_count}")

        if self.page_count == 1:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    self.remove_item(child)  # remove the buttons for one-page views

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page_index -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page_index += 1
        await self.update_message(interaction)

    @property
    def page_index(self) -> int:
        return self._page_index

    @page_index.setter
    def page_index(self, value: int) -> None:
        adjusted_page_count = self.page_count - 1
        # 0-based index, adjust for comparison
        if value < 1:
            self._page_index = 0
        elif value > adjusted_page_count:
            self._page_index = self.page_count - 1
        else:
            self._page_index = value

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        self.embed.description = "This interaction has timed out."
        await self.message.edit(view=self)  # this should be set immediately after sending the interaction response.

    async def update_message(self, interaction: discord.Interaction) -> None:
        try:
            await self.build_embed()
            self.embed.set_footer(text=f"Page {self.page_index + 1}/{self.page_count}")
            await interaction.response.edit_message(embed=self.embed, view=self)
        except Exception as e:
            logger.error("Failed to update message: %s", e)

    async def build_embed(self) -> discord.Embed:
        """Build the embed with the items for the current page."""
        self.embed.description = ""
        items = self.items[self.page_index*self.page_size:(self.page_index*self.page_size)+self.page_size]
        for item in items:
            self.embed.description += f"\n- {item}"
        return self.embed
