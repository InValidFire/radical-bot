from math import ceil
import logging

import discord

logger = logging.getLogger(__file__)


class Dropdown(discord.ui.Select):
    def __init__(self, *, options: list = None,
                 placeholder: str = None, page: int = 0, selected_handler=None, max_values: int = 1,
                 embed: discord.Embed):
        if options is None:
            options = []
        self.embed = embed
        self.selected_handler = selected_handler

        if len(options) < max_values:  # Discord requires max_values to be less than or equal to the number of options
            max_values = len(options)

        super().__init__(placeholder=placeholder, min_values=1, max_values=max_values, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.selected_handler(interaction, self.values, self.embed)


class BackupView(discord.ui.View):
    #  TODO: Create a way to paginate the items and expose the full backup count even beyond Discord's initial limits.
    # if a selection_handler is provided, a dropdown will be added to the view.
    def __init__(self, items: dict[str, str], embed: discord.Embed, selected_handler: callable):
        super().__init__()
        self.embed = embed
        self.page_size = 10
        self.page_count = ceil(len(items) / self.page_size)
        self.page_index = 0
        self.items = items

        if self.page_count > 1:
            self.embed.set_footer(text=f"Page {self.page_index + 1}/{self.page_count}")

        if self.page_count == 1:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    self.remove_item(item)  # remove the buttons for one-page views

        all_options = []
        for item in self.items:
            all_options.append(discord.SelectOption(label=item, value=items[item]))
        self.add_item(Dropdown(
            options=all_options[self.page_index*self.page_size:(self.page_index*self.page_size)+self.page_size],
            selected_handler=selected_handler, embed=embed,
            max_values=self.page_size, page=self.page_index))

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
        for item in self.children:
            item.disabled = True
        self.embed.description = "This interaction has timed out."
        await self.message.edit(view=self)  # this should be set immediately after sending the interaction response.

    async def update_message(self, interaction: discord.Interaction) -> None:
        try:
            all_options = []
            for item in self.items:
                all_options.append(discord.SelectOption(label=item, value=self.items[item]))
            options = all_options[self.page_index*self.page_size:(self.page_index*self.page_size)+self.page_size]
            self.embed.set_footer(text=f"Page {self.page_index + 1}/{self.page_count}")
            for item in self.children:
                if isinstance(item, Dropdown):
                    selected_handler = item.selected_handler
                    self.remove_item(item)
            self.add_item(Dropdown(
                options=options, selected_handler=selected_handler, embed=self.embed,
                max_values=self.page_size, page=self.page_index))
            await interaction.response.edit_message(embed=self.embed, view=self)
        except Exception as e:
            logger.error("Failed to update message: %s", e)
