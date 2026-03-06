import asyncio
from typing import Optional

import discord

from .cards import (
    CARD_CATALOG,
    card_base_display,
    card_dupe_display,
    card_value,
    get_burn_payout,
)
from .images import embed_image_payload, morph_transition_image_payload
from .fonts import font_label
from .frames import frame_label
from .morphs import morph_label
from .presentation import italy_embed
from .presentation import help_category_content, help_category_pages, help_overview_description
from .services import (
    execute_drop_claim,
    resolve_font_roll,
    resolve_frame_roll,
    resolve_morph_roll,
    resolve_trade_offer,
)
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
    add_dough,
    burn_instance,
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


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, parent_view: "HelpView"):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=label,
                value=key,
                description=f"Show {label.lower()} commands.",
            )
            for key, label, _description in help_category_pages()
        ]
        super().__init__(placeholder="Select a command category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message(
                embed=italy_embed("Help", "Only the command user can switch help categories."),
                ephemeral=True,
            )
            return

        selected_key = self.values[0]
        self.parent_view.selected_category = selected_key
        await interaction.response.edit_message(embed=self.parent_view.build_category_embed(selected_key), view=self.parent_view)


class HelpView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.selected_category: str | None = None
        self.message: Optional[discord.Message] = None
        self.category_select = HelpCategorySelect(self)
        self.add_item(self.category_select)

    def build_overview_embed(self) -> discord.Embed:
        return italy_embed("Help", help_overview_description())

    def build_category_embed(self, category_key: str) -> discord.Embed:
        page = help_category_content(category_key)
        if page is None:
            return italy_embed("Help", "Unknown help category.")
        label, description = page
        return italy_embed(f"Help: {label}", description)

    async def on_timeout(self) -> None:
        if self.message is None:
            return

        self.category_select.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass


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

                claim_result = execute_drop_claim(
                    self.guild_id,
                    interaction.user.id,
                    card_id,
                    generation,
                    now=discord.utils.utcnow().timestamp(),
                    pull_cooldown_seconds=PULL_COOLDOWN_SECONDS,
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

            pulled_dupe_code = claim_result.dupe_code

            pulled_embed = italy_embed(
                "Pulled Card",
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
            trade_result = resolve_trade_offer(
                guild_id=self.guild_id,
                seller_id=self.seller_id,
                buyer_id=self.buyer_id,
                card_id=self.card_id,
                dupe_code=self.dupe_code,
                amount=self.amount,
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
            amount=self.amount,
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


class MorphConfirmView(discord.ui.View):
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
                embed=italy_embed("Morph", "Only the command user can confirm this morph."),
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
                    embed=italy_embed("Morph Failed", result.error_message or "Morph failed."),
                    mention_author=False,
                )
            return

        if result.morph_key is None or result.morph_name is None or result.remaining_dough is None:
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
            send_kwargs: dict[str, object] = {"embed": morph_embed, "mention_author": False}
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
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class FrameConfirmView(discord.ui.View):
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
                embed=italy_embed("Frame", "Only the command user can confirm this frame."),
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
                    embed=italy_embed("Frame Failed", result.error_message or "Frame failed."),
                    mention_author=False,
                )
            return

        if result.frame_key is None or result.frame_name is None or result.remaining_dough is None:
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
            send_kwargs: dict[str, object] = {"embed": frame_embed, "mention_author": False}
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
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class FontConfirmView(discord.ui.View):
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
                embed=italy_embed("Font", "Only the command user can confirm this font."),
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
                    embed=italy_embed("Font Failed", result.error_message or "Font failed."),
                    mention_author=False,
                )
            return

        if result.font_key is None or result.font_name is None or result.remaining_dough is None:
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
            send_kwargs: dict[str, object] = {"embed": font_embed, "mention_author": False}
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
        instance_styles: dict[int, tuple[str | None, str | None, str | None]] | None,
        guard_title: str,
        locked_instance_ids: set[int] | None = None,
        page_size: int = 10,
    ):
        super().__init__(timeout=TRADE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.title = title
        self.instances = instances
        self.locked_instance_ids = locked_instance_ids or set()
        self.wish_counts = wish_counts or {}
        self.instance_styles = instance_styles or {}
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
        if mode == "generation":
            return sorted(
                self.instances,
                key=lambda item: (
                    item[2],
                    str(CARD_CATALOG[item[1]]["name"]),
                    item[0],
                ),
            )

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

        if mode == "actual_value":
            return sorted(
                self.instances,
                key=lambda item: (
                    -card_value(item[1], item[2]),
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
            instance_id, card_id, generation, dupe_code = page_instances[0]
            lock_marker = "🔒 " if instance_id in self.locked_instance_ids else "`  ` "
            description = f"{start + 1}. {lock_marker}{card_dupe_display(card_id, generation, dupe_code=dupe_code)}"
        else:
            lines = [
                f"{idx}. {'🔒 ' if instance_id in self.locked_instance_ids else '`  ` '}"
                f"{card_dupe_display(card_id, generation, dupe_code=dupe_code)}"
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


class PlayerLeaderboardView(discord.ui.View):
    def __init__(
        self,
        *,
        user_id: int,
        title: str,
        entries: list[tuple[int, int, int, int, int, int]],
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
        self.message: Optional[discord.Message] = None
        self._sorted_entries = self._sorted_entries_for_criteria(self.criteria)
        self._set_criteria_select_defaults()
        self._refresh_button_state()

    def _metric_value(self, entry: tuple[int, int, int, int, int, int], criteria: str) -> int:
        _user_id, cards, wishes, dough, starter, total_value = entry
        metric_by_criteria = {
            "cards": cards,
            "wishes": wishes,
            "dough": dough,
            "starter": starter,
            "value": total_value,
        }
        return metric_by_criteria.get(criteria, cards)

    def _criteria_label(self, criteria: str) -> str:
        return {
            "cards": "Cards",
            "wishes": "Wishes",
            "dough": "Dough",
            "starter": "Starter",
            "value": "Collection Value",
        }.get(criteria, "Cards")

    def _sorted_entries_for_criteria(self, criteria: str) -> list[tuple[int, int, int, int, int, int]]:
        return sorted(
            self.entries,
            key=lambda entry: (
                -self._metric_value(entry, criteria),
                -entry[5],
                -entry[3],
                entry[0],
            ),
        )

    def _set_criteria_select_defaults(self) -> None:
        selected = self.criteria
        for option in self.criteria_select.options:
            option.default = option.value == selected

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
            for rank, (player_id, cards, wishes, dough, starter, total_value) in enumerate(page_entries, start=start + 1):
                value = self._metric_value((player_id, cards, wishes, dough, starter, total_value), self.criteria)
                lines.append(f"{rank}. <@{player_id}> - {criteria_label}: **{value}**")
            description = multiline_text(lines)

        embed = italy_embed(self.title, description)
        embed.set_footer(text=f"Page {self.page_index + 1}/{self.total_pages} • Ranked by {criteria_label}")
        return embed

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self.page_index = max(0, min(self.total_pages - 1, self.page_index))
        self._refresh_button_state()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _guard_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=italy_embed(self.guard_title, "Only the command user can control this leaderboard."),
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
            discord.SelectOption(label="Collection Value", value="value", description="Highest total card value"),
        ],
    )
    async def criteria_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not await self._guard_user(interaction):
            return

        self.criteria = select.values[0]
        self.page_index = 0
        self._sorted_entries = self._sorted_entries_for_criteria(self.criteria)
        self._set_criteria_select_defaults()
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
            await self.message.edit(embed=self.build_embed(), view=self)
        except discord.HTTPException:
            pass
