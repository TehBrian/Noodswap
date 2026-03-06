from dataclasses import dataclass
import math
import random
from typing import Optional

from .cards import card_value, get_burn_payout, make_drop_choices, split_card_code
from .fonts import AVAILABLE_FONTS, FONT_COST_FRACTION, font_label
from .frames import FRAME_COST_FRACTION, available_frame_keys, frame_label
from .morphs import AVAILABLE_MORPHS, MORPH_COST_FRACTION, morph_label
from .settings import DROP_CHOICES_COUNT, DROP_COOLDOWN_SECONDS
from .storage import (
    add_card_to_player,
    apply_font_to_instance,
    apply_frame_to_instance,
    apply_morph_to_instance,
    consume_pull_cooldown_if_ready,
    divorce_card,
    execute_trade,
    get_instance_by_id,
    get_instance_font,
    get_instance_frame,
    get_locked_tags_for_instance,
    get_player_cooldown_timestamps,
    get_instance_morph,
    get_instance_by_code,
    get_last_pulled_instance,
    get_player_stats,
    marry_card_instance,
    set_last_drop_at,
)


@dataclass(frozen=True)
class DropPreparation:
    choices: list[tuple[str, int]]
    cooldown_remaining_seconds: float

    @property
    def is_cooldown(self) -> bool:
        return self.cooldown_remaining_seconds > 0


def prepare_drop(guild_id: int, user_id: int, now: float) -> DropPreparation:
    last_drop_at, _ = get_player_cooldown_timestamps(guild_id, user_id)
    elapsed = now - last_drop_at

    if elapsed < DROP_COOLDOWN_SECONDS:
        return DropPreparation(
            choices=[],
            cooldown_remaining_seconds=DROP_COOLDOWN_SECONDS - elapsed,
        )

    choices = make_drop_choices(DROP_CHOICES_COUNT)
    set_last_drop_at(guild_id, user_id, now)
    return DropPreparation(choices=choices, cooldown_remaining_seconds=0.0)


@dataclass(frozen=True)
class DropClaimExecution:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    cooldown_remaining_seconds: Optional[float]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def execute_drop_claim(
    guild_id: int,
    user_id: int,
    card_id: str,
    generation: int,
    *,
    now: float,
    pull_cooldown_seconds: float,
) -> DropClaimExecution:
    cooldown_remaining = consume_pull_cooldown_if_ready(
        guild_id,
        user_id,
        now,
        pull_cooldown_seconds,
    )
    if cooldown_remaining > 0:
        return DropClaimExecution(
            error_message="Pull cooldown active.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            cooldown_remaining_seconds=cooldown_remaining,
        )

    instance_id = add_card_to_player(guild_id, user_id, card_id, generation)
    persisted = get_instance_by_id(guild_id, instance_id)
    resolved_dupe_code: Optional[str] = None
    if persisted is not None:
        _, _, _, resolved_dupe_code = persisted

    return DropClaimExecution(
        error_message=None,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=resolved_dupe_code,
        cooldown_remaining_seconds=0.0,
    )


@dataclass(frozen=True)
class TradeResolution:
    status: str
    message: str
    generation: Optional[int]
    dupe_code: Optional[str]

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def is_denied(self) -> bool:
        return self.status == "denied"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"


def resolve_trade_offer(
    guild_id: int,
    seller_id: int,
    buyer_id: int,
    card_id: str,
    dupe_code: str,
    amount: int,
    *,
    accepted: bool,
) -> TradeResolution:
    if not accepted:
        return TradeResolution(
            status="denied",
            message="The trade was denied.",
            generation=None,
            dupe_code=None,
        )

    success, message, generation, received_dupe_code = execute_trade(
        guild_id=guild_id,
        seller_id=seller_id,
        buyer_id=buyer_id,
        card_id=card_id,
        dupe_code=dupe_code,
        amount=amount,
    )
    if not success:
        return TradeResolution(
            status="failed",
            message=message,
            generation=None,
            dupe_code=None,
        )

    return TradeResolution(
        status="accepted",
        message="",
        generation=generation,
        dupe_code=received_dupe_code,
    )


@dataclass(frozen=True)
class BurnPreparation:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    payout: Optional[int]
    value: Optional[int]
    base_value: Optional[int]
    delta: Optional[int]
    delta_range: Optional[int]
    multiplier: Optional[float]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def prepare_burn(guild_id: int, user_id: int, card_code: Optional[str]) -> BurnPreparation:
    target_instance: Optional[tuple[int, str, int, str]] = None

    if card_code is None:
        target_instance = get_last_pulled_instance(guild_id, user_id)
        if target_instance is None:
            return BurnPreparation(
                error_message="No previous pulled card found. Provide a card code, e.g. `ns burn 0`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                payout=None,
                value=None,
                base_value=None,
                delta=None,
                delta_range=None,
                multiplier=None,
            )
    else:
        parsed = split_card_code(card_code)
        if parsed is None:
            return BurnPreparation(
                error_message="Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                payout=None,
                value=None,
                base_value=None,
                delta=None,
                delta_range=None,
                multiplier=None,
            )

        target_instance = get_instance_by_code(guild_id, user_id, card_code)
        if target_instance is None:
            return BurnPreparation(
                error_message="You do not own that card code.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                payout=None,
                value=None,
                base_value=None,
                delta=None,
                delta_range=None,
                multiplier=None,
            )

    instance_id, burn_card_id, burn_generation, burn_dupe_code = target_instance
    locked_tags = get_locked_tags_for_instance(guild_id, user_id, instance_id)
    if locked_tags:
        locked_tags_text = ", ".join(f"`{tag}`" for tag in locked_tags)
        return BurnPreparation(
            error_message=f"That card is protected by locked tag(s): {locked_tags_text}.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            payout=None,
            value=None,
            base_value=None,
            delta=None,
            delta_range=None,
            multiplier=None,
        )

    payout, value, base_value, delta, multiplier, delta_range = get_burn_payout(burn_card_id, burn_generation)
    return BurnPreparation(
        error_message=None,
        instance_id=instance_id,
        card_id=burn_card_id,
        generation=burn_generation,
        dupe_code=burn_dupe_code,
        payout=payout,
        value=value,
        base_value=base_value,
        delta=delta,
        delta_range=delta_range,
        multiplier=multiplier,
    )


@dataclass(frozen=True)
class MarryExecution:
    error_message: Optional[str]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def execute_marry(guild_id: int, user_id: int, card_code: Optional[str]) -> MarryExecution:
    if card_code is None:
        last_pulled = get_last_pulled_instance(guild_id, user_id)
        if last_pulled is None:
            return MarryExecution(
                error_message="No previous pulled card found. Use `ns marry <card_code>` or pull from `ns drop` first.",
                card_id=None,
                generation=None,
                dupe_code=None,
            )

        instance_id, _, _, _ = last_pulled
        success, message, married_card_id, married_generation, married_dupe_code = marry_card_instance(
            guild_id,
            user_id,
            instance_id,
        )
        if not success or married_card_id is None or married_generation is None or married_dupe_code is None:
            return MarryExecution(error_message=message or "Marry failed.", card_id=None, generation=None, dupe_code=None)

        return MarryExecution(error_message=None, card_id=married_card_id, generation=married_generation, dupe_code=married_dupe_code)

    selected = get_instance_by_code(guild_id, user_id, card_code)
    if selected is None:
        return MarryExecution(
            error_message="You can only marry a card code you own.",
            card_id=None,
            generation=None,
            dupe_code=None,
        )

    instance_id, _, _, _ = selected
    success, message, married_card_id, married_generation, married_dupe_code = marry_card_instance(guild_id, user_id, instance_id)
    if not success or married_card_id is None or married_generation is None or married_dupe_code is None:
        return MarryExecution(error_message=message or "Marry failed.", card_id=None, generation=None, dupe_code=None)

    return MarryExecution(error_message=None, card_id=married_card_id, generation=married_generation, dupe_code=married_dupe_code)


@dataclass(frozen=True)
class DivorceExecution:
    error_message: Optional[str]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def execute_divorce(guild_id: int, user_id: int) -> DivorceExecution:
    divorced = divorce_card(guild_id, user_id)
    if divorced is None:
        return DivorceExecution(
            error_message="You are not married right now.",
            card_id=None,
            generation=None,
            dupe_code=None,
        )

    old_card_id, old_generation, old_dupe_code = divorced
    return DivorceExecution(error_message=None, card_id=old_card_id, generation=old_generation, dupe_code=old_dupe_code)


@dataclass(frozen=True)
class MorphExecution:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    morph_key: Optional[str]
    morph_name: Optional[str]
    cost: Optional[int]
    remaining_dough: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


@dataclass(frozen=True)
class MorphPreparation:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    current_morph_key: Optional[str]
    morph_key: Optional[str]
    morph_name: Optional[str]
    cost: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def prepare_morph(guild_id: int, user_id: int, card_code: Optional[str]) -> MorphPreparation:
    target_instance: Optional[tuple[int, str, int, str]] = None

    if card_code is None:
        target_instance = get_last_pulled_instance(guild_id, user_id)
        if target_instance is None:
            return MorphPreparation(
                error_message="No previous pulled card found. Provide a card code, e.g. `ns morph 0`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_morph_key=None,
                morph_key=None,
                morph_name=None,
                cost=None,
            )
    else:
        parsed = split_card_code(card_code)
        if parsed is None:
            return MorphPreparation(
                error_message="Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_morph_key=None,
                morph_key=None,
                morph_name=None,
                cost=None,
            )

        target_instance = get_instance_by_code(guild_id, user_id, card_code)
        if target_instance is None:
            return MorphPreparation(
                error_message="You do not own that card code.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_morph_key=None,
                morph_key=None,
                morph_name=None,
                cost=None,
            )

    if not AVAILABLE_MORPHS:
        return MorphPreparation(
            error_message="No morphs are currently available.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_morph_key=None,
            morph_key=None,
            morph_name=None,
            cost=None,
        )

    instance_id, morph_card_id, morph_generation, morph_dupe_code = target_instance
    current_morph_key = get_instance_morph(guild_id, instance_id)
    available_rolls = [morph_key for morph_key in AVAILABLE_MORPHS if morph_key != current_morph_key]
    if not available_rolls:
        return MorphPreparation(
            error_message="No new morphs are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_morph_key=None,
            morph_key=None,
            morph_name=None,
            cost=None,
        )

    value = card_value(morph_card_id, morph_generation)
    cost = max(1, int(math.ceil(value * MORPH_COST_FRACTION)))
    dough_before, _, _ = get_player_stats(guild_id, user_id)
    if dough_before < cost:
        return MorphPreparation(
            error_message="You do not have enough dough.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_morph_key=None,
            morph_key=None,
            morph_name=None,
            cost=None,
        )

    return MorphPreparation(
        error_message=None,
        instance_id=instance_id,
        card_id=morph_card_id,
        generation=morph_generation,
        dupe_code=morph_dupe_code,
        current_morph_key=current_morph_key,
        morph_key=None,
        morph_name=None,
        cost=cost,
    )


def confirm_morph(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    card_id: str,
    generation: int,
    dupe_code: str,
    morph_key: str,
    morph_name: str,
    cost: int,
) -> MorphExecution:
    applied, message = apply_morph_to_instance(guild_id, user_id, instance_id, morph_key, cost)
    if not applied:
        return MorphExecution(
            error_message=message or "Morph failed.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            morph_key=None,
            morph_name=None,
            cost=None,
            remaining_dough=None,
        )

    dough_after, _, _ = get_player_stats(guild_id, user_id)
    return MorphExecution(
        error_message=None,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        morph_key=morph_key,
        morph_name=morph_name,
        cost=cost,
        remaining_dough=dough_after,
    )


def execute_morph(guild_id: int, user_id: int, card_code: Optional[str]) -> MorphExecution:
    prepared = prepare_morph(guild_id, user_id, card_code)
    if prepared.is_error:
        return MorphExecution(
            error_message=prepared.error_message,
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            morph_key=None,
            morph_name=None,
            cost=None,
            remaining_dough=None,
        )

    if (
        prepared.instance_id is None
        or prepared.card_id is None
        or prepared.generation is None
        or prepared.dupe_code is None
        or prepared.cost is None
    ):
        return MorphExecution(
            error_message="Morph failed.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            morph_key=None,
            morph_name=None,
            cost=None,
            remaining_dough=None,
        )

    available_rolls = [morph_key for morph_key in AVAILABLE_MORPHS if morph_key != prepared.current_morph_key]
    if not available_rolls:
        return MorphExecution(
            error_message="No new morphs are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            morph_key=None,
            morph_name=None,
            cost=None,
            remaining_dough=None,
        )

    rolled_morph = random.choice(available_rolls)

    return confirm_morph(
        guild_id,
        user_id,
        instance_id=prepared.instance_id,
        card_id=prepared.card_id,
        generation=prepared.generation,
        dupe_code=prepared.dupe_code,
        morph_key=rolled_morph,
        morph_name=morph_label(rolled_morph),
        cost=prepared.cost,
    )


def resolve_morph_roll(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    card_id: str,
    generation: int,
    dupe_code: str,
    current_morph_key: str | None,
    cost: int,
) -> MorphExecution:
    available_rolls = [morph_key for morph_key in AVAILABLE_MORPHS if morph_key != current_morph_key]
    if not available_rolls:
        return MorphExecution(
            error_message="No new morphs are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            morph_key=None,
            morph_name=None,
            cost=None,
            remaining_dough=None,
        )

    rolled_morph = random.choice(available_rolls)
    return confirm_morph(
        guild_id,
        user_id,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        morph_key=rolled_morph,
        morph_name=morph_label(rolled_morph),
        cost=cost,
    )


@dataclass(frozen=True)
class FrameExecution:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    frame_key: Optional[str]
    frame_name: Optional[str]
    cost: Optional[int]
    remaining_dough: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


@dataclass(frozen=True)
class FramePreparation:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    current_frame_key: Optional[str]
    frame_key: Optional[str]
    frame_name: Optional[str]
    cost: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def prepare_frame(guild_id: int, user_id: int, card_code: Optional[str]) -> FramePreparation:
    target_instance: Optional[tuple[int, str, int, str]] = None

    if card_code is None:
        target_instance = get_last_pulled_instance(guild_id, user_id)
        if target_instance is None:
            return FramePreparation(
                error_message="No previous pulled card found. Provide a card code, e.g. `ns frame 0`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_frame_key=None,
                frame_key=None,
                frame_name=None,
                cost=None,
            )
    else:
        parsed = split_card_code(card_code)
        if parsed is None:
            return FramePreparation(
                error_message="Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_frame_key=None,
                frame_key=None,
                frame_name=None,
                cost=None,
            )

        target_instance = get_instance_by_code(guild_id, user_id, card_code)
        if target_instance is None:
            return FramePreparation(
                error_message="You do not own that card code.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_frame_key=None,
                frame_key=None,
                frame_name=None,
                cost=None,
            )

    frame_choices = available_frame_keys()
    if not frame_choices:
        return FramePreparation(
            error_message="No frames are currently available.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_frame_key=None,
            frame_key=None,
            frame_name=None,
            cost=None,
        )

    instance_id, frame_card_id, frame_generation, frame_dupe_code = target_instance
    current_frame_key = get_instance_frame(guild_id, instance_id)
    available_rolls = [frame_key for frame_key in frame_choices if frame_key != current_frame_key]
    if not available_rolls:
        return FramePreparation(
            error_message="No new frames are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_frame_key=None,
            frame_key=None,
            frame_name=None,
            cost=None,
        )

    value = card_value(frame_card_id, frame_generation)
    cost = max(1, int(math.ceil(value * FRAME_COST_FRACTION)))
    dough_before, _, _ = get_player_stats(guild_id, user_id)
    if dough_before < cost:
        return FramePreparation(
            error_message="You do not have enough dough.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_frame_key=None,
            frame_key=None,
            frame_name=None,
            cost=None,
        )

    return FramePreparation(
        error_message=None,
        instance_id=instance_id,
        card_id=frame_card_id,
        generation=frame_generation,
        dupe_code=frame_dupe_code,
        current_frame_key=current_frame_key,
        frame_key=None,
        frame_name=None,
        cost=cost,
    )


def confirm_frame(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    card_id: str,
    generation: int,
    dupe_code: str,
    frame_key: str,
    frame_name: str,
    cost: int,
) -> FrameExecution:
    applied, message = apply_frame_to_instance(guild_id, user_id, instance_id, frame_key, cost)
    if not applied:
        return FrameExecution(
            error_message=message or "Frame failed.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            frame_key=None,
            frame_name=None,
            cost=None,
            remaining_dough=None,
        )

    dough_after, _, _ = get_player_stats(guild_id, user_id)
    return FrameExecution(
        error_message=None,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        frame_key=frame_key,
        frame_name=frame_name,
        cost=cost,
        remaining_dough=dough_after,
    )


def execute_frame(guild_id: int, user_id: int, card_code: Optional[str]) -> FrameExecution:
    prepared = prepare_frame(guild_id, user_id, card_code)
    if prepared.is_error:
        return FrameExecution(
            error_message=prepared.error_message,
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            frame_key=None,
            frame_name=None,
            cost=None,
            remaining_dough=None,
        )

    if (
        prepared.instance_id is None
        or prepared.card_id is None
        or prepared.generation is None
        or prepared.dupe_code is None
        or prepared.cost is None
    ):
        return FrameExecution(
            error_message="Frame failed.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            frame_key=None,
            frame_name=None,
            cost=None,
            remaining_dough=None,
        )

    frame_choices = available_frame_keys()
    available_rolls = [frame_key for frame_key in frame_choices if frame_key != prepared.current_frame_key]
    if not available_rolls:
        return FrameExecution(
            error_message="No new frames are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            frame_key=None,
            frame_name=None,
            cost=None,
            remaining_dough=None,
        )

    rolled_frame = random.choice(available_rolls)

    return confirm_frame(
        guild_id,
        user_id,
        instance_id=prepared.instance_id,
        card_id=prepared.card_id,
        generation=prepared.generation,
        dupe_code=prepared.dupe_code,
        frame_key=rolled_frame,
        frame_name=frame_label(rolled_frame),
        cost=prepared.cost,
    )


def resolve_frame_roll(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    card_id: str,
    generation: int,
    dupe_code: str,
    current_frame_key: str | None,
    cost: int,
) -> FrameExecution:
    frame_choices = available_frame_keys()
    available_rolls = [frame_key for frame_key in frame_choices if frame_key != current_frame_key]
    if not available_rolls:
        return FrameExecution(
            error_message="No new frames are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            frame_key=None,
            frame_name=None,
            cost=None,
            remaining_dough=None,
        )

    rolled_frame = random.choice(available_rolls)
    return confirm_frame(
        guild_id,
        user_id,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        frame_key=rolled_frame,
        frame_name=frame_label(rolled_frame),
        cost=cost,
    )


@dataclass(frozen=True)
class FontExecution:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    font_key: Optional[str]
    font_name: Optional[str]
    cost: Optional[int]
    remaining_dough: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


@dataclass(frozen=True)
class FontPreparation:
    error_message: Optional[str]
    instance_id: Optional[int]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    current_font_key: Optional[str]
    font_key: Optional[str]
    font_name: Optional[str]
    cost: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def prepare_font(guild_id: int, user_id: int, card_code: Optional[str]) -> FontPreparation:
    target_instance: Optional[tuple[int, str, int, str]] = None

    if card_code is None:
        target_instance = get_last_pulled_instance(guild_id, user_id)
        if target_instance is None:
            return FontPreparation(
                error_message="No previous pulled card found. Provide a card code, e.g. `ns font 0`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_font_key=None,
                font_key=None,
                font_name=None,
                cost=None,
            )
    else:
        parsed = split_card_code(card_code)
        if parsed is None:
            return FontPreparation(
                error_message="Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_font_key=None,
                font_key=None,
                font_name=None,
                cost=None,
            )

        target_instance = get_instance_by_code(guild_id, user_id, card_code)
        if target_instance is None:
            return FontPreparation(
                error_message="You do not own that card code.",
                instance_id=None,
                card_id=None,
                generation=None,
                dupe_code=None,
                current_font_key=None,
                font_key=None,
                font_name=None,
                cost=None,
            )

    if not AVAILABLE_FONTS:
        return FontPreparation(
            error_message="No fonts are currently available.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_font_key=None,
            font_key=None,
            font_name=None,
            cost=None,
        )

    instance_id, font_card_id, font_generation, font_dupe_code = target_instance
    current_font_key = get_instance_font(guild_id, instance_id)
    available_rolls = [font_key for font_key in AVAILABLE_FONTS if font_key != current_font_key]
    if not available_rolls:
        return FontPreparation(
            error_message="No new fonts are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_font_key=None,
            font_key=None,
            font_name=None,
            cost=None,
        )

    value = card_value(font_card_id, font_generation)
    cost = max(1, int(math.ceil(value * FONT_COST_FRACTION)))
    dough_before, _, _ = get_player_stats(guild_id, user_id)
    if dough_before < cost:
        return FontPreparation(
            error_message="You do not have enough dough.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            current_font_key=None,
            font_key=None,
            font_name=None,
            cost=None,
        )

    return FontPreparation(
        error_message=None,
        instance_id=instance_id,
        card_id=font_card_id,
        generation=font_generation,
        dupe_code=font_dupe_code,
        current_font_key=current_font_key,
        font_key=None,
        font_name=None,
        cost=cost,
    )


def confirm_font(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    card_id: str,
    generation: int,
    dupe_code: str,
    font_key: str,
    font_name: str,
    cost: int,
) -> FontExecution:
    applied, message = apply_font_to_instance(guild_id, user_id, instance_id, font_key, cost)
    if not applied:
        return FontExecution(
            error_message=message or "Font failed.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            font_key=None,
            font_name=None,
            cost=None,
            remaining_dough=None,
        )

    dough_after, _, _ = get_player_stats(guild_id, user_id)
    return FontExecution(
        error_message=None,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        font_key=font_key,
        font_name=font_name,
        cost=cost,
        remaining_dough=dough_after,
    )


def execute_font(guild_id: int, user_id: int, card_code: Optional[str]) -> FontExecution:
    prepared = prepare_font(guild_id, user_id, card_code)
    if prepared.is_error:
        return FontExecution(
            error_message=prepared.error_message,
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            font_key=None,
            font_name=None,
            cost=None,
            remaining_dough=None,
        )

    if (
        prepared.instance_id is None
        or prepared.card_id is None
        or prepared.generation is None
        or prepared.dupe_code is None
        or prepared.cost is None
    ):
        return FontExecution(
            error_message="Font failed.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            font_key=None,
            font_name=None,
            cost=None,
            remaining_dough=None,
        )

    available_rolls = [font_key for font_key in AVAILABLE_FONTS if font_key != prepared.current_font_key]
    if not available_rolls:
        return FontExecution(
            error_message="No new fonts are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            font_key=None,
            font_name=None,
            cost=None,
            remaining_dough=None,
        )

    rolled_font = random.choice(available_rolls)

    return confirm_font(
        guild_id,
        user_id,
        instance_id=prepared.instance_id,
        card_id=prepared.card_id,
        generation=prepared.generation,
        dupe_code=prepared.dupe_code,
        font_key=rolled_font,
        font_name=font_label(rolled_font),
        cost=prepared.cost,
    )


def resolve_font_roll(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    card_id: str,
    generation: int,
    dupe_code: str,
    current_font_key: str | None,
    cost: int,
) -> FontExecution:
    available_rolls = [font_key for font_key in AVAILABLE_FONTS if font_key != current_font_key]
    if not available_rolls:
        return FontExecution(
            error_message="No new fonts are currently available for this card.",
            instance_id=None,
            card_id=None,
            generation=None,
            dupe_code=None,
            font_key=None,
            font_name=None,
            cost=None,
            remaining_dough=None,
        )

    rolled_font = random.choice(available_rolls)
    return confirm_font(
        guild_id,
        user_id,
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        font_key=rolled_font,
        font_name=font_label(rolled_font),
        cost=cost,
    )


@dataclass(frozen=True)
class TradeOfferPreparation:
    error_message: Optional[str]
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def prepare_trade_offer(
    guild_id: int,
    seller_id: int,
    buyer_id: int,
    buyer_is_bot: bool,
    card_code: str,
    amount: int,
) -> TradeOfferPreparation:
    if buyer_id == seller_id:
        return TradeOfferPreparation(error_message="You cannot trade with yourself.", card_id=None, generation=None, dupe_code=None)

    if buyer_is_bot:
        return TradeOfferPreparation(error_message="You cannot trade with bots.", card_id=None, generation=None, dupe_code=None)

    if amount < 0:
        return TradeOfferPreparation(error_message="Amount must be 0 or greater.", card_id=None, generation=None, dupe_code=None)

    parsed = split_card_code(card_code)
    if parsed is None:
        return TradeOfferPreparation(
            error_message="Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
            card_id=None,
            generation=None,
            dupe_code=None,
        )

    candidate = get_instance_by_code(guild_id, seller_id, card_code)
    if candidate is None:
        return TradeOfferPreparation(error_message="You do not own that card code.", card_id=None, generation=None, dupe_code=None)

    _, candidate_card_id, generation, dupe_code = candidate

    return TradeOfferPreparation(error_message=None, card_id=candidate_card_id, generation=generation, dupe_code=dupe_code)
