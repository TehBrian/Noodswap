import json
import io
from pathlib import Path

import discord

from .cards import CARD_CATALOG, normalize_card_id
from .fonts import (
    CARD_FONTS_DIR,
    font_asset_files,
    normalize_font_key,
)
from .frames import frame_path, normalize_frame_key
from .morphs import (
    MORPH_BLACK_AND_WHITE,
    MORPH_INVERSE,
    MORPH_TINT_AQUA,
    MORPH_TINT_COOL,
    MORPH_TINT_LIME,
    MORPH_TINT_ROSE,
    MORPH_TINT_VIOLET,
    MORPH_TINT_WARM,
    MORPH_UPSIDE_DOWN,
    normalize_morph_key,
)
from .settings import CARD_BODY_ASPECT_RATIO, CARD_IMAGE_MANIFEST

CARD_ASPECT_WIDTH = 5
CARD_ASPECT_HEIGHT = 7
DEFAULT_CARD_RENDER_SIZE = (350, 490)
HD_CARD_RENDER_SIZE = (1000, 1400)
OVERLAY_TEXT_SCALE = 1.5
# Unframed cards can use tighter margins by default.
CARD_BODY_SCALE = 0.96
# Framed cards render smaller so frame assets with built-in margins can sit on top cleanly.
FRAMED_CARD_BODY_SCALE = 0.72
# Drop previews currently render without frames.
DROP_CARD_BODY_SCALE = 0.96
# Higher supersampling gives smoother rounded border edges.
BORDER_MASK_SUPERSAMPLE_SCALE = 6

RARITY_BORDER_COLORS: dict[str, tuple[int, int, int]] = {
    "common": (189, 180, 177),
    "uncommon": (143, 105, 76),
    "rare": (151, 108, 204),
    "epic": (245, 162, 80),
    "legendary": (247, 79, 89),
    "mythical": (92, 214, 134),
    "divine": (250, 224, 32),
    "celestial": (91, 178, 250),
}


def _read_image_manifest() -> dict[str, dict[str, str | int]]:
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


def local_card_image_path(card_id: str) -> Path | None:
    normalized_card_id = normalize_card_id(card_id)
    manifest_data = _read_image_manifest()
    entry = manifest_data.get(normalized_card_id)

    if isinstance(entry, dict):
        file_name = entry.get("file")
        if isinstance(file_name, str) and file_name:
            image_path = CARD_IMAGE_MANIFEST.parent / Path(file_name)
            if image_path.exists() and image_path.is_file():
                return image_path

    for candidate in CARD_IMAGE_MANIFEST.parent.glob(f"{normalized_card_id}.*"):
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
    return f"G-{generation}"


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


def _load_overlay_font(size: int, *, bold: bool, font_key: str | None = None):
    from PIL import ImageFont

    normalized_font_key = normalize_font_key(font_key)
    regular_name, bold_name = font_asset_files(normalized_font_key)

    # These filenames are style references: classic->Arial, serif->Times New Roman,
    # mono->Courier New, script->SnellRoundhand, spooky->Papyrus,
    # pixel->Menlo, playful->Comic Sans MS.
    candidate_paths: list[Path] = []
    if bold:
        candidate_paths.append(CARD_FONTS_DIR / bold_name)
    candidate_paths.append(CARD_FONTS_DIR / regular_name)

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
    font_key: str | None = None,
):
    from PIL import Image, ImageDraw

    width, height = image.size
    # Two-stage overlay: solid base for text contrast, soft fade above for visual blend.
    fade_start = int(height * 0.26)
    solid_band_height = max(1, int(height * 0.22))
    solid_start = max(fade_start, height - solid_band_height)
    fade_height = max(1, solid_start - fade_start)
    solid_alpha = 228

    # Bottom-to-top rarity-tinted overlay keeps text readable while preserving art detail.
    gradient_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gradient_pixels = gradient_layer.load()
    assert gradient_pixels is not None
    for y in range(fade_start, height):
        if y >= solid_start:
            alpha = solid_alpha
        else:
            distance_from_start = y - fade_start
            progress = distance_from_start / max(1, fade_height - 1)

            # Ease-in keeps the upper fade light and ramps density near the solid band.
            alpha = int(round(solid_alpha * (progress**2.2)))

        for x in range(width):
            gradient_pixels[x, y] = (color[0], color[1], color[2], alpha)

    composed = Image.alpha_composite(image.convert("RGBA"), gradient_layer)

    draw = ImageDraw.Draw(composed)
    title_size = max(11, int(round(height * (0.14 / 3) * OVERLAY_TEXT_SCALE)))
    subtitle_size = max(9, int(round(height * (0.104 / 3) * OVERLAY_TEXT_SCALE)))
    title_font = _load_overlay_font(title_size, bold=True, font_key=font_key)
    subtitle_font = _load_overlay_font(subtitle_size, bold=False, font_key=font_key)

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

    cool_text = (0, 0, 0, 255)

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
    generation_line = f"G-{generation}" if generation is not None else "G-????"
    draw.multiline_text((14, 14), f"{code_line}\n{generation_line}", fill=(230, 230, 230), spacing=4)
    draw.text((14, height - 30), "Image unavailable", fill=(188, 188, 188))
    return image


def _apply_buttery_frame_effect(
    surface,
    *,
    body_x: int,
    body_y: int,
    body_width: int,
    body_height: int,
    outer_radius: int,
):
    from PIL import Image, ImageDraw, ImageFilter

    frame_layer = Image.new("RGBA", surface.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame_layer)

    border_thickness = max(7, int(round(min(body_width, body_height) * 0.032)))
    edge_pad = max(1, border_thickness // 4)
    outer_box = (
        body_x - edge_pad,
        body_y - edge_pad,
        body_x + body_width - 1 + edge_pad,
        body_y + body_height - 1 + edge_pad,
    )
    inner_box = (
        outer_box[0] + border_thickness,
        outer_box[1] + border_thickness,
        outer_box[2] - border_thickness,
        outer_box[3] - border_thickness,
    )

    # Build a ring mask so we only paint frame pixels.
    ring_mask = Image.new("L", surface.size, 0)
    ring_draw = ImageDraw.Draw(ring_mask)
    ring_draw.rounded_rectangle(outer_box, radius=outer_radius + edge_pad, fill=255)
    if inner_box[2] > inner_box[0] and inner_box[3] > inner_box[1]:
        ring_draw.rounded_rectangle(
            inner_box,
            radius=max(2, outer_radius - 1),
            fill=0,
        )

    # Paint a warm vertical metallic gradient into the frame ring.
    gradient_layer = Image.new("RGBA", surface.size, (0, 0, 0, 0))
    gradient_pixels = gradient_layer.load()
    mask_pixels = ring_mask.load()
    assert gradient_pixels is not None
    assert mask_pixels is not None
    top = outer_box[1]
    bottom = outer_box[3]
    span = max(1, bottom - top)
    for y in range(max(0, top), min(surface.height, bottom + 1)):
        progress = (y - top) / span
        if progress < 0.35:
            mix = progress / 0.35
            r = int(round(255 + (242 - 255) * mix))
            g = int(round(232 + (190 - 232) * mix))
            b = int(round(142 + (68 - 142) * mix))
        else:
            mix = (progress - 0.35) / 0.65
            r = int(round(242 + (171 - 242) * mix))
            g = int(round(190 + (112 - 190) * mix))
            b = int(round(68 + (30 - 68) * mix))

        for x in range(max(0, outer_box[0]), min(surface.width, outer_box[2] + 1)):
            mask_alpha_raw = mask_pixels[x, y]
            if isinstance(mask_alpha_raw, tuple):
                mask_alpha = int(mask_alpha_raw[0]) if mask_alpha_raw else 0
            else:
                mask_alpha = int(mask_alpha_raw)
            if mask_alpha > 0:
                gradient_pixels[x, y] = (r, g, b, int(round(228 * (mask_alpha / 255))))

    frame_layer = Image.alpha_composite(frame_layer, gradient_layer)
    draw = ImageDraw.Draw(frame_layer)

    draw.rounded_rectangle(
        outer_box,
        radius=outer_radius + edge_pad,
        outline=(255, 236, 170, 170),
        width=max(2, border_thickness // 3),
    )
    draw.rounded_rectangle(
        (
            outer_box[0] + 1,
            outer_box[1] + 1,
            outer_box[2] - 1,
            outer_box[3] - 1,
        ),
        radius=max(2, outer_radius + edge_pad - 1),
        outline=(128, 79, 22, 112),
        width=max(1, border_thickness // 4),
    )

    # Add top specular sweep so it reads glossy rather than matte.
    draw.arc(
        (
            outer_box[0] + border_thickness,
            outer_box[1] - border_thickness,
            outer_box[2] - border_thickness,
            outer_box[1] + int(round(body_height * 0.24)),
        ),
        start=200,
        end=338,
        fill=(255, 247, 206, 150),
        width=max(2, border_thickness // 3),
    )

    drip_layer = Image.new("RGBA", surface.size, (0, 0, 0, 0))
    drip_draw = ImageDraw.Draw(drip_layer)

    top_y = outer_box[1] + border_thickness - 1
    drip_count = max(4, body_width // 52)
    min_x = outer_box[0] + border_thickness
    max_x = outer_box[2] - border_thickness
    if max_x > min_x:
        span = max_x - min_x
        for idx in range(drip_count):
            progress = (idx + 1) / (drip_count + 1)
            center_x = min_x + int(round(progress * span))
            drip_width = max(8, border_thickness + (idx % 3) * 2)
            drip_height = max(12, int(round(body_height * (0.05 + ((idx % 4) * 0.01)))))
            left = center_x - (drip_width // 2)
            right = center_x + (drip_width // 2)
            bottom = top_y + drip_height

            drip_draw.rounded_rectangle(
                (left, top_y, right, bottom),
                radius=max(3, drip_width // 2),
                fill=(242, 193, 70, 214),
            )
            drip_draw.ellipse(
                (
                    left - 1,
                    bottom - drip_width // 2,
                    right + 1,
                    bottom + drip_width // 2,
                ),
                fill=(118, 72, 18, 164),
            )
            drip_draw.ellipse(
                (left + 1, top_y - 1, right - 1, top_y + max(3, drip_width // 3)),
                fill=(255, 238, 170, 148),
            )

        pool_count = drip_count + 2
        for idx in range(pool_count):
            progress = (idx + 0.5) / pool_count
            center_x = min_x + int(round(progress * span))
            pool_w = max(9, border_thickness * 2 + ((idx + 1) % 3) * 2)
            pool_h = max(6, border_thickness)
            drip_draw.ellipse(
                (
                    center_x - pool_w // 2,
                    top_y - pool_h // 2,
                    center_x + pool_w // 2,
                    top_y + pool_h // 2,
                ),
                fill=(244, 198, 77, 180),
            )

    softened_drips = drip_layer.filter(ImageFilter.GaussianBlur(radius=0.85))

    glow_layer = Image.new("RGBA", surface.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.rounded_rectangle(
        outer_box,
        radius=outer_radius + edge_pad,
        outline=(255, 214, 110, 86),
        width=max(3, border_thickness // 2),
    )
    softened_glow = glow_layer.filter(ImageFilter.GaussianBlur(radius=2.4))

    composited = Image.alpha_composite(surface.convert("RGBA"), softened_glow)
    composited = Image.alpha_composite(composited, frame_layer)
    return Image.alpha_composite(composited, softened_drips)


def _load_frame_image(frame_key: str, size: tuple[int, int]):
    resolved_frame_path = frame_path(frame_key)
    if resolved_frame_path is None:
        return None

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        overlay = Image.open(resolved_frame_path).convert("RGBA")
    except Exception:
        return None

    if overlay.size != size:
        overlay = overlay.resize(size, resample=Image.Resampling.LANCZOS)
    return overlay


def _antialiased_rounded_mask(size: tuple[int, int], radius: int, *, scale: int = 4):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    width, height = size
    if width <= 0 or height <= 0:
        return None

    clamped_radius = max(0, min(radius, min(width, height) // 2))
    hi_size = (max(1, width * scale), max(1, height * scale))
    hi_radius = max(0, clamped_radius * scale)

    hi_mask = Image.new("L", hi_size, 0)
    hi_draw = ImageDraw.Draw(hi_mask)
    hi_draw.rounded_rectangle(
        (0, 0, hi_size[0] - 1, hi_size[1] - 1),
        radius=hi_radius,
        fill=255,
    )
    return hi_mask.resize((width, height), resample=Image.Resampling.LANCZOS)


def _apply_color_tint(image, *, color: tuple[int, int, int], strength: float = 0.26):
    from PIL import Image

    base = image.convert("RGB")
    overlay = Image.new("RGB", base.size, color)
    return Image.blend(base, overlay, strength)


def render_card_surface(
    card_id: str,
    *,
    generation: int | None = None,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
    body_scale: float = CARD_BODY_SCALE,
    size: tuple[int, int] = DEFAULT_CARD_RENDER_SIZE,
):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    normalized_frame_key = normalize_frame_key(frame_key)

    width, height = _normalized_card_size(size)
    effective_body_scale = FRAMED_CARD_BODY_SCALE if normalized_frame_key is not None else body_scale
    clamped_body_scale = min(max(effective_body_scale, 0.0), 1.0)
    max_body_width = max(40, int(round(width * clamped_body_scale)))
    max_body_height = max(56, int(round(height * clamped_body_scale)))
    body_target_ratio = 1.0 / CARD_BODY_ASPECT_RATIO if CARD_BODY_ASPECT_RATIO > 0 else (1.0 / 1.6)
    if (max_body_width / max_body_height) > body_target_ratio:
        body_height = max_body_height
        body_width = max(1, int(round(body_height * body_target_ratio)))
    else:
        body_width = max_body_width
        body_height = max(1, int(round(body_width / body_target_ratio)))
    body_x = (width - body_width) // 2
    body_y = (height - body_height) // 2

    border_px = max(6, int(round(min(body_width, body_height) * 0.03)))
    outer_radius = max(border_px + 4, int(round(min(body_width, body_height) * 0.055)))
    inner_width = max(1, body_width - (border_px * 2))
    inner_height = max(1, body_height - (border_px * 2))
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
    elif normalized_morph_key == MORPH_INVERSE:
        fitted = ImageOps.invert(fitted.convert("RGB"))
    elif normalized_morph_key == MORPH_TINT_ROSE:
        fitted = _apply_color_tint(fitted, color=(255, 92, 140), strength=0.24)
    elif normalized_morph_key == MORPH_TINT_AQUA:
        fitted = _apply_color_tint(fitted, color=(74, 214, 228), strength=0.22)
    elif normalized_morph_key == MORPH_TINT_LIME:
        fitted = _apply_color_tint(fitted, color=(162, 232, 80), strength=0.20)
    elif normalized_morph_key == MORPH_TINT_WARM:
        fitted = _apply_color_tint(fitted, color=(255, 170, 88), strength=0.30)
    elif normalized_morph_key == MORPH_TINT_COOL:
        fitted = _apply_color_tint(fitted, color=(98, 170, 255), strength=0.28)
    elif normalized_morph_key == MORPH_TINT_VIOLET:
        fitted = _apply_color_tint(fitted, color=(176, 112, 255), strength=0.32)

    fitted = _apply_text_legibility_overlay(
        fitted,
        card_id=normalized_card_id,
        generation=generation,
        color=rarity_border_color(normalized_card_id),
        font_key=normalize_font_key(font_key),
    )
    if normalized_morph_key == MORPH_UPSIDE_DOWN:
        fitted = fitted.transpose(Image.Transpose.ROTATE_180)

    card_body = Image.new("RGBA", (body_width, body_height), (0, 0, 0, 0))

    # Build border using an anti-aliased rounded alpha mask for smoother edges.
    border_layer = Image.new(
        "RGBA",
        (body_width, body_height),
        rarity_border_color(normalized_card_id) + (255,),
    )
    outer_mask = _antialiased_rounded_mask(
        (body_width, body_height),
        outer_radius,
        scale=BORDER_MASK_SUPERSAMPLE_SCALE,
    )
    if outer_mask is not None:
        border_layer.putalpha(outer_mask)

    art_layer = Image.new("RGBA", (body_width, body_height), (0, 0, 0, 0))
    inner_mask = _antialiased_rounded_mask(
        (inner_width, inner_height),
        inner_radius,
        scale=BORDER_MASK_SUPERSAMPLE_SCALE,
    )
    if inner_mask is None:
        inner_mask = Image.new("L", (inner_width, inner_height), 255)
    art_layer.paste(fitted, (border_px, border_px), mask=inner_mask)

    card_body = Image.alpha_composite(border_layer, art_layer)

    card_surface = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    card_surface.paste(card_body, (body_x, body_y), card_body)

    if normalized_frame_key is not None:
        overlay = _load_frame_image(normalized_frame_key, (width, height))
        if overlay is not None:
            card_surface = Image.alpha_composite(card_surface, overlay)

    return card_surface


def render_card_image_bytes(
    card_id: str,
    *,
    generation: int | None = None,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
    size: tuple[int, int] = DEFAULT_CARD_RENDER_SIZE,
) -> bytes | None:
    rendered_surface = render_card_surface(
        card_id,
        generation=generation,
        morph_key=morph_key,
        frame_key=frame_key,
        font_key=font_key,
        size=size,
    )
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
    frame_key: str | None = None,
    font_key: str | None = None,
    size: tuple[int, int] = DEFAULT_CARD_RENDER_SIZE,
) -> tuple[str | None, discord.File | None]:
    normalized_card_id = normalize_card_id(card_id)
    normalized_morph_key = normalize_morph_key(morph_key)
    normalized_frame_key = normalize_frame_key(frame_key)
    normalized_font_key = normalize_font_key(font_key)

    rendered_image = render_card_image_bytes(
        normalized_card_id,
        generation=generation,
        morph_key=normalized_morph_key,
        frame_key=normalized_frame_key,
        font_key=normalized_font_key,
        size=size,
    )
    if rendered_image is not None:
        morph_suffix = normalized_morph_key or "base"
        frame_suffix = normalized_frame_key or "base"
        font_suffix = normalized_font_key or "base"
        file_name = f"{normalized_card_id}_{morph_suffix}_{frame_suffix}_{font_suffix}_card.png"
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


def render_morph_transition_image_bytes(
    card_id: str,
    *,
    generation: int | None = None,
    before_morph_key: str | None = None,
    after_morph_key: str | None = None,
    before_frame_key: str | None = None,
    after_frame_key: str | None = None,
    before_font_key: str | None = None,
    after_font_key: str | None = None,
    hide_after: bool = False,
    size: tuple[int, int] = DEFAULT_CARD_RENDER_SIZE,
) -> bytes | None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    normalized_card_id = normalize_card_id(card_id)
    normalized_before = normalize_morph_key(before_morph_key)
    normalized_after = normalize_morph_key(after_morph_key)
    normalized_before_frame = normalize_frame_key(before_frame_key)
    normalized_after_frame = normalize_frame_key(after_frame_key)
    normalized_before_font = normalize_font_key(before_font_key)
    normalized_after_font = normalize_font_key(after_font_key)

    before_surface = render_card_surface(
        normalized_card_id,
        generation=generation,
        morph_key=normalized_before,
        frame_key=normalized_before_frame,
        font_key=normalized_before_font,
        size=size,
    )
    after_surface = None
    if not hide_after:
        after_surface = render_card_surface(
            normalized_card_id,
            generation=generation,
            morph_key=normalized_after,
            frame_key=normalized_after_frame,
            font_key=normalized_after_font,
            size=size,
        )
    if before_surface is None:
        return None

    if hide_after:
        after_surface = Image.new("RGBA", before_surface.size, (0, 0, 0, 0))
        draw_after = ImageDraw.Draw(after_surface)
        question_font = _load_overlay_font(max(48, before_surface.size[1] // 4), bold=True)
        question = "?"
        question_bbox = draw_after.textbbox((0, 0), question, font=question_font)
        question_w = max(1, question_bbox[2] - question_bbox[0])
        question_h = max(1, question_bbox[3] - question_bbox[1])
        question_x = (before_surface.size[0] - question_w) // 2
        question_y = (before_surface.size[1] - question_h) // 2
        draw_after.text(
            (question_x, question_y),
            question,
            fill=(245, 245, 245, 255),
            font=question_font,
        )

    if after_surface is None:
        return None

    card_width, card_height = before_surface.size
    pad = 16
    gap = 18
    arrow_width = max(56, card_width // 3)
    canvas_width = (pad * 2) + card_width + gap + arrow_width + gap + card_width
    canvas_height = (pad * 2) + card_height

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    left_x = pad
    card_y = pad
    arrow_x = left_x + card_width + gap
    right_x = arrow_x + arrow_width + gap

    canvas.paste(before_surface, (left_x, card_y), before_surface)
    canvas.paste(after_surface, (right_x, card_y), after_surface)

    draw = ImageDraw.Draw(canvas)
    center_y = canvas_height // 2
    line_start = arrow_x + 8
    line_end = arrow_x + arrow_width - 12
    draw.line(
        (line_start, center_y, line_end, center_y),
        fill=(245, 245, 245, 255),
        width=max(4, card_height // 80),
    )
    head_half = max(10, card_height // 20)
    draw.polygon(
        [
            (line_end, center_y),
            (line_end - head_half, center_y - head_half),
            (line_end - head_half, center_y + head_half),
        ],
        fill=(245, 245, 245, 255),
    )

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


def morph_transition_image_payload(
    card_id: str,
    *,
    generation: int | None = None,
    before_morph_key: str | None = None,
    after_morph_key: str | None = None,
    before_frame_key: str | None = None,
    after_frame_key: str | None = None,
    before_font_key: str | None = None,
    after_font_key: str | None = None,
    hide_after: bool = False,
) -> tuple[str | None, discord.File | None]:
    rendered_image = render_morph_transition_image_bytes(
        card_id,
        generation=generation,
        before_morph_key=before_morph_key,
        after_morph_key=after_morph_key,
        before_frame_key=before_frame_key,
        after_frame_key=after_frame_key,
        before_font_key=before_font_key,
        after_font_key=after_font_key,
        hide_after=hide_after,
    )
    if rendered_image is None:
        return None, None

    normalized_card_id = normalize_card_id(card_id)
    before_suffix = normalize_morph_key(before_morph_key) or "base"
    after_suffix = normalize_morph_key(after_morph_key) or "base"
    before_frame_suffix = normalize_frame_key(before_frame_key) or "base"
    after_frame_suffix = normalize_frame_key(after_frame_key) or "base"
    before_font_suffix = normalize_font_key(before_font_key) or "base"
    after_font_suffix = normalize_font_key(after_font_key) or "base"
    file_name = (
        f"{normalized_card_id}_{before_suffix}_{before_frame_suffix}"
        f"_{before_font_suffix}_to_{after_suffix}_{after_frame_suffix}_{after_font_suffix}_morph.png"
    )
    attachment_url = f"attachment://{file_name}"
    return attachment_url, discord.File(io.BytesIO(rendered_image), filename=file_name)
