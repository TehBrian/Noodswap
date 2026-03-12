from typing import Optional

import discord

from .cards import CARD_CATALOG, card_base_display
from .images import embed_image_payload
from .presentation import italy_embed
from .settings import TRADE_TIMEOUT_SECONDS
from .utils import multiline_text
from .view_pagination import (
    FIRST_PAGE_EMOJI,
    LAST_PAGE_EMOJI,
    NEXT_PAGE_EMOJI,
    PREVIOUS_PAGE_EMOJI,
)
from .view_utils import InteractionView, logger


class CardCatalogView(InteractionView):
    def __init__(self, user_id: int, entries: list[tuple[str, int]], page_size: int = 10):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.entries = entries
        self.default_page_size = max(1, page_size)
        self.page_index = 0
        self.sort_mode = "alphabetical"
        self.sort_descending = self._default_sort_descending(self.sort_mode)
        self.gallery_mode = False
        self.message: Optional[discord.Message] = None
        self._sorted_entries = self._sorted_entries_for_mode(self.sort_mode, descending=self.sort_descending)
        self._set_gallery_button_label()
        self._set_sort_direction_button_label()
        self._set_sort_select_defaults()
        self._refresh_button_state()

    def _effective_page_size(self) -> int:
        return 1 if self.gallery_mode else self.default_page_size

    def _clamp_page_index(self) -> None:
        self.page_index = max(0, min(self.total_pages - 1, self.page_index))

    def _list_page_for_gallery_index(self, gallery_index: int) -> int:
        page_size = self.default_page_size
        return int(gallery_index // page_size)

    def _set_gallery_button_label(self) -> None:
        self.gallery_toggle_button.label = "Gallery: On" if self.gallery_mode else "Gallery: Off"

    def _set_sort_direction_button_label(self) -> None:
        self.sort_direction_button.label = "▼" if self.sort_descending else "▲"

    def _default_sort_descending(self, mode: str) -> bool:
        return mode in {"wishes", "base_value"}

    def _rarity_rank(self, rarity: str) -> int:
        order = {
            "celestial": 0,
            "divine": 1,
            "mythical": 2,
            "legendary": 3,
            "epic": 4,
            "rare": 5,
            "uncommon": 6,
            "common": 7,
        }
        return order.get(rarity, len(order))

    def _sorted_entries_for_mode(self, mode: str, *, descending: bool) -> list[tuple[str, int]]:
        if mode == "wishes":
            return sorted(
                self.entries,
                key=lambda entry: (
                    -entry[1] if descending else entry[1],
                    str(CARD_CATALOG[entry[0]]["name"]),
                    entry[0],
                ),
            )

        if mode == "series":
            return sorted(
                self.entries,
                key=lambda entry: (
                    str(CARD_CATALOG[entry[0]]["series"]),
                    str(CARD_CATALOG[entry[0]]["name"]),
                    entry[0],
                ),
                reverse=descending,
            )

        if mode == "base_value":
            return sorted(
                self.entries,
                key=lambda entry: (
                    (-int(CARD_CATALOG[entry[0]]["base_value"]) if descending else int(CARD_CATALOG[entry[0]]["base_value"])),
                    str(CARD_CATALOG[entry[0]]["name"]),
                    entry[0],
                ),
            )

        if mode == "alphabetical":
            return sorted(
                self.entries,
                key=lambda entry: (
                    str(CARD_CATALOG[entry[0]]["name"]),
                    entry[0],
                ),
                reverse=descending,
            )

        return sorted(
            self.entries,
            key=lambda entry: (
                self._rarity_rank(str(CARD_CATALOG[entry[0]]["rarity"])),
                str(CARD_CATALOG[entry[0]]["name"]),
                entry[0],
            ),
            reverse=descending,
        )

    def _set_sort_select_defaults(self) -> None:
        selected_value = self.sort_mode
        for option in self.sort_select.options:
            option.default = option.value == selected_value

    @property
    def total_pages(self) -> int:
        page_size = self._effective_page_size()
        return max(1, (len(self._sorted_entries) + page_size - 1) // page_size)

    def _page_slice(self) -> tuple[int, int]:
        page_size = self._effective_page_size()
        start = self.page_index * page_size
        end = start + page_size
        return start, end

    def _refresh_button_state(self) -> None:
        is_first = self.page_index <= 0
        is_last = self.page_index >= (self.total_pages - 1)
        self.first_page_button.disabled = is_first
        self.previous_page_button.disabled = is_first
        self.next_page_button.disabled = is_last
        self.last_page_button.disabled = is_last

    def _build_embed_and_file(self) -> tuple[discord.Embed, discord.File | None]:
        start, end = self._page_slice()
        page_entries = self._sorted_entries[start:end]
        image_file: discord.File | None = None
        if not page_entries:
            description = "No cards available."
        elif self.gallery_mode:
            card_id, wish_count = page_entries[0]
            description = f"{start + 1}. {card_base_display(card_id)} • Wishes: **{wish_count}**"
        else:
            lines = [
                f"{idx}. {card_base_display(card_id)} • Wishes: **{wish_count}**"
                for idx, (card_id, wish_count) in enumerate(page_entries, start=start + 1)
            ]
            description = multiline_text(lines)

        embed = italy_embed("All Cards", description)
        if self.gallery_mode and page_entries:
            image_url, image_file = embed_image_payload(page_entries[0][0])
            if image_url is not None:
                embed.set_image(url=image_url)
        sort_label_map = {
            "rarity": "Rarity",
            "wishes": "Wishes",
            "series": "Series",
            "base_value": "Base Value",
            "alphabetical": "Alphabetical",
        }
        direction_label = "Desc" if self.sort_descending else "Asc"
        embed.set_footer(
            text=(f"Page {self.page_index + 1}/{self.total_pages} • Sort: {sort_label_map.get(self.sort_mode, 'Alphabetical')} ({direction_label})")
        )
        return embed, image_file

    def build_embed(self) -> discord.Embed:
        embed, _file = self._build_embed_and_file()
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._set_gallery_button_label()
        self._set_sort_direction_button_label()
        self._clamp_page_index()
        self._refresh_button_state()
        embed, image_file = self._build_embed_and_file()
        edit_kwargs: dict[str, object] = {"embed": embed, "view": self}
        if self.gallery_mode and image_file is not None:
            edit_kwargs["attachments"] = [image_file]
        else:
            edit_kwargs["attachments"] = []
        await interaction.response.edit_message(**edit_kwargs)

    async def _guard_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("All Cards", "Only the command user can control this catalog."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        placeholder="Sort cards by...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Wishes", value="wishes", description="Highest wish count first"),
            discord.SelectOption(label="Rarity", value="rarity", description="Rarest cards first"),
            discord.SelectOption(label="Series", value="series", description="Group by series"),
            discord.SelectOption(
                label="Base Value",
                value="base_value",
                description="Highest base value first",
            ),
            discord.SelectOption(
                label="Alphabetical",
                value="alphabetical",
                description="Sort by card name",
            ),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not await self._guard_user(interaction):
            return

        selected_mode = select.values[0]
        self.sort_mode = selected_mode
        self.sort_descending = self._default_sort_descending(selected_mode)
        self.page_index = 0
        self._sorted_entries = self._sorted_entries_for_mode(selected_mode, descending=self.sort_descending)
        self._set_sort_select_defaults()
        await self._update_message(interaction)

    @discord.ui.button(emoji=FIRST_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def first_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = 0
        await self._update_message(interaction)

    @discord.ui.button(emoji=PREVIOUS_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def previous_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = max(0, self.page_index - 1)
        await self._update_message(interaction)

    @discord.ui.button(emoji=NEXT_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def next_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = min(self.total_pages - 1, self.page_index + 1)
        await self._update_message(interaction)

    @discord.ui.button(emoji=LAST_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def last_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = self.total_pages - 1
        await self._update_message(interaction)

    @discord.ui.button(label="▲", style=discord.ButtonStyle.primary)
    async def sort_direction_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.sort_descending = not self.sort_descending
        self.page_index = 0
        self._sorted_entries = self._sorted_entries_for_mode(self.sort_mode, descending=self.sort_descending)
        await self._update_message(interaction)

    @discord.ui.button(label="Gallery: Off", style=discord.ButtonStyle.primary)
    async def gallery_toggle_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        if self.gallery_mode:
            current_gallery_index = self.page_index
            self.gallery_mode = False
            self.page_index = self._list_page_for_gallery_index(current_gallery_index)
        else:
            current_list_first_index = self.page_index * self.default_page_size
            self.gallery_mode = True
            self.page_index = current_list_first_index
        self._set_gallery_button_label()
        await self._update_message(interaction)

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        try:
            embed, image_file = self._build_embed_and_file()
            edit_kwargs: dict[str, object] = {"embed": embed, "view": self}
            if self.gallery_mode and image_file is not None:
                edit_kwargs["attachments"] = [image_file]
            else:
                edit_kwargs["attachments"] = []
            await self.message.edit(**edit_kwargs)
        except discord.HTTPException:
            logger.warning(
                "Failed to edit card catalog message on timeout (message_id=%s)",
                self.message.id,
            )
