import random
import unittest

from noodswap.battle_engine import (
    MAX_ROLL,
    MIN_ROLL,
    build_battle_card,
    build_team_battle_cards,
    rarity_miss_chance,
    resolve_attack,
    series_multiplier,
    value_to_stats,
)


class BattleEngineTests(unittest.TestCase):
    def test_value_to_stats_grows_with_value(self) -> None:
        low = value_to_stats(50)
        high = value_to_stats(5000)
        self.assertLess(low[0], high[0])
        self.assertLess(low[1], high[1])
        self.assertLess(low[2], high[2])

    def test_series_multiplier_defaults_to_neutral(self) -> None:
        self.assertEqual(series_multiplier("unknown", "bread"), 1.0)
        self.assertEqual(series_multiplier("wine", "unknown"), 1.0)

    def test_known_series_matchup_values(self) -> None:
        self.assertEqual(series_multiplier("wine", "bread"), 2.5)
        self.assertEqual(series_multiplier("bread", "entree"), 0.4)

    def test_rarity_miss_chance_ordering(self) -> None:
        self.assertGreater(rarity_miss_chance("common"), rarity_miss_chance("rare"))
        self.assertGreater(rarity_miss_chance("rare"), rarity_miss_chance("celestial"))

    def test_build_team_battle_cards(self) -> None:
        cards = build_team_battle_cards([(1, "SPG", 100, "0"), (2, "PEN", 150, "1")])
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0].instance_id, 1)
        self.assertGreater(cards[0].max_hp, 0)

    def test_resolve_attack_damage_in_range_and_nonzero(self) -> None:
        attacker = build_battle_card(1, "SPG", 100, "0")
        defender = build_battle_card(2, "PEN", 200, "1")

        rng = random.Random(123)
        result = resolve_attack(attacker, defender, defender_is_defending=False, rng=rng)
        if not result.missed:
            self.assertGreaterEqual(result.atk_roll, MIN_ROLL)
            self.assertLessEqual(result.atk_roll, MAX_ROLL)
            self.assertGreaterEqual(result.def_roll, MIN_ROLL)
            self.assertLessEqual(result.def_roll, MAX_ROLL)
            self.assertGreaterEqual(result.damage, 1)

    def test_defend_reduces_damage(self) -> None:
        attacker = build_battle_card(1, "SPG", 100, "0")
        defender = build_battle_card(2, "PEN", 200, "1")

        # Force deterministic non-miss and deterministic rolls.
        class _NoMissRandom(random.Random):
            def random(self) -> float:
                return 0.99

        rng = _NoMissRandom(7)

        def fixed_roll(_rng: random.Random) -> float:
            return 1.0

        no_defend = resolve_attack(
            attacker,
            defender,
            defender_is_defending=False,
            rng=rng,
            roll_sampler=fixed_roll,
        )
        with_defend = resolve_attack(
            attacker,
            defender,
            defender_is_defending=True,
            rng=rng,
            roll_sampler=fixed_roll,
        )

        self.assertFalse(no_defend.missed)
        self.assertFalse(with_defend.missed)
        self.assertGreater(no_defend.damage, with_defend.damage)


if __name__ == "__main__":
    unittest.main()
