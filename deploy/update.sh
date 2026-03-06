#!/usr/bin/env bash
set -euo pipefail

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

mkdir -p "$SCRIPT_DIR/data/card_images"
touch "$SCRIPT_DIR/data/noodswap.db"

docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" pull
docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" up -d --remove-orphans

# Keep recent images around; remove older dangling layers.
docker image prune -f --filter "until=168h"
