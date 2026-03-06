import asyncio
import time
from typing import Optional

import discord

from .cards import (
    CARD_CATALOG,
    card_base_display,
    card_dupe_display,
    get_burn_payout,
)
from .images import embed_image_payload
from .presentation import italy_embed
from .settings import (
    BURN_CONFIRM_TIMEOUT_SECONDS,
    DROP_TIMEOUT_SECONDS,
    PAGINATION_FIRST_EMOJI,
    PAGINATION_LAST_EMOJI,
    PAGINATION_NEXT_EMOJI,
    PAGINATION_PREVIOUS_EMOJI,
    PULL_COOLDOWN_SECONDS,
    TRADE_TIMEOUT_SECONDS,
)
from .storage import (
    add_card_to_player,
    add_dough,
    burn_instance,
    consume_pull_cooldown_if_ready,
    execute_trade,
    get_instance_by_id,
    get_locked_tags_for_instance,
)
from .utils import multiline_text


def _resolve_pagination_emoji(token: str, fallback: str) -> discord.PartialEmoji | str:
    cleaned = token.strip()
    if not cleaned:
        return fallback

    emoji = discord.PartialEmoji.from_str(cleaned)
    if emoji.id is None and not emoji.name:
        return fallback
    return emoji


FIRST_PAGE_EMOJI = _resolve_pagination_emoji(PAGINATION_FIRST_EMOJI, "⏮️")
PREVIOUS_PAGE_EMOJI = _resolve_pagination_emoji(PAGINATION_PREVIOUS_EMOJI, "◀️")
NEXT_PAGE_EMOJI = _resolve_pagination_emoji(PAGINATION_NEXT_EMOJI, "▶️")
LAST_PAGE_EMOJI = _resolve_pagination_emoji(PAGINATION_LAST_EMOJI, "⏭️")


class DropView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, choices: list[tuple[str, int]]):
        super().__init__(timeout=DROP_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.choices = choices
        self.finished = False
        self.message: Optional[discord.Message] = None
        self._claim_lock = asyncio.Lock()
        self._claimed_button_ids: set[str] = set()

        for index, (card_id, generation) in enumerate(choices):
            card_name = CARD_CATALOG[card_id]["name"]
            button_id = f"drop:{index}"
            button = discord.ui.Button(
                label=f"Pull {card_name}",
                style=discord.ButtonStyle.primary,
                custom_id=button_id,
            )
            button.callback = self._make_pull_callback(card_id, generation, button_id)
            self.add_item(button)

    def _make_pull_callback(self, card_id: str, generation: int, button_id: str):
        async def callback(interaction: discord.Interaction):
            if self.finished:
                await interaction.response.send_message(
                    embed=italy_embed("Drop", "This drop is already resolved."),
                    ephemeral=True,
                )
                return

            async with self._claim_lock:
                if button_id in self._claimed_button_ids:
                    await interaction.response.send_message(
                        embed=italy_embed("Drop", "That card has already been claimed."),
                        ephemeral=True,
                    )
                    return

                cooldown_remaining = consume_pull_cooldown_if_ready(
                    self.guild_id,
                    interaction.user.id,
                    time.time(),
                    PULL_COOLDOWN_SECONDS,
                )
                if cooldown_remaining > 0:
                    await interaction.response.send_message(
                        embed=italy_embed(
                            "Pull Cooldown",
                            f"You need to wait before your next pull (**{int(cooldown_remaining)}s** remaining).",
                        ),
                        ephemeral=True,
                    )
                    return

                self._claimed_button_ids.add(button_id)

                claimed_button = next(
                    (
                        item
                        for item in self.children
                        if isinstance(item, discord.ui.Button) and item.custom_id == button_id
                    ),
                    None,
                )
                if claimed_button is not None:
                    claimed_button.disabled = True

                if all(isinstance(item, discord.ui.Button) and item.disabled for item in self.children):
                    self.finished = True

            instance_id = add_card_to_player(self.guild_id, interaction.user.id, card_id, generation)

            pulled_dupe_code: str | None = None
            persisted = get_instance_by_id(self.guild_id, instance_id)
            if persisted is not None:
                _, _, _, pulled_dupe_code = persisted

            pulled_embed = italy_embed(
                "Drop Complete",
                f"<@{interaction.user.id}> pulled {card_dupe_display(card_id, generation, dupe_code=pulled_dupe_code)}.",
            )
            image_url, image_file = embed_image_payload(card_id, generation=generation)
            if image_url is not None:
                pulled_embed.set_image(url=image_url)

            await interaction.response.edit_message(
                content=None,
                view=self,
            )
            if interaction.message is not None:
                send_kwargs: dict[str, object] = {"embed": pulled_embed, "mention_author": False}
                if image_file is not None:
                    send_kwargs["file"] = image_file
                await interaction.message.reply(**send_kwargs)

        return callback

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()

        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class TradeView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        seller_id: int,
        buyer_id: int,
        card_id: str,
        dupe_code: str,
        amount: int,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.seller_id = seller_id
        self.buyer_id = buyer_id
        self.card_id = card_id
        self.dupe_code = dupe_code
        self.amount = amount
        self.finished = False
        self.message: Optional[discord.Message] = None

    async def _resolve(self, interaction: discord.Interaction, accepted: bool):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message(
                embed=italy_embed("Trade", "Only the offered member can respond to this trade."),
                ephemeral=True,
            )
            return

        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Trade", "This trade has already been resolved."),
                ephemeral=True,
            )
            return

        if not accepted:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                content=None,
                embed=italy_embed("Trade Denied", "The trade was denied."),
                view=self,
            )
            return

        success, message, generation, dupe_code = execute_trade(
            guild_id=self.guild_id,
            seller_id=self.seller_id,
            buyer_id=self.buyer_id,
            card_id=self.card_id,
            dupe_code=self.dupe_code,
            amount=self.amount,
        )
        if not success:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                content=None,
                embed=italy_embed("Trade Failed", message),
                view=self,
            )
            return

        self.finished = True
        self._disable_buttons()

        traded_card_text = card_base_display(self.card_id)
        if generation is not None:
            traded_card_text = card_dupe_display(self.card_id, generation, dupe_code=dupe_code)

        await interaction.response.edit_message(
            view=self,
        )
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed(
                    "Trade Accepted",
                    (
                        f"Buyer: <@{self.buyer_id}>\n"
                        f"Seller: <@{self.seller_id}>\n"
                        "\n"
                        f"Card: {traded_card_text}\n"
                        f"Price: **{self.amount}** dough"
                    ),
                ),
                mention_author=False,
            )

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        await self._resolve(interaction, accepted=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        await self._resolve(interaction, accepted=False)

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()

        try:
            await self.message.edit(
                content=None,
                embed=italy_embed("Trade Expired", "Trade offer expired."),
                view=self,
            )
        except discord.HTTPException:
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class BurnConfirmView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, instance_id: int, card_id: str, generation: int, delta_range: int):
        super().__init__(timeout=BURN_CONFIRM_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.delta_range = delta_range
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Confirm Burn", style=discord.ButtonStyle.danger)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Burn", "Only the command user can confirm this burn."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Burn", "This burn request is already resolved."),
                ephemeral=True,
            )
            return

        locked_tags = get_locked_tags_for_instance(self.guild_id, self.user_id, self.instance_id)
        if locked_tags:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                locked_tags_text = ", ".join(f"`{tag}`" for tag in locked_tags)
                await interaction.message.reply(
                    embed=italy_embed(
                        "Burn Blocked",
                        f"This card is protected by locked tag(s): {locked_tags_text}.",
                    ),
                    mention_author=False,
                )
            return

        burned = burn_instance(self.guild_id, self.user_id, self.instance_id)
        if burned is None:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                view=self,
            )
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed("Burn Failed", "That card instance is no longer available."),
                    mention_author=False,
                )
            return

        burned_card_id, burned_generation, burned_dupe_code = burned
        payout, _value, _base_value, delta, _multiplier, _resolved_delta_range = get_burn_payout(
            burned_card_id,
            burned_generation,
            self.delta_range,
        )
        add_dough(self.guild_id, self.user_id, payout)
        burned_embed = italy_embed(
            "**Card Burned**",
            f"""{card_dupe_display(burned_card_id, burned_generation, dupe_code=burned_dupe_code)}

Payout: **{payout} dough**
    RNG: **{delta:+}**""",
        )

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(
            view=self,
        )
        if interaction.message is not None:
            await interaction.message.reply(embed=burned_embed, mention_author=False)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Burn", "Only the command user can cancel this burn."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Burn", "This burn request is already resolved."),
                ephemeral=True,
            )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(
            view=self,
        )
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed("Burn Cancelled", "No card was burned."),
                mention_author=False,
            )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(
                content=None,
                embed=italy_embed("Burn Expired", "Burn confirmation timed out."),
                view=self,
            )
        except discord.HTTPException:
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class CardCatalogView(discord.ui.View):
    def __init__(self, user_id: int, entries: list[tuple[str, int]], page_size: int = 10):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.entries = entries
        self.default_page_size = max(1, page_size)
        self.page_index = 0
        self.sort_mode = "alphabetical"
        self.gallery_mode = False
        self.message: Optional[discord.Message] = None
        self._sorted_entries = self._sorted_entries_for_mode(self.sort_mode)
        self._set_gallery_button_label()
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

    def _rarity_rank(self, rarity: str) -> int:
        order = {
            "celestial": 0,
            "divine": 1,
            "mythic": 2,
            "legendary": 3,
            "epic": 4,
            "rare": 5,
            "uncommon": 6,
            "common": 7,
        }
        return order.get(rarity, len(order))

    def _sorted_entries_for_mode(self, mode: str) -> list[tuple[str, int]]:
        if mode == "wishes":
            return sorted(
                self.entries,
                key=lambda entry: (
                    -entry[1],
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
            )

        if mode == "base_value":
            return sorted(
                self.entries,
                key=lambda entry: (
                    -int(CARD_CATALOG[entry[0]]["base_value"]),
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
            )

        return sorted(
            self.entries,
            key=lambda entry: (
                self._rarity_rank(str(CARD_CATALOG[entry[0]]["rarity"])),
                str(CARD_CATALOG[entry[0]]["name"]),
                entry[0],
            ),
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
        embed.set_footer(
            text=f"Page {self.page_index + 1}/{self.total_pages} • Sort: {sort_label_map.get(self.sort_mode, 'Alphabetical')}"
        )
        return embed, image_file

    def build_embed(self) -> discord.Embed:
        embed, _file = self._build_embed_and_file()
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._set_gallery_button_label()
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
            discord.SelectOption(label="Base Value", value="base_value", description="Highest base value first"),
            discord.SelectOption(label="Alphabetical", value="alphabetical", description="Sort by card name"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not await self._guard_user(interaction):
            return

        selected_mode = select.values[0]
        self.sort_mode = selected_mode
        self.page_index = 0
        self._sorted_entries = self._sorted_entries_for_mode(selected_mode)
        self._set_sort_select_defaults()
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
        self.gallery_mode = False
        self.message: Optional[discord.Message] = None
        self._sorted_card_ids = self._sorted_entries_for_mode(self.sort_mode)
        self._set_gallery_button_label()
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

    def _rarity_rank(self, rarity: str) -> int:
        order = {
            "celestial": 0,
            "divine": 1,
            "mythic": 2,
            "legendary": 3,
            "epic": 4,
            "rare": 5,
            "uncommon": 6,
            "common": 7,
        }
        return order.get(rarity, len(order))

    def _sorted_entries_for_mode(self, mode: str) -> list[str]:
        if mode == "wishes":
            return sorted(
                self.card_ids,
                key=lambda card_id: (
                    -self.wish_counts.get(card_id, 0),
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
            )

        if mode == "base_value":
            return sorted(
                self.card_ids,
                key=lambda card_id: (
                    -int(CARD_CATALOG[card_id]["base_value"]),
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
            )

        return sorted(
            self.card_ids,
            key=lambda card_id: (
                self._rarity_rank(str(CARD_CATALOG[card_id]["rarity"])),
                str(CARD_CATALOG[card_id]["name"]),
                card_id,
            ),
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
        embed.set_footer(
            text=f"Page {self.page_index + 1}/{self.total_pages} • Sort: {sort_label_map.get(self.sort_mode, 'Alphabetical')}"
        )
        return embed, image_file

    def build_embed(self) -> discord.Embed:
        embed, _file = self._build_embed_and_file()
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._set_gallery_button_label()
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
        self.page_index = 0
        self._sorted_card_ids = self._sorted_entries_for_mode(selected_mode)
        self._set_sort_select_defaults()
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
        guard_title: str,
        page_size: int = 10,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.title = title
        self.instances = instances
        self.wish_counts = wish_counts or {}
        self.guard_title = guard_title
        self.default_page_size = max(1, page_size)
        self.page_index = 0
        self.sort_mode = "alphabetical"
        self.gallery_mode = False
        self.message: Optional[discord.Message] = None
        self._sorted_instances = self._sorted_entries_for_mode(self.sort_mode)
        self._set_gallery_button_label()
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

    def _rarity_rank(self, rarity: str) -> int:
        order = {
            "celestial": 0,
            "divine": 1,
            "mythic": 2,
            "legendary": 3,
            "epic": 4,
            "rare": 5,
            "uncommon": 6,
            "common": 7,
        }
        return order.get(rarity, len(order))

    def _sorted_entries_for_mode(self, mode: str) -> list[tuple[int, str, int, str]]:
        if mode == "wishes":
            return sorted(
                self.instances,
                key=lambda item: (
                    -self.wish_counts.get(item[1], 0),
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
            )

        if mode == "base_value":
            return sorted(
                self.instances,
                key=lambda item: (
                    -int(CARD_CATALOG[item[1]]["base_value"]),
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[2],
                    item[0],
                ),
            )

        if mode == "rarity":
            return sorted(
                self.instances,
                key=lambda item: (
                    self._rarity_rank(str(CARD_CATALOG[item[1]]["rarity"])),
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
            _, card_id, generation, dupe_code = page_instances[0]
            description = f"{start + 1}. {card_dupe_display(card_id, generation, dupe_code=dupe_code)}"
        else:
            lines = [
                f"{idx}. {card_dupe_display(card_id, generation, dupe_code=dupe_code)}"
                for idx, (_instance_id, card_id, generation, dupe_code) in enumerate(page_instances, start=start + 1)
            ]
            description = multiline_text(lines)

        embed = italy_embed(self.title, description)
        if self.gallery_mode and page_instances:
            _, card_id, generation, _dupe_code = page_instances[0]
            image_url, image_file = embed_image_payload(card_id, generation=generation)
            if image_url is not None:
                embed.set_image(url=image_url)

        sort_label_map = {
            "wishes": "Wishes",
            "rarity": "Rarity",
            "series": "Series",
            "base_value": "Base Value",
            "alphabetical": "Alphabetical",
        }
        embed.set_footer(
            text=f"Page {self.page_index + 1}/{self.total_pages} • Sort: {sort_label_map.get(self.sort_mode, 'Alphabetical')}"
        )
        return embed, image_file

    def build_embed(self) -> discord.Embed:
        embed, _file = self._build_embed_and_file()
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._set_gallery_button_label()
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
        self.page_index = 0
        self._sorted_instances = self._sorted_entries_for_mode(selected_mode)
        self._set_sort_select_defaults()
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
                embed=italy_embed(self.guard_title, "Only the command user can control this pagination."),
                ephemeral=True,
            )
            return False
        return True

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
