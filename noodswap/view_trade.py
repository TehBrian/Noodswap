import asyncio
from typing import Optional

import discord

from .cards import card_base_display, card_dupe_display
from .presentation import italy_embed
from .services import TradeTerms, resolve_trade_offer
from .settings import TRADE_TIMEOUT_SECONDS
from .view_utils import InteractionView, logger


def _trade_accepted_payment_text(terms: TradeTerms) -> str:
    if terms.mode == "dough":
        return f"**{terms.amount}** dough"
    if terms.mode == "starter":
        return f"**{terms.amount}** starter"
    if terms.mode == "tickets":
        return f"**{terms.amount}** drop ticket(s)"
    # card mode
    return "card swap"


class TradeView(InteractionView):
    def __init__(
        self,
        guild_id: int,
        seller_id: int,
        buyer_id: int,
        card_id: str,
        dupe_code: str,
        terms: TradeTerms,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.seller_id = seller_id
        self.buyer_id = buyer_id
        self.card_id = card_id
        self.dupe_code = dupe_code
        self.terms = terms
        self.finished = False
        self.message: Optional[discord.Message] = None
        self._resolve_lock = asyncio.Lock()

    async def _resolve(self, interaction: discord.Interaction, accepted: bool):
        if interaction.user.id != self.buyer_id:
            await interaction.response.send_message(
                embed=italy_embed("Trade", "Only the offered member can respond to this trade."),
                ephemeral=True,
            )
            return

        async with self._resolve_lock:
            if self.finished:
                await interaction.response.send_message(
                    embed=italy_embed("Trade", "This trade has already been resolved."),
                    ephemeral=True,
                )
                return

            if not accepted:
                trade_result = resolve_trade_offer(
                    guild_id=self.guild_id,
                    seller_id=self.seller_id,
                    buyer_id=self.buyer_id,
                    card_id=self.card_id,
                    dupe_code=self.dupe_code,
                    terms=self.terms,
                    accepted=False,
                )
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(
                    content=None,
                    embed=italy_embed("Trade Denied", trade_result.message),
                    view=self,
                )
                return

            trade_result = resolve_trade_offer(
                guild_id=self.guild_id,
                seller_id=self.seller_id,
                buyer_id=self.buyer_id,
                card_id=self.card_id,
                dupe_code=self.dupe_code,
                terms=self.terms,
                accepted=True,
            )
            if trade_result.is_failed:
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(
                    content=None,
                    embed=italy_embed("Trade Failed", trade_result.message),
                    view=self,
                )
                return

            self.finished = True
            self._disable_buttons()

            traded_card_text = card_base_display(self.card_id)
            if trade_result.generation is not None:
                traded_card_text = card_dupe_display(
                    self.card_id,
                    trade_result.generation,
                    dupe_code=trade_result.dupe_code,
                )

            if self.terms.mode == "card" and trade_result.received_card_id is not None:
                received_text = card_base_display(trade_result.received_card_id)
                if trade_result.received_generation is not None:
                    received_text = card_dupe_display(
                        trade_result.received_card_id,
                        trade_result.received_generation,
                        dupe_code=trade_result.received_dupe_code,
                    )
                accepted_body = (
                    f"Buyer: <@{self.buyer_id}>\n"
                    f"Seller: <@{self.seller_id}>\n"
                    "\n"
                    f"Seller gave: {traded_card_text}\n"
                    f"Buyer gave: {received_text}"
                )
            else:
                accepted_body = (
                    f"Buyer: <@{self.buyer_id}>\n"
                    f"Seller: <@{self.seller_id}>\n"
                    "\n"
                    f"Card: {traded_card_text}\n"
                    f"Price: {_trade_accepted_payment_text(self.terms)}"
                )

        await interaction.response.edit_message(
            view=self,
        )
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed("Trade Accepted", accepted_body),
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
            logger.warning("Failed to edit trade message on timeout (message_id=%s)", self.message.id)

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
