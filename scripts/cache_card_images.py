import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG, card_image_url
from noodswap.settings import CARD_IMAGE_CACHE_DIR, CARD_IMAGE_CACHE_MANIFEST

USER_AGENT = "NoodswapBot/1.0 (local image cache)"
DOWNLOAD_TIMEOUT_SECONDS = 20
DOWNLOAD_MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.5


def _safe_extension(url: str, content_type: str | None) -> str:
    path_ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if path_ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return path_ext

    if content_type:
        content_type = content_type.lower()
        if "png" in content_type:
            return ".png"
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        if "webp" in content_type:
            return ".webp"
        if "gif" in content_type:
            return ".gif"

    return ".img"


def _download(url: str) -> tuple[tuple[bytes, str | None] | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            return (response.read(), response.headers.get("Content-Type")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _download_with_retries(url: str) -> tuple[tuple[bytes, str | None] | None, str | None, int]:
    last_error: str | None = None
    for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
        fetched, error = _download(url)
        if fetched is not None:
            return fetched, None, attempt

        last_error = error or "download failed"
        if attempt < DOWNLOAD_MAX_ATTEMPTS:
            sleep_seconds = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            time.sleep(sleep_seconds)

    return None, last_error, DOWNLOAD_MAX_ATTEMPTS


def main() -> None:
    CARD_IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict[str, str | int]] = {}
    downloaded = 0
    failed = 0
    failure_details: list[dict[str, str | int]] = []

    for card_id in sorted(CARD_CATALOG.keys()):
        source_url = card_image_url(card_id)
        fetched, error, attempts = _download_with_retries(source_url)
        if fetched is None:
            failed += 1
            failure_details.append(
                {
                    "card_id": card_id,
                    "source": source_url,
                    "error": error or "download failed",
                    "attempts": attempts,
                }
            )
            continue

        image_bytes, content_type = fetched
        extension = _safe_extension(source_url, content_type)
        filename = f"{card_id}{extension}"
        file_path = CARD_IMAGE_CACHE_DIR / filename
        file_path.write_bytes(image_bytes)

        manifest[card_id] = {
            "file": filename,
            "source": source_url,
            "attempts": attempts,
        }
        downloaded += 1

    CARD_IMAGE_CACHE_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print("card_image_cache: COMPLETE")
    print(f"cached: {downloaded}")
    print(f"failed: {failed}")
    print(f"cache_dir: {CARD_IMAGE_CACHE_DIR}")
    print(f"manifest: {CARD_IMAGE_CACHE_MANIFEST}")
    if failure_details:
        print("failed_cards:")
        for detail in failure_details:
            print(
                f"  - {detail['card_id']}: {detail['error']}"
                f" (attempts={detail['attempts']})"
            )


if __name__ == "__main__":
    main()
