# Development Runbook

This runbook is for contributors and coding agents.

## Environment

- Python: 3.14+
- Install dependencies:
  - `pip install -r requirements.txt`
- Set token (never commit secrets):
  - `export DISCORD_TOKEN=...`
  - or set `DISCORD_TOKEN_FILE=/path/to/secret-file` (for mounted secret files)

## Run

- Initialize runtime state from seed data:
  - `.venv/bin/python scripts/init_runtime.py`
- Start bot:
  - `python bot.py`

## Docker runtime

- Build image:
  - `docker build -t noodswap:local .`
- Run image:
  - `docker run --rm -e DISCORD_TOKEN=... noodswap:local`

## CI/CD overview

- CI workflow: `.github/workflows/ci.yml`
  - compile check, migration smoke check, unit tests
- CD workflow: `.github/workflows/cd.yml`
  - triggered only after CI succeeds on `main`
  - builds/pushes GHCR image (`latest` + commit SHA)
- Deploy workflow: `.github/workflows/deploy.yml`
  - runs on GitHub-hosted runner (`ubuntu-latest`)
  - deploys to Ubuntu server via SSH
  - waits for SHA-tagged GHCR image, deploys via `deploy/update.sh`, verifies running image

## Ubuntu deploy flow

- Compose file: `deploy/docker-compose.prod.yml`
- Deploy script: `deploy/update.sh`
- Required server files:
  - `deploy/.env` (image repository config)
  - `deploy/runtime.env` (runtime secrets)
- Manual rollout command:
  - `./deploy/update.sh`
- GitHub Actions deploy setup guide:
  - `docs/deploy-github-actions.md`

## Validate after changes

- Compile check:
  - `.venv/bin/python -m py_compile bot.py noodswap/*.py`
- Check diagnostics in editor Problems view.
- VS Code task shortcut (compile + migration smoke):
  - `check:quick`
- VS Code task shortcut (compile + migration smoke + unit tests):
  - `check:all`

## Rarity balancing helper

- Print current target vs effective rarity odds from live catalog data:
  - `.venv/bin/python scripts/rarity_odds.py`

## Adding cards

When adding a new card to the live catalog, use this workflow to keep metadata and economy values consistent.

### General Card Add Flow

Use this default process unless there is a specific reason to do otherwise:

1. Add the card metadata entry in `noodswap/data/cards.json`.
2. Run `.venv/bin/python scripts/rebalance_base_values.py --mode missing` to fill only absent base values.
3. Keep card image paths under `runtime/card_images`; image files can be populated later as needed.

1. Add the new card entry to `noodswap/data/cards.json` with:
  - unique `card_id`
  - `name`, `series`, `rarity`
  - optional `image` path (no need to add a default/local image file up front)
2. Do not manually write a base value in `noodswap/data/base_values.json` for new card IDs.
3. Generate missing base values only:
  - preview: `.venv/bin/python scripts/rebalance_base_values.py --mode missing --dry-run`
  - write: `.venv/bin/python scripts/rebalance_base_values.py --mode missing`
4. Validate quickly:
  - `.venv/bin/python -m py_compile bot.py noodswap/*.py scripts/*.py`
  - `.venv/bin/python scripts/migration_smoke.py`

Notes:
- `--mode missing` preserves existing values and only fills absent IDs.
- Use `--mode all` only when intentionally rebalancing the full catalog.
- No need to add image files for new cards immediately; keep the metadata path under `runtime/card_images` and populate files later.

## Card image sync helper

- Pull image URLs dynamically from `CARD_CATALOG` and write a JSON report:
  - Missing-only mode (default):
    - `.venv/bin/python scripts/pull_card_images.py`
  - Full refresh mode:
    - `.venv/bin/python scripts/pull_card_images.py --all`
  - Custom output path:
    - `.venv/bin/python scripts/pull_card_images.py --output tmp/card_image_pull_report.json`

  - Cache all card images locally for drop preview composition (avoids remote rate limiting):

    - `.venv/bin/python scripts/cache_card_images.py`

## Migration validation helper

- Run migration smoke checks (fresh init path):
  - `.venv/bin/python scripts/migration_smoke.py`
- VS Code task shortcut:
  - `check:migrations`

## Unit tests

- Run tests:
  - `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- VS Code task shortcut:
  - `check:tests`
- SQLite guardrail:
  - `tests/test_sqlite_guardrails.py` blocks raw `with sqlite3.connect(...) as conn:` usage.
  - Prefer explicit-close patterns (`contextlib.closing`) for direct sqlite handles.

## Recommended edit flow

1. Read `AGENTS.md` and relevant docs in `docs/`.
2. Identify the correct module boundary.
3. Make smallest targeted change.
4. Update docs if behavior changed.
5. Compile check.
6. Sanity-run bot if command behavior changed.

## Subsystem guide

- Catalog/cards logic: `noodswap/cards.py`
- Rarity tuning: `noodswap/rarities.py`
- DB and ownership semantics: `noodswap/storage.py`
- Command/use-case orchestration: `noodswap/services.py`
- Command Discord wiring + routing: `noodswap/commands.py`
- Interaction UX: `noodswap/views.py`
- Shared embed theme + reusable description formatting: `noodswap/presentation.py`

## Operational conventions

- Keep user-facing command failures embed-based through app-level `on_command_error` in `noodswap/app.py`.
- Prefer changing operational knobs in `noodswap/settings.py` (drop count, interaction timeouts, generation bounds, cooldowns).
- For direct sqlite usage outside `storage.get_db_connection()`, explicitly close connections.

## High-risk edits

Use extra caution when editing:

- migration logic in `init_db()`
- schema version constants / migration steps in `noodswap/storage.py`
- trade transfer logic
- marriage uniqueness constraints
- generation selection ordering

## Manual smoke checklist

- `ns drop` creates offers with `G-####`
- drop buttons show card names (not IDs)
- claiming from a drop adds one instance for the claimant and updates their last pulled target
- each drop card can only be claimed once, while other cards remain claimable until timeout
- inventory/dough/marriage state appears consistently across guilds for the same user
- `ns collection` shows instance generations
- `ns marry <card_code>` marries the exact referenced dupe (code examples: `0`, `a`, `10`, `#10`)
- `ns burn` asks for confirm/cancel before burning
- `ns burn` (no arg) defaults to the last pulled card instance
- `ns burn <card_code>` burns the exact referenced dupe (code examples: `0`, `a`, `10`, `#10`)
- `ns trade <player> <card_code> <amount>` transfers the exact referenced dupe and dough
- `ns cooldown [player]` shows correct pull cooldown status for self/target
- `ns info` shows correct dough/married display
- `ns help` displays grouped command sections with descriptions
- `ns dbexport` and `ns dbreset` work for owner
