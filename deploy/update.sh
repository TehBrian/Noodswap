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
touch "$SCRIPT_DIR/data/noodswap.db"

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" pull

# Bind-mounted paths must be writable by the container's runtime UID/GID.
image_ref="${IMAGE_REPOSITORY}:${IMAGE_TAG:-latest}"
container_uid="$(docker run --rm --entrypoint id "$image_ref" -u)"
container_gid="$(docker run --rm --entrypoint id "$image_ref" -g)"

chown "$container_uid:$container_gid" "$SCRIPT_DIR/data/noodswap.db"
chown -R "$container_uid:$container_gid" "$SCRIPT_DIR/data/card_images"
chmod 664 "$SCRIPT_DIR/data/noodswap.db"
chmod 775 "$SCRIPT_DIR/data/card_images"

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" up -d --remove-orphans

# Keep recent images around; remove older dangling layers.
docker image prune -f --filter "until=168h"
