from typing import Optional

import discord

from .cards import card_display
from .fonts import font_label
from .frames import frame_label
from .images import morph_transition_image_payload
from .morphs import morph_label
from .presentation import italy_embed
from .services import (
    apply_pending_font_no_charge,
    apply_pending_frame_no_charge,
    apply_pending_morph_no_charge,
    execute_burn_batch_confirmation,
    execute_burn_confirmation,
    roll_font_preview_paid,
    roll_frame_preview_paid,
    roll_morph_preview_paid,
)
from .settings import BURN_CONFIRM_TIMEOUT_SECONDS, TRAIT_ROLL_TIMEOUT_SECONDS
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
    return all(getattr(result, field_name) is not None for field_name in ("card_id", "generation", "card_code", "payout", "delta"))


def _format_trait_roll_details(rolled_rarity: str, rolled_multiplier: float) -> str:
    rarity_label = rolled_rarity.replace("_", " ").title()
    return f"Trait Rarity: **{rarity_label}** (x{rolled_multiplier:.2f})"


def _trait_roll_description(
    *,
    card_line: str,
    current_label: str,
    rolled_name: str,
    rolled_rarity: str,
    rolled_multiplier: float,
    remaining_dough: int,
    cost: int,
    trait_name: str,
) -> str:
    return (
        f"{card_line}\n\n"
        f"Current {trait_name}: **{current_label}**\n"
        f"Rolled {trait_name}: **{rolled_name}**\n"
        f"{_format_trait_roll_details(rolled_rarity, rolled_multiplier)}\n"
        f"Current Balance: **{remaining_dough}** dough\n"
        f"Reroll Cost: **{cost}** dough"
    )


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
                f"""{card_display(burn_result.card_id, burn_result.generation, card_code=burn_result.card_code)}

Payout: **{burn_result.payout} dough**
    RNG: **{burn_result.delta:+}**""",
            )

            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                view=self,
            )
            if interaction.message is not None:
                await interaction.message.reply(embed=burned_embed, mention_author=False)
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
                    skipped_lines = [f"`#{instance_id}`: {_format_skip_reasons(reasons)}" for instance_id, reasons in burn_result.skipped_instances]
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
                f"{card_display(entry.card_id, entry.generation, card_code=entry.card_code)}\n"
                f"Payout: **{entry.payout} dough** | RNG: **{entry.delta:+}**"
            )

        description_blocks: list[str] = []
        if burned_lines:
            description_blocks.append("\n\n".join(burned_lines))
            description_blocks.append(f"Total Payout: **{total_payout} dough**")

        if burn_result.skipped_instances:
            skipped_lines = [f"`#{instance_id}`: {_format_skip_reasons(reasons)}" for instance_id, reasons in burn_result.skipped_instances]
            description_blocks.append("Skipped:\n" + "\n".join(skipped_lines))

        burned_embed = italy_embed(
            ("**Cards Burned**" if not burn_result.skipped_instances else "**Cards Burned (Partial)**"),
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
        card_code: str,
        before_morph_key: str | None,
        before_frame_key: str | None,
        before_font_key: str | None,
        cost: int,
    ):
        super().__init__(timeout=TRAIT_ROLL_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.card_code = card_code
        self.before_morph_key = before_morph_key
        self.before_frame_key = before_frame_key
        self.before_font_key = before_font_key
        self.cost = cost
        self.pending_morph_key: str | None = None
        self.pending_morph_name: str | None = None
        self.pending_rarity: str | None = None
        self.pending_multiplier: float | None = None
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="<:ns_no:1481805593533481093>")
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "Only the command user can cancel this morph."),
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
        await interaction.response.edit_message(
            embed=italy_embed("Morph Cancelled", "No morph was applied."),
            view=self,
            attachments=[],
        )

    @discord.ui.button(label="Roll", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def roll_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "Only the command user can roll this morph."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "This morph request is already resolved."),
                ephemeral=True,
            )
            return

        result = roll_morph_preview_paid(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            card_code=self.card_code,
            current_morph_key=self.before_morph_key,
            cost=self.cost,
        )
        if result.is_error:
            await interaction.response.send_message(
                embed=italy_embed("Morph Failed", result.error_message or "Morph failed."),
                ephemeral=True,
            )
            return

        if (
            result.morph_key is None
            or result.morph_name is None
            or result.rolled_rarity is None
            or result.rolled_multiplier is None
            or result.remaining_dough is None
        ):
            await interaction.response.send_message(
                embed=italy_embed("Morph Failed", "Morph failed."),
                ephemeral=True,
            )
            return

        self.pending_morph_key = result.morph_key
        self.pending_morph_name = result.morph_name
        self.pending_rarity = result.rolled_rarity
        self.pending_multiplier = result.rolled_multiplier
        self.apply_button.disabled = False

        morph_embed = italy_embed(
            "Morph Roll",
            _trait_roll_description(
                card_line=card_display(
                    self.card_id,
                    self.generation,
                    card_code=self.card_code,
                    morph_key=self.before_morph_key,
                    frame_key=self.before_frame_key,
                    font_key=self.before_font_key,
                ),
                current_label=morph_label(self.before_morph_key),
                rolled_name=result.morph_name,
                rolled_rarity=result.rolled_rarity,
                rolled_multiplier=result.rolled_multiplier,
                remaining_dough=result.remaining_dough,
                cost=self.cost,
                trait_name="Morph",
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=self.pending_morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=self.before_frame_key,
            before_font_key=self.before_font_key,
            after_font_key=self.before_font_key,
        )
        if image_url is not None:
            morph_embed.set_image(url=image_url)

        await interaction.response.edit_message(
            embed=morph_embed,
            view=self,
            attachments=[image_file] if image_file is not None else [],
        )

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.success, emoji="<:ns_yes:1481805623115907202>", disabled=True)
    async def apply_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "Only the command user can apply this morph."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Morph", "This morph request is already resolved."),
                ephemeral=True,
            )
            return
        if (
            self.pending_morph_key is None
            or self.pending_morph_name is None
            or self.pending_rarity is None
            or self.pending_multiplier is None
        ):
            await interaction.response.send_message(
                embed=italy_embed("Morph", "Roll at least once before applying."),
                ephemeral=True,
            )
            return

        result = apply_pending_morph_no_charge(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            card_code=self.card_code,
            morph_key=self.pending_morph_key,
            morph_name=self.pending_morph_name,
            rolled_rarity=self.pending_rarity,
            rolled_multiplier=self.pending_multiplier,
            cost=self.cost,
        )
        if result.is_error or result.remaining_dough is None:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                embed=italy_embed("Morph Failed", result.error_message or "Morph failed."),
                view=self,
                attachments=[],
            )
            return

        self.finished = True
        self._disable_buttons()

        morph_embed = italy_embed(
            "Morph Applied",
            _trait_roll_description(
                card_line=card_display(
                    self.card_id,
                    self.generation,
                    card_code=self.card_code,
                    morph_key=self.before_morph_key,
                    frame_key=self.before_frame_key,
                    font_key=self.before_font_key,
                ),
                current_label=morph_label(self.before_morph_key),
                rolled_name=self.pending_morph_name,
                rolled_rarity=self.pending_rarity,
                rolled_multiplier=self.pending_multiplier,
                remaining_dough=result.remaining_dough,
                cost=self.cost,
                trait_name="Morph",
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=self.pending_morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=self.before_frame_key,
            before_font_key=self.before_font_key,
            after_font_key=self.before_font_key,
        )
        if image_url is not None:
            morph_embed.set_image(url=image_url)

        await interaction.response.edit_message(
            embed=morph_embed,
            view=self,
            attachments=[image_file] if image_file is not None else [],
        )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(
                embed=italy_embed("Morph Expired", "Morph interaction timed out."),
                view=self,
                attachments=[],
            )
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
        card_code: str,
        before_morph_key: str | None,
        before_frame_key: str | None,
        before_font_key: str | None,
        cost: int,
    ):
        super().__init__(timeout=TRAIT_ROLL_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.card_code = card_code
        self.before_morph_key = before_morph_key
        self.before_frame_key = before_frame_key
        self.before_font_key = before_font_key
        self.cost = cost
        self.pending_frame_key: str | None = None
        self.pending_frame_name: str | None = None
        self.pending_rarity: str | None = None
        self.pending_multiplier: float | None = None
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="<:ns_no:1481805593533481093>")
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "Only the command user can cancel this frame."),
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
        await interaction.response.edit_message(
            embed=italy_embed("Frame Cancelled", "No frame was applied."),
            view=self,
            attachments=[],
        )

    @discord.ui.button(label="Roll", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def roll_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "Only the command user can roll this frame."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "This frame request is already resolved."),
                ephemeral=True,
            )
            return

        result = roll_frame_preview_paid(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            card_code=self.card_code,
            current_frame_key=self.before_frame_key,
            cost=self.cost,
        )
        if result.is_error:
            await interaction.response.send_message(
                embed=italy_embed("Frame Failed", result.error_message or "Frame failed."),
                ephemeral=True,
            )
            return

        if (
            result.frame_key is None
            or result.frame_name is None
            or result.rolled_rarity is None
            or result.rolled_multiplier is None
            or result.remaining_dough is None
        ):
            await interaction.response.send_message(
                embed=italy_embed("Frame Failed", "Frame failed."),
                ephemeral=True,
            )
            return

        self.pending_frame_key = result.frame_key
        self.pending_frame_name = result.frame_name
        self.pending_rarity = result.rolled_rarity
        self.pending_multiplier = result.rolled_multiplier
        self.apply_button.disabled = False

        frame_embed = italy_embed(
            "Frame Roll",
            _trait_roll_description(
                card_line=card_display(
                    self.card_id,
                    self.generation,
                    card_code=self.card_code,
                    morph_key=self.before_morph_key,
                    frame_key=self.before_frame_key,
                    font_key=self.before_font_key,
                ),
                current_label=frame_label(self.before_frame_key),
                rolled_name=result.frame_name,
                rolled_rarity=result.rolled_rarity,
                rolled_multiplier=result.rolled_multiplier,
                remaining_dough=result.remaining_dough,
                cost=self.cost,
                trait_name="Frame",
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=self.before_morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=self.pending_frame_key,
            before_font_key=self.before_font_key,
            after_font_key=self.before_font_key,
        )
        if image_url is not None:
            frame_embed.set_image(url=image_url)

        await interaction.response.edit_message(
            embed=frame_embed,
            view=self,
            attachments=[image_file] if image_file is not None else [],
        )

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.success, emoji="<:ns_yes:1481805623115907202>", disabled=True)
    async def apply_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "Only the command user can apply this frame."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Frame", "This frame request is already resolved."),
                ephemeral=True,
            )
            return
        if (
            self.pending_frame_key is None
            or self.pending_frame_name is None
            or self.pending_rarity is None
            or self.pending_multiplier is None
        ):
            await interaction.response.send_message(
                embed=italy_embed("Frame", "Roll at least once before applying."),
                ephemeral=True,
            )
            return

        result = apply_pending_frame_no_charge(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            card_code=self.card_code,
            frame_key=self.pending_frame_key,
            frame_name=self.pending_frame_name,
            rolled_rarity=self.pending_rarity,
            rolled_multiplier=self.pending_multiplier,
            cost=self.cost,
        )
        if result.is_error or result.remaining_dough is None:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                embed=italy_embed("Frame Failed", result.error_message or "Frame failed."),
                view=self,
                attachments=[],
            )
            return

        self.finished = True
        self._disable_buttons()

        frame_embed = italy_embed(
            "Frame Applied",
            _trait_roll_description(
                card_line=card_display(
                    self.card_id,
                    self.generation,
                    card_code=self.card_code,
                    morph_key=self.before_morph_key,
                    frame_key=self.before_frame_key,
                    font_key=self.before_font_key,
                ),
                current_label=frame_label(self.before_frame_key),
                rolled_name=self.pending_frame_name,
                rolled_rarity=self.pending_rarity,
                rolled_multiplier=self.pending_multiplier,
                remaining_dough=result.remaining_dough,
                cost=self.cost,
                trait_name="Frame",
            ),
        )
        image_url, image_file = morph_transition_image_payload(
            self.card_id,
            generation=self.generation,
            before_morph_key=self.before_morph_key,
            after_morph_key=self.before_morph_key,
            before_frame_key=self.before_frame_key,
            after_frame_key=self.pending_frame_key,
            before_font_key=self.before_font_key,
            after_font_key=self.before_font_key,
        )
        if image_url is not None:
            frame_embed.set_image(url=image_url)

        await interaction.response.edit_message(
            embed=frame_embed,
            view=self,
            attachments=[image_file] if image_file is not None else [],
        )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(
                embed=italy_embed("Frame Expired", "Frame interaction timed out."),
                view=self,
                attachments=[],
            )
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
        card_code: str,
        before_morph_key: str | None,
        before_frame_key: str | None,
        before_font_key: str | None,
        cost: int,
    ):
        super().__init__(timeout=TRAIT_ROLL_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.user_id = user_id
        self.instance_id = instance_id
        self.card_id = card_id
        self.generation = generation
        self.card_code = card_code
        self.before_morph_key = before_morph_key
        self.before_frame_key = before_frame_key
        self.before_font_key = before_font_key
        self.cost = cost
        self.pending_font_key: str | None = None
        self.pending_font_name: str | None = None
        self.pending_rarity: str | None = None
        self.pending_multiplier: float | None = None
        self.finished = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="<:ns_no:1481805593533481093>")
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Font", "Only the command user can cancel this font."),
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
        await interaction.response.edit_message(
            embed=italy_embed("Font Cancelled", "No font was applied."),
            view=self,
            attachments=[],
        )

    @discord.ui.button(label="Roll", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def roll_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Font", "Only the command user can roll this font."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Font", "This font request is already resolved."),
                ephemeral=True,
            )
            return

        result = roll_font_preview_paid(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            card_code=self.card_code,
            current_font_key=self.before_font_key,
            cost=self.cost,
        )
        if result.is_error:
            await interaction.response.send_message(
                embed=italy_embed("Font Failed", result.error_message or "Font failed."),
                ephemeral=True,
            )
            return

        if (
            result.font_key is None
            or result.font_name is None
            or result.rolled_rarity is None
            or result.rolled_multiplier is None
            or result.remaining_dough is None
        ):
            await interaction.response.send_message(
                embed=italy_embed("Font Failed", "Font failed."),
                ephemeral=True,
            )
            return

        self.pending_font_key = result.font_key
        self.pending_font_name = result.font_name
        self.pending_rarity = result.rolled_rarity
        self.pending_multiplier = result.rolled_multiplier
        self.apply_button.disabled = False

        font_embed = italy_embed(
            "Font Roll",
            _trait_roll_description(
                card_line=card_display(
                    self.card_id,
                    self.generation,
                    card_code=self.card_code,
                    morph_key=self.before_morph_key,
                    frame_key=self.before_frame_key,
                    font_key=self.before_font_key,
                ),
                current_label=font_label(self.before_font_key),
                rolled_name=result.font_name,
                rolled_rarity=result.rolled_rarity,
                rolled_multiplier=result.rolled_multiplier,
                remaining_dough=result.remaining_dough,
                cost=self.cost,
                trait_name="Font",
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
            after_font_key=self.pending_font_key,
        )
        if image_url is not None:
            font_embed.set_image(url=image_url)

        await interaction.response.edit_message(
            embed=font_embed,
            view=self,
            attachments=[image_file] if image_file is not None else [],
        )

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.success, emoji="<:ns_yes:1481805623115907202>", disabled=True)
    async def apply_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Font", "Only the command user can apply this font."),
                ephemeral=True,
            )
            return
        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Font", "This font request is already resolved."),
                ephemeral=True,
            )
            return
        if (
            self.pending_font_key is None
            or self.pending_font_name is None
            or self.pending_rarity is None
            or self.pending_multiplier is None
        ):
            await interaction.response.send_message(
                embed=italy_embed("Font", "Roll at least once before applying."),
                ephemeral=True,
            )
            return

        result = apply_pending_font_no_charge(
            self.guild_id,
            self.user_id,
            instance_id=self.instance_id,
            card_id=self.card_id,
            generation=self.generation,
            card_code=self.card_code,
            font_key=self.pending_font_key,
            font_name=self.pending_font_name,
            rolled_rarity=self.pending_rarity,
            rolled_multiplier=self.pending_multiplier,
            cost=self.cost,
        )
        if result.is_error or result.remaining_dough is None:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                embed=italy_embed("Font Failed", result.error_message or "Font failed."),
                view=self,
                attachments=[],
            )
            return

        self.finished = True
        self._disable_buttons()

        font_embed = italy_embed(
            "Font Applied",
            _trait_roll_description(
                card_line=card_display(
                    self.card_id,
                    self.generation,
                    card_code=self.card_code,
                    morph_key=self.before_morph_key,
                    frame_key=self.before_frame_key,
                    font_key=self.before_font_key,
                ),
                current_label=font_label(self.before_font_key),
                rolled_name=self.pending_font_name,
                rolled_rarity=self.pending_rarity,
                rolled_multiplier=self.pending_multiplier,
                remaining_dough=result.remaining_dough,
                cost=self.cost,
                trait_name="Font",
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
            after_font_key=self.pending_font_key,
        )
        if image_url is not None:
            font_embed.set_image(url=image_url)

        await interaction.response.edit_message(
            embed=font_embed,
            view=self,
            attachments=[image_file] if image_file is not None else [],
        )

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()
        try:
            await self.message.edit(
                embed=italy_embed("Font Expired", "Font interaction timed out."),
                view=self,
                attachments=[],
            )
        except discord.HTTPException:
            logger.warning(
                "Failed to edit font confirmation message on timeout (message_id=%s)",
                self.message.id,
            )

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
