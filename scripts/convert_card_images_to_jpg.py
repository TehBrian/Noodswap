from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Convert images to JPEG with very light compression and write them to a destination card_images directory.")
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root path (default: auto-detected from this script).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("assets/card_images_inbox"),
        help="Source image directory (default: assets/card_images_inbox).",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("assets/card_images"),
        help="Destination directory for converted JPG files (default: assets/card_images).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality from 1-100 (default: 95 for very light compression).",
    )
    parser.add_argument(
        "--move-source",
        action="store_true",
        help="Delete original source image files after successful conversion.",
    )
    return parser.parse_args()


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path)


def _convert_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"}:
        # Flatten transparency against white so PNG assets convert safely to JPEG.
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.getchannel("A")
        background.paste(image, mask=alpha)
        return background
    if image.mode == "P":
        return image.convert("RGB")
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _iter_source_images(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES)


def main() -> None:
    args = _parse_args()
    if not 1 <= args.quality <= 100:
        raise ValueError("--quality must be between 1 and 100")

    repo_root = args.repo_root.resolve()
    source_dir = _resolve_path(repo_root, args.source).resolve()
    dest_dir = _resolve_path(repo_root, args.dest).resolve()

    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    dest_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0
    deleted = 0

    for source_path in _iter_source_images(source_dir):
        relative_path = source_path.relative_to(source_dir)
        dest_path = (dest_dir / relative_path).with_suffix(".jpg")
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(source_path) as image:
                rgb_image = _convert_to_rgb(image)
                save_kwargs = {
                    "format": "JPEG",
                    "quality": args.quality,
                    "optimize": True,
                    "progressive": True,
                    "subsampling": 0,
                }
                exif_data = image.info.get("exif")
                if exif_data:
                    save_kwargs["exif"] = exif_data
                rgb_image.save(dest_path, **save_kwargs)
        except (UnidentifiedImageError, OSError) as exc:
            skipped += 1
            print(f"Skipped {source_path}: {exc}")
            continue

        converted += 1
        print(f"Converted {source_path} -> {dest_path}")

        if args.move_source:
            if source_path.resolve() != dest_path.resolve():
                source_path.unlink(missing_ok=True)
                deleted += 1

    print(f"Done. Converted: {converted}, Skipped: {skipped}, Source files deleted: {deleted}")


if __name__ == "__main__":
    main()
