#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPOSITORY_OVERRIDE=""
IMAGE_TAG_OVERRIDE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --image-repository)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --image-repository" >&2
        exit 2
      fi
      IMAGE_REPOSITORY_OVERRIDE="$2"
      shift 2
      ;;
    --image-tag)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --image-tag" >&2
        exit 2
      fi
      IMAGE_TAG_OVERRIDE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--image-repository <repo>] [--image-tag <tag>]" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "Missing $SCRIPT_DIR/.env (copy from .env.example and set IMAGE_REPOSITORY)." >&2
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/runtime.env" ]; then
  echo "Missing $SCRIPT_DIR/runtime.env (copy from runtime.env.example and set secrets)." >&2
  exit 1
fi

if [ -n "$IMAGE_REPOSITORY_OVERRIDE" ]; then
  export IMAGE_REPOSITORY="$IMAGE_REPOSITORY_OVERRIDE"
fi

if [ -n "$IMAGE_TAG_OVERRIDE" ]; then
  export IMAGE_TAG="$IMAGE_TAG_OVERRIDE"
fi

mkdir -p "$SCRIPT_DIR/data/card_images"
DB_PATH="$SCRIPT_DIR/data/noodswap.db"
CARD_IMAGE_DATA_DIR="$SCRIPT_DIR/data/card_images"
REPO_CARD_IMAGE_DIR="$SCRIPT_DIR/../assets/card_images"

target_manifest="$CARD_IMAGE_DATA_DIR/manifest.json"
source_manifest="$REPO_CARD_IMAGE_DIR/manifest.json"
target_entries_count=$(find "$CARD_IMAGE_DATA_DIR" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')

if [ -f "$source_manifest" ] && {
  [ ! -s "$target_manifest" ] || [ "$target_entries_count" -lt 2 ];
}; then
  echo "Seeding card image cache into $CARD_IMAGE_DATA_DIR"
  cp -a "$REPO_CARD_IMAGE_DIR/." "$CARD_IMAGE_DATA_DIR/"
fi

if [ ! -f "$DB_PATH" ]; then
  LEGACY_DB_PATHS=(
    "$SCRIPT_DIR/noodswap.db"
    "$SCRIPT_DIR/../noodswap.db"
  )
  for legacy in "${LEGACY_DB_PATHS[@]}"; do
    if [ -s "$legacy" ]; then
      cp "$legacy" "$DB_PATH"
      echo "Migrated existing DB from $legacy to $DB_PATH"
      break
    fi
  done
fi

if [ ! -f "$DB_PATH" ]; then
  touch "$DB_PATH"
  echo "No existing DB found; created new empty DB at $DB_PATH"
fi

if [ ! -s "$DB_PATH" ]; then
  echo "Warning: $DB_PATH is empty. If this is not a fresh install, restore your previous noodswap.db backup." >&2
fi

# Run container using the same UID/GID as the deploy user so bind-mounted data stays writable.
export BOT_UID="${BOT_UID:-$(id -u)}"
export BOT_GID="${BOT_GID:-$(id -g)}"
if ! chown -R "$BOT_UID:$BOT_GID" "$SCRIPT_DIR/data" 2>/dev/null; then
  echo "Warning: could not chown $SCRIPT_DIR/data to $BOT_UID:$BOT_GID (insufficient privileges)." >&2
  echo "If the bot still fails with readonly SQLite errors, run:" >&2
  echo "  sudo chown -R $BOT_UID:$BOT_GID $SCRIPT_DIR/data" >&2
fi
chmod 664 "$DB_PATH" || true
chmod 775 "$SCRIPT_DIR/data/card_images" || true

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" pull

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" up -d --remove-orphans

# Keep recent images around; remove older dangling layers.
docker image prune -f --filter "until=168h"
