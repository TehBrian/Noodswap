from typing import Optional

import discord

from .cards import (
    CARD_CATALOG,
    card_base_display,
    card_dupe_display,
    card_image_url,
    get_burn_payout,
)
from .presentation import italy_embed
from .settings import BURN_CONFIRM_TIMEOUT_SECONDS, DROP_TIMEOUT_SECONDS, TRADE_TIMEOUT_SECONDS
from .storage import add_card_to_player, add_dough, burn_instance, execute_trade, get_instance_by_id
from .utils import multiline_text


class DropView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, choices: list[tuple[str, int]]):
        super().__init__(timeout=DROP_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.choices = choices
        self.finished = False
        self.message: Optional[discord.Message] = None

        for card_id, generation in choices:
            card_name = CARD_CATALOG[card_id]["name"]
            button = discord.ui.Button(
                label=f"Pull {card_name}",
                style=discord.ButtonStyle.primary,
            )
            button.callback = self._make_pull_callback(card_id, generation)
            self.add_item(button)

    def _make_pull_callback(self, card_id: str, generation: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    embed=italy_embed("Drop", "Only the command user can pull from this drop."),
                    ephemeral=True,
                )
                return

            if self.finished:
                await interaction.response.send_message(
                    embed=italy_embed("Drop", "This drop is already resolved."),
                    ephemeral=True,
                )
                return

            instance_id = add_card_to_player(self.guild_id, self.user_id, card_id, generation)
            self.finished = True

            self._disable_buttons()

            pulled_dupe_code: str | None = None
            persisted = get_instance_by_id(self.guild_id, instance_id)
            if persisted is not None:
                _, _, _, pulled_dupe_code = persisted

            pulled_embed = italy_embed(
                "Drop Complete",
                f"You pulled {card_dupe_display(card_id, generation, dupe_code=pulled_dupe_code)}.",
            )
            pulled_embed.set_image(url=card_image_url(card_id))

            await interaction.response.edit_message(
                content=None,
                view=self,
            )
            if interaction.message is not None:
                await interaction.message.reply(embed=pulled_embed, mention_author=False)

        return callback

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()

        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass

        try:
            await self.message.reply(
                embed=italy_embed("Drop Expired", "No card was pulled from this drop."),
                mention_author=False,
            )
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
                        ""
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
        self.page_size = max(1, page_size)
        self.page_index = 0
        self.message: Optional[discord.Message] = None
        self._refresh_button_state()

    @property
    def total_pages(self) -> int:
        return max(1, (len(self.entries) + self.page_size - 1) // self.page_size)

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
        page_entries = self.entries[start:end]
        if not page_entries:
            description = "No cards available."
        else:
            lines = [
                f"{idx}. {card_base_display(card_id)} • Wishes: **{wish_count}**"
                for idx, (card_id, wish_count) in enumerate(page_entries, start=start + 1)
            ]
            description = multiline_text(lines)

        embed = italy_embed("All Cards", description)
        embed.set_footer(text=f"Page {self.page_index + 1}/{self.total_pages}")
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._refresh_button_state()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _guard_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("All Cards", "Only the command user can control this pagination."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="First Page", style=discord.ButtonStyle.secondary)
    async def first_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = 0
        await self._update_message(interaction)

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
    async def previous_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = max(0, self.page_index - 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.secondary)
    async def next_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = min(self.total_pages - 1, self.page_index + 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Last Page", style=discord.ButtonStyle.secondary)
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

    @discord.ui.button(label="First Page", style=discord.ButtonStyle.secondary)
    async def first_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = 0
        await self._update_message(interaction)

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
    async def previous_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = max(0, self.page_index - 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.secondary)
    async def next_page_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        self.page_index = min(self.total_pages - 1, self.page_index + 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Last Page", style=discord.ButtonStyle.secondary)
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
