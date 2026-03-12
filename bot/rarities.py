import warnings
from math import exp, floor, log

RARITY_ORDER = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "legendary",
    "mythical",
    "divine",
    "celestial",
)

# Tuning knobs:
# - Increase RARITY_CURVE_LINEAR_RATE to make high-tier cards rarer overall.
# - Increase RARITY_TAIL_CURVATURE to make top tiers drop off faster than mid tiers.
# - Increase RARITY_TOTAL_WEIGHT for finer granularity without changing odds.
# - Increase RARITY_CURVE_SMOOTHING to flatten the curve (top tiers become less rare).
#
# The curved-exponential form is:
#   raw(rank) = exp(linear_rate * rank + tail_curvature * rank^2)
# where rank=0 is celestial and rank=7 is common.
RARITY_CURVE_LINEAR_RATE = 0.59
RARITY_TAIL_CURVATURE = 0.023
RARITY_TOTAL_WEIGHT = 30_000
RARITY_CURVE_SMOOTHING = 0.02


def _shape_from_legacy_growth_ratio(growth_ratio: float, rarity_count: int) -> float:
    """Convert old geometric growth ratio into an equivalent power-law shape.

    This preserves the common-to-rarest ratio so old tuning can migrate with
    similar feel before fine-tuning the new shape parameter.
    """
    if growth_ratio <= 1.0:
        raise ValueError("growth_ratio must be > 1.0")
    if rarity_count < 2:
        raise ValueError("rarity_count must be >= 2")
    return ((rarity_count - 1) * log(growth_ratio)) / log(rarity_count)


def _linear_rate_from_power_shape(shape: float, rarity_count: int) -> float:
    """Convert old power-law shape into equivalent linear exponential slope.

    Matches the common-to-rarest ratio so existing tuning values can migrate
    with similar overall spread.
    """
    if shape <= 0.0:
        raise ValueError("shape must be > 0.0")
    if rarity_count < 2:
        raise ValueError("rarity_count must be >= 2")
    return (shape * log(rarity_count)) / (rarity_count - 1)


def _enforce_strict_monotonic_common_to_rarest(weights: list[int]) -> list[int]:
    """Ensure strict descending weights while preserving total sum."""
    adjusted = list(weights)

    deficit = 0
    for reverse_offset, _ in enumerate(reversed(adjusted[:-1]), start=1):
        index = len(adjusted) - 1 - reverse_offset
        minimum = adjusted[index + 1] + 1
        if adjusted[index] < minimum:
            needed = minimum - adjusted[index]
            adjusted[index] = minimum
            deficit += needed

    if deficit == 0:
        return adjusted

    for index, _value in enumerate(adjusted):
        right = adjusted[index + 1] if index < len(adjusted) - 1 else 0
        minimum = right + 1 if index < len(adjusted) - 1 else 1
        room = adjusted[index] - minimum
        if room <= 0:
            continue
        taken = min(room, deficit)
        adjusted[index] -= taken
        deficit -= taken
        if deficit == 0:
            return adjusted

    raise ValueError("Unable to enforce strict monotonicity; increase total_weight")


def build_rarity_weights(
    *,
    linear_rate: float | None = None,
    tail_curvature: float = 0.0,
    shape: float | None = None,
    total_weight: int,
    smoothing: float = 0.0,
    growth_ratio: float | None = None,
    rarest_weight: int | None = None,
) -> dict[str, int]:
    """Build rarity weights from a curved-exponential curve.

    Primary controls:
    - ``linear_rate``: higher values make high tiers rarer overall.
    - ``tail_curvature``: higher values steepen top-tier rarity drop-off.
    - ``smoothing``: higher values flatten the curve.

    Legacy migration:
    - ``shape`` is accepted and converted into ``linear_rate``.
    - ``growth_ratio`` is accepted and converted into an equivalent shape.
    - ``rarest_weight`` is deprecated and intentionally ignored.
    """
    rarity_count = len(RARITY_ORDER)
    minimum_strict_total = rarity_count * (rarity_count + 1) // 2
    if total_weight < minimum_strict_total:
        raise ValueError(f"total_weight must be >= {minimum_strict_total}")
    if smoothing < 0.0:
        raise ValueError("smoothing must be >= 0.0")
    if tail_curvature < 0.0:
        raise ValueError("tail_curvature must be >= 0.0")

    resolved_linear_rate = linear_rate
    if resolved_linear_rate is None:
        resolved_shape = shape
        if resolved_shape is None:
            if growth_ratio is None:
                raise ValueError("linear_rate is required when shape/growth_ratio are not provided")
            resolved_shape = _shape_from_legacy_growth_ratio(growth_ratio, rarity_count)
        resolved_linear_rate = _linear_rate_from_power_shape(resolved_shape, rarity_count)

    if resolved_linear_rate <= 0.0:
        raise ValueError("linear_rate must be > 0.0")

    if rarest_weight is not None:
        _ = rarest_weight
        warnings.warn(
            "`rarest_weight` is deprecated and ignored; use linear_rate/tail_curvature/smoothing.",
            DeprecationWarning,
            stacklevel=2,
        )

    steepness_scale = 1.0 / (1.0 + smoothing)
    raw_rarest_to_common = [
        exp((resolved_linear_rate * steepness_scale * (index + 1)) + (tail_curvature * steepness_scale * (index + 1) ** 2))
        for index in range(rarity_count)
    ]
    raw_total = sum(raw_rarest_to_common)
    scaled_rarest_to_common = [value * total_weight / raw_total for value in raw_rarest_to_common]
    floored_rarest_to_common = [int(floor(value)) for value in scaled_rarest_to_common]
    remainder = total_weight - sum(floored_rarest_to_common)

    # Largest remainder allocation keeps totals exact after integer rounding.
    fractions = sorted(
        enumerate(value - floor(value) for value in scaled_rarest_to_common),
        key=lambda item: item[1],
        reverse=True,
    )
    for index, _fraction in fractions[:remainder]:
        floored_rarest_to_common[index] += 1

    common_to_rarest = list(reversed(floored_rarest_to_common))
    common_to_rarest = _enforce_strict_monotonic_common_to_rarest(common_to_rarest)
    return dict(zip(RARITY_ORDER, common_to_rarest, strict=True))


RARITY_WEIGHTS = build_rarity_weights(
    linear_rate=RARITY_CURVE_LINEAR_RATE,
    tail_curvature=RARITY_TAIL_CURVATURE,
    total_weight=RARITY_TOTAL_WEIGHT,
    smoothing=RARITY_CURVE_SMOOTHING,
)
