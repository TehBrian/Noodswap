from typing import Optional

import discord

from .cards import card_dupe_display
from .fonts import font_label
from .frames import frame_label
from .images import morph_transition_image_payload
from .morphs import morph_label
from .presentation import italy_embed
from .services import (
    execute_burn_batch_confirmation,
    execute_burn_confirmation,
    resolve_font_roll,
    resolve_frame_roll,
    resolve_morph_roll,
)
from .settings import BURN_CONFIRM_TIMEOUT_SECONDS
from .view_utils import InteractionView, logger


def _format_lock_reason(reason: str) -> str:
    if reason.startswith("folder:"):
        return f"folder `{reason.removeprefix('folder:')}`"
    return f"tag `{reason}`"


def _format_lock_reasons(reasons: tuple[str, ...] | list[str]) -> str:
    if not reasons:
        return "lock(s)"
    return ", ".join(_format_lock_reason(reason) for reason in reasons)


def _format_skip_reasons(reasons: tuple[str, ...] | list[str]) -> str:
    if not reasons:
        return "unknown reason"
    formatted: list[str] = []
    for reason in reasons:
        if reason == "unavailable":
            formatted.append("no longer available")
            continue
        formatted.append(_format_lock_reason(reason))
    return ", ".join(formatted)


def _burn_result_has_required_fields(result: object) -> bool:
    return all(
        getattr(result, field_name) is not None
        for field_name in ("card_id", "generation", "dupe_code", "payout", "delta")
    )


def _format_trait_roll_details(rolled_rarity: str, rolled_multiplier: float) -> str:
    rarity_label = rolled_rarity.replace("_", " ").title()
    return f"Trait Rarity: **{rarity_label}** (x{rolled_multiplier:.2f})"


class BurnConfirmView(InteractionView):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        instance_id: int,
        card_id: str,
        generation: int,
        delta_range: int,
        burn_items: list[tuple[int, int]] | None = None,
    ):
        super().__init__(timeout=BURN_CONFIRM_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.delta_range = delta_range
        if burn_items is None:
            self.burn_items = [(instance_id, delta_range)]
        else:
            self.burn_items = burn_items
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
                embed=italy_embed(
                    "Burn", "Only the command user can confirm this burn."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Burn", "This burn request is already resolved."),
                ephemeral=True,
            )
            return

        if len(self.burn_items) <= 1:
            burn_result = execute_burn_confirmation(
                self.guild_id,
                self.user_id,
                instance_id=self.instance_id,
                delta_range=self.delta_range,
            )
            if burn_result.is_blocked:
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(view=self)
                if interaction.message is not None:
                    lock_reason_text = _format_lock_reasons(burn_result.locked_tags)
                    await interaction.message.reply(
                        embed=italy_embed(
                            "Burn Blocked",
                            f"This card is protected by {lock_reason_text}.",
                        ),
                        mention_author=False,
                    )
                return

            if burn_result.is_failed:
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(
                    view=self,
                )
                if interaction.message is not None:
                    await interaction.message.reply(
                        embed=italy_embed("Burn Failed", burn_result.message),
                        mention_author=False,
                    )
                return

            if not _burn_result_has_required_fields(burn_result):
                self.finished = True
                self._disable_buttons()
                await interaction.response.edit_message(view=self)
                if interaction.message is not None:
                    await interaction.message.reply(
                        embed=italy_embed("Burn Failed", "Burn failed."),
                        mention_author=False,
                    )
                return

            burned_embed = italy_embed(
                "**Card Burned**",
                f"""{card_dupe_display(burn_result.card_id, burn_result.generation, dupe_code=burn_result.dupe_code)}

Payout: **{burn_result.payout} dough**
    RNG: **{burn_result.delta:+}**""",
            )

            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                view=self,
            )
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=burned_embed, mention_author=False
                )
            return

        burn_result = execute_burn_batch_confirmation(
            self.guild_id,
            self.user_id,
            burn_targets=self.burn_items,
        )
        if burn_result.is_failed:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                view=self,
            )
            if interaction.message is not None:
                if burn_result.skipped_instances:
                    skipped_lines = [
                        f"`#{instance_id}`: {_format_skip_reasons(reasons)}"
                        for instance_id, reasons in burn_result.skipped_instances
                    ]
                    await interaction.message.reply(
                        embed=italy_embed("Burn Failed", "\n".join(skipped_lines)),
                        mention_author=False,
                    )
                    return
                await interaction.message.reply(
                    embed=italy_embed("Burn Failed", burn_result.message),
                    mention_author=False,
                )
            return

        burned_lines: list[str] = []
        total_payout = 0
        for entry in burn_result.burned_entries:
            total_payout += entry.payout
            burned_lines.append(
                f"{card_dupe_display(entry.card_id, entry.generation, dupe_code=entry.dupe_code)}\n"
                f"Payout: **{entry.payout} dough** | RNG: **{entry.delta:+}**"
            )

        description_blocks: list[str] = []
        if burned_lines:
            description_blocks.append("\n\n".join(burned_lines))
            description_blocks.append(f"Total Payout: **{total_payout} dough**")

        if burn_result.skipped_instances:
            skipped_lines = [
                f"`#{instance_id}`: {_format_skip_reasons(reasons)}"
                for instance_id, reasons in burn_result.skipped_instances
            ]
            description_blocks.append("Skipped:\n" + "\n".join(skipped_lines))

        burned_embed = italy_embed(
            (
                "**Cards Burned**"
                if not burn_result.skipped_instances
                else "**Cards Burned (Partial)**"
            ),
            "\n\n".join(description_blocks),
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
                embed=italy_embed(
                    "Burn", "Only the command user can cancel this burn."
                ),
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
            logger.warning(
                "Failed to edit burn confirmation message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class MorphConfirmView(InteractionView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        instance_id: int,
        card_id: str,
        generation: int,
        dupe_code: str,
        before_morph_key: str | None,
        before_frame_key: str | None,
        before_font_key: str | None,
        cost: int,
    ):
        super().__init__(timeout=BURN_CONFIRM_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.dupe_code = dupe_code
        self.before_morph_key = before_morph_key
        self.before_frame_key = before_frame_key
        self.before_font_key = before_font_key
        self.cost = cost
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Confirm Morph", style=discord.ButtonStyle.success)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Morph", "Only the command user can confirm this morph."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "This morph request is already resolved."),
                ephemeral=True,
            )
            return

        result = resolve_morph_roll(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            dupe_code=self.dupe_code,
            current_morph_key=self.before_morph_key,
            cost=self.cost,
        )
        if result.is_error:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed(
                        "Morph Failed", result.error_message or "Morph failed."
                    ),
                    mention_author=False,
                )
            return

        if (
            result.morph_key is None
            or result.morph_name is None
            or result.rolled_rarity is None
            or result.rolled_multiplier is None
            or result.remaining_dough is None
        ):
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed("Morph Failed", "Morph failed."),
                    mention_author=False,
                )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(view=self)

        morph_embed = italy_embed(
            "Morph Rolled",
            (
                f"Rolled **{result.morph_name}** for "
                f"{card_dupe_display(self.card_id, self.generation, dupe_code=self.dupe_code)}.\n\n"
                f"Before: **{morph_label(self.before_morph_key)}**\n"
                f"After: **{result.morph_name}**\n\n"
                f"{_format_trait_roll_details(result.rolled_rarity, result.rolled_multiplier)}\n"
                f"Morph Cost: **{self.cost}** dough\n"
                f"Dough Remaining: **{result.remaining_dough}**"
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=result.morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=self.before_frame_key,
            before_font_key=self.before_font_key,
            after_font_key=self.before_font_key,
        )
        if image_url is not None:
            morph_embed.set_image(url=image_url)

        if interaction.message is not None:
            send_kwargs: dict[str, object] = {
                "embed": morph_embed,
                "mention_author": False,
            }
            if image_file is not None:
                send_kwargs["file"] = image_file
            await interaction.message.reply(**send_kwargs)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Morph", "Only the command user can cancel this morph."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "This morph request is already resolved."),
                ephemeral=True,
            )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(view=self)
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed("Morph Cancelled", "No morph was applied."),
                mention_author=False,
            )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            logger.warning(
                "Failed to edit morph confirmation message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class FrameConfirmView(InteractionView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        instance_id: int,
        card_id: str,
        generation: int,
        dupe_code: str,
        before_morph_key: str | None,
        before_frame_key: str | None,
        before_font_key: str | None,
        cost: int,
    ):
        super().__init__(timeout=BURN_CONFIRM_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.dupe_code = dupe_code
        self.before_morph_key = before_morph_key
        self.before_frame_key = before_frame_key
        self.before_font_key = before_font_key
        self.cost = cost
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Confirm Frame", style=discord.ButtonStyle.success)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Frame", "Only the command user can confirm this frame."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "This frame request is already resolved."),
                ephemeral=True,
            )
            return

        result = resolve_frame_roll(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            dupe_code=self.dupe_code,
            current_frame_key=self.before_frame_key,
            cost=self.cost,
        )
        if result.is_error:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed(
                        "Frame Failed", result.error_message or "Frame failed."
                    ),
                    mention_author=False,
                )
            return

        if (
            result.frame_key is None
            or result.frame_name is None
            or result.rolled_rarity is None
            or result.rolled_multiplier is None
            or result.remaining_dough is None
        ):
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed("Frame Failed", "Frame failed."),
                    mention_author=False,
                )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(view=self)

        frame_embed = italy_embed(
            "Frame Rolled",
            (
                f"Rolled **{result.frame_name}** for "
                f"{card_dupe_display(self.card_id, self.generation, dupe_code=self.dupe_code)}.\n\n"
                f"Before: **{frame_label(self.before_frame_key)}**\n"
                f"After: **{result.frame_name}**\n\n"
                f"{_format_trait_roll_details(result.rolled_rarity, result.rolled_multiplier)}\n"
                f"Frame Cost: **{self.cost}** dough\n"
                f"Dough Remaining: **{result.remaining_dough}**"
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=self.before_morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=result.frame_key,
            before_font_key=self.before_font_key,
            after_font_key=self.before_font_key,
        )
        if image_url is not None:
            frame_embed.set_image(url=image_url)

        if interaction.message is not None:
            send_kwargs: dict[str, object] = {
                "embed": frame_embed,
                "mention_author": False,
            }
            if image_file is not None:
                send_kwargs["file"] = image_file
            await interaction.message.reply(**send_kwargs)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Frame", "Only the command user can cancel this frame."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "This frame request is already resolved."),
                ephemeral=True,
            )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(view=self)
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed("Frame Cancelled", "No frame was applied."),
                mention_author=False,
            )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            logger.warning(
                "Failed to edit frame confirmation message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class FontConfirmView(InteractionView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        instance_id: int,
        card_id: str,
        generation: int,
        dupe_code: str,
        before_morph_key: str | None,
        before_frame_key: str | None,
        before_font_key: str | None,
        cost: int,
    ):
        super().__init__(timeout=BURN_CONFIRM_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.dupe_code = dupe_code
        self.before_morph_key = before_morph_key
        self.before_frame_key = before_frame_key
        self.before_font_key = before_font_key
        self.cost = cost
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Confirm Font", style=discord.ButtonStyle.success)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Font", "Only the command user can confirm this font."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Font", "This font request is already resolved."),
                ephemeral=True,
            )
            return

        result = resolve_font_roll(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            dupe_code=self.dupe_code,
            current_font_key=self.before_font_key,
            cost=self.cost,
        )
        if result.is_error:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed(
                        "Font Failed", result.error_message or "Font failed."
                    ),
                    mention_author=False,
                )
            return

        if (
            result.font_key is None
            or result.font_name is None
            or result.rolled_rarity is None
            or result.rolled_multiplier is None
            or result.remaining_dough is None
        ):
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(view=self)
            if interaction.message is not None:
                await interaction.message.reply(
                    embed=italy_embed("Font Failed", "Font failed."),
                    mention_author=False,
                )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(view=self)

        font_embed = italy_embed(
            "Font Rolled",
            (
                f"Rolled **{result.font_name}** for "
                f"{card_dupe_display(self.card_id, self.generation, dupe_code=self.dupe_code)}.\n\n"
                f"Before: **{font_label(self.before_font_key)}**\n"
                f"After: **{result.font_name}**\n\n"
                f"{_format_trait_roll_details(result.rolled_rarity, result.rolled_multiplier)}\n"
                f"Font Cost: **{self.cost}** dough\n"
                f"Dough Remaining: **{result.remaining_dough}**"
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=self.before_morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=self.before_frame_key,
            before_font_key=self.before_font_key,
            after_font_key=result.font_key,
        )
        if image_url is not None:
            font_embed.set_image(url=image_url)

        if interaction.message is not None:
            send_kwargs: dict[str, object] = {
                "embed": font_embed,
                "mention_author": False,
            }
            if image_file is not None:
                send_kwargs["file"] = image_file
            await interaction.message.reply(**send_kwargs)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Font", "Only the command user can cancel this font."
                ),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Font", "This font request is already resolved."),
                ephemeral=True,
            )
            return

        self.finished = True
        self._disable_buttons()
        await interaction.response.edit_message(view=self)
        if interaction.message is not None:
            await interaction.message.reply(
                embed=italy_embed("Font Cancelled", "No font was applied."),
                mention_author=False,
            )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            logger.warning(
                "Failed to edit font confirmation message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
