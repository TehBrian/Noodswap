import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG, CARD_IMAGE_URLS

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "NoodswapBot/1.0 (distinct image resolver)"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
STOPWORDS = {
    "the",
    "and",
    "with",
    "from",
    "for",
    "alla",
    "alla",
    "della",
    "del",
    "di",
    "de",
    "la",
    "al",
    "con",
}

SERIES_HINTS = {
    "noodles": "noodle dish",
    "pasta": "pasta",
    "bread": "bread",
    "cheese": "cheese",
    "dessert": "dessert",
    "wine": "wine",
}


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def _commons_candidates(query: str, limit: int = 30) -> list[str]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    data = _request_json(url)
    pages = (data.get("query") or {}).get("pages") or {}

    candidates: list[str] = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        image_url = str(infos[0].get("url") or "")
        lower = image_url.lower()
        if any(lower.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            candidates.append(image_url)
    return candidates


def _wikipedia_thumb_candidates(query: str, limit: int = 8) -> list[str]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": str(limit),
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": "1280",
    }
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(params)
    data = _request_json(url)
    pages = (data.get("query") or {}).get("pages") or {}

    candidates: list[str] = []
    for page in pages.values():
        thumb = (page.get("thumbnail") or {}).get("source")
        if isinstance(thumb, str) and thumb:
            candidates.append(thumb)
    return candidates


def _search_queries(card_name: str, series: str) -> list[str]:
    hint = SERIES_HINTS.get(series, "")
    cleaned = "".join(ch for ch in card_name if ch.isalnum() or ch.isspace()).strip()

    queries = [card_name]
    if hint and hint not in card_name.lower():
        queries.append(f"{card_name} {hint}")
    if cleaned and cleaned != card_name:
        queries.append(cleaned)
        if hint and hint not in cleaned.lower():
            queries.append(f"{cleaned} {hint}")

    if hint:
        queries.append(f"{card_name} food")

    deduped: list[str] = []
    for query in queries:
        if query not in deduped:
            deduped.append(query)
    return deduped


def _tokenize(value: str) -> set[str]:
    lowered = value.lower()
    tokens = {t for t in re.split(r"[^a-z0-9]+", lowered) if len(t) >= 3 and t not in STOPWORDS}
    return tokens


def _url_tokens(url: str) -> set[str]:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    return _tokenize(path)


def _target_tokens(card_name: str, series: str) -> set[str]:
    tokens = _tokenize(card_name)
    hint = SERIES_HINTS.get(series)
    if hint:
        tokens.update(_tokenize(hint))
    tokens.add(series.lower())
    return tokens


def _candidate_score(url: str, card_name: str, series: str) -> int:
    targets = _target_tokens(card_name, series)
    source_tokens = _url_tokens(url)
    overlap = targets & source_tokens
    if not overlap:
        return -1

    score = len(overlap) * 3
    card_slug_tokens = _tokenize(card_name)
    if card_slug_tokens and card_slug_tokens.issubset(source_tokens):
        score += 6
    if series.lower() in source_tokens:
        score += 2
    return score


def _normalized(url: str) -> str:
    return url.strip()


def _duplicate_groups(mapping: dict[str, str]) -> dict[str, list[str]]:
    by_url: dict[str, list[str]] = defaultdict(list)
    for card_id, image_url in mapping.items():
        by_url[_normalized(image_url)].append(card_id)
    return {url: ids for url, ids in by_url.items() if len(ids) > 1}


def _pick_replacements(mapping: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    duplicates = _duplicate_groups(mapping)
    used_urls = {_normalized(url) for url in mapping.values()}
    replacements: dict[str, str] = {}
    unresolved: list[str] = []

    for duplicate_url, ids in sorted(duplicates.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        keep = sorted(ids)[0]
        for card_id in sorted(ids):
            if card_id == keep:
                continue

            card = CARD_CATALOG[card_id]
            queries = _search_queries(card["name"], card["series"])
            candidate: str | None = None

            for query in queries:
                options = _commons_candidates(query)
                if not options:
                    options = _wikipedia_thumb_candidates(query)
                scored_options = sorted(
                    options,
                    key=lambda option: _candidate_score(option, card["name"], card["series"]),
                    reverse=True,
                )
                for option in scored_options:
                    if _candidate_score(option, card["name"], card["series"]) < 0:
                        continue
                    norm = _normalized(option)
                    if norm in used_urls:
                        continue
                    if norm == _normalized(duplicate_url):
                        continue
                    candidate = option
                    break
                if candidate:
                    break

            if candidate is None:
                unresolved.append(card_id)
                continue

            replacements[card_id] = candidate
            used_urls.add(_normalized(candidate))

    return replacements, unresolved


def _rewrite_card_image_urls(cards_py_path: Path, replacements: dict[str, str]) -> None:
    text = cards_py_path.read_text(encoding="utf-8")
    pattern = r"CARD_IMAGE_URLS: dict\[str, str\] = \{.*?\n\}\n\n\ndef _validate_explicit_images"
    match = re.search(pattern, text, re.S)
    if not match:
        raise RuntimeError("Unable to locate CARD_IMAGE_URLS block in noodswap/cards.py")

    merged = dict(CARD_IMAGE_URLS)
    merged.update(replacements)

    lines = ["CARD_IMAGE_URLS: dict[str, str] = {"]
    for card_id, image_url in merged.items():
        safe_url = image_url.replace('"', '\\"')
        lines.append(f'    "{card_id}": "{safe_url}",')
    lines.append("}")
    block = "\n".join(lines)

    replacement_text = block + "\n\n\ndef _validate_explicit_images"
    updated = text[: match.start()] + replacement_text + text[match.end() :]
    cards_py_path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure all card image URLs are distinct.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply replacements directly to noodswap/cards.py.",
    )
    parser.add_argument(
        "--report",
        default="card_image_distinct_report.json",
        help="Path to write JSON report.",
    )
    args = parser.parse_args()

    replacements, unresolved = _pick_replacements(CARD_IMAGE_URLS)

    updated = dict(CARD_IMAGE_URLS)
    updated.update(replacements)
    remaining_duplicate_groups = _duplicate_groups(updated)

    report = {
        "cards": len(CARD_IMAGE_URLS),
        "initial_duplicate_groups": len(_duplicate_groups(CARD_IMAGE_URLS)),
        "replacements_found": len(replacements),
        "remaining_duplicate_groups": len(remaining_duplicate_groups),
        "remaining_duplicate_cards": sum(len(v) for v in remaining_duplicate_groups.values()),
        "unresolved_cards": sorted(unresolved),
        "replacements": replacements,
        "remaining_groups": {
            url: sorted(ids) for url, ids in sorted(remaining_duplicate_groups.items())
        },
    }

    report_path = Path(args.report).resolve()
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.apply and replacements:
        cards_py_path = Path(__file__).resolve().parents[1] / "noodswap" / "cards.py"
        _rewrite_card_image_urls(cards_py_path, replacements)

    print("distinct-image audit complete")
    print(f"cards: {report['cards']}")
    print(f"initial duplicate groups: {report['initial_duplicate_groups']}")
    print(f"replacements found: {report['replacements_found']}")
    print(f"remaining duplicate groups: {report['remaining_duplicate_groups']}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
