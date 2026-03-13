import bisect
import math
import random
from collections import Counter
from functools import lru_cache
from typing import Callable, Mapping, TypedDict

from .settings import GENERATION_MAX, GENERATION_MIN

GENERATION_ROLL_TAU = 0.69


class CardValueRecord(TypedDict):
    rarity: str
    base_value: int


def compute_rarity_card_counts(
    card_catalog: Mapping[str, CardValueRecord],
) -> Counter[str]:
    return Counter(card["rarity"] for card in card_catalog.values())


def compute_normalized_rarity_weights(
    rarity_weights: Mapping[str, float | int],
    rarity_card_counts: Counter[str],
) -> dict[str, float]:
    return {rarity: weight / rarity_card_counts[rarity] for rarity, weight in rarity_weights.items() if rarity_card_counts.get(rarity, 0) > 0}


def effective_rarity_odds(
    *,
    normalized_rarity_weights: Mapping[str, float],
    rarity_card_counts: Counter[str],
) -> dict[str, float]:
    weighted_totals = {rarity: normalized_rarity_weights[rarity] * rarity_card_counts[rarity] for rarity in normalized_rarity_weights}
    grand_total = sum(weighted_totals.values())
    if grand_total <= 0:
        return {rarity: 0.0 for rarity in weighted_totals}
    return {rarity: weighted_totals[rarity] / grand_total for rarity in weighted_totals}


def target_rarity_odds(
    *,
    rarity_weights: Mapping[str, float | int],
    rarity_card_counts: Counter[str],
) -> dict[str, float]:
    active_weights = {rarity: weight for rarity, weight in rarity_weights.items() if rarity_card_counts.get(rarity, 0) > 0}
    total_weight = sum(active_weights.values())
    if total_weight <= 0:
        return {rarity: 0.0 for rarity in active_weights}
    return {rarity: active_weights[rarity] / total_weight for rarity in active_weights}


def card_base_value(card_type_id: str, *, card_catalog: Mapping[str, CardValueRecord]) -> int:
    return int(card_catalog[card_type_id]["base_value"])


def generation_value_multiplier(generation: int, *, generation_min: int, generation_max: int) -> float:
    clamped_generation = max(generation_min, min(generation_max, generation))
    progress = (generation_max - clamped_generation) / (generation_max - generation_min)
    return 1.0 + (2 * progress**2) + (9 * progress**9) + (49 * progress**49)


def card_value(
    card_type_id: str,
    generation: int,
    *,
    card_base_value_func: Callable[[str], int],
    generation_multiplier_func: Callable[[int], float],
    trait_multiplier: float = 1.0,
) -> int:
    base_value = card_base_value_func(card_type_id)
    multiplier = generation_multiplier_func(generation) * max(1.0, trait_multiplier)
    return max(1, int(round(base_value * multiplier)))


def random_card_id(
    *,
    card_catalog: Mapping[str, CardValueRecord],
    normalized_rarity_weights: Mapping[str, float],
) -> str:
    card_ids = list(card_catalog.keys())
    weights = [normalized_rarity_weights.get(card_catalog[cid]["rarity"], 1.0) for cid in card_ids]
    return random.choices(card_ids, weights=weights, k=1)[0]


def random_generation(*, generation_min: int, generation_max: int) -> int:
    if generation_min >= generation_max:
        return int(generation_min)

    generations, cdf = _generation_sampler(
        generation_min,
        generation_max,
        GENERATION_ROLL_TAU,
    )
    if not generations or not cdf:
        return random.randint(generation_min, generation_max)

    index = bisect.bisect_left(cdf, random.random())
    if index >= len(generations):
        index = len(generations) - 1
    return generations[index]


@lru_cache(maxsize=16)
def _generation_sampler(generation_min: int, generation_max: int, tau: float) -> tuple[tuple[int, ...], tuple[float, ...]]:
    if generation_min >= generation_max:
        return (int(generation_min),), (1.0,)

    generations = tuple(range(generation_min, generation_max + 1))
    multipliers = tuple(
        generation_value_multiplier(generation, generation_min=generation_min, generation_max=generation_max) for generation in generations
    )
    weights = tuple(1.0 / (multiplier**tau) for multiplier in multipliers)
    total = sum(weights)
    if total <= 0 or not math.isfinite(total):
        return (), ()

    running = 0.0
    cdf: list[float] = []
    for weight in weights:
        running += weight / total
        cdf.append(running)
    cdf[-1] = 1.0
    return generations, tuple(cdf)


_generation_sampler(GENERATION_MIN, GENERATION_MAX, GENERATION_ROLL_TAU)


def make_drop_choices(
    *,
    card_catalog: Mapping[str, CardValueRecord],
    random_card_id_func: Callable[[], str],
    random_generation_func: Callable[[], int],
    size: int = 3,
) -> list[tuple[str, int]]:
    if size >= len(card_catalog):
        card_ids = random.sample(list(card_catalog.keys()), len(card_catalog))
        return [(card_type_id, random_generation_func()) for card_type_id in card_ids]

    chosen: set[str] = set()
    while len(chosen) < size:
        chosen.add(random_card_id_func())
    return [(card_type_id, random_generation_func()) for card_type_id in chosen]


def burn_delta_range(value: int) -> int:
    percent = random.randint(5, 20)
    return max(1, int(round(value * (percent / 100.0))))


def get_burn_payout(
    card_type_id: str,
    generation: int,
    *,
    card_base_value_func: Callable[[str], int],
    generation_multiplier_func: Callable[[int], float],
    burn_delta_range_func: Callable[[int], int],
    trait_multiplier: float = 1.0,
    delta_range: int | None = None,
) -> tuple[int, int, int, int, float, int]:
    base_value = card_base_value_func(card_type_id)
    multiplier = generation_multiplier_func(generation) * max(1.0, trait_multiplier)
    value = max(1, int(round(base_value * multiplier)))
    resolved_delta_range = burn_delta_range_func(value) if delta_range is None else max(1, delta_range)
    delta = random.randint(-resolved_delta_range, resolved_delta_range)
    payout = max(1, value + delta)
    return payout, value, base_value, delta, multiplier, resolved_delta_range
