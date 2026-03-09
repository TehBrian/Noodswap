import unittest
from collections import Counter

from noodswap.cards import CARD_CATALOG, SERIES_CATALOG, default_card_image
from noodswap.card_economy import random_generation
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


if __name__ == "__main__":
    unittest.main()
