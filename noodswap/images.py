import json
import io
from pathlib import Path

import discord

from .cards import CARD_CATALOG, normalize_card_id
from .morphs import MORPH_BLACK_AND_WHITE, normalize_morph_key
from .settings import CARD_IMAGE_CACHE_MANIFEST


CARD_ASPECT_WIDTH = 5
CARD_ASPECT_HEIGHT = 7
DEFAULT_CARD_RENDER_SIZE = (300, 420)
OVERLAY_TEXT_SCALE = 1.5

RARITY_BORDER_COLORS: dict[str, tuple[int, int, int]] = {
    "common": (124, 86, 48),
    "uncommon": (132, 132, 132),
    "rare": (186, 154, 255),
    "epic": (238, 141, 42),
    "legendary": (128, 205, 255),
    "mythic": (96, 52, 145),
    "divine": (242, 211, 74),
    "celestial": (198, 242, 255),
}


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


def _normalized_card_size(size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    if width <= 0 or height <= 0:
        return DEFAULT_CARD_RENDER_SIZE

    # Normalize every rendered card to a 2.5x3.5 (5:7) portrait ratio.
    target_ratio = CARD_ASPECT_WIDTH / CARD_ASPECT_HEIGHT
    if (width / height) > target_ratio:
        width = max(1, int(round(height * target_ratio)))
    else:
        height = max(1, int(round(width / target_ratio)))
    return width, height


def _card_rarity(card_id: str) -> str:
    normalized_card_id = normalize_card_id(card_id)
    card = CARD_CATALOG.get(normalized_card_id)
    if card is None:
        return "common"

    rarity = str(card.get("rarity", "common")).casefold()
    if rarity == "dividine":
        return "divine"
    return rarity


def rarity_border_color(card_id: str) -> tuple[int, int, int]:
    rarity = _card_rarity(card_id)
    return RARITY_BORDER_COLORS.get(rarity, RARITY_BORDER_COLORS["common"])


def _card_name_for_display(card_id: str) -> str:
    normalized_card_id = normalize_card_id(card_id)
    card = CARD_CATALOG.get(normalized_card_id)
    if card is None:
        return normalized_card_id
    return str(card.get("name", normalized_card_id))


def _generation_overlay_text(generation: int | None) -> str:
    if generation is None:
        return "G-????"
    return f"G-{generation:04d}"


def _wrap_text_to_width(*, draw, text: str, font, max_width: int) -> str:
    if max_width <= 0 or not text:
        return text

    words = text.split()
    if not words:
        return text

    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"
        candidate_width = draw.textbbox((0, 0), candidate, font=font)[2]
        if candidate_width <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        # If a single word is too long, hard-wrap it by characters.
        segment = ""
        for char in word:
            probe = f"{segment}{char}"
            probe_width = draw.textbbox((0, 0), probe, font=font)[2]
            if probe_width <= max_width:
                segment = probe
            else:
                if segment:
                    lines.append(segment)
                segment = char
        current = segment

    if current:
        lines.append(current)

    return "\n".join(lines)


def _load_overlay_font(size: int, *, bold: bool):
    from PIL import ImageFont

    candidate_paths: list[Path] = []
    try:
        import PIL

        pil_dir = Path(PIL.__file__).resolve().parent
        if bold:
            candidate_paths.append(pil_dir / "fonts" / "DejaVuSans-Bold.ttf")
        else:
            candidate_paths.append(pil_dir / "fonts" / "DejaVuSans.ttf")
    except Exception:
        pass

    if bold:
        candidate_paths.extend(
            [
                Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                Path("/System/Library/Fonts/Supplemental/Helvetica Bold.ttf"),
                Path("/Library/Fonts/Arial Bold.ttf"),
            ]
        )
    else:
        candidate_paths.extend(
            [
                Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
                Path("/System/Library/Fonts/Supplemental/Helvetica.ttf"),
                Path("/Library/Fonts/Arial.ttf"),
            ]
        )

    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        try:
            return ImageFont.truetype(str(candidate), size)
        except Exception:
            continue

    # Last resort: default bitmap font (fixed-size).
    return ImageFont.load_default()


def _apply_text_legibility_overlay(
    image,
    *,
    card_id: str,
    generation: int | None,
    color: tuple[int, int, int],
):
    from PIL import Image, ImageDraw, ImageFont

    width, height = image.size
    # Start the fade a bit higher so the overlay reaches further into the art.
    gradient_start = int(height * 0.44)
    gradient_height = max(1, height - gradient_start)

    # Bottom-to-top rarity-tinted fade keeps text readable while preserving art detail.
    gradient_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gradient_pixels = gradient_layer.load()
    for y in range(gradient_start, height):
        distance_from_start = y - gradient_start
        progress = distance_from_start / gradient_height

        # Keep a near-solid band around bottom text, then fade out faster above it.
        solid_band_start = 0.72
        if progress >= solid_band_start:
            alpha = 255
        else:
            normalized = progress / solid_band_start
            alpha = int(round(255 * (normalized**2.5)))

        for x in range(width):
            gradient_pixels[x, y] = (color[0], color[1], color[2], alpha)

    composed = Image.alpha_composite(image.convert("RGBA"), gradient_layer)

    draw = ImageDraw.Draw(composed)
    title_size = max(11, int(round(height * (0.14 / 3) * OVERLAY_TEXT_SCALE)))
    subtitle_size = max(9, int(round(height * (0.104 / 3) * OVERLAY_TEXT_SCALE)))
    title_font = _load_overlay_font(title_size, bold=True)
    subtitle_font = _load_overlay_font(subtitle_size, bold=False)

    subtitle = _generation_overlay_text(generation).upper()
    title = _card_name_for_display(card_id).upper()

    left_padding = max(10, int(width * 0.05))
    right_padding = max(10, int(width * 0.05))
    bottom_padding = max(10, int(height * 0.05))
    text_max_width = max(1, width - left_padding - right_padding)
    title_wrapped = _wrap_text_to_width(draw=draw, text=title, font=title_font, max_width=text_max_width)

    title_bbox = draw.multiline_textbbox((0, 0), title_wrapped, font=title_font, spacing=3)
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    title_height = max(1, title_bbox[3] - title_bbox[1])
    subtitle_height = max(1, subtitle_bbox[3] - subtitle_bbox[1])
    line_gap = max(2, int(round(height * 0.01)))
    text_height = title_height + line_gap + subtitle_height
    text_y = max(0, height - bottom_padding - text_height)

    cool_text = (24, 38, 62, 255)

    draw.text(
        (left_padding, text_y),
        subtitle,
        fill=cool_text,
        font=subtitle_font,
    )
    draw.multiline_text(
        (left_padding, text_y + subtitle_height + line_gap),
        title_wrapped,
        fill=cool_text,
        font=title_font,
        spacing=3,
    )
    return composed


def _placeholder_card_art(card_id: str, generation: int | None, size: tuple[int, int]):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    width, height = size
    image = Image.new("RGB", (width, height), (28, 28, 28))
    draw = ImageDraw.Draw(image)
    code_line = normalize_card_id(card_id)
    generation_line = f"G-{generation:04d}" if generation is not None else "G-????"
    draw.multiline_text((14, 14), f"{code_line}\n{generation_line}", fill=(230, 230, 230), spacing=4)
    draw.text((14, height - 30), "Image unavailable", fill=(188, 188, 188))
    return image


def render_card_surface(
    card_id: str,
    *,
    generation: int | None = None,
    morph_key: str | None = None,
    size: tuple[int, int] = DEFAULT_CARD_RENDER_SIZE,
):
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError:
        return None

    width, height = _normalized_card_size(size)
    border_px = max(6, int(round(min(width, height) * 0.03)))
    outer_radius = max(border_px + 4, int(round(min(width, height) * 0.055)))
    inner_width = max(1, width - (border_px * 2))
    inner_height = max(1, height - (border_px * 2))
    inner_radius = max(2, outer_radius - border_px + 1)

    normalized_card_id = normalize_card_id(card_id)
    raw_image = read_local_card_image_bytes(normalized_card_id)
    source_image = None

    if raw_image is not None:
        try:
            source_image = Image.open(io.BytesIO(raw_image)).convert("RGB")
        except Exception:
            source_image = None

    if source_image is None:
        source_image = _placeholder_card_art(normalized_card_id, generation, (inner_width, inner_height))

    if source_image is None:
        return None

    fitted = ImageOps.fit(source_image, (inner_width, inner_height), method=Image.Resampling.LANCZOS)
    normalized_morph_key = normalize_morph_key(morph_key)
    if normalized_morph_key == MORPH_BLACK_AND_WHITE:
        fitted = ImageOps.grayscale(fitted).convert("RGB")

    fitted = _apply_text_legibility_overlay(
        fitted,
        card_id=normalized_card_id,
        generation=generation,
        color=rarity_border_color(normalized_card_id),
    )

    card_surface = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card_surface)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=outer_radius,
        fill=rarity_border_color(normalized_card_id),
    )

    inner_mask = Image.new("L", (inner_width, inner_height), 0)
    inner_draw = ImageDraw.Draw(inner_mask)
    inner_draw.rounded_rectangle((0, 0, inner_width - 1, inner_height - 1), radius=inner_radius, fill=255)
    card_surface.paste(fitted, (border_px, border_px), mask=inner_mask)
    return card_surface


def render_card_image_bytes(
    card_id: str,
    *,
    generation: int | None = None,
    morph_key: str | None = None,
    size: tuple[int, int] = DEFAULT_CARD_RENDER_SIZE,
) -> bytes | None:
    rendered_surface = render_card_surface(card_id, generation=generation, morph_key=morph_key, size=size)
    if rendered_surface is None:
        return None

    output = io.BytesIO()
    rendered_surface.save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


def embed_image_payload(
    card_id: str,
    generation: int | None = None,
    morph_key: str | None = None,
) -> tuple[str | None, discord.File | None]:
    normalized_card_id = normalize_card_id(card_id)
    normalized_morph_key = normalize_morph_key(morph_key)

    rendered_image = render_card_image_bytes(normalized_card_id, generation=generation, morph_key=normalized_morph_key)
    if rendered_image is not None:
        morph_suffix = normalized_morph_key or "base"
        file_name = f"{normalized_card_id}_{morph_suffix}_card.png"
        attachment_url = f"attachment://{file_name}"
        return attachment_url, discord.File(io.BytesIO(rendered_image), filename=file_name)

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
