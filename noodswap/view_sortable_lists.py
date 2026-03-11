from collections.abc import Callable
from typing import Optional

import discord

from .cards import CARD_CATALOG, card_base_display, card_dupe_display, card_value
from .images import embed_image_payload
from .presentation import italy_embed
from .settings import TRADE_TIMEOUT_SECONDS
from .utils import multiline_text
from .view_pagination import FIRST_PAGE_EMOJI, LAST_PAGE_EMOJI, NEXT_PAGE_EMOJI, PREVIOUS_PAGE_EMOJI


class SortableCardListView(discord.ui.View):
    def __init__(
        self,
        *,
        user_id: int,
        title: str,
        card_ids: list[str],
        wish_counts: dict[str, int] | None = None,
        guard_title: str,
        page_size: int = 10,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.title = title
        self.guard_title = guard_title
        self.card_ids = card_ids
        self.wish_counts = wish_counts or {}
        self.default_page_size = max(1, page_size)
        self.page_index = 0
        self.sort_mode = "alphabetical"
        self.sort_descending = self._default_sort_descending(self.sort_mode)
        self.gallery_mode = False
        self.message: Optional[discord.Message] = None
        self._sorted_card_ids = self._sorted_entries_for_mode(self.sort_mode, descending=self.sort_descending)
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

    def _sorted_entries_for_mode(self, mode: str, *, descending: bool) -> list[str]:
        if mode == "wishes":
            return sorted(
                self.card_ids,
                key=lambda card_id: (
                    -self.wish_counts.get(card_id, 0) if descending else self.wish_counts.get(card_id, 0),
                    str(CARD_CATALOG[card_id]["name"]),
                    card_id,
                ),
            )

        if mode == "series":
            return sorted(
                self.card_ids,
                key=lambda card_id: (
                    str(CARD_CATALOG[card_id]["series"]),
                    str(CARD_CATALOG[card_id]["name"]),
                    card_id,
                ),
                reverse=descending,
            )

        if mode == "base_value":
            return sorted(
                self.card_ids,
                key=lambda card_id: (
                    -int(CARD_CATALOG[card_id]["base_value"])
                    if descending
                    else int(CARD_CATALOG[card_id]["base_value"]),
                    str(CARD_CATALOG[card_id]["name"]),
                    card_id,
                ),
            )

        if mode == "alphabetical":
            return sorted(
                self.card_ids,
                key=lambda card_id: (
                    str(CARD_CATALOG[card_id]["name"]),
                    card_id,
                ),
                reverse=descending,
            )

        return sorted(
            self.card_ids,
            key=lambda card_id: (
                self._rarity_rank(str(CARD_CATALOG[card_id]["rarity"])),
                str(CARD_CATALOG[card_id]["name"]),
                card_id,
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
        return max(1, (len(self._sorted_card_ids) + page_size - 1) // page_size)

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
        page_card_ids = self._sorted_card_ids[start:end]
        image_file: discord.File | None = None
        if not page_card_ids:
            description = "No entries available."
        elif self.gallery_mode:
            card_id = page_card_ids[0]
            description = f"{start + 1}. {card_base_display(card_id)}"
        else:
            lines = [
                f"{idx}. {card_base_display(card_id)}"
                for idx, card_id in enumerate(page_card_ids, start=start + 1)
            ]
            description = multiline_text(lines)

        embed = italy_embed(self.title, description)
        if self.gallery_mode and page_card_ids:
            image_url, image_file = embed_image_payload(page_card_ids[0])
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
            text=(
                f"Page {self.page_index + 1}/{self.total_pages} • "
                f"Sort: {sort_label_map.get(self.sort_mode, 'Alphabetical')} ({direction_label})"
            )
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
                embed=italy_embed(self.guard_title, "Only the command user can control this list."),
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
            discord.SelectOption(label="Base Value", value="base_value", description="Highest base value first"),
            discord.SelectOption(label="Alphabetical", value="alphabetical", description="Sort by card name"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not await self._guard_user(interaction):
            return

        selected_mode = select.values[0]
        self.sort_mode = selected_mode
        self.sort_descending = self._default_sort_descending(selected_mode)
        self.page_index = 0
        self._sorted_card_ids = self._sorted_entries_for_mode(selected_mode, descending=self.sort_descending)
        self._set_sort_select_defaults()
        await self._update_message(interaction)

    @discord.ui.button(label="First", emoji=FIRST_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def first_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = 0
        await self._update_message(interaction)

    @discord.ui.button(label="Prev", emoji=PREVIOUS_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def previous_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = max(0, self.page_index - 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Next", emoji=NEXT_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def next_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = min(self.total_pages - 1, self.page_index + 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Last", emoji=LAST_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
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
        self._sorted_card_ids = self._sorted_entries_for_mode(self.sort_mode, descending=self.sort_descending)
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
            pass


class SortableCollectionView(discord.ui.View):
    def __init__(
        self,
        *,
        user_id: int,
        title: str,
        instances: list[tuple[int, str, int, str]],
        wish_counts: dict[str, int] | None,
        instance_styles: dict[int, tuple[str | None, str | None, str | None]] | None,
        guard_title: str,
        locked_instance_ids: set[int] | None = None,
        folder_emojis_by_instance: dict[int, str] | None = None,
        card_line_formatter: Callable[..., str] | None = None,
        page_size: int = 10,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.title = title
        self.instances = instances
        self.locked_instance_ids = locked_instance_ids or set()
        self.folder_emojis_by_instance = folder_emojis_by_instance or {}
        self.wish_counts = wish_counts or {}
        self.instance_styles = instance_styles or {}
        self.card_line_formatter = card_line_formatter or card_dupe_display
        self.guard_title = guard_title
        self.default_page_size = max(1, page_size)
        self.page_index = 0
        self.sort_mode = "alphabetical"
        self.sort_descending = self._default_sort_descending(self.sort_mode)
        self.gallery_mode = False
        self.message: Optional[discord.Message] = None
        self._sorted_instances = self._sorted_entries_for_mode(self.sort_mode, descending=self.sort_descending)
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
        return mode in {"wishes", "base_value", "actual_value"}

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

    def _sorted_entries_for_mode(self, mode: str, *, descending: bool) -> list[tuple[int, str, int, str]]:
        if mode == "generation":
            return sorted(
                self.instances,
                key=lambda item: (
                    -item[2] if descending else item[2],
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[0],
                ),
            )

        if mode == "wishes":
            return sorted(
                self.instances,
                key=lambda item: (
                    -self.wish_counts.get(item[1], 0) if descending else self.wish_counts.get(item[1], 0),
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[2],
                    item[0],
                ),
            )

        if mode == "series":
            return sorted(
                self.instances,
                key=lambda item: (
                    str(CARD_CATALOG[item[1]]["series"]),
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[2],
                    item[0],
                ),
                reverse=descending,
            )

        if mode == "base_value":
            return sorted(
                self.instances,
                key=lambda item: (
                    -int(CARD_CATALOG[item[1]]["base_value"])
                    if descending
                    else int(CARD_CATALOG[item[1]]["base_value"]),
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[2],
                    item[0],
                ),
            )

        if mode == "actual_value":
            return sorted(
                self.instances,
                key=lambda item: (
                    -card_value(
                        item[1],
                        item[2],
                        morph_key=self.instance_styles.get(item[0], (None, None, None))[0],
                        frame_key=self.instance_styles.get(item[0], (None, None, None))[1],
                        font_key=self.instance_styles.get(item[0], (None, None, None))[2],
                    )
                    if descending
                    else card_value(
                        item[1],
                        item[2],
                        morph_key=self.instance_styles.get(item[0], (None, None, None))[0],
                        frame_key=self.instance_styles.get(item[0], (None, None, None))[1],
                        font_key=self.instance_styles.get(item[0], (None, None, None))[2],
                    ),
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[2],
                    item[0],
                ),
            )

        if mode == "rarity":
            return sorted(
                self.instances,
                key=lambda item: (
                    -self._rarity_rank(str(CARD_CATALOG[item[1]]["rarity"]))
                    if descending
                    else self._rarity_rank(str(CARD_CATALOG[item[1]]["rarity"])),
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[2],
                    item[0],
                ),
            )

        return sorted(
            self.instances,
            key=lambda item: (
                str(CARD_CATALOG[item[1]]["name"]),
                item[2],
                item[0],
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
        return max(1, (len(self._sorted_instances) + page_size - 1) // page_size)

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
        page_instances = self._sorted_instances[start:end]
        image_file: discord.File | None = None

        if not page_instances:
            description = "No entries available."
        elif self.gallery_mode:
            instance_id, card_id, generation, dupe_code = page_instances[0]
            marker = self._instance_marker(instance_id)
            description = f"{start + 1}. {marker}{self._format_card_line(instance_id, card_id, generation, dupe_code)}"
        else:
            lines = [
                f"{idx}. {self._instance_marker(instance_id)}"
                f"{self._format_card_line(instance_id, card_id, generation, dupe_code)}"
                for idx, (instance_id, card_id, generation, dupe_code) in enumerate(page_instances, start=start + 1)
            ]
            description = multiline_text(lines)

        embed = italy_embed(self.title, description)
        if self.gallery_mode and page_instances:
            instance_id, card_id, generation, _dupe_code = page_instances[0]
            morph_key, frame_key, font_key = self.instance_styles.get(instance_id, (None, None, None))

            image_url, image_file = embed_image_payload(
                card_id,
                generation=generation,
                morph_key=morph_key,
                frame_key=frame_key,
                font_key=font_key,
            )
            if image_url is not None:
                embed.set_image(url=image_url)

        sort_label_map = {
            "generation": "Generation",
            "wishes": "Wishes",
            "rarity": "Rarity",
            "series": "Series",
            "base_value": "Base Value",
            "actual_value": "Actual Value",
            "alphabetical": "Alphabetical",
        }
        direction_label = "Desc" if self.sort_descending else "Asc"
        embed.set_footer(
            text=(
                f"Page {self.page_index + 1}/{self.total_pages} • "
                f"Sort: {sort_label_map.get(self.sort_mode, 'Alphabetical')} ({direction_label})"
            )
        )
        return embed, image_file

    def _instance_marker(self, instance_id: int) -> str:
        lock_marker = "🔒 " if instance_id in self.locked_instance_ids else "`  ` "
        folder_emoji = self.folder_emojis_by_instance.get(instance_id)
        folder_marker = f"{folder_emoji} " if folder_emoji is not None else "`  ` "
        return f"{folder_marker}{lock_marker}"

    def _format_card_line(self, instance_id: int, card_id: str, generation: int, dupe_code: str | None) -> str:
        morph_key, frame_key, font_key = self.instance_styles.get(instance_id, (None, None, None))
        try:
            return self.card_line_formatter(
                card_id,
                generation,
                dupe_code,
                morph_key=morph_key,
                frame_key=frame_key,
                font_key=font_key,
            )
        except TypeError:
            return self.card_line_formatter(card_id, generation, dupe_code)

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
                embed=italy_embed(self.guard_title, "Only the command user can control this collection."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        placeholder="Sort cards by...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Generation", value="generation", description="Lowest generation first"),
            discord.SelectOption(label="Wishes", value="wishes", description="Highest wish count first"),
            discord.SelectOption(label="Rarity", value="rarity", description="Rarest cards first"),
            discord.SelectOption(label="Series", value="series", description="Group by series"),
            discord.SelectOption(label="Base Value", value="base_value", description="Highest base value first"),
            discord.SelectOption(
                label="Actual Value",
                value="actual_value",
                description="Highest computed value first",
            ),
            discord.SelectOption(label="Alphabetical", value="alphabetical", description="Sort by card name"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not await self._guard_user(interaction):
            return

        selected_mode = select.values[0]
        self.sort_mode = selected_mode
        self.sort_descending = self._default_sort_descending(selected_mode)
        self.page_index = 0
        self._sorted_instances = self._sorted_entries_for_mode(selected_mode, descending=self.sort_descending)
        self._set_sort_select_defaults()
        await self._update_message(interaction)

    @discord.ui.button(label="First", emoji=FIRST_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def first_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = 0
        await self._update_message(interaction)

    @discord.ui.button(label="Prev", emoji=PREVIOUS_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def previous_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = max(0, self.page_index - 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Next", emoji=NEXT_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
    async def next_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = min(self.total_pages - 1, self.page_index + 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Last", emoji=LAST_PAGE_EMOJI, style=discord.ButtonStyle.secondary)
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
        self._sorted_instances = self._sorted_entries_for_mode(self.sort_mode, descending=self.sort_descending)
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
            pass
