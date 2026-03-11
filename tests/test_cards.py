import unittest
from collections import Counter

from noodswap.cards import CARD_CATALOG, SERIES_CATALOG, default_card_image
from noodswap.card_economy import random_generation
from noodswap.rarities import (
    RARITY_CURVE_LINEAR_RATE,
    RARITY_ORDER,
    RARITY_TAIL_CURVATURE,
    RARITY_TOTAL_WEIGHT,
    build_rarity_weights,
)
from noodswap.settings import GENERATION_MAX, GENERATION_MIN


class CardsImageTests(unittest.TestCase):
    def test_every_card_has_local_path_image_value(self) -> None:
        missing_local_path_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if not isinstance(card.get("image"), str) or not card["image"].startswith("runtime/card_images/")
        ]
        self.assertEqual(missing_local_path_ids, [])

    def test_no_card_uses_remote_image_urls(self) -> None:
        remote_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if isinstance(card.get("image"), str) and card["image"].startswith(("http://", "https://"))
        ]
        self.assertEqual(remote_ids, [])

    def test_default_card_image_is_local_placeholder_path(self) -> None:
        self.assertEqual(default_card_image("SPG"), "runtime/card_images/SPG.img")


class CardsSeriesTests(unittest.TestCase):
    def test_every_card_series_is_declared(self) -> None:
        undeclared_series = sorted(
            {card["series"] for card in CARD_CATALOG.values() if card["series"] not in SERIES_CATALOG}
        )
        self.assertEqual(undeclared_series, [])

    def test_declared_series_have_non_empty_emoji(self) -> None:
        missing_emojis = sorted(
            series_id
            for series_id, series_meta in SERIES_CATALOG.items()
            if not isinstance(series_meta.get("emoji"), str) or not series_meta["emoji"].strip()
        )
        self.assertEqual(missing_emojis, [])


class GenerationSamplerTests(unittest.TestCase):
    def test_random_generation_within_default_bounds(self) -> None:
        for _ in range(5000):
            generation = random_generation(
                generation_min=GENERATION_MIN,
                generation_max=GENERATION_MAX,
            )
            self.assertIsInstance(generation, int)
            self.assertGreaterEqual(generation, GENERATION_MIN)
            self.assertLessEqual(generation, GENERATION_MAX)

    def test_random_generation_respects_custom_bounds(self) -> None:
        lower = 100
        upper = 150
        for _ in range(1000):
            generation = random_generation(generation_min=lower, generation_max=upper)
            self.assertGreaterEqual(generation, lower)
            self.assertLessEqual(generation, upper)

    def test_random_generation_is_right_skewed_toward_high_generations(self) -> None:
        sample_size = 20000
        rolls = [
            random_generation(generation_min=GENERATION_MIN, generation_max=GENERATION_MAX)
            for _ in range(sample_size)
        ]
        bucket_counts = Counter()
        for generation in rolls:
            if generation <= 100:
                bucket_counts["low"] += 1
            elif generation <= 500:
                bucket_counts["mid_low"] += 1
            elif generation >= 1500:
                bucket_counts["high"] += 1

        self.assertGreater(bucket_counts["high"], bucket_counts["mid_low"])
        self.assertGreater(bucket_counts["mid_low"], bucket_counts["low"])


class RarityWeightCurveTests(unittest.TestCase):
    def test_generated_weights_sum_and_order_invariants(self) -> None:
        weights = build_rarity_weights(
            linear_rate=RARITY_CURVE_LINEAR_RATE,
            tail_curvature=RARITY_TAIL_CURVATURE,
            total_weight=RARITY_TOTAL_WEIGHT,
            smoothing=0.0,
        )

        self.assertEqual(sum(weights.values()), RARITY_TOTAL_WEIGHT)
        for rarity in RARITY_ORDER:
            self.assertGreater(weights[rarity], 0)

        for index in range(len(RARITY_ORDER) - 1):
            left = RARITY_ORDER[index]
            right = RARITY_ORDER[index + 1]
            self.assertGreater(weights[left], weights[right])

    def test_lower_linear_rate_makes_top_tiers_more_common(self) -> None:
        flatter = build_rarity_weights(linear_rate=0.45, tail_curvature=0.0, total_weight=RARITY_TOTAL_WEIGHT, smoothing=0.0)
        steeper = build_rarity_weights(linear_rate=0.70, tail_curvature=0.0, total_weight=RARITY_TOTAL_WEIGHT, smoothing=0.0)

        self.assertGreater(flatter["celestial"], steeper["celestial"])
        self.assertGreater(steeper["common"], flatter["common"])

    def test_higher_tail_curvature_steepens_top_end(self) -> None:
        low_curve = build_rarity_weights(linear_rate=0.541, tail_curvature=0.0, total_weight=RARITY_TOTAL_WEIGHT, smoothing=0.0)
        high_curve = build_rarity_weights(linear_rate=0.541, tail_curvature=0.03, total_weight=RARITY_TOTAL_WEIGHT, smoothing=0.0)

        self.assertLess(high_curve["celestial"], low_curve["celestial"])
        self.assertLess(high_curve["divine"], low_curve["divine"])
        self.assertGreater(high_curve["common"], low_curve["common"])

    def test_smoothing_flattens_curve(self) -> None:
        baseline = build_rarity_weights(linear_rate=0.541, tail_curvature=0.02, total_weight=RARITY_TOTAL_WEIGHT, smoothing=0.0)
        smoothed = build_rarity_weights(linear_rate=0.541, tail_curvature=0.02, total_weight=RARITY_TOTAL_WEIGHT, smoothing=1.0)

        self.assertGreater(smoothed["celestial"], baseline["celestial"])
        self.assertLess(smoothed["common"], baseline["common"])


if __name__ == "__main__":
    unittest.main()
