import asyncio
from typing import Optional

import discord

from .cards import card_base_display, card_dupe_display
from .presentation import italy_embed
from .services import resolve_gift_offer
from .settings import TRADE_TIMEOUT_SECONDS
from .view_utils import InteractionView, logger


class GiftCardView(InteractionView):
    def __init__(
        self,
        guild_id: int,
        sender_id: int,
        recipient_id: int,
        card_code: str,
        card_id: str,
        dupe_code: str,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.card_code = card_code
        self.card_id = card_id
        self.dupe_code = dupe_code
        self.finished = False
        self.message: Optional[discord.Message] = None
        self._resolve_lock = asyncio.Lock()

    async def _resolve(self, interaction: discord.Interaction, accepted: bool):
        if interaction.user.id != self.recipient_id:
            await interaction.response.send_message(
                embed=italy_embed("Gift", "Only the gifted member can respond to this gift."),
                ephemeral=True,
            )
            return

        async with self._resolve_lock:
            if self.finished:
                await interaction.response.send_message(
                    embed=italy_embed("Gift", "This gift has already been resolved."),
                    ephemeral=True,
                )
                return

            if not accepted:
                gift_result = resolve_gift_offer(
                    guild_id=self.guild_id,
                    sender_id=self.sender_id,
                    recipient_id=self.recipient_id,
                    card_code=self.card_code,
                    accepted=False,
                )
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(
                    content=None,
                    embed=italy_embed("Gift Declined", gift_result.message),
                    view=self,
                )
                return

            gift_result = resolve_gift_offer(
                guild_id=self.guild_id,
                sender_id=self.sender_id,
                recipient_id=self.recipient_id,
                card_code=self.card_code,
                accepted=True,
            )
            if gift_result.is_failed:
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(
                    content=None,
                    embed=italy_embed("Gift Failed", gift_result.message),
                    view=self,
                )
                return

            self.finished = True
            self._disable_buttons()

            gifted_card_text = card_base_display(self.card_id)
            if gift_result.generation is not None:
                gifted_card_text = card_dupe_display(
                    self.card_id,
                    gift_result.generation,
                    dupe_code=gift_result.dupe_code,
                )

        await interaction.response.edit_message(view=self)
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed(
                    "Gift Accepted",
                    (
                        f"Recipient: <@{self.recipient_id}>\n"
                        f"Sender: <@{self.sender_id}>\n"
                        "\n"
                        f"Card: {gifted_card_text}"
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
                embed=italy_embed("Gift Expired", "Gift offer expired."),
                view=self,
            )
        except discord.HTTPException:
            logger.warning("Failed to edit gift message on timeout (message_id=%s)", self.message.id)

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
