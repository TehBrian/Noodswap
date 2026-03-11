from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable

from .cards import CARD_CATALOG, card_value

# Miss chance tuned by rarity: lower rarity misses more often.
RARITY_MISS_CHANCE: dict[str, float] = {
    "common": 0.35,
    "uncommon": 0.30,
    "rare": 0.24,
    "epic": 0.18,
    "legendary": 0.13,
    "mythical": 0.10,
    "divine": 0.07,
    "celestial": 0.05,
}

SERIES_EFFECTIVENESS: dict[str, dict[str, float]] = {
    "wine": {"bread": 2.5, "cheese": 2.5, "dessert": 0.4, "snack": 0.4},
    "bread": {"entree": 0.4, "wine": 0.4, "cheese": 2.5, "ingredient": 2.5},
    "entree": {"bread": 2.5, "dessert": 0.4, "ingredient": 2.5, "snack": 2.5},
    "dessert": {"cheese": 0.4, "wine": 2.5, "snack": 2.5, "entree": 2.5},
    "cheese": {"wine": 0.4, "dessert": 2.5, "grain": 2.5, "ingredient": 0.4},
    "grain": {"noodle": 2.5, "snack": 0.4, "entree": 0.4, "ingredient": 2.5},
    "noodle": {"ingredient": 2.5, "grain": 0.4, "entree": 2.5, "bread": 2.5},
    "ingredient": {"entree": 0.4, "dessert": 2.5, "wine": 2.5, "noodle": 0.4},
    "snack": {"wine": 2.5, "grain": 2.5, "bread": 0.4, "entree": 0.4},
}

MIN_ROLL = 0.7
MAX_ROLL = 1.3
ROLL_SIGMA = 0.15
DEFEND_DAMAGE_MULTIPLIER = 0.6

# Series-specific attack verb templates. Use {card} for the attacker name and {damage} for the damage dealt.
SERIES_ATTACK_VERBS: dict[str, list[str]] = {
    "wine": [
        "{card} splashed their opponent, dealing {damage} damage!",
        "{card} doused the enemy in a bold pour, dealing {damage} damage!",
        "{card} swirled and sloshed, dealing {damage} damage!",
        "{card} uncorked a tidal wave, dealing {damage} damage!",
        "{card} baptized the opposition in tannins, dealing {damage} damage!",
        "{card} let loose a vinous flood, dealing {damage} damage!",
    ],
    "bread": [
        "{card} muffled their opponent under a dense loaf, dealing {damage} damage!",
        "{card} suffocated the enemy in doughy layers, dealing {damage} damage!",
        "{card} smothered the opposition with a thick crust, dealing {damage} damage!",
        "{card} buried the enemy beneath a pile of crumbs, dealing {damage} damage!",
        "{card} swatted their opponent with a crusty swing, dealing {damage} damage!",
        "{card} pressed down on the enemy with full loaf force, dealing {damage} damage!",
    ],
    "cheese": [
        "{card} aged the competition right out, dealing {damage} damage!",
        "{card} melted all over their opponent, dealing {damage} damage!",
        "{card} wedged into the enemy's defenses, dealing {damage} damage!",
        "{card} unleashed a pungent assault, dealing {damage} damage!",
        "{card} crumbled onto the opposition, dealing {damage} damage!",
        "{card} rinded the enemy into submission, dealing {damage} damage!",
    ],
    "dessert": [
        "{card} drowned their opponent in sweetness, dealing {damage} damage!",
        "{card} layered the competition in sugary ruin, dealing {damage} damage!",
        "{card} glazed the enemy into a stupor, dealing {damage} damage!",
        "{card} frosted over the opposition, dealing {damage} damage!",
        "{card} caramelized the enemy on the spot, dealing {damage} damage!",
        "{card} showered the opponent in confectionery chaos, dealing {damage} damage!",
    ],
    "entree": [
        "{card} plated the enemy for dinner, dealing {damage} damage!",
        "{card} served up a devastating portion, dealing {damage} damage!",
        "{card} sautéed their opponent into the ground, dealing {damage} damage!",
        "{card} slow-cooked the competition, dealing {damage} damage!",
        "{card} broiled the enemy to perfection, dealing {damage} damage!",
        "{card} reduced their opponent to a garnish, dealing {damage} damage!",
    ],
    "grain": [
        "{card} ground the enemy down, dealing {damage} damage!",
        "{card} threshed their opponent into dust, dealing {damage} damage!",
        "{card} pelted the competition with a grain storm, dealing {damage} damage!",
        "{card} hulled the enemy right through, dealing {damage} damage!",
        "{card} scattered the opposition with a mighty harvest, dealing {damage} damage!",
        "{card} milled the enemy into fine powder, dealing {damage} damage!",
    ],
    "noodle": [
        "{card} tangled up their opponent, dealing {damage} damage!",
        "{card} whipped the competition into shape, dealing {damage} damage!",
        "{card} ensnared the enemy in a noodle net, dealing {damage} damage!",
        "{card} lashed their opponent with a saucy strand, dealing {damage} damage!",
        "{card} coiled around the enemy and squeezed, dealing {damage} damage!",
        "{card} slapped the opposition with a wet noodle, dealing {damage} damage!",
    ],
    "ingredient": [
        "{card} infused the enemy with potent force, dealing {damage} damage!",
        "{card} seasoned the competition heavily, dealing {damage} damage!",
        "{card} marinated their opponent into submission, dealing {damage} damage!",
        "{card} extracted all resistance from the enemy, dealing {damage} damage!",
        "{card} distilled pure pain into the opposition, dealing {damage} damage!",
        "{card} reduced the enemy to base components, dealing {damage} damage!",
    ],
    "snack": [
        "{card} crunched their opponent mercilessly, dealing {damage} damage!",
        "{card} snapped the enemy's resolve in two, dealing {damage} damage!",
        "{card} pelted the competition with a rapid burst, dealing {damage} damage!",
        "{card} nibbled away at the enemy's defenses, dealing {damage} damage!",
        "{card} popped off on the opposition, dealing {damage} damage!",
        "{card} spiraled into the enemy with reckless abandon, dealing {damage} damage!",
    ],
}

_DEFAULT_ATTACK_VERBS = [
    "{card} struck their opponent, dealing {damage} damage!",
    "{card} delivered a decisive blow, dealing {damage} damage!",
    "{card} landed a clean hit, dealing {damage} damage!",
]


def series_attack_message(series: str, card_name: str, damage: int, rng: random.Random) -> str:
    pool = SERIES_ATTACK_VERBS.get(series, _DEFAULT_ATTACK_VERBS)
    template = rng.choice(pool)
    return template.format(card=f"**{card_name}**", damage=f"**{damage}**")


@dataclass(frozen=True)
class BattleCard:
    instance_id: int
    card_id: str
    generation: int
    dupe_code: str
    rarity: str
    series: str
    max_hp: int
    attack: int
    defense: int


@dataclass(frozen=True)
class DamageResult:
    missed: bool
    damage: int
    effectiveness: float
    atk_roll: float
    def_roll: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sample_bell_roll(rng: random.Random) -> float:
    return _clamp(rng.gauss(1.0, ROLL_SIGMA), MIN_ROLL, MAX_ROLL)


def series_multiplier(attacker_series: str, defender_series: str) -> float:
    return SERIES_EFFECTIVENESS.get(attacker_series, {}).get(defender_series, 1.0)


def rarity_miss_chance(rarity: str) -> float:
    return RARITY_MISS_CHANCE.get(rarity, 0.20)


def value_to_stats(value: int) -> tuple[int, int, int]:
    rooted = math.sqrt(max(1, value))
    hp = max(40, int(round(90 + (rooted * 9.5))))
    attack = max(8, int(round(10 + (rooted * 2.3))))
    defense = max(6, int(round(9 + (rooted * 1.9))))
    return hp, attack, defense


def build_battle_card(instance_id: int, card_id: str, generation: int, dupe_code: str) -> BattleCard:
    card = CARD_CATALOG[card_id]
    rarity = str(card["rarity"])
    series = str(card["series"])
    computed_value = card_value(card_id, generation)
    hp, attack, defense = value_to_stats(computed_value)
    return BattleCard(
        instance_id=instance_id,
        card_id=card_id,
        generation=generation,
        dupe_code=dupe_code,
        rarity=rarity,
        series=series,
        max_hp=hp,
        attack=attack,
        defense=defense,
    )


def build_team_battle_cards(instances: list[tuple[int, str, int, str]]) -> list[BattleCard]:
    return [build_battle_card(instance_id, card_id, generation, dupe_code) for instance_id, card_id, generation, dupe_code in instances]


def resolve_attack(
    attacker: BattleCard,
    defender: BattleCard,
    *,
    defender_is_defending: bool,
    rng: random.Random,
    roll_sampler: Callable[[random.Random], float] = sample_bell_roll,
) -> DamageResult:
    if rng.random() < rarity_miss_chance(attacker.rarity):
        return DamageResult(
            missed=True,
            damage=0,
            effectiveness=series_multiplier(attacker.series, defender.series),
            atk_roll=1.0,
            def_roll=1.0,
        )

    atk_roll = roll_sampler(rng)
    def_roll = roll_sampler(rng)
    effectiveness = series_multiplier(attacker.series, defender.series)

    attack_power = attacker.attack * atk_roll
    defense_power = defender.defense * def_roll
    mitigation = 100.0 / (100.0 + defense_power)
    raw_damage = attack_power * effectiveness * mitigation
    if defender_is_defending:
        raw_damage *= DEFEND_DAMAGE_MULTIPLIER

    damage = max(1, int(round(raw_damage)))
    return DamageResult(
        missed=False,
        damage=damage,
        effectiveness=effectiveness,
        atk_roll=atk_roll,
        def_roll=def_roll,
    )
