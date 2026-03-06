from typing import Final


MORPH_BLACK_AND_WHITE: Final[str] = "black_and_white"
MORPH_INVERSE: Final[str] = "inverse"
MORPH_TINT_ROSE: Final[str] = "tint_rose"
MORPH_TINT_AQUA: Final[str] = "tint_aqua"
MORPH_TINT_LIME: Final[str] = "tint_lime"
MORPH_TINT_WARM: Final[str] = "tint_warm"
MORPH_TINT_COOL: Final[str] = "tint_cool"
MORPH_TINT_VIOLET: Final[str] = "tint_violet"
MORPH_UPSIDE_DOWN: Final[str] = "upside_down"
MORPH_COST_FRACTION: Final[float] = 0.20

AVAILABLE_MORPHS: Final[tuple[str, ...]] = (
    MORPH_BLACK_AND_WHITE,
    MORPH_INVERSE,
    MORPH_TINT_ROSE,
    MORPH_TINT_AQUA,
    MORPH_TINT_LIME,
    MORPH_TINT_WARM,
    MORPH_TINT_COOL,
    MORPH_TINT_VIOLET,
    MORPH_UPSIDE_DOWN,
)

MORPH_LABELS: Final[dict[str, str]] = {
    MORPH_BLACK_AND_WHITE: "Black and White",
    MORPH_INVERSE: "Inverse",
    MORPH_TINT_ROSE: "Rose Tint",
    MORPH_TINT_AQUA: "Aqua Tint",
    MORPH_TINT_LIME: "Lime Tint",
    MORPH_TINT_WARM: "Warm Tint",
    MORPH_TINT_COOL: "Cool Tint",
    MORPH_TINT_VIOLET: "Violet Tint",
    MORPH_UPSIDE_DOWN: "Upside Down",
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
