from dataclasses import dataclass
from typing import Optional

from .cards import get_burn_payout, make_drop_choices, split_card_code
from .settings import DROP_CHOICES_COUNT, PULL_COOLDOWN_SECONDS
from .storage import (
    divorce_card,
    get_instance_by_code,
    get_last_dropped_instance,
    get_player_stats,
    marry_card_instance,
    set_last_pull_at,
)


@dataclass(frozen=True)
class DropPreparation:
    choices: list[tuple[str, int]]
    cooldown_remaining_seconds: float

    @property
    def is_cooldown(self) -> bool:
        return self.cooldown_remaining_seconds > 0


def prepare_drop(guild_id: int, user_id: int, now: float) -> DropPreparation:
    _, last_pull_at, _ = get_player_stats(guild_id, user_id)
    elapsed = now - last_pull_at

    if elapsed < PULL_COOLDOWN_SECONDS:
        return DropPreparation(
            choices=[],
            cooldown_remaining_seconds=PULL_COOLDOWN_SECONDS - elapsed,
        )

    choices = make_drop_choices(DROP_CHOICES_COUNT)
    set_last_pull_at(guild_id, user_id, now)
    return DropPreparation(choices=choices, cooldown_remaining_seconds=0.0)


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
        target_instance = get_last_dropped_instance(guild_id, user_id)
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
                error_message="Invalid card code. Use format like `0`, `a`, or `10`.",
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
        last_dropped = get_last_dropped_instance(guild_id, user_id)
        if last_dropped is None:
            return MarryExecution(
                error_message="No previous pulled card found. Use `ns marry <card_code>` or pull from `ns drop` first.",
                card_id=None,
                generation=None,
                dupe_code=None,
            )

        instance_id, _, _, _ = last_dropped
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
            error_message="Invalid card code. Use format like `0`, `a`, or `10`.",
            card_id=None,
            generation=None,
            dupe_code=None,
        )

    candidate = get_instance_by_code(guild_id, seller_id, card_code)
    if candidate is None:
        return TradeOfferPreparation(error_message="You do not own that card code.", card_id=None, generation=None, dupe_code=None)

    _, candidate_card_id, generation, dupe_code = candidate

    return TradeOfferPreparation(error_message=None, card_id=candidate_card_id, generation=generation, dupe_code=dupe_code)
