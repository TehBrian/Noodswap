import asyncio
import time
from typing import Optional

import discord

from .cards import card_display
from .images import embed_image_payload
from .presentation import italy_embed, lootbox_result_description
from .services import execute_lootbox_claim
from .view_utils import InteractionView, logger


class LootboxClaimView(InteractionView):
    def __init__(
        self,
        guild_id: int,
        opener_user_id: int,
        card_type_id: str,
        generation: int,
        *,
        timeout_seconds: float,
    ):
        super().__init__(timeout=timeout_seconds)
        self.guild_id = guild_id
        self.opener_user_id = opener_user_id
        self.card_type_id = card_type_id
        self.generation = generation
        self.finished = False
        self.message: Optional[discord.Message] = None
        self._claim_lock = asyncio.Lock()

    @discord.ui.button(label="Claim Reward", style=discord.ButtonStyle.success, emoji="🎁")
    async def claim_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if interaction.user.id != self.opener_user_id:
            await interaction.response.send_message(
                embed=italy_embed("Lootbox", "Only the opener can claim this reward."),
                ephemeral=True,
            )
            return

        async with self._claim_lock:
            if self.finished:
                await interaction.response.send_message(
                    embed=italy_embed("Lootbox", "This lootbox has already been claimed."),
                    ephemeral=True,
                )
                return

            opened = execute_lootbox_claim(
                self.guild_id,
                self.opener_user_id,
                time.time(),
                card_type_id=self.card_type_id,
                generation=self.generation,
            )

            self.finished = True
            self._disable_buttons()

            if opened.is_error or opened.card_type_id is None or opened.generation is None:
                await interaction.response.edit_message(
                    embed=italy_embed("Lootbox", opened.error_message or "Lootbox claim failed."),
                    view=self,
                )
                return

            image_url, image_file = embed_image_payload(
                opened.card_type_id,
                generation=opened.generation,
            )
            result_embed = italy_embed(
                "Lootbox",
                lootbox_result_description(
                    card_display(opened.card_type_id, opened.generation, card_id=opened.card_id),
                    opened.remaining_keys,
                ),
            )
            if image_url is not None:
                result_embed.set_image(url=image_url)

            if image_file is not None:
                await interaction.response.edit_message(
                    embed=result_embed,
                    view=self,
                    attachments=[image_file],
                )
            else:
                await interaction.response.edit_message(
                    embed=result_embed,
                    view=self,
                )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()

        try:
            await self.message.edit(
                embed=italy_embed("Lootbox", "Lootbox expired before claim."),
                view=self,
            )
        except discord.HTTPException:
            logger.warning(
                "Failed to edit lootbox message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
