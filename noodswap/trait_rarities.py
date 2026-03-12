import random
from collections.abc import Callable, Sequence
from typing import TypeVar

from .rarities import RARITY_ORDER, build_rarity_weights

TRAIT_CURVE_LINEAR_RATE = 0.20
TRAIT_CURVE_TAIL_CURVATURE = 0.0
TRAIT_CURVE_SMOOTHING = 1.5
TRAIT_TOTAL_WEIGHT = 10_000

TRAIT_RARITY_WEIGHTS = build_rarity_weights(
    linear_rate=TRAIT_CURVE_LINEAR_RATE,
    tail_curvature=TRAIT_CURVE_TAIL_CURVATURE,
    total_weight=TRAIT_TOTAL_WEIGHT,
    smoothing=TRAIT_CURVE_SMOOTHING,
)

# Trait multipliers are intentionally conservative because they stack across
# morph/frame/font and then multiply with generation value.
TRAIT_RARITY_MULTIPLIERS: dict[str, float] = {
    "common": 1.00,
    "uncommon": 1.02,
    "rare": 1.05,
    "epic": 1.12,
    "legendary": 1.22,
    "mythical": 1.28,
    "divine": 1.33,
    "celestial": 1.38,
}

_DEFAULT_TRAIT_RARITY = "common"
T = TypeVar("T")


def normalize_trait_rarity(rarity: str | None) -> str:
    if rarity is None:
        return _DEFAULT_TRAIT_RARITY
    normalized = rarity.strip().lower()
    if normalized in RARITY_ORDER:
        return normalized
    return _DEFAULT_TRAIT_RARITY


def trait_rarity_multiplier(rarity: str | None) -> float:
    normalized = normalize_trait_rarity(rarity)
    return TRAIT_RARITY_MULTIPLIERS.get(
        normalized, TRAIT_RARITY_MULTIPLIERS[_DEFAULT_TRAIT_RARITY]
    )


def trait_rarity_weight(rarity: str | None) -> int:
    normalized = normalize_trait_rarity(rarity)
    return int(
        TRAIT_RARITY_WEIGHTS.get(
            normalized, TRAIT_RARITY_WEIGHTS[_DEFAULT_TRAIT_RARITY]
        )
    )


def weighted_trait_choice(
    options: Sequence[T], rarity_for_option: Callable[[T], str]
) -> T:
    if not options:
        raise ValueError("options must be non-empty")
    if len(options) == 1:
        return options[0]

    weights = [trait_rarity_weight(rarity_for_option(option)) for option in options]
    return random.choices(list(options), weights=weights, k=1)[0]
