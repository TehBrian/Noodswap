from pathlib import Path
from typing import Final

from .settings import CARD_FONTS_DIR as SETTINGS_CARD_FONTS_DIR


FONT_CLASSIC: Final[str] = "classic"
FONT_SERIF: Final[str] = "serif"
FONT_MONO: Final[str] = "mono"
FONT_SCRIPT: Final[str] = "script"
FONT_SPOOKY: Final[str] = "spooky"
FONT_PIXEL: Final[str] = "pixel"
FONT_PLAYFUL: Final[str] = "playful"
FONT_COST_FRACTION: Final[float] = 0.20

DEFAULT_FONT_KEY: Final[str] = FONT_CLASSIC
DEFAULT_FONT_LABEL: Final[str] = "Classic"

AVAILABLE_FONTS: Final[tuple[str, ...]] = (
    FONT_CLASSIC,
    FONT_SERIF,
    FONT_MONO,
    FONT_SCRIPT,
    FONT_SPOOKY,
    FONT_PIXEL,
    FONT_PLAYFUL,
)

FONT_LABELS: Final[dict[str, str]] = {
    FONT_CLASSIC: "Classic",
    FONT_SERIF: "Serif",
    FONT_MONO: "Monospace",
    FONT_SCRIPT: "Storybook",
    FONT_SPOOKY: "Spooky",
    FONT_PIXEL: "Pixel",
    FONT_PLAYFUL: "Playful",
}

FONT_RARITIES: Final[dict[str, str]] = {
    FONT_CLASSIC: "common",
    FONT_SERIF: "uncommon",
    FONT_MONO: "rare",
    FONT_SCRIPT: "epic",
    FONT_SPOOKY: "legendary",
    FONT_PIXEL: "mythical",
    FONT_PLAYFUL: "divine",
}

# Card render styles are mapped to explicit bundled font files in runtime/fonts.
FONT_FILE_MAP: Final[dict[str, dict[str, str]]] = {
    # Classic/default face: Arial regular + bold.
    FONT_CLASSIC: {
        "regular": "Arial.ttf",
        "bold": "Arial Bold.ttf",
    },
    # Serif style: Times New Roman regular + bold.
    FONT_SERIF: {
        "regular": "Times New Roman.ttf",
        "bold": "Times New Roman Bold.ttf",
    },
    # Mono style: Courier New regular + bold.
    FONT_MONO: {
        "regular": "Courier New.ttf",
        "bold": "Courier New Bold.ttf",
    },
    # Storybook/script style.
    FONT_SCRIPT: {
        "regular": "SnellRoundhand.ttc",
        "bold": "SnellRoundhand Bold.ttc",
    },
    # Spooky style.
    FONT_SPOOKY: {
        "regular": "Papyrus.ttc",
        "bold": "Papyrus Bold.ttc",
    },
    # Pixel style family.
    FONT_PIXEL: {
        "regular": "Menlo.ttc",
        "bold": "Menlo Bold.ttc",
    },
    # Playful style.
    FONT_PLAYFUL: {
        "regular": "Comic Sans MS.ttf",
        "bold": "Comic Sans MS Bold.ttf",
    },
}

CARD_FONTS_DIR: Final[Path] = SETTINGS_CARD_FONTS_DIR


def normalize_font_key(font_key: str | None) -> str | None:
    if font_key is None:
        return None

    normalized = font_key.strip().lower()
    if not normalized:
        return None

    if normalized not in AVAILABLE_FONTS:
        return None
    return normalized


def font_label(font_key: str | None) -> str:
    normalized = normalize_font_key(font_key)
    if normalized is None:
        return DEFAULT_FONT_LABEL
    return FONT_LABELS.get(normalized, normalized)


def font_asset_files(font_key: str | None) -> tuple[str, str]:
    normalized = normalize_font_key(font_key) or DEFAULT_FONT_KEY
    mapped = FONT_FILE_MAP.get(normalized)
    if mapped is None:
        fallback = FONT_FILE_MAP[DEFAULT_FONT_KEY]
        return fallback["regular"], fallback["bold"]
    return mapped["regular"], mapped["bold"]


def font_rarity(font_key: str | None) -> str:
    normalized = normalize_font_key(font_key)
    if normalized is None:
        return "common"
    return FONT_RARITIES.get(normalized, "common")
