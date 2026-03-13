import argparse
import json
from pathlib import Path

DEFAULT_CARDS_PATH = Path("bot/data/cards.json")
DEFAULT_BASE_VALUES_PATH = Path("bot/data/base_values.json")

# Tuned for strong rarity separation with a steeper late-tier curve and
# celestial values capped at 1200.
RARITY_VALUE_BANDS: dict[str, tuple[int, int]] = {
    "common": (5, 30),
    "uncommon": (40, 70),
    "rare": (85, 145),
    "epic": (170, 260),
    "legendary": (300, 420),
    "mythical": (480, 650),
    "divine": (740, 930),
    "celestial": (1040, 1200),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute card base values by rarity band and write them to a JSON map. Use --mode missing to fill only IDs without base values."
        )
    )
    parser.add_argument(
        "--cards-file",
        type=Path,
        default=DEFAULT_CARDS_PATH,
        help=f"Card metadata JSON path (default: {DEFAULT_CARDS_PATH})",
    )
    parser.add_argument(
        "--base-values-file",
        type=Path,
        default=DEFAULT_BASE_VALUES_PATH,
        help=f"Base values JSON path (default: {DEFAULT_BASE_VALUES_PATH})",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "missing"),
        default="all",
        help="all: rewrite every base value; missing: only write missing IDs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show summary without writing output file",
    )
    return parser.parse_args()


def _load_cards(cards_file: Path) -> dict[str, dict[str, str]]:
    parsed = json.loads(cards_file.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Invalid cards JSON: {cards_file}")

    cards: dict[str, dict[str, str]] = {}
    for card_type_id, value in parsed.items():
        if not isinstance(card_type_id, str) or not isinstance(value, dict):
            continue
        rarity = value.get("rarity")
        if isinstance(rarity, str):
            cards[card_type_id] = value
    return cards


def _load_base_values(base_values_file: Path) -> dict[str, int]:
    if not base_values_file.exists():
        return {}

    parsed = json.loads(base_values_file.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Invalid base values JSON: {base_values_file}")

    base_values: dict[str, int] = {}
    for card_type_id, value in parsed.items():
        if isinstance(card_type_id, str) and isinstance(value, int):
            base_values[card_type_id] = value
    return base_values


def _compute_values(
    cards: dict[str, dict[str, str]],
    existing_base_values: dict[str, int],
) -> dict[str, int]:
    computed: dict[str, int] = {}

    for rarity, (low, high) in RARITY_VALUE_BANDS.items():
        rarity_card_ids = [card_type_id for card_type_id, card in cards.items() if card.get("rarity") == rarity]
        if not rarity_card_ids:
            continue

        ranked_ids = sorted(
            rarity_card_ids,
            key=lambda card_type_id: (existing_base_values.get(card_type_id, 0), card_type_id),
        )

        if len(ranked_ids) == 1:
            computed[ranked_ids[0]] = low
            continue

        span = high - low
        last_idx = len(ranked_ids) - 1
        for idx, card_type_id in enumerate(ranked_ids):
            computed[card_type_id] = int(round(low + (span * idx / last_idx)))

    return computed


def main() -> None:
    args = _parse_args()
    cards_file = args.cards_file.expanduser().resolve()
    base_values_file = args.base_values_file.expanduser().resolve()

    cards = _load_cards(cards_file)
    existing_base_values = _load_base_values(base_values_file)
    computed_values = _compute_values(cards, existing_base_values)

    if args.mode == "all":
        merged_values = dict(computed_values)
    else:
        merged_values = dict(existing_base_values)
        for card_type_id, computed_value in computed_values.items():
            if card_type_id not in merged_values:
                merged_values[card_type_id] = computed_value

    missing_after_merge = sorted(card_type_id for card_type_id in cards if card_type_id not in merged_values)

    print(f"Cards loaded: {len(cards)}")
    print(f"Existing base values: {len(existing_base_values)}")
    print(f"Computed base values: {len(computed_values)}")
    print(f"Mode: {args.mode}")
    print(f"Output entries: {len(merged_values)}")
    if missing_after_merge:
        print(f"Warning: {len(missing_after_merge)} cards still missing base values")

    if args.dry_run:
        return

    base_values_file.parent.mkdir(parents=True, exist_ok=True)
    base_values_file.write_text(json.dumps(merged_values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote: {base_values_file}")


if __name__ == "__main__":
    main()
