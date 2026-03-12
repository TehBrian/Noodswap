from collections import Counter
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
MORPH_SEPIA: Final[str] = "sepia"
MORPH_HIGH_SATURATION: Final[str] = "high_saturation"
MORPH_DESATURATED: Final[str] = "desaturated"
MORPH_ULTRA_CONTRAST: Final[str] = "ultra_contrast"
MORPH_LOW_CONTRAST: Final[str] = "low_contrast"
MORPH_BRIGHTENED: Final[str] = "brightened"
MORPH_DARKENED: Final[str] = "darkened"
MORPH_TINT_RED: Final[str] = "tint_red"
MORPH_TINT_BLUE: Final[str] = "tint_blue"
MORPH_TINT_GREEN: Final[str] = "tint_green"
MORPH_TINT_GOLD: Final[str] = "tint_gold"
MORPH_TINT_PINK: Final[str] = "tint_pink"
MORPH_TINT_CYAN: Final[str] = "tint_cyan"
MORPH_POSTERIZED: Final[str] = "posterized"
MORPH_SOLARIZED: Final[str] = "solarized"
MORPH_THRESHOLD_BW: Final[str] = "threshold_bw"
MORPH_DUOTONE_SUNSET: Final[str] = "duotone_sunset"
MORPH_DUOTONE_MOONLIGHT: Final[str] = "duotone_moonlight"
MORPH_TRITONE: Final[str] = "tritone"
MORPH_CHANNEL_SHIFT_WARM: Final[str] = "channel_shift_warm"
MORPH_CHANNEL_SHIFT_COOL: Final[str] = "channel_shift_cool"
MORPH_PARTIAL_INVERSION: Final[str] = "partial_inversion"
MORPH_FLIP_HORIZONTAL: Final[str] = "flip_horizontal"
MORPH_FLIP_VERTICAL: Final[str] = "flip_vertical"
MORPH_ROTATE_90: Final[str] = "rotate_90"
MORPH_ROTATE_180: Final[str] = "rotate_180"
MORPH_ROTATE_270: Final[str] = "rotate_270"
MORPH_TILT_LEFT: Final[str] = "tilt_left"
MORPH_TILT_RIGHT: Final[str] = "tilt_right"
MORPH_SHEAR_LEFT: Final[str] = "shear_left"
MORPH_SHEAR_RIGHT: Final[str] = "shear_right"
MORPH_TOP_BOTTOM_SWAP: Final[str] = "top_bottom_swap"
MORPH_QUADRANT_SWAP: Final[str] = "quadrant_swap"
MORPH_VIGNETTE: Final[str] = "vignette"
MORPH_REVERSE_VIGNETTE: Final[str] = "reverse_vignette"
MORPH_SOFT_GLOW: Final[str] = "soft_glow"
MORPH_BLOOM: Final[str] = "bloom"
MORPH_GAUSSIAN_BLUR: Final[str] = "gaussian_blur"
MORPH_MOTION_BLUR_H: Final[str] = "motion_blur_h"
MORPH_MOTION_BLUR_V: Final[str] = "motion_blur_v"
MORPH_SHARPEN: Final[str] = "sharpen"
MORPH_OVERSHARPEN: Final[str] = "oversharpen"
MORPH_DOUBLE_VISION: Final[str] = "double_vision"
MORPH_EMBOSS: Final[str] = "emboss"
MORPH_CONTOUR: Final[str] = "contour"
MORPH_EDGE_GLOW: Final[str] = "edge_glow"
MORPH_FILM_GRAIN: Final[str] = "film_grain"
MORPH_HEAVY_GRAIN: Final[str] = "heavy_grain"
MORPH_DUST_SPECKS: Final[str] = "dust_specks"
MORPH_SCANLINES: Final[str] = "scanlines"
MORPH_CRT_MASK: Final[str] = "crt_mask"
MORPH_GLITCH_SLICES: Final[str] = "glitch_slices"
MORPH_RGB_SHIFT: Final[str] = "rgb_shift"
MORPH_DEAD_PIXELS: Final[str] = "dead_pixels"
MORPH_PIXELATE: Final[str] = "pixelate"
MORPH_MOSAIC: Final[str] = "mosaic"
MORPH_CHECKER_OVERLAY: Final[str] = "checker_overlay"
MORPH_DIAGONAL_STRIPES: Final[str] = "diagonal_stripes"
MORPH_HALFTONE: Final[str] = "halftone"
MORPH_WORN_EDGES: Final[str] = "worn_edges"
MORPH_BURNT_EDGES: Final[str] = "burnt_edges"
MORPH_FROSTED_EDGES: Final[str] = "frosted_edges"
MORPH_PHOTOCOPY: Final[str] = "photocopy"
MORPH_BLUEPRINT: Final[str] = "blueprint"
MORPH_SECURITY_CAM: Final[str] = "security_cam"
MORPH_XRAY: Final[str] = "xray"
MORPH_LOW_INK: Final[str] = "low_ink"
MORPH_NEON_CYBER: Final[str] = "neon_cyber"
MORPH_FROZEN: Final[str] = "frozen"
MORPH_INFERNAL: Final[str] = "infernal"
MORPH_VOID: Final[str] = "void"
MORPH_HOLY: Final[str] = "holy"
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
    MORPH_SEPIA,
    MORPH_HIGH_SATURATION,
    MORPH_DESATURATED,
    MORPH_ULTRA_CONTRAST,
    MORPH_LOW_CONTRAST,
    MORPH_BRIGHTENED,
    MORPH_DARKENED,
    MORPH_TINT_RED,
    MORPH_TINT_BLUE,
    MORPH_TINT_GREEN,
    MORPH_TINT_GOLD,
    MORPH_TINT_PINK,
    MORPH_TINT_CYAN,
    MORPH_POSTERIZED,
    MORPH_SOLARIZED,
    MORPH_THRESHOLD_BW,
    MORPH_DUOTONE_SUNSET,
    MORPH_DUOTONE_MOONLIGHT,
    MORPH_TRITONE,
    MORPH_CHANNEL_SHIFT_WARM,
    MORPH_CHANNEL_SHIFT_COOL,
    MORPH_PARTIAL_INVERSION,
    MORPH_FLIP_HORIZONTAL,
    MORPH_FLIP_VERTICAL,
    MORPH_ROTATE_90,
    MORPH_ROTATE_180,
    MORPH_ROTATE_270,
    MORPH_TILT_LEFT,
    MORPH_TILT_RIGHT,
    MORPH_SHEAR_LEFT,
    MORPH_SHEAR_RIGHT,
    MORPH_TOP_BOTTOM_SWAP,
    MORPH_QUADRANT_SWAP,
    MORPH_VIGNETTE,
    MORPH_REVERSE_VIGNETTE,
    MORPH_SOFT_GLOW,
    MORPH_BLOOM,
    MORPH_GAUSSIAN_BLUR,
    MORPH_MOTION_BLUR_H,
    MORPH_MOTION_BLUR_V,
    MORPH_SHARPEN,
    MORPH_OVERSHARPEN,
    MORPH_DOUBLE_VISION,
    MORPH_EMBOSS,
    MORPH_CONTOUR,
    MORPH_EDGE_GLOW,
    MORPH_FILM_GRAIN,
    MORPH_HEAVY_GRAIN,
    MORPH_DUST_SPECKS,
    MORPH_SCANLINES,
    MORPH_CRT_MASK,
    MORPH_GLITCH_SLICES,
    MORPH_RGB_SHIFT,
    MORPH_DEAD_PIXELS,
    MORPH_PIXELATE,
    MORPH_MOSAIC,
    MORPH_CHECKER_OVERLAY,
    MORPH_DIAGONAL_STRIPES,
    MORPH_HALFTONE,
    MORPH_WORN_EDGES,
    MORPH_BURNT_EDGES,
    MORPH_FROSTED_EDGES,
    MORPH_PHOTOCOPY,
    MORPH_BLUEPRINT,
    MORPH_SECURITY_CAM,
    MORPH_XRAY,
    MORPH_LOW_INK,
    MORPH_NEON_CYBER,
    MORPH_FROZEN,
    MORPH_INFERNAL,
    MORPH_VOID,
    MORPH_HOLY,
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
    MORPH_SEPIA: "Sepia",
    MORPH_HIGH_SATURATION: "High Saturation",
    MORPH_DESATURATED: "Desaturated",
    MORPH_ULTRA_CONTRAST: "Ultra Contrast",
    MORPH_LOW_CONTRAST: "Low Contrast",
    MORPH_BRIGHTENED: "Brightened",
    MORPH_DARKENED: "Darkened",
    MORPH_TINT_RED: "Red Tint",
    MORPH_TINT_BLUE: "Blue Tint",
    MORPH_TINT_GREEN: "Green Tint",
    MORPH_TINT_GOLD: "Gold Tint",
    MORPH_TINT_PINK: "Pink Tint",
    MORPH_TINT_CYAN: "Cyan Tint",
    MORPH_POSTERIZED: "Posterized",
    MORPH_SOLARIZED: "Solarized",
    MORPH_THRESHOLD_BW: "Threshold B/W",
    MORPH_DUOTONE_SUNSET: "Duotone Sunset",
    MORPH_DUOTONE_MOONLIGHT: "Duotone Moonlight",
    MORPH_TRITONE: "Tritone",
    MORPH_CHANNEL_SHIFT_WARM: "Channel Shift Warm",
    MORPH_CHANNEL_SHIFT_COOL: "Channel Shift Cool",
    MORPH_PARTIAL_INVERSION: "Partial Inversion",
    MORPH_FLIP_HORIZONTAL: "Flip Horizontal",
    MORPH_FLIP_VERTICAL: "Flip Vertical",
    MORPH_ROTATE_90: "Rotate 90",
    MORPH_ROTATE_180: "Rotate 180",
    MORPH_ROTATE_270: "Rotate 270",
    MORPH_TILT_LEFT: "Tilt Left",
    MORPH_TILT_RIGHT: "Tilt Right",
    MORPH_SHEAR_LEFT: "Shear Left",
    MORPH_SHEAR_RIGHT: "Shear Right",
    MORPH_TOP_BOTTOM_SWAP: "Top-Bottom Swap",
    MORPH_QUADRANT_SWAP: "Quadrant Swap",
    MORPH_VIGNETTE: "Vignette",
    MORPH_REVERSE_VIGNETTE: "Reverse Vignette",
    MORPH_SOFT_GLOW: "Soft Glow",
    MORPH_BLOOM: "Bloom",
    MORPH_GAUSSIAN_BLUR: "Gaussian Blur",
    MORPH_MOTION_BLUR_H: "Motion Blur H",
    MORPH_MOTION_BLUR_V: "Motion Blur V",
    MORPH_SHARPEN: "Sharpen",
    MORPH_OVERSHARPEN: "Oversharpen",
    MORPH_DOUBLE_VISION: "Double Vision",
    MORPH_EMBOSS: "Emboss",
    MORPH_CONTOUR: "Contour",
    MORPH_EDGE_GLOW: "Edge Glow",
    MORPH_FILM_GRAIN: "Film Grain",
    MORPH_HEAVY_GRAIN: "Heavy Grain",
    MORPH_DUST_SPECKS: "Dust Specks",
    MORPH_SCANLINES: "Scanlines",
    MORPH_CRT_MASK: "CRT Mask",
    MORPH_GLITCH_SLICES: "Glitch Slices",
    MORPH_RGB_SHIFT: "RGB Shift",
    MORPH_DEAD_PIXELS: "Dead Pixels",
    MORPH_PIXELATE: "Pixelate",
    MORPH_MOSAIC: "Mosaic",
    MORPH_CHECKER_OVERLAY: "Checker Overlay",
    MORPH_DIAGONAL_STRIPES: "Diagonal Stripes",
    MORPH_HALFTONE: "Halftone",
    MORPH_WORN_EDGES: "Worn Edges",
    MORPH_BURNT_EDGES: "Burnt Edges",
    MORPH_FROSTED_EDGES: "Frosted Edges",
    MORPH_PHOTOCOPY: "Photocopy",
    MORPH_BLUEPRINT: "Blueprint",
    MORPH_SECURITY_CAM: "Security Cam",
    MORPH_XRAY: "X-Ray",
    MORPH_LOW_INK: "Low Ink",
    MORPH_NEON_CYBER: "Neon Cyber",
    MORPH_FROZEN: "Frozen",
    MORPH_INFERNAL: "Infernal",
    MORPH_VOID: "Void",
    MORPH_HOLY: "Holy",
}

MORPH_RARITIES: Final[dict[str, str]] = {
    MORPH_BLACK_AND_WHITE: "common",
    MORPH_INVERSE: "uncommon",
    MORPH_TINT_ROSE: "rare",
    MORPH_TINT_AQUA: "epic",
    MORPH_TINT_LIME: "legendary",
    MORPH_TINT_WARM: "mythical",
    MORPH_TINT_COOL: "divine",
    MORPH_TINT_VIOLET: "celestial",
    MORPH_UPSIDE_DOWN: "common",
    MORPH_SEPIA: "uncommon",
    MORPH_HIGH_SATURATION: "rare",
    MORPH_DESATURATED: "epic",
    MORPH_ULTRA_CONTRAST: "legendary",
    MORPH_LOW_CONTRAST: "mythical",
    MORPH_BRIGHTENED: "divine",
    MORPH_DARKENED: "celestial",
    MORPH_TINT_RED: "common",
    MORPH_TINT_BLUE: "uncommon",
    MORPH_TINT_GREEN: "rare",
    MORPH_TINT_GOLD: "epic",
    MORPH_TINT_PINK: "legendary",
    MORPH_TINT_CYAN: "mythical",
    MORPH_POSTERIZED: "divine",
    MORPH_SOLARIZED: "celestial",
    MORPH_THRESHOLD_BW: "common",
    MORPH_DUOTONE_SUNSET: "uncommon",
    MORPH_DUOTONE_MOONLIGHT: "rare",
    MORPH_TRITONE: "epic",
    MORPH_CHANNEL_SHIFT_WARM: "epic",
    MORPH_CHANNEL_SHIFT_COOL: "legendary",
    MORPH_PARTIAL_INVERSION: "legendary",
    MORPH_FLIP_HORIZONTAL: "mythical",
    MORPH_FLIP_VERTICAL: "divine",
    MORPH_ROTATE_90: "celestial",
    MORPH_ROTATE_180: "mythical",
    MORPH_ROTATE_270: "common",
    MORPH_TILT_LEFT: "uncommon",
    MORPH_TILT_RIGHT: "rare",
    MORPH_SHEAR_LEFT: "epic",
    MORPH_SHEAR_RIGHT: "legendary",
    MORPH_TOP_BOTTOM_SWAP: "divine",
    MORPH_QUADRANT_SWAP: "celestial",
    MORPH_VIGNETTE: "mythical",
    MORPH_REVERSE_VIGNETTE: "divine",
    MORPH_SOFT_GLOW: "celestial",
    MORPH_BLOOM: "common",
    MORPH_GAUSSIAN_BLUR: "uncommon",
    MORPH_MOTION_BLUR_H: "rare",
    MORPH_MOTION_BLUR_V: "epic",
    MORPH_SHARPEN: "legendary",
    MORPH_OVERSHARPEN: "mythical",
    MORPH_DOUBLE_VISION: "rare",
    MORPH_EMBOSS: "divine",
    MORPH_CONTOUR: "celestial",
    MORPH_EDGE_GLOW: "common",
    MORPH_FILM_GRAIN: "uncommon",
    MORPH_HEAVY_GRAIN: "rare",
    MORPH_DUST_SPECKS: "uncommon",
    MORPH_SCANLINES: "epic",
    MORPH_CRT_MASK: "legendary",
    MORPH_GLITCH_SLICES: "mythical",
    MORPH_RGB_SHIFT: "divine",
    MORPH_DEAD_PIXELS: "common",
    MORPH_PIXELATE: "celestial",
    MORPH_MOSAIC: "common",
    MORPH_CHECKER_OVERLAY: "uncommon",
    MORPH_DIAGONAL_STRIPES: "rare",
    MORPH_HALFTONE: "epic",
    MORPH_WORN_EDGES: "legendary",
    MORPH_BURNT_EDGES: "mythical",
    MORPH_FROSTED_EDGES: "divine",
    MORPH_PHOTOCOPY: "celestial",
    MORPH_BLUEPRINT: "common",
    MORPH_SECURITY_CAM: "uncommon",
    MORPH_XRAY: "rare",
    MORPH_LOW_INK: "epic",
    MORPH_NEON_CYBER: "legendary",
    MORPH_FROZEN: "mythical",
    MORPH_INFERNAL: "divine",
    MORPH_VOID: "celestial",
    MORPH_HOLY: "common",
}


def _humanize_morph_key(morph_key: str) -> str:
    words = morph_key.replace("_", " ").split()
    normalized: list[str] = []
    for word in words:
        if word in {"bw", "crt", "rgb", "xray"}:
            normalized.append(word.upper())
            continue
        normalized.append(word.capitalize())
    return " ".join(normalized)


_MORPH_EXPANSION_KEYS: Final[tuple[str, ...]] = (
    "grayscale",
    "saturation_up",
    "saturation_down",
    "contrast_up",
    "contrast_down",
    "brighten",
    "darken",
    "duotone",
    "vintage_fade",
    "moonlight_cast",
    "toxic_cast",
    "small_tilt",
    "strong_tilt",
    "mirrored_halves",
    "slice_shuffle",
    "off_center_crop_zoom",
    "thin_gold_border",
    "thick_gold_border",
    "thin_silver_border",
    "thick_silver_border",
    "thin_bronze_border",
    "thick_bronze_border",
    "silver_border",
    "bronze_border",
    "rainbow_border",
    "neon_border",
    "double_border",
    "dashed_border",
    "dotted_border",
    "vignette_edge",
    "glow_border",
    "shadow_border",
    "checker_border",
    "barcode_border",
    "pixel_frame",
    "outer_glow",
    "inner_glow",
    "spotlight_left",
    "spotlight_center",
    "spotlight_right",
    "halo",
    "rim_light",
    "light_leak_left",
    "light_leak_right",
    "dreamy_glow_haze",
    "neon_edge_glow",
    "soft_blur",
    "heavy_blur",
    "soft_focus",
    "ghosted_duplicate",
    "noise_grain",
    "scratches",
    "crosshatch",
    "newsprint",
    "frosted_overlay",
    "smudged_ink",
    "crackle_aged_print",
    "glitter_noise",
    "cloudy_veil",
    "corner_wear",
    "edge_wear",
    "fold_lines",
    "scuffs",
    "burn_corners",
    "soot_darkening",
    "water_stain",
    "ink_splatter",
    "torn_corner_illusion",
    "top_sun_fade",
    "static_corruption",
    "glitch_tears",
    "polka_dots",
    "stripes",
    "chevron",
    "checkerboard",
    "grid",
    "hex_grid",
    "zigzag",
    "concentric_rings",
    "wave_pattern",
    "star_field",
    "rain_streaks",
    "lightning_zigzags",
    "circuit_traces",
    "glyph_rain",
    "binary_overlay",
    "web_lattice",
    "rgb_offset",
    "glitch_slices_horizontal",
    "glitch_slices_vertical",
    "random_band_displacement",
    "static_burst",
    "corrupted_strip",
    "jitter",
    "frame_tearing",
    "low_bit_8",
    "low_bit_4",
    "pixelation",
    "mosaic_blocks",
    "terminal_green",
    "blue_screen_tint",
    "chromatic_aberration",
    "prism_split",
    "kaleidoscope_quadrant_mirror",
    "radial_echo",
    "toxic",
    "arcane",
    "storm",
    "retro_arcade",
    "vintage_print",
    "haunted",
    "dreamscape",
    "nightmare",
    "industrial",
    "celestial",
    "lunar",
    "solar",
    "photocopied",
    "flashlight_mode",
    "security_cam_mono",
    "xray_fake",
    "low_ink_printer",
    "lagging_echo",
)

_EXPANSION_KEYS: Final[tuple[str, ...]] = tuple(
    key for key in _MORPH_EXPANSION_KEYS if key not in AVAILABLE_MORPHS
)

if _EXPANSION_KEYS:
    AVAILABLE_MORPHS = (*AVAILABLE_MORPHS, *_EXPANSION_KEYS)

    MORPH_LABELS = {
        **MORPH_LABELS,
        **{key: _humanize_morph_key(key) for key in _EXPANSION_KEYS},
    }
    MORPH_LABELS["xray_fake"] = "X-Ray Fake"

    rarity_tiers: tuple[str, ...] = (
        "common",
        "uncommon",
        "rare",
        "epic",
        "legendary",
        "mythical",
        "divine",
        "celestial",
    )
    rarity_counts = Counter(MORPH_RARITIES.values())
    expanded_rarities = dict(MORPH_RARITIES)
    for key in _EXPANSION_KEYS:
        tier = min(rarity_tiers, key=lambda candidate: (rarity_counts[candidate], rarity_tiers.index(candidate)))
        expanded_rarities[key] = tier
        rarity_counts[tier] += 1
    MORPH_RARITIES = expanded_rarities


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


def morph_rarity(morph_key: str | None) -> str:
    normalized = normalize_morph_key(morph_key)
    if normalized is None:
        return "common"
    return MORPH_RARITIES.get(normalized, "common")
