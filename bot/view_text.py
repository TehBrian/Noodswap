from typing import Optional

import discord

from .presentation import italy_embed
from .settings import TRADE_TIMEOUT_SECONDS
from .utils import multiline_text
from .view_pagination import (
    FIRST_PAGE_EMOJI,
    LAST_PAGE_EMOJI,
    NEXT_PAGE_EMOJI,
    PREVIOUS_PAGE_EMOJI,
)


class PaginatedLinesView(discord.ui.View):
    def __init__(
        self,
        *,
        user_id: int,
        title: str,
        lines: list[str],
        guard_title: str,
        page_size: int = 10,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.title = title
        self.lines = lines
        self.guard_title = guard_title
        self.page_size = max(1, page_size)
        self.page_index = 0
        self.message: Optional[discord.Message] = None
        self._refresh_button_state()

    @property
    def total_pages(self) -> int:
        return max(1, (len(self.lines) + self.page_size - 1) // self.page_size)

    def _page_slice(self) -> tuple[int, int]:
        start = self.page_index * self.page_size
        end = start + self.page_size
        return start, end

    def _refresh_button_state(self) -> None:
        is_first = self.page_index <= 0
        is_last = self.page_index >= (self.total_pages - 1)
        self.first_page_button.disabled = is_first
        self.previous_page_button.disabled = is_first
        self.next_page_button.disabled = is_last
        self.last_page_button.disabled = is_last

    def build_embed(self) -> discord.Embed:
        start, end = self._page_slice()
        page_lines = self.lines[start:end]
        description = multiline_text(page_lines) if page_lines else "No entries available."

        embed = italy_embed(self.title, description)
        embed.set_footer(text=f"Page {self.page_index + 1}/{self.total_pages}")
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._refresh_button_state()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _guard_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    self.guard_title,
                    "Only the command user can control this pagination.",
                ),
                ephemeral=True,
            )
            return False
        return True

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

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass


class PlayerLeaderboardView(discord.ui.View):
    def __init__(
        self,
        *,
        user_id: int,
        title: str,
        entries: list[tuple[int, int, int, int, int, int, int]],
        guard_title: str,
        page_size: int = 10,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.title = title
        self.entries = entries
        self.guard_title = guard_title
        self.page_size = max(1, page_size)
        self.page_index = 0
        self.criteria = "cards"
        self.sort_descending = True
        self.message: Optional[discord.Message] = None
        self._sorted_entries = self._sorted_entries_for_criteria(self.criteria, descending=self.sort_descending)
        self._set_criteria_select_defaults()
        self._set_sort_direction_button_label()
        self._refresh_button_state()

    def _metric_value(self, entry: tuple[int, int, int, int, int, int, int], criteria: str) -> int:
        _user_id, cards, wishes, dough, starter, votes, total_value = entry
        metric_by_criteria = {
            "cards": cards,
            "wishes": wishes,
            "dough": dough,
            "starter": starter,
            "votes": votes,
            "value": total_value,
        }
        return metric_by_criteria.get(criteria, cards)

    def _criteria_label(self, criteria: str) -> str:
        return {
            "cards": "Cards",
            "wishes": "Wishes",
            "dough": "Dough",
            "starter": "Starter",
            "votes": "Votes",
            "value": "Collection Value",
        }.get(criteria, "Cards")

    def _sorted_entries_for_criteria(self, criteria: str, *, descending: bool) -> list[tuple[int, int, int, int, int, int, int]]:
        return sorted(
            self.entries,
            key=lambda entry: (
                (-self._metric_value(entry, criteria) if descending else self._metric_value(entry, criteria)),
                -entry[6],
                -entry[3],
                entry[0],
            ),
        )

    def _set_criteria_select_defaults(self) -> None:
        selected = self.criteria
        for option in self.criteria_select.options:
            option.default = option.value == selected

    def _set_sort_direction_button_label(self) -> None:
        self.sort_direction_button.label = "▼" if self.sort_descending else "▲"

    @property
    def total_pages(self) -> int:
        return max(1, (len(self._sorted_entries) + self.page_size - 1) // self.page_size)

    def _page_slice(self) -> tuple[int, int]:
        start = self.page_index * self.page_size
        end = start + self.page_size
        return start, end

    def _refresh_button_state(self) -> None:
        is_first = self.page_index <= 0
        is_last = self.page_index >= (self.total_pages - 1)
        self.first_page_button.disabled = is_first
        self.previous_page_button.disabled = is_first
        self.next_page_button.disabled = is_last
        self.last_page_button.disabled = is_last

    def build_embed(self) -> discord.Embed:
        start, end = self._page_slice()
        page_entries = self._sorted_entries[start:end]

        criteria_label = self._criteria_label(self.criteria)
        if not page_entries:
            description = "No players available."
        else:
            lines = []
            for rank, (
                player_id,
                cards,
                wishes,
                dough,
                starter,
                votes,
                total_value,
            ) in enumerate(
                page_entries,
                start=start + 1,
            ):
                value = self._metric_value(
                    (player_id, cards, wishes, dough, starter, votes, total_value),
                    self.criteria,
                )
                lines.append(f"{rank}. {criteria_label}: **{value}** • <@{player_id}>")
            description = multiline_text(lines)

        embed = italy_embed(self.title, description)
        direction_label = "Desc" if self.sort_descending else "Asc"
        embed.set_footer(text=f"Page {self.page_index + 1}/{self.total_pages} • Ranked by {criteria_label} ({direction_label})")
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self.page_index = max(0, min(self.total_pages - 1, self.page_index))
        self._set_sort_direction_button_label()
        self._refresh_button_state()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _guard_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    self.guard_title,
                    "Only the command user can control this leaderboard.",
                ),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        placeholder="Rank players by...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Cards", value="cards", description="Most owned cards"),
            discord.SelectOption(label="Wishes", value="wishes", description="Most wishlisted cards"),
            discord.SelectOption(label="Dough", value="dough", description="Most dough"),
            discord.SelectOption(label="Starter", value="starter", description="Most starter"),
            discord.SelectOption(label="Votes", value="votes", description="Most Top.gg votes"),
            discord.SelectOption(
                label="Collection Value",
                value="value",
                description="Highest total card value",
            ),
        ],
    )
    async def criteria_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not await self._guard_user(interaction):
            return

        self.criteria = select.values[0]
        self.page_index = 0
        self._sorted_entries = self._sorted_entries_for_criteria(self.criteria, descending=self.sort_descending)
        self._set_criteria_select_defaults()
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

    @discord.ui.button(label="▼", style=discord.ButtonStyle.primary)
    async def sort_direction_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.sort_descending = not self.sort_descending
        self.page_index = 0
        self._sorted_entries = self._sorted_entries_for_criteria(self.criteria, descending=self.sort_descending)
        await self._update_message(interaction)

    async def on_timeout(self) -> None:
        if self.message is None:
            return
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        try:
            await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass
