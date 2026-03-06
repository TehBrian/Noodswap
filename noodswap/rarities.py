from math import floor

RARITY_ORDER = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "legendary",
    "mythic",
    "divine",
    "celestial",
)

# Tuning knobs:
# - Increase RARITY_GROWTH_RATIO to make high-tier cards rarer.
# - Increase RARITY_TOTAL_WEIGHT for finer granularity without changing odds.
# - Keep RARITY_RAREST_WEIGHT at 1 to make celestial "godlike".
RARITY_GROWTH_RATIO = 2.8
RARITY_TOTAL_WEIGHT = 10_000
RARITY_RAREST_WEIGHT = 1


def build_rarity_weights(
    *,
    growth_ratio: float,
    total_weight: int,
    rarest_weight: int,
) -> dict[str, int]:
    """Build rarity weights from a geometric curve.

    The curve is generated from rarest->common and then normalized to
    ``total_weight`` while pinning the rarest tier to ``rarest_weight``.
    """
    if growth_ratio <= 1.0:
        raise ValueError("growth_ratio must be > 1.0")
    if total_weight <= rarest_weight:
        raise ValueError("total_weight must be > rarest_weight")
    if rarest_weight < 1:
        raise ValueError("rarest_weight must be >= 1")

    rarity_count = len(RARITY_ORDER)
    raw_rarest_to_common = [growth_ratio**idx for idx in range(rarity_count)]

    raw_tail_total = sum(raw_rarest_to_common[1:])
    normalized_budget = total_weight - rarest_weight
    scale = normalized_budget / raw_tail_total

    weighted_tail = [value * scale for value in raw_rarest_to_common[1:]]
    floored_tail = [int(floor(value)) for value in weighted_tail]
    remainder = normalized_budget - sum(floored_tail)

    # Largest remainder allocation keeps totals exact after integer rounding.
    fractions = sorted(
        enumerate(value - floor(value) for value in weighted_tail),
        key=lambda item: item[1],
        reverse=True,
    )
    for index, _fraction in fractions[:remainder]:
        floored_tail[index] += 1

    rarest_to_common = [rarest_weight, *floored_tail]
    common_to_rarest = list(reversed(rarest_to_common))
    return dict(zip(RARITY_ORDER, common_to_rarest, strict=True))


RARITY_WEIGHTS = build_rarity_weights(
    growth_ratio=RARITY_GROWTH_RATIO,
    total_weight=RARITY_TOTAL_WEIGHT,
    rarest_weight=RARITY_RAREST_WEIGHT,
)
