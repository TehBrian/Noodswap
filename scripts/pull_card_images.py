import argparse
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG, CARD_IMAGE_URLS

SERIES_HINTS = {
    "noodles": "pasta",
    "pasta": "pasta",
    "bread": "bread",
    "cheese": "cheese",
    "dessert": "dessert",
    "wine": "wine",
}

SEARCH_OVERRIDES = {
    "MOZ": "Mozzarella",
    "CHJ": "Colby-Jack cheese",
    "ESC": "Cheddar cheese",
    "SHC": "Cheddar cheese",
    "TRF": "Pecorino Romano",
    "GRA": "Artisan bread loaf",
    "IMM": "Garlic bread",
    "TRG": "Garlic bread",
    "BLA": "Ravioli",
    "GOL": "Parmigiano-Reggiano",
    "AMS": "Amarone wine",
    "NOO": "Flying Spaghetti Monster",
    "FUS": "Fusilli",
    "ROT": "Rotini pasta",
    "BAT": "Sourdough batard",
    "HAV": "Havarti cheese",
    "PIN": "Pinot Noir wine glass",
    "MER": "Merlot wine",
    "CHB": "Chardonnay wine bottle and glass",
    "SOV": "Sauvignon Blanc wine",
    "RIO": "Rioja wine",
    "ICE": "Ice wine bottle",
}

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "NoodswapBot/1.0 (card image sync helper)"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class PullResult:
    card_id: str
    name: str
    current_image: str | None
    found_image: str | None
    source: str | None
    query_used: str | None


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def _wikipedia_thumbnail(query: str) -> str | None:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "3",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": "1000",
    }
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(params)
    data = _request_json(url)
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            return str(thumb)
    return None


def _commons_file_image(query: str) -> str | None:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "12",
        "prop": "imageinfo",
        "iiprop": "url",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    data = _request_json(url)
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        image_url = str(infos[0].get("url") or "")
        lower = image_url.lower()
        if any(lower.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            return image_url
    return None


def _search_queries(card_id: str, card_name: str, series: str) -> list[str]:
    if card_id in SEARCH_OVERRIDES:
        return [SEARCH_OVERRIDES[card_id]]

    queries: list[str] = [card_name]
    hint = SERIES_HINTS.get(series)
    if hint and hint not in card_name.lower():
        queries.append(f"{card_name} {hint}")
        queries.append(f"{card_name} ({hint})")

    cleaned = "".join(ch for ch in card_name if ch.isalnum() or ch.isspace()).strip()
    if cleaned and cleaned not in queries:
        queries.append(cleaned)

    return queries


def pull_card_images(only_missing: bool, card_ids: set[str] | None = None) -> list[PullResult]:
    results: list[PullResult] = []

    for card_id, card in CARD_CATALOG.items():
        if card_ids is not None and card_id not in card_ids:
            continue

        existing = CARD_IMAGE_URLS.get(card_id)
        if only_missing and existing:
            continue

        queries = _search_queries(card_id, card["name"], card["series"])
        found_image: str | None = None
        source: str | None = None
        query_used: str | None = None

        for query in queries:
            found_image = _wikipedia_thumbnail(query)
            if found_image:
                source = "wikipedia-thumbnail"
                query_used = query
                break

            found_image = _commons_file_image(query)
            if found_image:
                source = "commons-file"
                query_used = query
                break

        results.append(
            PullResult(
                card_id=card_id,
                name=card["name"],
                current_image=existing,
                found_image=found_image,
                source=source,
                query_used=query_used,
            )
        )

    return results


def write_report(results: list[PullResult], output_path: Path, only_missing: bool) -> None:
    found = [r for r in results if r.found_image]
    missing = [r for r in results if not r.found_image]

    payload = {
        "mode": "missing-only" if only_missing else "all-cards",
        "catalog_size": len(CARD_CATALOG),
        "processed": len(results),
        "found": len(found),
        "missing": len(missing),
        "mapping": {r.card_id: r.found_image for r in found if r.found_image},
        "details": [
            {
                "card_id": r.card_id,
                "name": r.name,
                "current_image": r.current_image,
                "found_image": r.found_image,
                "source": r.source,
                "query_used": r.query_used,
            }
            for r in results
        ],
    }

    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull card image URLs from Wikimedia sources.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all cards in CARD_CATALOG (default is only cards missing CARD_IMAGE_URLS entries).",
    )
    parser.add_argument(
        "--output",
        default="card_image_pull_report.json",
        help="Path to write JSON report.",
    )
    parser.add_argument(
        "--card-ids",
        default="",
        help="Comma-separated card IDs to process (optional).",
    )
    args = parser.parse_args()

    only_missing = not args.all
    output_path = Path(args.output).resolve()
    requested_ids = {
        token.strip().upper()
        for token in args.card_ids.split(",")
        if token.strip()
    }
    card_ids = requested_ids or None

    results = pull_card_images(only_missing=only_missing, card_ids=card_ids)
    write_report(results, output_path, only_missing=only_missing)

    found = sum(1 for r in results if r.found_image)
    missing = len(results) - found

    print("Card image pull complete")
    print(f"Catalog size: {len(CARD_CATALOG)}")
    print(f"Processed: {len(results)}")
    print(f"Found: {found}")
    print(f"Missing: {missing}")
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
