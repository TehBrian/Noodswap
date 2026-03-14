import asyncio
from typing import Optional

import discord

from .cards import CARD_CATALOG, card_display
from .command_gate import command_execution_gate
from .images import embed_image_payload
from .presentation import italy_embed
from .services import execute_drop_claim
from .settings import DROP_TIMEOUT_SECONDS, PULL_COOLDOWN_SECONDS
from .view_utils import InteractionView, logger


class DropView(InteractionView):
    def __init__(self, guild_id: int, user_id: int, choices: list[tuple[str, int]]):
        super().__init__(timeout=DROP_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.choices = choices
        self.finished = False
        self.message: Optional[discord.Message] = None
        self._claim_lock = asyncio.Lock()
        self._claimed_button_ids: set[str] = set()

        for index, (card_type_id, generation) in enumerate(choices):
            card_name = CARD_CATALOG[card_type_id]["name"]
            button_id = f"drop:{index}"
            button = discord.ui.Button(
                label=f"Pull {card_name}",
                style=discord.ButtonStyle.primary,
                custom_id=button_id,
            )
            button.callback = self._make_pull_callback(card_type_id, generation, button_id)
            self.add_item(button)

    def _make_pull_callback(self, card_type_id: str, generation: int, button_id: str):
        async def callback(interaction: discord.Interaction):
            if self.finished:
                await interaction.response.send_message(
                    embed=italy_embed("Drop", "This drop is already resolved."),
                    ephemeral=True,
                )
                return

            async with command_execution_gate(interaction.user.id, "pull") as entered:
                if not entered:
                    await interaction.response.send_message(
                        embed=italy_embed("Drop", "A pull is already in progress."),
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

                    claim_result = execute_drop_claim(
                        self.guild_id,
                        interaction.user.id,
                        card_type_id,
                        generation,
                        now=discord.utils.utcnow().timestamp(),
                        pull_cooldown_seconds=PULL_COOLDOWN_SECONDS,
                        dropped_by_user_id=self.user_id,
                    )
                    if claim_result.is_error:
                        cooldown_remaining = claim_result.cooldown_remaining_seconds or 0.0
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
                        (item for item in self.children if isinstance(item, discord.ui.Button) and item.custom_id == button_id),
                        None,
                    )
                    if claimed_button is not None:
                        claimed_button.disabled = True

                    if all(isinstance(item, discord.ui.Button) and item.disabled for item in self.children):
                        self.finished = True

                pulled_card_id = claim_result.card_id

                pulled_embed = italy_embed(
                    "Pulled Card",
                    (f"<@{interaction.user.id}> pulled {card_display(card_type_id, generation, card_id=pulled_card_id, pad_card_id=False)}."),
                )
                image_url, image_file = embed_image_payload(card_type_id, generation=generation)
                if image_url is not None:
                    pulled_embed.set_thumbnail(url=image_url)

                await interaction.response.edit_message(
                    content=None,
                    view=self,
                )
                if interaction.message is not None:
                    send_kwargs: dict[str, object] = {
                        "embed": pulled_embed,
                        "mention_author": True,
                    }
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
            logger.warning(
                "Failed to edit drop message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
