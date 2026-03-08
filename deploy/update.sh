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
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

assert_writable_path() {
  local path="$1"
  local probe="$path/.write_probe.$$"
  if ! touch "$probe" 2>/dev/null; then
    echo "ERROR: path is not writable: $path" >&2
    echo "Ensure ownership/permissions are correct before deploy." >&2
    exit 1
  fi
  rm -f "$probe"
}

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

RUNTIME_DIR="$REPO_ROOT/runtime"
RUNTIME_DB_DIR="$RUNTIME_DIR/db"
RUNTIME_IMAGE_DIR="$RUNTIME_DIR/card_images"
RUNTIME_FONTS_DIR="$RUNTIME_DIR/fonts"
RUNTIME_FRAMES_DIR="$RUNTIME_DIR/frame_overlays"
RUNTIME_LOG_DIR="$RUNTIME_DIR/logs"
DB_PATH="$RUNTIME_DB_DIR/noodswap.db"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: Python interpreter not found (required for scripts/init_runtime.py)." >&2
  exit 1
fi

# Keep runtime assets aligned with versioned seeds before (re)starting the container.
"$PYTHON_BIN" "$REPO_ROOT/scripts/init_runtime.py" --repo-root "$REPO_ROOT"

if [ ! -s "$DB_PATH" ]; then
  echo "Warning: $DB_PATH is empty. If this is not a fresh install, restore your previous noodswap.db backup." >&2
fi

# Run container using the same UID/GID as the deploy user so bind-mounted data stays writable.
export BOT_UID="${BOT_UID:-$(id -u)}"
export BOT_GID="${BOT_GID:-$(id -g)}"
if ! chown -R "$BOT_UID:$BOT_GID" "$RUNTIME_DIR" 2>/dev/null; then
  echo "Warning: could not chown $RUNTIME_DIR to $BOT_UID:$BOT_GID (insufficient privileges)." >&2
  if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: chown failed while running as root." >&2
    exit 1
  fi
  echo "Continuing only if runtime paths are already writable by the current user." >&2
fi

chmod 664 "$DB_PATH" 2>/dev/null || true
chmod 775 "$RUNTIME_DB_DIR" 2>/dev/null || true
chmod 775 "$RUNTIME_IMAGE_DIR" 2>/dev/null || true
chmod 775 "$RUNTIME_FONTS_DIR" 2>/dev/null || true
chmod 775 "$RUNTIME_FRAMES_DIR" 2>/dev/null || true
chmod 775 "$RUNTIME_LOG_DIR" 2>/dev/null || true

# Fail fast before container startup if runtime state cannot be written.
assert_writable_path "$RUNTIME_DB_DIR"
assert_writable_path "$RUNTIME_IMAGE_DIR"
assert_writable_path "$RUNTIME_LOG_DIR"
if ! [ -w "$DB_PATH" ]; then
  echo "ERROR: database file is not writable: $DB_PATH" >&2
  exit 1
fi

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" pull

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" up -d --remove-orphans

# Keep recent images around; remove older dangling layers.
docker image prune -f --filter "until=168h"
