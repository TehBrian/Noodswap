import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.rarities import RARITY_ORDER, build_rarity_weights
from bot.trait_rarities import (
    TRAIT_CURVE_LINEAR_RATE,
    TRAIT_CURVE_SMOOTHING,
    TRAIT_CURVE_TAIL_CURVATURE,
    TRAIT_RARITY_MULTIPLIERS,
    TRAIT_RARITY_WEIGHTS,
    TRAIT_TOTAL_WEIGHT,
)


def pct(value: float) -> str:
    return f"{value * 100:5.2f}%"


def inv(value: float) -> str:
    if value <= 0.0:
        return "n/a"
    return f"1/{round(1.0 / value):,}"


def at_least_one(success_rate: float, trials: int) -> float:
    if success_rate <= 0.0:
        return 0.0
    if success_rate >= 1.0:
        return 1.0
    if trials <= 0:
        return 0.0
    return 1.0 - ((1.0 - success_rate) ** trials)


def odds_from_weights(weights: dict[str, int]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {rarity: 0.0 for rarity in weights}
    return {rarity: weight / total for rarity, weight in weights.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print trait rarity odds and multipliers. If a curve argument is set, "
            "weights are generated dynamically from the same formula used by bot trait rarities."
        )
    )
    parser.add_argument(
        "--linear-rate",
        type=float,
        default=None,
        help=(
            "Generate weights from curved-exponential formula using this linear rate "
            f"(configured default: {TRAIT_CURVE_LINEAR_RATE})."
        ),
    )
    parser.add_argument(
        "--tail-curvature",
        type=float,
        default=TRAIT_CURVE_TAIL_CURVATURE,
        help=(
            "Tail steepness for curved-exponential formula "
            f"(configured default: {TRAIT_CURVE_TAIL_CURVATURE})."
        ),
    )
    parser.add_argument(
        "--shape",
        type=float,
        default=None,
        help="Legacy compatibility mode; converted internally to linear-rate baseline.",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=TRAIT_CURVE_SMOOTHING,
        help=(
            "Global curve smoothing; higher values flatten top-tier rarity "
            f"(configured default: {TRAIT_CURVE_SMOOTHING})."
        ),
    )
    parser.add_argument(
        "--growth-ratio",
        type=float,
        default=None,
        help="Legacy compatibility mode; converted internally to power-law shape.",
    )
    parser.add_argument(
        "--total-weight",
        type=int,
        default=TRAIT_TOTAL_WEIGHT,
        help=f"Total sum of generated weights (default: {TRAIT_TOTAL_WEIGHT}).",
    )
    parser.add_argument(
        "--traits-per-roll",
        type=int,
        default=1,
        help="How many trait rolls happen in one event (default: 1).",
    )
    parser.add_argument(
        "--rolls-per-player",
        type=int,
        default=1,
        help="Approx trait rolls a player gets for personal odds (default: 1).",
    )
    return parser.parse_args()


def print_configured_weights_report(*, traits_per_roll: int, rolls_per_player: int) -> None:
    odds = odds_from_weights(TRAIT_RARITY_WEIGHTS)

    print("Noodswap trait rarity odds report")
    print("Source: configured bot.trait_rarities.TRAIT_RARITY_WEIGHTS")
    print(f"Traits per roll event: {traits_per_roll}")
    print(f"Approx rolls per player event: {rolls_per_player}")
    print()
    print(f"{'Rarity':<10} {'Weight':>7} {'Odds':>8} {'PerRoll':>9} {'PerPlayer':>10} {'ValueMult':>10}")
    print("-" * 70)
    for rarity in RARITY_ORDER:
        per_trait = odds.get(rarity, 0.0)
        per_roll_event = at_least_one(per_trait, traits_per_roll)
        per_player_event = at_least_one(per_trait, rolls_per_player)
        mult = TRAIT_RARITY_MULTIPLIERS.get(rarity, 1.0)
        print(
            f"{rarity:<10} {TRAIT_RARITY_WEIGHTS.get(rarity, 0):>7} {pct(per_trait):>8}"
            f" {inv(per_roll_event):>9} {inv(per_player_event):>10} {mult:>9.2f}x"
        )


def print_generated_weights_report(
    *,
    linear_rate: float | None,
    tail_curvature: float,
    shape: float | None,
    total_weight: int,
    smoothing: float,
    growth_ratio: float | None,
    traits_per_roll: int,
    rolls_per_player: int,
) -> None:
    weights = build_rarity_weights(
        linear_rate=linear_rate,
        tail_curvature=tail_curvature,
        shape=shape,
        total_weight=total_weight,
        smoothing=smoothing,
        growth_ratio=growth_ratio,
    )
    odds = odds_from_weights(weights)

    print("Noodswap trait rarity odds report")
    print("Source: curved-exponential formula-generated weights")
    print(
        "linear_rate="
        f"{linear_rate if linear_rate is not None else 'auto'}, "
        f"tail_curvature={tail_curvature}, "
        f"shape={shape if shape is not None else 'n/a'}, "
        f"growth_ratio={growth_ratio if growth_ratio is not None else 'n/a'}, "
        f"smoothing={smoothing}, total_weight={total_weight}"
    )
    print(f"Traits per roll event: {traits_per_roll}")
    print(f"Approx rolls per player event: {rolls_per_player}")
    print()
    print(f"Generated weights: {weights}")
    print()
    print(f"{'Rarity':<10} {'Weight':>7} {'PerTrait':>9} {'PerRoll':>9} {'PerPlayer':>10} {'ValueMult':>10}")
    print("-" * 73)
    for rarity in RARITY_ORDER:
        per_trait = odds.get(rarity, 0.0)
        per_roll_event = at_least_one(per_trait, traits_per_roll)
        per_player_event = at_least_one(per_trait, rolls_per_player)
        mult = TRAIT_RARITY_MULTIPLIERS.get(rarity, 1.0)
        print(
            f"{rarity:<10} {weights.get(rarity, 0):>7} {inv(per_trait):>9}"
            f" {inv(per_roll_event):>9} {inv(per_player_event):>10} {mult:>9.2f}x"
        )


def main() -> None:
    args = parse_args()

    if args.traits_per_roll < 1:
        raise ValueError("--traits-per-roll must be >= 1")
    if args.rolls_per_player < 1:
        raise ValueError("--rolls-per-player must be >= 1")

    if args.linear_rate is None and args.shape is None and args.growth_ratio is None:
        print_configured_weights_report(
            traits_per_roll=args.traits_per_roll,
            rolls_per_player=args.rolls_per_player,
        )
        return

    print_generated_weights_report(
        linear_rate=args.linear_rate,
        tail_curvature=args.tail_curvature,
        shape=args.shape,
        total_weight=args.total_weight,
        smoothing=args.smoothing,
        growth_ratio=args.growth_ratio,
        traits_per_roll=args.traits_per_roll,
        rolls_per_player=args.rolls_per_player,
    )


if __name__ == "__main__":
    main()
