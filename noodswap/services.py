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
    add_dough,
    apply_font_to_instance,
    apply_frame_to_instance,
    apply_morph_to_instance,
    burn_instances,
    consume_drop_cooldown_or_ticket,
    consume_pull_cooldown_if_ready,
    divorce_card,
    execute_trade,
    create_battle_proposal,
    end_open_battles_for_shutdown as storage_end_open_battles_for_shutdown,
    execute_battle_turn_action,
    get_battle_session,
    get_battle_state,
    get_instance_by_id,
    get_instance_font,
    get_instance_frame,
    get_locked_protection_for_instance,
    get_instance_morph,
    get_instance_by_code,
    get_last_pulled_instance,
    get_player_info,
    resolve_battle_proposal,
    marry_card_instance,
)


@dataclass(frozen=True)
class DropPreparation:
    choices: list[tuple[str, int]]
    cooldown_remaining_seconds: float
    used_drop_ticket: bool

    @property
    def is_cooldown(self) -> bool:
        return self.cooldown_remaining_seconds > 0


def prepare_drop(guild_id: int, user_id: int, now: float) -> DropPreparation:
    used_drop_ticket, cooldown_remaining_seconds = consume_drop_cooldown_or_ticket(
        guild_id,
        user_id,
        now=now,
        cooldown_seconds=DROP_COOLDOWN_SECONDS,
    )
    if cooldown_remaining_seconds > 0:
        return DropPreparation(
            choices=[],
            cooldown_remaining_seconds=cooldown_remaining_seconds,
            used_drop_ticket=False,
        )

    choices = make_drop_choices(DROP_CHOICES_COUNT)
    return DropPreparation(choices=choices, cooldown_remaining_seconds=0.0, used_drop_ticket=used_drop_ticket)


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
    locked_tags, locked_folder_name = get_locked_protection_for_instance(guild_id, user_id, instance_id)
    if locked_tags or locked_folder_name is not None:
        details: list[str] = []
        if locked_tags:
            details.append("locked tag(s): " + ", ".join(f"`{tag}`" for tag in locked_tags))
        if locked_folder_name is not None:
            details.append(f"locked folder: `{locked_folder_name}`")
        return BurnPreparation(
            error_message=f"That card is protected by {'; '.join(details)}.",
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
class BurnConfirmationExecution:
    status: str
    message: str
    card_id: Optional[str]
    generation: Optional[int]
    dupe_code: Optional[str]
    payout: Optional[int]
    delta: Optional[int]
    locked_tags: tuple[str, ...]

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_burned(self) -> bool:
        return self.status == "burned"


@dataclass(frozen=True)
class BurnPreviewItem:
    instance_id: int
    card_id: str
    generation: int
    dupe_code: str
    value: int
    base_value: int
    delta_range: int
    multiplier: float


@dataclass(frozen=True)
class BurnBatchPreparation:
    error_message: Optional[str]
    items: tuple[BurnPreviewItem, ...]
    total_value: Optional[int]
    total_delta_range: Optional[int]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


@dataclass(frozen=True)
class BurnBatchConfirmationEntry:
    card_id: str
    generation: int
    dupe_code: str
    payout: int
    delta: int


@dataclass(frozen=True)
class BurnBatchConfirmationExecution:
    status: str
    message: str
    burned_entries: tuple[BurnBatchConfirmationEntry, ...]
    locked_instances: tuple[tuple[int, tuple[str, ...]], ...]

    @property
    def is_blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_burned(self) -> bool:
        return self.status == "burned"


def prepare_burn_batch(
    guild_id: int,
    user_id: int,
    targets: list[tuple[int, str, int, str]],
) -> BurnBatchPreparation:
    if not targets:
        return BurnBatchPreparation(
            error_message="No burn targets found.",
            items=(),
            total_value=None,
            total_delta_range=None,
        )

    seen_instance_ids: set[int] = set()
    unique_targets: list[tuple[int, str, int, str]] = []
    for instance_id, card_id, generation, dupe_code in targets:
        if instance_id in seen_instance_ids:
            continue
        seen_instance_ids.add(instance_id)
        unique_targets.append((instance_id, card_id, generation, dupe_code))

    locked_cards: list[str] = []
    preview_items: list[BurnPreviewItem] = []
    total_value = 0
    total_delta_range = 0

    for instance_id, card_id, generation, dupe_code in unique_targets:
        locked_tags, locked_folder_name = get_locked_protection_for_instance(guild_id, user_id, instance_id)
        if locked_tags or locked_folder_name is not None:
            details: list[str] = []
            if locked_tags:
                details.append("locked tag(s): " + ", ".join(f"`{tag}`" for tag in locked_tags))
            if locked_folder_name is not None:
                details.append(f"locked folder: `{locked_folder_name}`")
            locked_cards.append(f"`{dupe_code}` ({'; '.join(details)})")
            continue

        _payout, value, base_value, _delta, multiplier, delta_range = get_burn_payout(card_id, generation)
        total_value += value
        total_delta_range += delta_range
        preview_items.append(
            BurnPreviewItem(
                instance_id=instance_id,
                card_id=card_id,
                generation=generation,
                dupe_code=dupe_code,
                value=value,
                base_value=base_value,
                delta_range=delta_range,
                multiplier=multiplier,
            )
        )

    if locked_cards:
        return BurnBatchPreparation(
            error_message=(
                "Burn blocked because at least one target is protected by lock(s):\n"
                + "\n".join(f"- {card_line}" for card_line in locked_cards)
            ),
            items=(),
            total_value=None,
            total_delta_range=None,
        )

    return BurnBatchPreparation(
        error_message=None,
        items=tuple(preview_items),
        total_value=total_value,
        total_delta_range=total_delta_range,
    )


def execute_burn_batch_confirmation(
    guild_id: int,
    user_id: int,
    *,
    burn_targets: list[tuple[int, int]],
) -> BurnBatchConfirmationExecution:
    if not burn_targets:
        return BurnBatchConfirmationExecution(
            status="failed",
            message="No burn targets were provided.",
            burned_entries=(),
            locked_instances=(),
        )

    instance_ids = [instance_id for instance_id, _delta_range in burn_targets]
    delta_by_instance = dict(burn_targets)

    burned_rows, locked_by_instance = burn_instances(guild_id, user_id, instance_ids)
    if locked_by_instance:
        locked_instances = tuple(
            (instance_id, tuple(tags))
            for instance_id, tags in sorted(locked_by_instance.items(), key=lambda entry: entry[0])
        )
        return BurnBatchConfirmationExecution(
            status="blocked",
            message="Burn blocked: at least one selected card is protected by lock(s).",
            burned_entries=(),
            locked_instances=locked_instances,
        )

    if burned_rows is None:
        return BurnBatchConfirmationExecution(
            status="failed",
            message="One or more selected cards are no longer available.",
            burned_entries=(),
            locked_instances=(),
        )

    burned_entries: list[BurnBatchConfirmationEntry] = []
    total_payout = 0
    for instance_id, card_id, generation, dupe_code in burned_rows:
        resolved_delta_range = delta_by_instance.get(instance_id)
        payout, _value, _base_value, delta, _multiplier, _resolved_delta_range = get_burn_payout(
            card_id,
            generation,
            resolved_delta_range,
        )
        total_payout += payout
        burned_entries.append(
            BurnBatchConfirmationEntry(
                card_id=card_id,
                generation=generation,
                dupe_code=dupe_code,
                payout=payout,
                delta=delta,
            )
        )

    add_dough(guild_id, user_id, total_payout)
    return BurnBatchConfirmationExecution(
        status="burned",
        message="",
        burned_entries=tuple(burned_entries),
        locked_instances=(),
    )


def execute_burn_confirmation(
    guild_id: int,
    user_id: int,
    *,
    instance_id: int,
    delta_range: int,
) -> BurnConfirmationExecution:
    batch_result = execute_burn_batch_confirmation(
        guild_id,
        user_id,
        burn_targets=[(instance_id, delta_range)],
    )

    if batch_result.is_blocked:
        locked_tags = tuple(batch_result.locked_instances[0][1]) if batch_result.locked_instances else tuple()
        return BurnConfirmationExecution(
            status="blocked",
            message="Card is protected by lock(s).",
            card_id=None,
            generation=None,
            dupe_code=None,
            payout=None,
            delta=None,
            locked_tags=locked_tags,
        )

    if batch_result.is_failed or not batch_result.burned_entries:
        return BurnConfirmationExecution(
            status="failed",
            message="That card instance is no longer available.",
            card_id=None,
            generation=None,
            dupe_code=None,
            payout=None,
            delta=None,
            locked_tags=(),
        )

    burned_entry = batch_result.burned_entries[0]

    return BurnConfirmationExecution(
        status="burned",
        message="",
        card_id=burned_entry.card_id,
        generation=burned_entry.generation,
        dupe_code=burned_entry.dupe_code,
        payout=burned_entry.payout,
        delta=burned_entry.delta,
        locked_tags=(),
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
    dough_before, _, _ = get_player_info(guild_id, user_id)
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

    dough_after, _, _ = get_player_info(guild_id, user_id)
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
    dough_before, _, _ = get_player_info(guild_id, user_id)
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

    dough_after, _, _ = get_player_info(guild_id, user_id)
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
    dough_before, _, _ = get_player_info(guild_id, user_id)
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

    dough_after, _, _ = get_player_info(guild_id, user_id)
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


@dataclass(frozen=True)
class BattleOfferPreparation:
    error_message: Optional[str]
    battle_id: Optional[int]
    challenger_team_name: Optional[str]
    challenged_team_name: Optional[str]

    @property
    def is_error(self) -> bool:
        return self.error_message is not None


def prepare_battle_offer(
    guild_id: int,
    challenger_id: int,
    challenged_id: int,
    challenged_is_bot: bool,
    stake: int,
) -> BattleOfferPreparation:
    if challenged_is_bot:
        return BattleOfferPreparation(
            error_message="You cannot battle bots.",
            battle_id=None,
            challenger_team_name=None,
            challenged_team_name=None,
        )

    success, message, battle_id, challenger_team_name, challenged_team_name = create_battle_proposal(
        guild_id,
        challenger_id,
        challenged_id,
        stake,
    )
    if not success:
        return BattleOfferPreparation(
            error_message=message,
            battle_id=None,
            challenger_team_name=None,
            challenged_team_name=None,
        )

    return BattleOfferPreparation(
        error_message=None,
        battle_id=battle_id,
        challenger_team_name=challenger_team_name,
        challenged_team_name=challenged_team_name,
    )


@dataclass(frozen=True)
class BattleOfferResolution:
    status: str
    message: str
    battle_id: int
    stake: Optional[int]
    challenger_id: Optional[int]
    challenged_id: Optional[int]

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def is_denied(self) -> bool:
        return self.status == "denied"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"


def resolve_battle_offer(
    guild_id: int,
    battle_id: int,
    responder_id: int,
    *,
    accepted: bool,
) -> BattleOfferResolution:
    status, message = resolve_battle_proposal(
        guild_id,
        battle_id,
        responder_id,
        accepted=accepted,
    )
    battle = get_battle_session(guild_id, battle_id)
    stake = int(battle["stake"]) if battle is not None and battle["stake"] is not None else None
    challenger_id = int(battle["challenger_id"]) if battle is not None and battle["challenger_id"] is not None else None
    challenged_id = int(battle["challenged_id"]) if battle is not None and battle["challenged_id"] is not None else None
    return BattleOfferResolution(
        status=status,
        message=message,
        battle_id=battle_id,
        stake=stake,
        challenger_id=challenger_id,
        challenged_id=challenged_id,
    )


@dataclass(frozen=True)
class BattleSnapshot:
    battle_id: int
    status: str
    challenger_id: int
    challenged_id: int
    acting_user_id: Optional[int]
    winner_user_id: Optional[int]
    turn_number: int
    stake: int
    last_action: str
    challenger_team_name: str
    challenged_team_name: str
    challenger_combatants: tuple[dict[str, int | str | bool], ...]
    challenged_combatants: tuple[dict[str, int | str | bool], ...]


def get_battle_snapshot(guild_id: int, battle_id: int) -> Optional[BattleSnapshot]:
    state = get_battle_state(guild_id, battle_id)
    if state is None:
        return None
    battle = state["battle"]
    assert isinstance(battle, dict)
    challenger_rows = state["challenger_combatants"]
    challenged_rows = state["challenged_combatants"]
    assert isinstance(challenger_rows, list)
    assert isinstance(challenged_rows, list)

    return BattleSnapshot(
        battle_id=int(battle["battle_id"]),
        status=str(battle["status"]),
        challenger_id=int(battle["challenger_id"]),
        challenged_id=int(battle["challenged_id"]),
        acting_user_id=int(battle["acting_user_id"]) if battle["acting_user_id"] is not None else None,
        winner_user_id=int(battle["winner_user_id"]) if battle["winner_user_id"] is not None else None,
        turn_number=int(battle["turn_number"]),
        stake=int(battle["stake"]),
        last_action=str(battle["last_action"] or "Battle started."),
        challenger_team_name=str(battle["challenger_team_name"]),
        challenged_team_name=str(battle["challenged_team_name"]),
        challenger_combatants=tuple(challenger_rows),
        challenged_combatants=tuple(challenged_rows),
    )


@dataclass(frozen=True)
class BattleTurnResolution:
    status: str
    message: str
    winner_user_id: Optional[int]
    next_actor_id: Optional[int]
    snapshot: Optional[BattleSnapshot]

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_finished(self) -> bool:
        return self.status == "finished"


def resolve_battle_turn_action(
    guild_id: int,
    battle_id: int,
    actor_id: int,
    action: str,
) -> BattleTurnResolution:
    status, message, winner_user_id, next_actor_id = execute_battle_turn_action(
        guild_id,
        battle_id,
        actor_id,
        action,
    )
    snapshot = get_battle_snapshot(guild_id, battle_id)
    return BattleTurnResolution(
        status=status,
        message=message,
        winner_user_id=winner_user_id,
        next_actor_id=next_actor_id,
        snapshot=snapshot,
    )


def end_open_battles_for_shutdown() -> int:
    return storage_end_open_battles_for_shutdown()
