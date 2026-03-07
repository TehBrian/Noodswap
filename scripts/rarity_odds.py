import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG, RARITY_CARD_COUNTS, effective_rarity_odds, target_rarity_odds
from noodswap.rarities import (
    RARITY_ORDER,
    RARITY_RAREST_WEIGHT,
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
            "If --growth-ratio is set, weights are generated dynamically from the formula."
        )
    )
    parser.add_argument(
        "--growth-ratio",
        type=float,
        default=None,
        help="Generate weights from formula using this growth ratio (example: 2.8).",
    )
    parser.add_argument(
        "--total-weight",
        type=int,
        default=RARITY_TOTAL_WEIGHT,
        help=f"Total sum of generated weights (default: {RARITY_TOTAL_WEIGHT}).",
    )
    parser.add_argument(
        "--rarest-weight",
        type=int,
        default=RARITY_RAREST_WEIGHT,
        help=f"Weight for rarest tier (default: {RARITY_RAREST_WEIGHT}).",
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
    growth_ratio: float,
    total_weight: int,
    rarest_weight: int,
    drop_size: int,
    claims_per_player: int,
) -> None:
    weights = build_rarity_weights(
        growth_ratio=growth_ratio,
        total_weight=total_weight,
        rarest_weight=rarest_weight,
    )
    odds = odds_from_weights(weights)

    print("Noodswap rarity odds report")
    print("Source: formula-generated weights")
    print(f"growth_ratio={growth_ratio}, total_weight={total_weight}, rarest_weight={rarest_weight}")
    print(f"Cards per drop: {drop_size}")
    print(f"Approx claims per player per drop: {claims_per_player}")
    print()
    print(f"Generated weights: {weights}")
    print()
    print(f"{'Rarity':<10} {'Weight':>7} {'PerCard':>9} {'PerDrop':>9} {'PerPlayer':>10}")
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

    if args.growth_ratio is None:
        print_configured_weights_report(
            drop_size=args.drop_size,
            claims_per_player=args.claims_per_player,
        )
        return

    print_generated_weights_report(
        growth_ratio=args.growth_ratio,
        total_weight=args.total_weight,
        rarest_weight=args.rarest_weight,
        drop_size=args.drop_size,
        claims_per_player=args.claims_per_player,
    )


if __name__ == '__main__':
    main()
