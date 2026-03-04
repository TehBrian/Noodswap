import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG, RARITY_CARD_COUNTS, effective_rarity_odds, target_rarity_odds
from noodswap.rarities import RARITY_WEIGHTS


def pct(value: float) -> str:
    return f"{value * 100:5.2f}%"


def main() -> None:
    target = target_rarity_odds()
    effective = effective_rarity_odds()

    ordered = list(RARITY_WEIGHTS.keys())

    print("Noodswap rarity odds report")
    print(f"Total cards in catalog: {len(CARD_CATALOG)}")
    print()
    print(f"{'Rarity':<10} {'Cards':>5} {'Target':>8} {'Effective':>10}")
    print("-" * 38)
    for rarity in ordered:
        if rarity not in target and rarity not in effective:
            continue
        count = RARITY_CARD_COUNTS.get(rarity, 0)
        print(
            f"{rarity:<10} {count:>5} {pct(target.get(rarity, 0.0)):>8} {pct(effective.get(rarity, 0.0)):>10}"
        )


if __name__ == '__main__':
    main()
