import unittest

from noodswap.rarities import RARITY_ORDER
from noodswap.trait_rarities import (
    TRAIT_RARITY_MULTIPLIERS,
    TRAIT_RARITY_WEIGHTS,
    TRAIT_TOTAL_WEIGHT,
    normalize_trait_rarity,
    trait_rarity_multiplier,
    trait_rarity_weight,
)


class TraitRaritiesTests(unittest.TestCase):
    def test_trait_weights_sum_and_monotonic(self) -> None:
        self.assertEqual(sum(TRAIT_RARITY_WEIGHTS.values()), TRAIT_TOTAL_WEIGHT)
        for index in range(len(RARITY_ORDER) - 1):
            left = RARITY_ORDER[index]
            right = RARITY_ORDER[index + 1]
            self.assertGreater(TRAIT_RARITY_WEIGHTS[left], TRAIT_RARITY_WEIGHTS[right])

    def test_normalize_trait_rarity_fallback(self) -> None:
        self.assertEqual(normalize_trait_rarity(None), "common")
        self.assertEqual(normalize_trait_rarity("unknown"), "common")
        self.assertEqual(normalize_trait_rarity(" EPIC "), "epic")

    def test_multiplier_and_weight_fallback(self) -> None:
        self.assertEqual(trait_rarity_multiplier("unknown"), TRAIT_RARITY_MULTIPLIERS["common"])
        self.assertEqual(trait_rarity_weight("unknown"), TRAIT_RARITY_WEIGHTS["common"])


if __name__ == "__main__":
    unittest.main()
