from typing import Optional

import discord

from .presentation import (
    help_category_content,
    help_category_pages,
    help_overview_description,
    italy_embed,
)


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, parent_view: "HelpView"):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=label,
                value=key,
                description=f"Show {label.lower()} commands.",
            )
            for key, label, _description in help_category_pages()
        ]
        super().__init__(
            placeholder="Select a command category...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Help", "Only the command user can switch help categories."
                ),
                ephemeral=True,
            )
            return

        selected_key = self.values[0]
        self.parent_view.selected_category = selected_key
        await interaction.response.edit_message(
            embed=self.parent_view.build_category_embed(selected_key),
            view=self.parent_view,
        )


class HelpView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.selected_category: str | None = None
        self.message: Optional[discord.Message] = None
        self.category_select = HelpCategorySelect(self)
        self.add_item(self.category_select)

    def build_overview_embed(self) -> discord.Embed:
        return italy_embed("Help", help_overview_description())

    def build_category_embed(self, category_key: str) -> discord.Embed:
        page = help_category_content(category_key)
        if page is None:
            return italy_embed("Help", "Unknown help category.")
        label, description = page
        return italy_embed(f"Help: {label}", description)

    async def on_timeout(self) -> None:
        if self.message is None:
            return

        self.category_select.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass
