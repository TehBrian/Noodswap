from collections import Counter

from bot.cards import CARD_CATALOG, SERIES_CATALOG, default_card_image
from bot.card_economy import random_generation
from bot.rarities import (
    RARITY_CURVE_LINEAR_RATE,
    RARITY_ORDER,
    RARITY_TAIL_CURVATURE,
    RARITY_TOTAL_WEIGHT,
    build_rarity_weights,
)
from bot.settings import GENERATION_MAX, GENERATION_MIN

def test_every_card_has_local_path_image_value() -> None:
    missing_local_path_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if not isinstance(card.get("image"), str) or not card["image"].startswith("runtime/card_images/")
    ]
    assert missing_local_path_ids == []


def test_no_card_uses_remote_image_urls() -> None:
    remote_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if isinstance(card.get("image"), str) and card["image"].startswith(("http://", "https://"))
    ]
    assert remote_ids == []


def test_default_card_image_is_local_placeholder_path() -> None:
    assert default_card_image("SPG") == "runtime/card_images/SPG.img"


def test_every_card_series_is_declared() -> None:
    undeclared_series = sorted({card["series"] for card in CARD_CATALOG.values() if card["series"] not in SERIES_CATALOG})
    assert undeclared_series == []


def test_declared_series_have_non_empty_emoji() -> None:
    missing_emojis = sorted(
        series_id
        for series_id, series_meta in SERIES_CATALOG.items()
        if not isinstance(series_meta.get("emoji"), str) or not series_meta["emoji"].strip()
    )
    assert missing_emojis == []


def test_random_generation_within_default_bounds() -> None:
    for _ in range(5000):
        generation = random_generation(
            generation_min=GENERATION_MIN,
            generation_max=GENERATION_MAX,
        )
        assert isinstance(generation, int)
        assert generation >= GENERATION_MIN
        assert generation <= GENERATION_MAX


def test_random_generation_respects_custom_bounds() -> None:
    lower = 100
    upper = 150
    for _ in range(1000):
        generation = random_generation(generation_min=lower, generation_max=upper)
        assert generation >= lower
        assert generation <= upper


def test_random_generation_is_right_skewed_toward_high_generations() -> None:
    sample_size = 20000
    rolls = [random_generation(generation_min=GENERATION_MIN, generation_max=GENERATION_MAX) for _ in range(sample_size)]
    bucket_counts = Counter()
    for generation in rolls:
        if generation <= 100:
            bucket_counts["low"] += 1
        elif generation <= 500:
            bucket_counts["mid_low"] += 1
        elif generation >= 1500:
            bucket_counts["high"] += 1

    assert bucket_counts["high"] > bucket_counts["mid_low"]
    assert bucket_counts["mid_low"] > bucket_counts["low"]


def test_generated_weights_sum_and_order_invariants() -> None:
    weights = build_rarity_weights(
        linear_rate=RARITY_CURVE_LINEAR_RATE,
        tail_curvature=RARITY_TAIL_CURVATURE,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=0.0,
    )

    assert sum(weights.values()) == RARITY_TOTAL_WEIGHT
    for rarity in RARITY_ORDER:
        assert weights[rarity] > 0

    for index in range(len(RARITY_ORDER) - 1):
        left = RARITY_ORDER[index]
        right = RARITY_ORDER[index + 1]
        assert weights[left] > weights[right]


def test_lower_linear_rate_makes_top_tiers_more_common() -> None:
    flatter = build_rarity_weights(
        linear_rate=0.45,
        tail_curvature=0.0,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=0.0,
    )
    steeper = build_rarity_weights(
        linear_rate=0.70,
        tail_curvature=0.0,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=0.0,
    )

    assert flatter["celestial"] > steeper["celestial"]
    assert steeper["common"] > flatter["common"]


def test_higher_tail_curvature_steepens_top_end() -> None:
    low_curve = build_rarity_weights(
        linear_rate=0.541,
        tail_curvature=0.0,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=0.0,
    )
    high_curve = build_rarity_weights(
        linear_rate=0.541,
        tail_curvature=0.03,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=0.0,
    )

    assert high_curve["celestial"] < low_curve["celestial"]
    assert high_curve["divine"] < low_curve["divine"]
    assert high_curve["common"] > low_curve["common"]


def test_smoothing_flattens_curve() -> None:
    baseline = build_rarity_weights(
        linear_rate=0.541,
        tail_curvature=0.02,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=0.0,
    )
    smoothed = build_rarity_weights(
        linear_rate=0.541,
        tail_curvature=0.02,
        total_weight=RARITY_TOTAL_WEIGHT,
        smoothing=1.0,
    )

    assert smoothed["celestial"] > baseline["celestial"]
    assert smoothed["common"] < baseline["common"]
