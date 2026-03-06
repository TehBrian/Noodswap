import json
import random
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict

from .rarities import RARITY_WEIGHTS
from .settings import CARD_IMAGE_CACHE_MANIFEST, GENERATION_MAX, GENERATION_MIN


class CardData(TypedDict):
    name: str
    series: str
    rarity: str
    base_value: int
    image: NotRequired[str]


class _CardMetaData(TypedDict):
    name: str
    series: str
    rarity: str
    image: NotRequired[str]


CARD_DATA_DIR = Path(__file__).resolve().parent / "data"
CARD_CATALOG_PATH = CARD_DATA_DIR / "cards.json"
CARD_BASE_VALUES_PATH = CARD_DATA_DIR / "base_values.json"


def _read_card_metadata() -> dict[str, _CardMetaData]:
    parsed = json.loads(CARD_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Invalid card metadata JSON: {CARD_CATALOG_PATH}")

    metadata: dict[str, _CardMetaData] = {}
    for card_id, value in parsed.items():
        if not isinstance(card_id, str) or not isinstance(value, dict):
            continue

        name = value.get("name")
        series = value.get("series")
        rarity = value.get("rarity")
        image = value.get("image")
        if not isinstance(name, str) or not isinstance(series, str) or not isinstance(rarity, str):
            continue

        card_meta: _CardMetaData = {
            "name": name,
            "series": series,
            "rarity": rarity,
        }
        if isinstance(image, str):
            card_meta["image"] = image
        metadata[card_id] = card_meta

    return metadata


def _read_card_base_values() -> dict[str, int]:
    if not CARD_BASE_VALUES_PATH.exists():
        return {}

    parsed = json.loads(CARD_BASE_VALUES_PATH.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Invalid card base values JSON: {CARD_BASE_VALUES_PATH}")

    base_values: dict[str, int] = {}
    for card_id, value in parsed.items():
        if isinstance(card_id, str) and isinstance(value, int):
            base_values[card_id] = value
    return base_values


def _load_card_catalog() -> dict[str, CardData]:
    card_metadata = _read_card_metadata()
    card_base_values = _read_card_base_values()

    catalog: dict[str, CardData] = {}
    for card_id, metadata in card_metadata.items():
        card: CardData = {
            "name": metadata["name"],
            "series": metadata["series"],
            "rarity": metadata["rarity"],
            "base_value": int(card_base_values.get(card_id, 0)),
        }
        image = metadata.get("image")
        if isinstance(image, str):
            card["image"] = image
        catalog[card_id] = card

    return catalog


CARD_CATALOG: dict[str, CardData] = _load_card_catalog()


def default_card_image(card_id: str) -> str:
    return f"assets/card_images/{card_id}.img"


def _read_local_image_manifest() -> dict[str, dict[str, str | int]]:
    try:
        parsed = json.loads(CARD_IMAGE_CACHE_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(parsed, dict):
        return {}

    manifest: dict[str, dict[str, str | int]] = {}
    for card_id, value in parsed.items():
        if isinstance(card_id, str) and isinstance(value, dict):
            manifest[card_id] = value
    return manifest


def _build_local_card_image_map() -> dict[str, str]:
    manifest_data = _read_local_image_manifest()
    relative_base = Path("assets") / "card_images"
    mapped: dict[str, str] = {}

    for card_id in CARD_CATALOG:
        entry = manifest_data.get(card_id)
        if isinstance(entry, dict):
            file_name = entry.get("file")
            if isinstance(file_name, str) and file_name:
                mapped[card_id] = str(relative_base / file_name)
                continue

        candidates = sorted(CARD_IMAGE_CACHE_MANIFEST.parent.glob(f"{card_id}.*"))
        if candidates:
            mapped[card_id] = str(relative_base / candidates[0].name)

    return mapped


CARD_IMAGE_URLS: dict[str, str] = _build_local_card_image_map()


for _card_id, _card in CARD_CATALOG.items():
    _card["image"] = _card.get("image") or CARD_IMAGE_URLS.get(_card_id) or default_card_image(_card_id)


def _validate_no_remote_image_paths() -> None:
    remote_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if isinstance(card.get("image"), str) and card["image"].startswith(("http://", "https://"))
    ]
    if remote_ids:
        raise RuntimeError(
            "Remote image URLs are not allowed in local-only mode for: " + ", ".join(sorted(remote_ids))
        )


_validate_no_remote_image_paths()


RARITY_CARD_COUNTS = Counter(card["rarity"] for card in CARD_CATALOG.values())
NORMALIZED_RARITY_WEIGHTS = {
    rarity: weight / RARITY_CARD_COUNTS[rarity]
    for rarity, weight in RARITY_WEIGHTS.items()
    if RARITY_CARD_COUNTS.get(rarity, 0) > 0
}


def effective_rarity_odds() -> dict[str, float]:
    weighted_totals = {
        rarity: NORMALIZED_RARITY_WEIGHTS[rarity] * RARITY_CARD_COUNTS[rarity]
        for rarity in NORMALIZED_RARITY_WEIGHTS
    }
    grand_total = sum(weighted_totals.values())
    if grand_total <= 0:
        return {rarity: 0.0 for rarity in weighted_totals}
    return {rarity: weighted_totals[rarity] / grand_total for rarity in weighted_totals}


def target_rarity_odds() -> dict[str, float]:
    active_weights = {
        rarity: weight
        for rarity, weight in RARITY_WEIGHTS.items()
        if RARITY_CARD_COUNTS.get(rarity, 0) > 0
    }
    total_weight = sum(active_weights.values())
    if total_weight <= 0:
        return {rarity: 0.0 for rarity in active_weights}
    return {rarity: active_weights[rarity] / total_weight for rarity in active_weights}


def normalize_card_id(card_id: str) -> str:
    return card_id.strip().upper()


def search_card_ids(query: str, *, include_series: bool = False) -> list[str]:
    cleaned_query = query.strip().casefold()
    if not cleaned_query:
        return []

    exact_name_matches: list[str] = []
    prefix_name_matches: list[str] = []
    contains_name_matches: list[str] = []
    exact_series_matches: list[str] = []
    prefix_series_matches: list[str] = []
    contains_series_matches: list[str] = []

    for card_id, card in CARD_CATALOG.items():
        card_name = card["name"]
        normalized_name = card_name.casefold()
        if normalized_name == cleaned_query:
            exact_name_matches.append(card_id)
        elif normalized_name.startswith(cleaned_query):
            prefix_name_matches.append(card_id)
        elif cleaned_query in normalized_name:
            contains_name_matches.append(card_id)

        if include_series:
            normalized_series = card["series"].casefold()
            if normalized_series == cleaned_query:
                exact_series_matches.append(card_id)
            elif normalized_series.startswith(cleaned_query):
                prefix_series_matches.append(card_id)
            elif cleaned_query in normalized_series:
                contains_series_matches.append(card_id)

    key = lambda cid: (CARD_CATALOG[cid]["name"].casefold(), cid)

    ordered_groups = [
        sorted(exact_name_matches, key=key),
        sorted(prefix_name_matches, key=key),
        sorted(contains_name_matches, key=key),
    ]
    if include_series:
        ordered_groups.extend(
            [
                sorted(exact_series_matches, key=key),
                sorted(prefix_series_matches, key=key),
                sorted(contains_series_matches, key=key),
            ]
        )

    seen: set[str] = set()
    results: list[str] = []
    for group in ordered_groups:
        for card_id in group:
            if card_id in seen:
                continue
            seen.add(card_id)
            results.append(card_id)
    return results


def search_card_ids_by_name(query: str) -> list[str]:
    return search_card_ids(query)


def card_code(card_id: str, dupe_code: str) -> str:
    return dupe_code.strip().lower()


def split_card_code(raw_code: str) -> str | None:
    cleaned = raw_code.strip()
    if not cleaned:
        return None

    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
        if not cleaned:
            return None

    dupe_code = cleaned.lower()

    if not all(char.isdigit() or ("a" <= char <= "z") for char in dupe_code):
        return None

    return dupe_code


def generation_label(generation: int) -> str:
    return f"G-{generation}"


def proper_case(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())


def card_base_value(card_id: str) -> int:
    return int(CARD_CATALOG[card_id]["base_value"])


def card_value(card_id: str, generation: int) -> int:
    base_value = card_base_value(card_id)
    multiplier = generation_value_multiplier(generation)
    return max(1, int(round(base_value * multiplier)))


def card_base_display(card_id: str) -> str:
    card = CARD_CATALOG[card_id]
    return (
        f"**{card['name']}** • (`{card_id}`) "
        f"[{proper_case(card['series'])}] ({proper_case(card['rarity'])}) "
        f"(Base: **{card_base_value(card_id)}** dough)"
    )


def card_dupe_display(card_id: str, generation: int, dupe_code: str | None = None) -> str:
    card = CARD_CATALOG[card_id]
    dupe_code_text = card_code(card_id, dupe_code) if dupe_code is not None else "?"
    return (
        f"`#{dupe_code_text}` **{card['name']}** • (`{card_id}`) "
        f"[{proper_case(card['series'])}] ({proper_case(card['rarity'])}) "
        f"• **{generation_label(generation)}** (Value: **{card_value(card_id, generation)}** dough)"
    )


def card_image_url(card_id: str) -> str:
    card = CARD_CATALOG[card_id]
    return card.get("image") or default_card_image(card_id)


def random_card_id() -> str:
    card_ids = list(CARD_CATALOG.keys())
    weights = [
        NORMALIZED_RARITY_WEIGHTS.get(CARD_CATALOG[cid]["rarity"], 1.0)
        for cid in card_ids
    ]
    return random.choices(card_ids, weights=weights, k=1)[0]


def random_generation() -> int:
    x = random.betavariate(1.6, 1.04)
    return int(max(GENERATION_MIN, min(GENERATION_MAX, GENERATION_MAX * x)))


def make_drop_choices(size: int = 3) -> list[tuple[str, int]]:
    if size >= len(CARD_CATALOG):
        card_ids = random.sample(list(CARD_CATALOG.keys()), len(CARD_CATALOG))
        return [(card_id, random_generation()) for card_id in card_ids]

    chosen: set[str] = set()
    while len(chosen) < size:
        chosen.add(random_card_id())
    return [(card_id, random_generation()) for card_id in chosen]


def generation_value_multiplier(generation: int) -> float:
    clamped_generation = max(GENERATION_MIN, min(GENERATION_MAX, generation))
    progress = (GENERATION_MAX - clamped_generation) / (GENERATION_MAX - GENERATION_MIN)
    return 1.0 + (2 * progress ** 2) + (9 * progress ** 9) + (49 * progress ** 49)


def burn_delta_range(value: int) -> int:
    percent = random.randint(5, 20)
    return max(1, int(round(value * (percent / 100.0))))


def get_burn_payout(card_id: str, generation: int, delta_range: int | None = None) -> tuple[int, int, int, int, float, int]:
    base_value = card_base_value(card_id)
    multiplier = generation_value_multiplier(generation)
    value = max(1, int(round(base_value * multiplier)))
    resolved_delta_range = burn_delta_range(value) if delta_range is None else max(1, delta_range)
    delta = random.randint(-resolved_delta_range, resolved_delta_range)
    payout = max(1, value + delta)
    return payout, value, base_value, delta, multiplier, resolved_delta_range
