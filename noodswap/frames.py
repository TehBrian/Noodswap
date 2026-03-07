from pathlib import Path
from typing import Final

from .settings import FRAME_OVERLAYS_DIR as SETTINGS_FRAME_OVERLAYS_DIR


FRAME_BUTTERY: Final[str] = "buttery"
FRAME_GILDED: Final[str] = "gilded"
FRAME_DRIZZLED: Final[str] = "drizzled"
FRAME_COST_FRACTION: Final[float] = 0.20

AVAILABLE_FRAMES: Final[tuple[str, ...]] = (
    FRAME_BUTTERY,
    FRAME_GILDED,
    FRAME_DRIZZLED,
)

FRAME_LABELS: Final[dict[str, str]] = {
    FRAME_BUTTERY: "Buttery",
    FRAME_GILDED: "Gilded",
    FRAME_DRIZZLED: "Drizzled",
}

FRAME_OVERLAYS_DIR: Final[Path] = SETTINGS_FRAME_OVERLAYS_DIR


def normalize_frame_key(frame_key: str | None) -> str | None:
    if frame_key is None:
        return None

    normalized = frame_key.strip().lower()
    if not normalized:
        return None

    if normalized not in AVAILABLE_FRAMES:
        return None
    return normalized


def frame_label(frame_key: str | None) -> str:
    normalized = normalize_frame_key(frame_key)
    if normalized is None:
        return "None"
    return FRAME_LABELS.get(normalized, normalized)


def frame_overlay_path(frame_key: str) -> Path | None:
    normalized = normalize_frame_key(frame_key)
    if normalized is None:
        return None

    for extension in ("png", "webp"):
        candidate = FRAME_OVERLAYS_DIR / f"{normalized}.{extension}"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def available_frame_keys() -> tuple[str, ...]:
    return tuple(frame_key for frame_key in AVAILABLE_FRAMES if frame_overlay_path(frame_key) is not None)
