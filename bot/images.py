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


def _apply_duotone(image, *, dark: tuple[int, int, int], light: tuple[int, int, int]):
    from PIL import ImageOps

    gray = ImageOps.grayscale(image.convert("RGB"))
    return ImageOps.colorize(gray, black=dark, white=light)


def _apply_tritone(image):
    from PIL import Image, ImageOps

    base = image.convert("RGB")
    gray = ImageOps.grayscale(base)
    low = ImageOps.colorize(gray, black=(12, 18, 56), white=(136, 198, 255)).convert("RGB")
    high = ImageOps.colorize(gray, black=(44, 12, 64), white=(255, 182, 104)).convert("RGB")
    mask = gray.point(lambda value: 255 if value >= 132 else 0)
    mixed = Image.composite(high, low, mask)
    return Image.blend(base, mixed, 0.42)


def _apply_partial_inversion(image):
    from PIL import Image, ImageOps

    base = image.convert("RGB")
    inverted = ImageOps.invert(base)
    mask = Image.new("L", base.size, 0)

    start_x = int(base.width * 0.60)
    for x in range(start_x, base.width):
        ratio = (x - start_x) / max(1, base.width - start_x)
        alpha = int(255 * min(1.0, ratio * 1.25))
        for y in range(base.height):
            mask.putpixel((x, y), alpha)

    return Image.composite(inverted, base, mask)


def _apply_channel_shift(
    image,
    *,
    r_mul: float = 1.0,
    g_mul: float = 1.0,
    b_mul: float = 1.0,
    r_add: int = 0,
    g_add: int = 0,
    b_add: int = 0,
):
    from PIL import Image

    red, green, blue = image.convert("RGB").split()

    def _apply(band, mul: float, add: int):
        return band.point(lambda value: max(0, min(255, int(round((value * mul) + add)))))

    shifted_red = _apply(red, r_mul, r_add)
    shifted_green = _apply(green, g_mul, g_add)
    shifted_blue = _apply(blue, b_mul, b_add)
    return Image.merge("RGB", (shifted_red, shifted_green, shifted_blue))


def _apply_quadrant_swap(image):
    from PIL import Image

    base = image.convert("RGB")
    mid_x = base.width // 2
    mid_y = base.height // 2

    tl = base.crop((0, 0, mid_x, mid_y))
    tr = base.crop((mid_x, 0, base.width, mid_y))
    bl = base.crop((0, mid_y, mid_x, base.height))
    br = base.crop((mid_x, mid_y, base.width, base.height))

    out = Image.new("RGB", base.size)
    out.paste(br, (0, 0))
    out.paste(bl, (mid_x, 0))
    out.paste(tr, (0, mid_y))
    out.paste(tl, (mid_x, mid_y))
    return out


def _apply_double_vision(image):
    from PIL import Image, ImageChops

    base = image.convert("RGB")
    ghost = ImageChops.offset(base, 6, 0)
    return Image.blend(base, ghost, 0.35)


def _apply_motion_blur(image, *, horizontal: bool, radius: int = 4):
    from PIL import Image, ImageChops

    base = image.convert("RGB")
    offsets = range(-radius, radius + 1)
    accum = Image.new("RGB", base.size, (0, 0, 0))
    weight = 1.0 / float(len(list(offsets)))

    for offset in offsets:
        shifted = ImageChops.offset(base, offset if horizontal else 0, 0 if horizontal else offset)
        accum = Image.blend(accum, shifted, weight)

    return accum


def _apply_vignette(image, *, reverse: bool = False, strength: float = 0.48):
    from PIL import Image, ImageDraw, ImageFilter

    base = image.convert("RGB")
    width, height = base.size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    inset_x = max(12, width // 7)
    inset_y = max(12, height // 7)
    draw.ellipse((inset_x, inset_y, width - inset_x, height - inset_y), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(8.0, min(width, height) * 0.12)))

    edge_target = Image.new("RGB", (width, height), (255, 255, 255) if reverse else (0, 0, 0))
    edged = Image.blend(base, edge_target, 0.60 if reverse else strength)
    return Image.composite(base, edged, mask)


def _apply_scanlines(image, *, spacing: int = 4, opacity: int = 34):
    from PIL import Image, ImageDraw

    base = image.convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for y in range(0, base.height, max(1, spacing)):
        draw.line((0, y, base.width, y), fill=(0, 0, 0, opacity), width=1)

    composed = Image.alpha_composite(base.convert("RGBA"), overlay)
    return composed.convert("RGB")


def _apply_checker_overlay(image, *, cell_size: int = 12, opacity: int = 30):
    from PIL import Image, ImageDraw

    base = image.convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    step = max(3, cell_size)

    for y in range(0, base.height, step):
        row_index = y // step
        for x in range(0, base.width, step):
            col_index = x // step
            if (row_index + col_index) % 2 == 0:
                draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(255, 255, 255, opacity))

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def _apply_diagonal_stripes(image, *, spacing: int = 18, opacity: int = 24):
    from PIL import Image, ImageDraw

    base = image.convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    span = base.width + base.height
    step = max(6, spacing)
    for start in range(-base.height, span, step):
        draw.line((start, 0, start + base.height, base.height), fill=(255, 255, 255, opacity), width=2)
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def _apply_film_grain(image, *, alpha: float = 0.10):
    from PIL import Image

    base = image.convert("RGB")
    noise = Image.effect_noise(base.size, 16)
    noise_rgb = noise.convert("RGB")
    return Image.blend(base, noise_rgb, alpha)


def _apply_dust_specks(image):
    from PIL import Image, ImageDraw

    base = image.convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    step = max(14, min(base.size) // 18)
    offset = step // 2
    for y in range(offset, base.height, step):
        for x in range(offset, base.width, step):
            if ((x // step) + (y // step)) % 3 == 0:
                draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(245, 238, 225, 64))

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def _apply_glitch_slices(image):
    from PIL import ImageChops

    base = image.convert("RGB")
    shifted = base.copy()
    band_height = max(6, base.height // 18)
    for band in range(0, base.height, band_height):
        offset = ((band // band_height) % 5 - 2) * 5
        crop = base.crop((0, band, base.width, min(base.height, band + band_height)))
        shifted.paste(ImageChops.offset(crop, offset, 0), (0, band))
    return shifted


def _apply_rgb_shift(image):
    from PIL import Image

    base = image.convert("RGB")
    red, green, blue = base.split()
    shifted_red = red.transform(red.size, Image.Transform.AFFINE, (1, 0, 2, 0, 1, 0))
    shifted_blue = blue.transform(blue.size, Image.Transform.AFFINE, (1, 0, -2, 0, 1, 0))
    return Image.merge("RGB", (shifted_red, green, shifted_blue))


def _apply_dead_pixels(image):
    base = image.convert("RGB")
    result = base.copy()
    step = max(16, min(base.size) // 14)

    for y in range(0, base.height, step):
        for x in range(0, base.width, step):
            selector = ((x // step) * 7 + (y // step) * 13) % 19
            if selector == 0:
                result.putpixel((x, y), (0, 0, 0))
            elif selector == 1:
                result.putpixel((x, y), (255, 255, 255))
            elif selector == 2:
                result.putpixel((x, y), (255, 0, 255))

    return result


def _apply_pixelate(image, *, factor: int = 8):
    from PIL import Image

    base = image.convert("RGB")
    width, height = base.size
    block = max(2, factor)
    small = base.resize((max(1, width // block), max(1, height // block)), resample=Image.Resampling.NEAREST)
    return small.resize((width, height), resample=Image.Resampling.NEAREST)


def _apply_edge_tint(image, *, color: tuple[int, int, int], strength: float = 0.38):
    from PIL import Image, ImageDraw, ImageFilter

    base = image.convert("RGB")
    overlay = Image.new("RGB", base.size, color)
    tinted = Image.blend(base, overlay, strength)

    mask = Image.new("L", base.size, 0)
    draw = ImageDraw.Draw(mask)
    margin = max(8, min(base.size) // 10)
    draw.rectangle((0, 0, base.width - 1, base.height - 1), fill=255)
    draw.rectangle((margin, margin, base.width - margin, base.height - margin), fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(4.0, margin * 0.3)))
    return Image.composite(tinted, base, mask)


def _apply_halftone(image):
    from PIL import Image, ImageOps

    base = image.convert("RGB")
    gray = ImageOps.grayscale(base)
    small = gray.resize((max(1, base.width // 6), max(1, base.height // 6)), resample=Image.Resampling.BOX)
    dots = small.point(lambda value: 255 if value > 120 else 0)
    dots = dots.resize(base.size, resample=Image.Resampling.NEAREST).convert("RGB")
    return Image.blend(base, dots, 0.24)


def _apply_morph_effect(image, morph_key: str | None):
    if morph_key is None:
        return image.convert("RGB")

    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    base = image.convert("RGB")

    alias_map: dict[str, str] = {
        "grayscale": "black_and_white",
        "saturation_up": "high_saturation",
        "saturation_down": "desaturated",
        "contrast_up": "ultra_contrast",
        "contrast_down": "low_contrast",
        "brighten": "brightened",
        "darken": "darkened",
        "duotone": "duotone_sunset",
        "vintage_fade": "sepia",
        "moonlight_cast": "duotone_moonlight",
        "toxic_cast": "neon_cyber",
        "small_tilt": "tilt_left",
        "strong_tilt": "tilt_right",
        "mirrored_halves": "flip_horizontal",
        "slice_shuffle": "glitch_slices",
        "off_center_crop_zoom": "mosaic",
        "thin_gold_border": "tint_gold",
        "thick_gold_border": "tint_gold",
        "thin_silver_border": "frosted_edges",
        "thick_silver_border": "frosted_edges",
        "thin_bronze_border": "worn_edges",
        "thick_bronze_border": "worn_edges",
        "silver_border": "frosted_edges",
        "bronze_border": "worn_edges",
        "rainbow_border": "tint_violet",
        "neon_border": "neon_cyber",
        "double_border": "edge_glow",
        "dashed_border": "scanlines",
        "dotted_border": "dust_specks",
        "vignette_edge": "vignette",
        "glow_border": "edge_glow",
        "shadow_border": "reverse_vignette",
        "checker_border": "checker_overlay",
        "barcode_border": "scanlines",
        "pixel_frame": "pixelate",
        "outer_glow": "edge_glow",
        "inner_glow": "soft_glow",
        "spotlight_left": "reverse_vignette",
        "spotlight_center": "reverse_vignette",
        "spotlight_right": "reverse_vignette",
        "halo": "reverse_vignette",
        "rim_light": "edge_glow",
        "light_leak_left": "tint_warm",
        "light_leak_right": "tint_cool",
        "dreamy_glow_haze": "bloom",
        "neon_edge_glow": "neon_cyber",
        "soft_blur": "gaussian_blur",
        "heavy_blur": "motion_blur_h",
        "soft_focus": "soft_glow",
        "ghosted_duplicate": "double_vision",
        "noise_grain": "film_grain",
        "scratches": "contour",
        "crosshatch": "diagonal_stripes",
        "newsprint": "halftone",
        "frosted_overlay": "frosted_edges",
        "smudged_ink": "emboss",
        "crackle_aged_print": "photocopy",
        "glitter_noise": "heavy_grain",
        "cloudy_veil": "soft_glow",
        "corner_wear": "worn_edges",
        "edge_wear": "worn_edges",
        "fold_lines": "diagonal_stripes",
        "scuffs": "film_grain",
        "burn_corners": "burnt_edges",
        "soot_darkening": "darkened",
        "water_stain": "frosted_edges",
        "ink_splatter": "dust_specks",
        "torn_corner_illusion": "worn_edges",
        "top_sun_fade": "brightened",
        "static_corruption": "dead_pixels",
        "glitch_tears": "glitch_slices",
        "polka_dots": "dust_specks",
        "stripes": "diagonal_stripes",
        "chevron": "diagonal_stripes",
        "checkerboard": "checker_overlay",
        "grid": "checker_overlay",
        "hex_grid": "checker_overlay",
        "zigzag": "diagonal_stripes",
        "concentric_rings": "reverse_vignette",
        "wave_pattern": "motion_blur_h",
        "star_field": "dust_specks",
        "rain_streaks": "scanlines",
        "lightning_zigzags": "edge_glow",
        "circuit_traces": "contour",
        "glyph_rain": "security_cam",
        "binary_overlay": "security_cam",
        "web_lattice": "checker_overlay",
        "rgb_offset": "rgb_shift",
        "glitch_slices_horizontal": "glitch_slices",
        "glitch_slices_vertical": "glitch_slices",
        "random_band_displacement": "glitch_slices",
        "static_burst": "heavy_grain",
        "corrupted_strip": "glitch_slices",
        "jitter": "double_vision",
        "frame_tearing": "top_bottom_swap",
        "low_bit_8": "posterized",
        "low_bit_4": "mosaic",
        "pixelation": "pixelate",
        "mosaic_blocks": "mosaic",
        "terminal_green": "security_cam",
        "blue_screen_tint": "tint_blue",
        "chromatic_aberration": "rgb_shift",
        "prism_split": "rgb_shift",
        "kaleidoscope_quadrant_mirror": "quadrant_swap",
        "radial_echo": "double_vision",
        "toxic": "toxic_cast",
        "arcane": "void",
        "storm": "channel_shift_cool",
        "retro_arcade": "posterized",
        "vintage_print": "photocopy",
        "haunted": "xray",
        "dreamscape": "soft_glow",
        "nightmare": "infernal",
        "industrial": "contour",
        "celestial": "holy",
        "lunar": "duotone_moonlight",
        "solar": "duotone_sunset",
        "photocopied": "photocopy",
        "flashlight_mode": "reverse_vignette",
        "security_cam_mono": "security_cam",
        "xray_fake": "xray",
        "low_ink_printer": "low_ink",
        "lagging_echo": "double_vision",
    }
    morph_key = alias_map.get(morph_key, morph_key)

    if morph_key == "black_and_white":
        return ImageOps.grayscale(base).convert("RGB")
    if morph_key == "inverse":
        return ImageOps.invert(base)
    if morph_key == "sepia":
        return _apply_duotone(base, dark=(38, 24, 16), light=(236, 209, 161))

    tint_settings: dict[str, tuple[tuple[int, int, int], float]] = {
        "tint_rose": ((255, 92, 140), 0.24),
        "tint_aqua": ((74, 214, 228), 0.22),
        "tint_lime": ((162, 232, 80), 0.20),
        "tint_warm": ((255, 170, 88), 0.30),
        "tint_cool": ((98, 170, 255), 0.28),
        "tint_violet": ((176, 112, 255), 0.32),
        "tint_red": ((230, 72, 66), 0.24),
        "tint_blue": ((72, 132, 255), 0.24),
        "tint_green": ((90, 210, 120), 0.24),
        "tint_gold": ((248, 192, 72), 0.30),
        "tint_pink": ((255, 145, 194), 0.24),
        "tint_cyan": ((70, 229, 238), 0.24),
    }
    tint_config = tint_settings.get(morph_key)
    if tint_config is not None:
        tint_color, tint_strength = tint_config
        return _apply_color_tint(base, color=tint_color, strength=tint_strength)

    if morph_key == "high_saturation":
        return ImageEnhance.Color(base).enhance(1.55)
    if morph_key == "desaturated":
        return ImageEnhance.Color(base).enhance(0.42)
    if morph_key == "ultra_contrast":
        return ImageEnhance.Contrast(base).enhance(1.55)
    if morph_key == "low_contrast":
        return ImageEnhance.Contrast(base).enhance(0.72)
    if morph_key == "brightened":
        return ImageEnhance.Brightness(base).enhance(1.20)
    if morph_key == "darkened":
        return ImageEnhance.Brightness(base).enhance(0.78)
    if morph_key == "posterized":
        return ImageOps.posterize(base, bits=4)
    if morph_key == "solarized":
        return ImageOps.solarize(base, threshold=132)
    if morph_key == "threshold_bw":
        return base.convert("L").point(lambda value: 255 if value > 122 else 0).convert("RGB")
    if morph_key == "duotone_sunset":
        return _apply_duotone(base, dark=(48, 11, 62), light=(255, 172, 92))
    if morph_key == "duotone_moonlight":
        return _apply_duotone(base, dark=(14, 28, 66), light=(175, 220, 252))
    if morph_key == "tritone":
        return _apply_tritone(base)
    if morph_key == "channel_shift_warm":
        return _apply_channel_shift(base, r_mul=1.12, g_mul=1.00, b_mul=0.92, r_add=8)
    if morph_key == "channel_shift_cool":
        return _apply_channel_shift(base, r_mul=0.90, g_mul=1.02, b_mul=1.14, b_add=8)
    if morph_key == "partial_inversion":
        return _apply_partial_inversion(base)

    if morph_key == "flip_horizontal":
        return ImageOps.mirror(base)
    if morph_key == "flip_vertical":
        return ImageOps.flip(base)
    if morph_key == "rotate_90":
        return base.rotate(90, resample=Image.Resampling.BICUBIC, expand=False)
    if morph_key == "rotate_180":
        return base.transpose(Image.Transpose.ROTATE_180)
    if morph_key == "rotate_270":
        return base.rotate(270, resample=Image.Resampling.BICUBIC, expand=False)
    if morph_key == "tilt_left":
        return base.rotate(8, resample=Image.Resampling.BICUBIC, expand=False)
    if morph_key == "tilt_right":
        return base.rotate(-8, resample=Image.Resampling.BICUBIC, expand=False)
    if morph_key == "shear_left":
        return base.transform(base.size, Image.Transform.AFFINE, (1, -0.16, 24, 0, 1, 0), resample=Image.Resampling.BICUBIC)
    if morph_key == "shear_right":
        return base.transform(base.size, Image.Transform.AFFINE, (1, 0.16, -24, 0, 1, 0), resample=Image.Resampling.BICUBIC)
    if morph_key == "top_bottom_swap":
        top = base.crop((0, 0, base.width, base.height // 2))
        bottom = base.crop((0, base.height // 2, base.width, base.height))
        swapped = base.copy()
        swapped.paste(bottom, (0, 0))
        swapped.paste(top, (0, base.height - top.height))
        return swapped
    if morph_key == "quadrant_swap":
        return _apply_quadrant_swap(base)

    if morph_key == "vignette":
        return _apply_vignette(base, reverse=False)
    if morph_key == "reverse_vignette":
        return _apply_vignette(base, reverse=True)
    if morph_key == "soft_glow":
        blur = base.filter(ImageFilter.GaussianBlur(radius=3.0))
        return ImageEnhance.Brightness(Image.blend(base, blur, 0.34)).enhance(1.08)
    if morph_key == "bloom":
        blur = base.filter(ImageFilter.GaussianBlur(radius=5.2))
        return ImageEnhance.Brightness(Image.blend(base, blur, 0.46)).enhance(1.14)
    if morph_key == "gaussian_blur":
        return base.filter(ImageFilter.GaussianBlur(radius=2.2))
    if morph_key == "motion_blur_h":
        return _apply_motion_blur(base, horizontal=True, radius=4)
    if morph_key == "motion_blur_v":
        return _apply_motion_blur(base, horizontal=False, radius=4)
    if morph_key == "sharpen":
        return base.filter(ImageFilter.SHARPEN)
    if morph_key == "oversharpen":
        return ImageEnhance.Sharpness(base).enhance(2.2)
    if morph_key == "double_vision":
        return _apply_double_vision(base)
    if morph_key == "emboss":
        return base.filter(ImageFilter.EMBOSS)
    if morph_key == "contour":
        return base.filter(ImageFilter.CONTOUR)
    if morph_key == "edge_glow":
        edges = base.filter(ImageFilter.FIND_EDGES)
        return Image.blend(base, ImageEnhance.Color(edges).enhance(1.3), 0.30)

    if morph_key == "film_grain":
        return _apply_film_grain(base, alpha=0.11)
    if morph_key == "heavy_grain":
        return _apply_film_grain(base, alpha=0.24)
    if morph_key == "dust_specks":
        return _apply_dust_specks(base)
    if morph_key == "scanlines":
        return _apply_scanlines(base, spacing=4, opacity=36)
    if morph_key == "crt_mask":
        return _apply_scanlines(_apply_channel_shift(base, r_mul=1.05, g_mul=1.0, b_mul=0.95), spacing=3, opacity=24)
    if morph_key == "glitch_slices":
        return _apply_glitch_slices(base)
    if morph_key == "rgb_shift":
        return _apply_rgb_shift(base)
    if morph_key == "dead_pixels":
        return _apply_dead_pixels(base)
    if morph_key == "pixelate":
        return _apply_pixelate(base, factor=8)
    if morph_key == "mosaic":
        return _apply_pixelate(base, factor=14)
    if morph_key == "checker_overlay":
        return _apply_checker_overlay(base)
    if morph_key == "diagonal_stripes":
        return _apply_diagonal_stripes(base)
    if morph_key == "halftone":
        return _apply_halftone(base)

    if morph_key == "worn_edges":
        return _apply_edge_tint(base, color=(112, 96, 82), strength=0.30)
    if morph_key == "burnt_edges":
        return _apply_edge_tint(base, color=(70, 22, 10), strength=0.45)
    if morph_key == "frosted_edges":
        return _apply_edge_tint(base, color=(210, 235, 255), strength=0.35)

    if morph_key == "photocopy":
        bw = ImageOps.grayscale(base).convert("RGB")
        high = ImageEnhance.Contrast(bw).enhance(1.5)
        return _apply_film_grain(high, alpha=0.08)
    if morph_key == "blueprint":
        return _apply_duotone(base, dark=(8, 38, 112), light=(199, 227, 255))
    if morph_key == "security_cam":
        mono = _apply_duotone(base, dark=(7, 30, 7), light=(142, 247, 112))
        return _apply_scanlines(mono, spacing=3, opacity=28)
    if morph_key == "xray":
        return ImageOps.invert(ImageOps.grayscale(base)).convert("RGB")
    if morph_key == "low_ink":
        return _apply_channel_shift(base, r_mul=0.82, g_mul=0.88, b_mul=0.84, r_add=18, g_add=18, b_add=18)

    if morph_key == "neon_cyber":
        shifted = _apply_rgb_shift(base)
        tinted = _apply_color_tint(shifted, color=(66, 220, 255), strength=0.20)
        return _apply_scanlines(tinted, spacing=3, opacity=18)
    if morph_key == "frozen":
        cool = _apply_color_tint(base, color=(166, 222, 255), strength=0.30)
        return ImageEnhance.Contrast(cool).enhance(1.12)
    if morph_key == "infernal":
        hot = _apply_color_tint(base, color=(255, 90, 44), strength=0.32)
        return ImageEnhance.Contrast(hot).enhance(1.18)
    if morph_key == "void":
        dark = ImageEnhance.Brightness(base).enhance(0.62)
        return _apply_color_tint(dark, color=(122, 52, 170), strength=0.25)
    if morph_key == "holy":
        bright = ImageEnhance.Brightness(base).enhance(1.18)
        return _apply_color_tint(bright, color=(255, 244, 188), strength=0.24)

    return base


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
            _img = Image.open(io.BytesIO(raw_image)).convert("RGBA")
            _bg = Image.new("RGBA", _img.size, (255, 255, 255, 255))
            _bg.alpha_composite(_img)
            source_image = _bg.convert("RGB")
        except Exception:
            source_image = None

    if source_image is None:
        source_image = _placeholder_card_art(normalized_card_id, generation, (inner_width, inner_height))

    if source_image is None:
        return None

    fitted = ImageOps.fit(source_image, (inner_width, inner_height), method=Image.Resampling.LANCZOS)
    normalized_morph_key = normalize_morph_key(morph_key)
    fitted = _apply_morph_effect(fitted, normalized_morph_key)

    fitted = _apply_text_legibility_overlay(
        fitted,
        card_id=normalized_card_id,
        generation=generation,
        color=rarity_border_color(normalized_card_id),
        font_key=normalize_font_key(font_key),
    )
    if normalized_morph_key == "upside_down":
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
