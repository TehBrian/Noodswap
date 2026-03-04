import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import CARD_CATALOG
from noodswap.settings import CARD_IMAGE_CACHE_MANIFEST

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
USER_AGENT = "NoodswapBot/1.0 (local image cache sync; contact: noc@wikimedia.org)"
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_SPACING_SECONDS = 0.8
MAX_RETRIES = 5
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _read_manifest() -> dict[str, dict[str, str | int]]:
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


def _write_manifest(manifest: dict[str, dict[str, str | int]]) -> None:
    CARD_IMAGE_CACHE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    CARD_IMAGE_CACHE_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _extension_for_url(url: str) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix in ALLOWED_EXTENSIONS:
        return suffix
    return ".img"


def _derive_original_from_thumb_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("wikimedia.org"):
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 6:
        return None
    if "thumb" not in parts:
        return None

    thumb_index = parts.index("thumb")
    if thumb_index + 3 >= len(parts):
        return None

    original_parts = parts[:thumb_index] + parts[thumb_index + 1: thumb_index + 3]
    original_path = "/" + "/".join(original_parts)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, original_path, "", "", ""))


def _candidate_urls(source_url: str) -> list[str]:
    candidates = [source_url]
    thumb_fallback = _derive_original_from_thumb_url(source_url)
    if thumb_fallback is not None and thumb_fallback != source_url:
        candidates.append(thumb_fallback)
    return candidates


def _fetch_bytes_once(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def _fetch_bytes_with_retry(url: str) -> tuple[bytes | None, str | None]:
    last_error: str | None = None
    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            sleep_seconds = min(15.0, 1.5 * (2 ** (attempt - 1)))
            time.sleep(sleep_seconds)

        try:
            payload = _fetch_bytes_once(url)
            return payload, None
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code == 429:
                retry_after_header = exc.headers.get("Retry-After") if exc.headers is not None else None
                if retry_after_header:
                    try:
                        retry_after_seconds = int(retry_after_header)
                        time.sleep(max(1, retry_after_seconds))
                    except ValueError:
                        pass
                continue
            if 500 <= exc.code <= 599:
                continue
            break
        except Exception as exc:
            last_error = str(exc)
            continue

    return None, last_error


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def _wikipedia_thumbnail(query: str) -> str | None:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "3",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": "1000",
    }
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(params)
    data = _request_json(url)
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            return str(thumb)
    return None


def _commons_file_image(query: str) -> str | None:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    data = _request_json(url)
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        image_url = str(infos[0].get("url") or "")
        lower = image_url.lower()
        if any(lower.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            return image_url
    return None


def _search_queries(card_id: str) -> list[str]:
    card = CARD_CATALOG.get(card_id)
    if card is None:
        return [card_id]

    name = card["name"]
    series = card["series"]
    queries = [name, f"{name} {series}", f"{name} food"]
    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        normalized = query.strip().casefold()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(query)
    return deduped


def _discover_replacement_url(card_id: str) -> str | None:
    for query in _search_queries(card_id):
        thumbnail_url = _wikipedia_thumbnail(query)
        if thumbnail_url:
            return thumbnail_url
        commons_url = _commons_file_image(query)
        if commons_url:
            return commons_url
    return None


def _load_backup_mapping(backup_path: Path) -> dict[str, str]:
    parsed = json.loads(backup_path.read_text(encoding="utf-8"))
    mapping = parsed.get("mapping") if isinstance(parsed, dict) else None
    if not isinstance(mapping, dict):
        return {}

    result: dict[str, str] = {}
    for card_id, image_url in mapping.items():
        if isinstance(card_id, str) and isinstance(image_url, str) and image_url:
            result[card_id] = image_url
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache card images from URL backup JSON.")
    parser.add_argument(
        "--backup",
        default="assets/card_images/url_backup.json",
        help="Path to URL backup JSON file.",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Skip cards that already have a local cached file recorded in manifest.",
    )
    parser.add_argument(
        "--failures-report",
        default="assets/card_images/cache_failures.json",
        help="Path to write detailed failures JSON.",
    )
    args = parser.parse_args()

    backup_path = Path(args.backup).resolve()
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    mapping = _load_backup_mapping(backup_path)
    manifest = _read_manifest()
    CARD_IMAGE_CACHE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    downloaded = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, str]] = []

    for card_id, source_url in sorted(mapping.items()):
        processed += 1

        existing_entry = manifest.get(card_id)
        if args.only_missing and isinstance(existing_entry, dict):
            existing_file = existing_entry.get("file")
            if isinstance(existing_file, str) and existing_file:
                existing_path = CARD_IMAGE_CACHE_MANIFEST.parent / existing_file
                if existing_path.exists() and existing_path.is_file():
                    skipped += 1
                    continue

        fetched: bytes | None = None
        resolved_source_url = source_url
        last_error: str | None = None
        for candidate_url in _candidate_urls(source_url):
            fetched, candidate_error = _fetch_bytes_with_retry(candidate_url)
            if fetched is not None:
                resolved_source_url = candidate_url
                break
            last_error = candidate_error

        if fetched is None:
            discovered_source_url = _discover_replacement_url(card_id)
            if discovered_source_url is not None:
                for candidate_url in _candidate_urls(discovered_source_url):
                    fetched, candidate_error = _fetch_bytes_with_retry(candidate_url)
                    if fetched is not None:
                        resolved_source_url = candidate_url
                        break
                    last_error = candidate_error

        if fetched is None:
            failed += 1
            failures.append(
                {
                    "card_id": card_id,
                    "source": source_url,
                    "error": last_error or "unknown",
                }
            )
            time.sleep(REQUEST_SPACING_SECONDS)
            continue

        extension = _extension_for_url(resolved_source_url)
        file_name = f"{card_id}{extension}"
        file_path = CARD_IMAGE_CACHE_MANIFEST.parent / file_name
        file_path.write_bytes(fetched)

        previous_attempts = 0
        if isinstance(existing_entry, dict):
            attempts_value = existing_entry.get("attempts")
            if isinstance(attempts_value, int):
                previous_attempts = attempts_value

        manifest[card_id] = {
            "file": file_name,
            "source": resolved_source_url,
            "attempts": previous_attempts + 1,
        }
        downloaded += 1
        time.sleep(REQUEST_SPACING_SECONDS)

    _write_manifest(manifest)

    print("Cache sync complete")
    print(f"Backup: {backup_path}")
    print(f"Processed: {processed}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"Manifest: {CARD_IMAGE_CACHE_MANIFEST}")

    failures_report_path = Path(args.failures_report).resolve()
    failures_report_path.parent.mkdir(parents=True, exist_ok=True)
    failures_report_path.write_text(
        json.dumps({"failed": failures, "count": len(failures)}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Failures report: {failures_report_path}")


if __name__ == "__main__":
    main()
