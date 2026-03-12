from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _replace_directory(src: Path, dst: Path) -> bool:
    if not src.is_dir():
        return False

    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize runtime state from versioned assets.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root path (default: auto-detected from this script).",
    )
    parser.add_argument(
        "--force-db",
        action="store_true",
        help="Replace existing runtime DB from assets/bot.seed.db when present.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = args.repo_root.resolve()

    runtime_dir = repo_root / "runtime"
    runtime_db_dir = runtime_dir / "db"
    runtime_image_dir = runtime_dir / "card_images"
    runtime_fonts_dir = runtime_dir / "fonts"
    runtime_frames_dir = runtime_dir / "frames"
    runtime_log_dir = runtime_dir / "logs"

    seed_dir = repo_root / "assets"
    seed_db_path = seed_dir / "bot.seed.db"
    seed_image_dir = seed_dir / "card_images"
    seed_fonts_dir = seed_dir / "fonts"
    seed_frames_dir = seed_dir / "frames"

    runtime_db_dir.mkdir(parents=True, exist_ok=True)
    runtime_log_dir.mkdir(parents=True, exist_ok=True)

    runtime_db_path = runtime_db_dir / "noodswap.db"
    if not runtime_db_path.exists() or args.force_db:
        if seed_db_path.is_file() and seed_db_path.stat().st_size > 0:
            shutil.copy2(seed_db_path, runtime_db_path)
            print(f"Initialized DB from seed: {seed_db_path} -> {runtime_db_path}")
        else:
            runtime_db_path.touch(exist_ok=True)
            print(f"Initialized empty DB file: {runtime_db_path}")
    else:
        print(f"Kept existing DB: {runtime_db_path}")

    if _replace_directory(seed_image_dir, runtime_image_dir):
        print(f"Replaced runtime card images: {seed_image_dir} -> {runtime_image_dir}")
    else:
        print(f"No seed image directory found at: {seed_image_dir}")

    if _replace_directory(seed_fonts_dir, runtime_fonts_dir):
        print(f"Replaced runtime fonts: {seed_fonts_dir} -> {runtime_fonts_dir}")
    else:
        print(f"No seed font directory found at: {seed_fonts_dir}")

    if _replace_directory(seed_frames_dir, runtime_frames_dir):
        print(f"Replaced runtime frames: {seed_frames_dir} -> {runtime_frames_dir}")
    else:
        print(f"No seed frame directory found at: {seed_frames_dir}")

    print("Runtime initialization complete.")


if __name__ == "__main__":
    main()
