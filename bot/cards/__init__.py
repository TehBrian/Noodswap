import json
from pathlib import Path
from typing import NotRequired, TypedDict

from ..card_display import (
    card_base_display as _card_base_display_impl,
    card_dupe_display as _card_dupe_display_impl,
    card_dupe_display_concise as _card_dupe_display_concise_impl,
    display_dupe_code as _display_dupe_code_impl,
    display_dupe_code_raw as _display_dupe_code_raw_impl,
    generation_label as _generation_label_impl,
    proper_case as _proper_case_impl,
    series_display as _series_display_impl,
    series_emoji as _series_emoji_impl,
)
from ..card_value import (
    burn_delta_range as _burn_delta_range_impl,
    card_base_value as _card_base_value_impl,
    card_value as _card_value_impl,
    compute_normalized_rarity_weights as _compute_normalized_rarity_weights_impl,
    compute_rarity_card_counts as _compute_rarity_card_counts_impl,
    effective_rarity_odds as _effective_rarity_odds_impl,
    generation_value_multiplier as _generation_value_multiplier_impl,
    get_burn_payout as _get_burn_payout_impl,
    make_drop_choices as _make_drop_choices_impl,
    random_card_id as _random_card_id_impl,
    random_generation as _random_generation_impl,
    target_rarity_odds as _target_rarity_odds_impl,
)
from ..card_search import (
    card_code as _card_code_impl,
    normalize_card_id as _normalize_card_id_impl,
    search_card_ids as _search_card_ids_impl,
    search_card_ids_by_name as _search_card_ids_by_name_impl,
    split_card_code as _split_card_code_impl,
)
from ..fonts import font_rarity
from ..frames import frame_rarity
from ..morphs import morph_rarity
from ..rarities import RARITY_WEIGHTS
from ..settings import CARD_IMAGE_MANIFEST, GENERATION_MAX, GENERATION_MIN
from ..trait_rarities import trait_rarity_multiplier


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


class SeriesData(TypedDict):
    emoji: str
    label: NotRequired[str]


CARD_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CARD_CATALOG_PATH = CARD_DATA_DIR / "cards.json"
CARD_BASE_VALUES_PATH = CARD_DATA_DIR / "base_values.json"
SERIES_CATALOG_PATH = CARD_DATA_DIR / "series.json"


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


def _read_series_catalog() -> dict[str, SeriesData]:
    parsed = json.loads(SERIES_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Invalid series metadata JSON: {SERIES_CATALOG_PATH}")

    metadata: dict[str, SeriesData] = {}
    for series_id, value in parsed.items():
        if not isinstance(series_id, str) or not isinstance(value, dict):
            continue

        emoji = value.get("emoji")
        label = value.get("label")
        if not isinstance(emoji, str) or not emoji.strip():
            continue

        series_meta: SeriesData = {"emoji": emoji}
        if isinstance(label, str) and label.strip():
            series_meta["label"] = label
        metadata[series_id] = series_meta

    return metadata


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
SERIES_CATALOG: dict[str, SeriesData] = _read_series_catalog()


def default_card_image(card_id: str) -> str:
    return f"runtime/card_images/{card_id}.img"


def _read_local_image_manifest() -> dict[str, dict[str, str | int]]:
    try:
        parsed = json.loads(CARD_IMAGE_MANIFEST.read_text(encoding="utf-8"))
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
    relative_base = Path("runtime") / "card_images"
    mapped: dict[str, str] = {}

    for card_id in CARD_CATALOG:
        entry = manifest_data.get(card_id)
        if isinstance(entry, dict):
            file_name = entry.get("file")
            if isinstance(file_name, str) and file_name:
                mapped[card_id] = str(relative_base / file_name)
                continue

        candidates = sorted(CARD_IMAGE_MANIFEST.parent.glob(f"{card_id}.*"))
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
        if isinstance(card.get("image"), str) and str(card.get("image")).startswith(("http://", "https://"))
    ]
    if remote_ids:
        raise RuntimeError("Remote image URLs are not allowed in local-only mode for: " + ", ".join(sorted(remote_ids)))


def _validate_image_paths_use_runtime_card_images() -> None:
    invalid_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if not isinstance(card.get("image"), str) or not str(card.get("image")).startswith("runtime/card_images/")
    ]
    if invalid_ids:
        raise RuntimeError("Card image paths must use runtime/card_images/: " + ", ".join(sorted(invalid_ids)))


def _validate_card_series_metadata() -> None:
    unknown_series = sorted({card["series"] for card in CARD_CATALOG.values() if card["series"] not in SERIES_CATALOG})
    if unknown_series:
        raise RuntimeError("Card series must be declared in data/series.json; unknown series: " + ", ".join(unknown_series))

    missing_emojis = sorted(series_id for series_id, series in SERIES_CATALOG.items() if not series["emoji"].strip())
    if missing_emojis:
        raise RuntimeError("Series emojis must be non-empty for: " + ", ".join(missing_emojis))


_validate_no_remote_image_paths()
_validate_image_paths_use_runtime_card_images()
_validate_card_series_metadata()


RARITY_CARD_COUNTS = _compute_rarity_card_counts_impl(CARD_CATALOG)
NORMALIZED_RARITY_WEIGHTS = _compute_normalized_rarity_weights_impl(
    RARITY_WEIGHTS,
    RARITY_CARD_COUNTS,
)


def effective_rarity_odds() -> dict[str, float]:
    return _effective_rarity_odds_impl(
        normalized_rarity_weights=NORMALIZED_RARITY_WEIGHTS,
        rarity_card_counts=RARITY_CARD_COUNTS,
    )


def target_rarity_odds() -> dict[str, float]:
    return _target_rarity_odds_impl(
        rarity_weights=RARITY_WEIGHTS,
        rarity_card_counts=RARITY_CARD_COUNTS,
    )


def normalize_card_id(card_id: str) -> str:
    return _normalize_card_id_impl(card_id)


def search_card_ids(query: str, *, include_series: bool = False) -> list[str]:
    return _search_card_ids_impl(
        query,
        card_catalog=CARD_CATALOG,
        include_series=include_series,
    )


def search_card_ids_by_name(query: str) -> list[str]:
    return _search_card_ids_by_name_impl(query, card_catalog=CARD_CATALOG)


def card_code(card_id: str, dupe_code: str) -> str:
    return _card_code_impl(card_id, dupe_code)


def split_card_code(raw_code: str) -> str | None:
    return _split_card_code_impl(raw_code)


def display_dupe_code(dupe_code: str | None) -> str:
    return _display_dupe_code_impl(dupe_code)


def display_dupe_code_raw(dupe_code: str | None) -> str:
    return _display_dupe_code_raw_impl(dupe_code)


def generation_label(generation: int) -> str:
    return _generation_label_impl(generation)


def proper_case(value: str) -> str:
    return _proper_case_impl(value)


def series_display(series: str) -> str:
    return _series_display_impl(series, series_catalog=SERIES_CATALOG)


def series_emoji(series: str) -> str:
    return _series_emoji_impl(series, series_catalog=SERIES_CATALOG)


def card_base_value(card_id: str) -> int:
    return _card_base_value_impl(card_id, card_catalog=CARD_CATALOG)


def trait_value_multiplier(
    *,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
) -> float:
    return (
        trait_rarity_multiplier(morph_rarity(morph_key))
        * trait_rarity_multiplier(frame_rarity(frame_key))
        * trait_rarity_multiplier(font_rarity(font_key))
    )


def card_value(
    card_id: str,
    generation: int,
    *,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
) -> int:
    return _card_value_impl(
        card_id,
        generation,
        card_base_value_func=card_base_value,
        generation_multiplier_func=generation_value_multiplier,
        trait_multiplier=trait_value_multiplier(
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        ),
    )


def card_base_display(card_id: str) -> str:
    return _card_base_display_impl(
        card_id,
        card_catalog=CARD_CATALOG,
        series_catalog=SERIES_CATALOG,
        card_base_value=card_base_value,
    )


def card_dupe_display(
    card_id: str,
    generation: int,
    dupe_code: str | None = None,
    *,
    pad_dupe_code: bool = True,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
) -> str:
    return _card_dupe_display_impl(
        card_id,
        generation,
        dupe_code,
        pad_dupe_code=pad_dupe_code,
        morph_key=morph_key,
        frame_key=frame_key,
        font_key=font_key,
        card_catalog=CARD_CATALOG,
        series_catalog=SERIES_CATALOG,
        card_value=card_value,
    )


def card_dupe_display_concise(
    card_id: str,
    generation: int,
    dupe_code: str | None = None,
    *,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
) -> str:
    return _card_dupe_display_concise_impl(
        card_id,
        generation,
        dupe_code,
        morph_key=morph_key,
        frame_key=frame_key,
        font_key=font_key,
        card_catalog=CARD_CATALOG,
        series_catalog=SERIES_CATALOG,
        card_value=card_value,
    )


def card_image_url(card_id: str) -> str:
    card = CARD_CATALOG[card_id]
    return card.get("image") or default_card_image(card_id)


def random_card_id() -> str:
    return _random_card_id_impl(
        card_catalog=CARD_CATALOG,
        normalized_rarity_weights=NORMALIZED_RARITY_WEIGHTS,
    )


def random_generation() -> int:
    return _random_generation_impl(
        generation_min=GENERATION_MIN,
        generation_max=GENERATION_MAX,
    )


def make_drop_choices(size: int = 3) -> list[tuple[str, int]]:
    return _make_drop_choices_impl(
        card_catalog=CARD_CATALOG,
        random_card_id_func=random_card_id,
        random_generation_func=random_generation,
        size=size,
    )


def generation_value_multiplier(generation: int) -> float:
    return _generation_value_multiplier_impl(
        generation,
        generation_min=GENERATION_MIN,
        generation_max=GENERATION_MAX,
    )


def burn_delta_range(value: int) -> int:
    return _burn_delta_range_impl(value)


def get_burn_payout(
    card_id: str,
    generation: int,
    delta_range: int | None = None,
    *,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
) -> tuple[int, int, int, int, float, int]:
    return _get_burn_payout_impl(
        card_id,
        generation,
        card_base_value_func=card_base_value,
        generation_multiplier_func=generation_value_multiplier,
        burn_delta_range_func=burn_delta_range,
        trait_multiplier=trait_value_multiplier(
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        ),
        delta_range=delta_range,
    )
