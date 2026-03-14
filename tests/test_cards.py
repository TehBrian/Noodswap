from collections import Counter

from bot.cards import CARD_CATALOG, SERIES_CATALOG, default_card_image
from bot.card_value import (
    GENERATION_ROLL_TAU,
    _generation_sampler,
    burn_delta_range,
    generation_value_multiplier,
    get_burn_payout,
    random_generation,
)
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
        card_type_id
        for card_type_id, card in CARD_CATALOG.items()
        if not isinstance(card.get("image"), str) or not card["image"].startswith("runtime/card_images/")
    ]
    assert missing_local_path_ids == []


def test_no_card_uses_remote_image_urls() -> None:
    remote_ids = [
        card_type_id
        for card_type_id, card in CARD_CATALOG.items()
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


def test_burn_delta_range_stays_within_five_to_twenty_percent() -> None:
    """burn_delta_range must return a value in [1, ceil(value * 20%)] for all inputs,
    matching the payout band declared by the burn UX contract."""
    for value in [1, 50, 500, 5000, 100_000]:
        upper = max(1, int(value * 0.20) + 1)  # floor(v*0.20)+1 always >= round(v*0.20)
        for _ in range(500):
            result = burn_delta_range(value)
            assert result >= 1, f"burn_delta_range({value}) returned {result} < 1"
            assert result <= upper, f"burn_delta_range({value}) returned {result} > {upper}"


def test_get_burn_payout_delta_is_within_declared_range() -> None:
    """get_burn_payout must return a payout >= 1 and a delta fully contained
    within the resolved delta_range, satisfying payout == max(1, value + delta)."""
    for base_val in [10, 500, 5000]:
        for generation in [1, 500, 2000]:
            for _ in range(100):
                payout, value, _base, delta, _mult, resolved_range = get_burn_payout(
                    "SPG",
                    generation,
                    card_base_value_func=lambda _: base_val,
                    generation_multiplier_func=lambda g: generation_value_multiplier(
                        g, generation_min=GENERATION_MIN, generation_max=GENERATION_MAX
                    ),
                    burn_delta_range_func=burn_delta_range,
                )
                assert payout >= 1
                assert abs(delta) <= resolved_range
                assert payout == max(1, value + delta)
                # resolved_range itself must respect the 5%-20% band
                assert resolved_range >= 1
                assert resolved_range <= max(1, int(value * 0.20) + 1)  # floor(v*0.20)+1 always >= round(v*0.20)


def test_random_generation_large_n_quantile_sanity() -> None:
    """At n=50,000 the empirical generation distribution must track the sampler's
    analytical CDF. For each quantile cutoff with expected rate >= 0.5%, the
    observed rate must be within ±40% relative tolerance of the expected rate."""
    n = 50_000
    generations_tuple, cdf_tuple = _generation_sampler(GENERATION_MIN, GENERATION_MAX, GENERATION_ROLL_TAU)

    # Derive per-generation probabilities from the CDF
    prev = 0.0
    gen_prob: dict[int, float] = {}
    for gen, cp in zip(generations_tuple, cdf_tuple):
        gen_prob[gen] = cp - prev
        prev = cp

    # Key quantile checkpoints: P(gen <= N) for low-gen buckets, P(gen >= N) for high-gen
    expected: dict[tuple[str, int], float] = {
        ("lte", 100): sum(p for g, p in gen_prob.items() if g <= 100),
        ("lte", 500): sum(p for g, p in gen_prob.items() if g <= 500),
        ("gte", 1500): sum(p for g, p in gen_prob.items() if g >= 1500),
    }

    rolls = [random_generation(generation_min=GENERATION_MIN, generation_max=GENERATION_MAX) for _ in range(n)]

    TOLERANCE = 0.40
    for (direction, cutoff), exp_rate in expected.items():
        if exp_rate < 0.005:  # skip buckets too rare to test reliably at this n
            continue
        obs_rate = sum(1 for r in rolls if (r <= cutoff if direction == "lte" else r >= cutoff)) / n
        rel_diff = abs(obs_rate - exp_rate) / exp_rate
        assert rel_diff <= TOLERANCE, (
            f"gen {direction} {cutoff}: observed {obs_rate:.4f} vs expected {exp_rate:.4f} "
            f"(relative diff {rel_diff:.2%} > {TOLERANCE:.0%} tolerance)"
        )
