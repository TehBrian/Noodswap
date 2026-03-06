from typing import Final


MORPH_BLACK_AND_WHITE: Final[str] = "black_and_white"
MORPH_COST_FRACTION: Final[float] = 0.20

AVAILABLE_MORPHS: Final[tuple[str, ...]] = (
    MORPH_BLACK_AND_WHITE,
)

MORPH_LABELS: Final[dict[str, str]] = {
    MORPH_BLACK_AND_WHITE: "Black and White",
}


def normalize_morph_key(morph_key: str | None) -> str | None:
    if morph_key is None:
        return None

    normalized = morph_key.strip().lower()
    if not normalized:
        return None

    if normalized not in AVAILABLE_MORPHS:
        return None
    return normalized


def morph_label(morph_key: str | None) -> str:
    normalized = normalize_morph_key(morph_key)
    if normalized is None:
        return "None"
    return MORPH_LABELS.get(normalized, normalized)
