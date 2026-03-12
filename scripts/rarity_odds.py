import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import (
    CARD_CATALOG,
    RARITY_CARD_COUNTS,
    effective_rarity_odds,
    target_rarity_odds,
)
from noodswap.rarities import (
    RARITY_CURVE_LINEAR_RATE,
    RARITY_CURVE_SMOOTHING,
    RARITY_TAIL_CURVATURE,
    RARITY_ORDER,
    RARITY_TOTAL_WEIGHT,
    RARITY_WEIGHTS,
    build_rarity_weights,
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
            "Print rarity odds, including per-card, per-drop, and approximate per-player chances. "
            "If a curve argument is set, weights are generated dynamically from the formula."
        )
    )
    parser.add_argument(
        "--linear-rate",
        type=float,
        default=None,
        help=(
            "Generate weights from curved-exponential formula using this linear rate "
            f"(configured default: {RARITY_CURVE_LINEAR_RATE})."
        ),
    )
    parser.add_argument(
        "--tail-curvature",
        type=float,
        default=RARITY_TAIL_CURVATURE,
        help=(
            "Tail steepness for curved-exponential formula "
            f"(configured default: {RARITY_TAIL_CURVATURE})."
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
        default=RARITY_CURVE_SMOOTHING,
        help=(
            "Global curve smoothing; higher values flatten top-tier rarity "
            f"(configured default: {RARITY_CURVE_SMOOTHING})."
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
        default=RARITY_TOTAL_WEIGHT,
        help=f"Total sum of generated weights (default: {RARITY_TOTAL_WEIGHT}).",
    )
    parser.add_argument(
        "--drop-size",
        type=int,
        default=3,
        help="How many cards appear in each drop (default: 3).",
    )
    parser.add_argument(
        "--claims-per-player",
        type=int,
        default=1,
        help="Approx cards a player claims per drop for personal odds (default: 1).",
    )
    return parser.parse_args()


def print_configured_weights_report(*, drop_size: int, claims_per_player: int) -> None:
    target = target_rarity_odds()
    effective = effective_rarity_odds()

    ordered = list(RARITY_WEIGHTS.keys())

    print("Noodswap rarity odds report")
    print("Source: configured noodswap.rarities.RARITY_WEIGHTS")
    print(f"Total cards in catalog: {len(CARD_CATALOG)}")
    print(f"Cards per drop: {drop_size}")
    print(f"Approx claims per player per drop: {claims_per_player}")
    print()
    print(
        f"{'Rarity':<10} {'Cards':>5} {'Target':>8} {'Effective':>10} {'PerCard':>9} {'PerDrop':>9} {'PerPlayer':>10}"
    )
    print("-" * 80)
    for rarity in ordered:
        if rarity not in target and rarity not in effective:
            continue
        count = RARITY_CARD_COUNTS.get(rarity, 0)
        per_card = target.get(rarity, 0.0)
        per_drop = at_least_one(per_card, drop_size)
        per_player = at_least_one(per_card, claims_per_player)
        print(
            f"{rarity:<10} {count:>5} {pct(per_card):>8} {pct(effective.get(rarity, 0.0)):>10}"
            f" {inv(per_card):>9} {inv(per_drop):>9} {inv(per_player):>10}"
        )


def print_generated_weights_report(
    *,
    linear_rate: float | None,
    tail_curvature: float,
    shape: float | None,
    total_weight: int,
    smoothing: float,
    growth_ratio: float | None,
    drop_size: int,
    claims_per_player: int,
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

    print("Noodswap rarity odds report")
    print("Source: curved-exponential formula-generated weights")
    print(
        "linear_rate="
        f"{linear_rate if linear_rate is not None else 'auto'}, "
        f"tail_curvature={tail_curvature}, "
        f"shape={shape if shape is not None else 'n/a'}, "
        f"growth_ratio={growth_ratio if growth_ratio is not None else 'n/a'}, "
        f"smoothing={smoothing}, total_weight={total_weight}"
    )
    print(f"Cards per drop: {drop_size}")
    print(f"Approx claims per player per drop: {claims_per_player}")
    print()
    print(f"Generated weights: {weights}")
    print()
    print(
        f"{'Rarity':<10} {'Weight':>7} {'PerCard':>9} {'PerDrop':>9} {'PerPlayer':>10}"
    )
    print("-" * 53)
    for rarity in RARITY_ORDER:
        per_card = odds.get(rarity, 0.0)
        per_drop = at_least_one(per_card, drop_size)
        per_player = at_least_one(per_card, claims_per_player)
        print(
            f"{rarity:<10} {weights[rarity]:>7} {inv(per_card):>9} {inv(per_drop):>9} {inv(per_player):>10}"
        )


def main() -> None:
    args = parse_args()

    if args.drop_size < 1:
        raise ValueError("--drop-size must be >= 1")
    if args.claims_per_player < 1:
        raise ValueError("--claims-per-player must be >= 1")

    if args.linear_rate is None and args.shape is None and args.growth_ratio is None:
        print_configured_weights_report(
            drop_size=args.drop_size,
            claims_per_player=args.claims_per_player,
        )
        return

    print_generated_weights_report(
        linear_rate=args.linear_rate,
        tail_curvature=args.tail_curvature,
        shape=args.shape,
        total_weight=args.total_weight,
        smoothing=args.smoothing,
        growth_ratio=args.growth_ratio,
        drop_size=args.drop_size,
        claims_per_player=args.claims_per_player,
    )


if __name__ == "__main__":
    main()
