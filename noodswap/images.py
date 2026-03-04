import json
import io
from pathlib import Path

import discord

from .cards import normalize_card_id
from .settings import CARD_IMAGE_CACHE_MANIFEST


def _read_image_manifest() -> dict[str, dict[str, str | int]]:
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


def local_card_image_path(card_id: str) -> Path | None:
    normalized_card_id = normalize_card_id(card_id)
    manifest_data = _read_image_manifest()
    entry = manifest_data.get(normalized_card_id)

    if isinstance(entry, dict):
        file_name = entry.get("file")
        if isinstance(file_name, str) and file_name:
            image_path = CARD_IMAGE_CACHE_MANIFEST.parent / Path(file_name)
            if image_path.exists() and image_path.is_file():
                return image_path

    for candidate in CARD_IMAGE_CACHE_MANIFEST.parent.glob(f"{normalized_card_id}.*"):
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def read_local_card_image_bytes(card_id: str) -> bytes | None:
    image_path = local_card_image_path(card_id)
    if image_path is None:
        return None

    try:
        return image_path.read_bytes()
    except Exception:
        return None


def embed_image_payload(card_id: str) -> tuple[str | None, discord.File | None]:
    normalized_card_id = normalize_card_id(card_id)
    image_path = local_card_image_path(normalized_card_id)
    if image_path is None:
        return None, None

    suffix = image_path.suffix.lower() or ".img"
    file_name = f"{normalized_card_id}{suffix}"
    attachment_url = f"attachment://{file_name}"
    try:
        image_bytes = image_path.read_bytes()
    except Exception:
        return None, None

    return attachment_url, discord.File(io.BytesIO(image_bytes), filename=file_name)
