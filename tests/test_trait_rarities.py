from bot.rarities import RARITY_ORDER
from bot.trait_rarities import (
    TRAIT_RARITY_MULTIPLIERS,
    TRAIT_RARITY_WEIGHTS,
    TRAIT_TOTAL_WEIGHT,
    normalize_trait_rarity,
    trait_rarity_multiplier,
    trait_rarity_weight,
)


def test_trait_weights_sum_and_monotonic() -> None:
    assert sum(TRAIT_RARITY_WEIGHTS.values()) == TRAIT_TOTAL_WEIGHT
    for index in range(len(RARITY_ORDER) - 1):
        left = RARITY_ORDER[index]
        right = RARITY_ORDER[index + 1]
        assert TRAIT_RARITY_WEIGHTS[left] > TRAIT_RARITY_WEIGHTS[right]


def test_normalize_trait_rarity_fallback() -> None:
    assert normalize_trait_rarity(None) == "common"
    assert normalize_trait_rarity("unknown") == "common"
    assert normalize_trait_rarity(" EPIC ") == "epic"


def test_multiplier_and_weight_fallback() -> None:
    assert trait_rarity_multiplier("unknown") == TRAIT_RARITY_MULTIPLIERS["common"]
    assert trait_rarity_weight("unknown") == TRAIT_RARITY_WEIGHTS["common"]
