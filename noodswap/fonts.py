from pathlib import Path
from typing import Final

from .settings import CARD_FONTS_DIR as SETTINGS_CARD_FONTS_DIR


FONT_SERIF: Final[str] = "serif"
FONT_MONO: Final[str] = "mono"
FONT_SCRIPT: Final[str] = "script"
FONT_SPOOKY: Final[str] = "spooky"
FONT_PIXEL: Final[str] = "pixel"
FONT_PLAYFUL: Final[str] = "playful"
FONT_COST_FRACTION: Final[float] = 0.20

# Classic is now the built-in default style, not a purchasable modifier.
DEFAULT_FONT_LABEL: Final[str] = "Classic"

AVAILABLE_FONTS: Final[tuple[str, ...]] = (
    FONT_SERIF,
    FONT_MONO,
    FONT_SCRIPT,
    FONT_SPOOKY,
    FONT_PIXEL,
    FONT_PLAYFUL,
)

FONT_LABELS: Final[dict[str, str]] = {
    FONT_SERIF: "Serif",
    FONT_MONO: "Monospace",
    FONT_SCRIPT: "Storybook",
    FONT_SPOOKY: "Spooky",
    FONT_PIXEL: "Pixel",
    FONT_PLAYFUL: "Playful",
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
