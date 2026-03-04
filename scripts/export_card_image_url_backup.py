import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG


def build_backup_payload() -> dict[str, object]:
    mapping: dict[str, str] = {}
    for card_id, card in CARD_CATALOG.items():
        image_url = card.get("image")
        if isinstance(image_url, str) and image_url:
            mapping[card_id] = image_url

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "card_count": len(CARD_CATALOG),
        "url_count": len(mapping),
        "mapping": dict(sorted(mapping.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export current card image URL mapping to a backup file.")
    parser.add_argument(
        "--output",
        default="assets/card_images/url_backup.json",
        help="Output path for backup JSON.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_backup_payload()
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Exported URL backup to: {output_path}")
    print(f"Cards: {payload['card_count']} | URLs: {payload['url_count']}")


if __name__ == "__main__":
    main()
