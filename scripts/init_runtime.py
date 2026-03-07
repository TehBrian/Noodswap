from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _copy_dir_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        elif child.is_file():
            shutil.copy2(child, target)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize runtime state from versioned assets.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root path (default: auto-detected from this script).",
    )
    parser.add_argument(
        "--force-images",
        action="store_true",
        help="Copy seeded images even when runtime/card_images is non-empty.",
    )
    parser.add_argument(
        "--force-db",
        action="store_true",
        help="Replace existing runtime DB from assets/noodswap.seed.db when present.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = args.repo_root.resolve()

    runtime_dir = repo_root / "runtime"
    runtime_db_dir = runtime_dir / "db"
    runtime_image_dir = runtime_dir / "card_images"
    runtime_log_dir = runtime_dir / "logs"
    runtime_cache_dir = runtime_dir / "cache"

    seed_dir = repo_root / "assets"
    seed_db_path = seed_dir / "noodswap.seed.db"
    seed_image_dir = seed_dir / "card_images"

    runtime_db_dir.mkdir(parents=True, exist_ok=True)
    runtime_image_dir.mkdir(parents=True, exist_ok=True)
    runtime_log_dir.mkdir(parents=True, exist_ok=True)
    runtime_cache_dir.mkdir(parents=True, exist_ok=True)

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

    runtime_has_images = any(path.name != ".gitkeep" for path in runtime_image_dir.iterdir())
    if seed_image_dir.is_dir() and (args.force_images or not runtime_has_images):
        _copy_dir_contents(seed_image_dir, runtime_image_dir)
        print(f"Initialized image cache from seeds: {seed_image_dir} -> {runtime_image_dir}")
    elif seed_image_dir.is_dir():
        print(f"Kept existing runtime images: {runtime_image_dir}")
    else:
        print(f"No seed image directory found at: {seed_image_dir}")

    print("Runtime initialization complete.")


if __name__ == "__main__":
    main()
