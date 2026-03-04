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

- Start bot:
  - `python bot.py`

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

- Run migration smoke checks (fresh init + legacy backfill path):
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
- pulling from a drop adds one instance and updates the last pulled target
- inventory/dough/marriage state appears consistently across guilds for the same user
- `ns collection` shows instance generations
- `ns marry <card_code>` marries the exact referenced dupe (code examples: `0`, `a`, `10`)
- `ns burn` asks for confirm/cancel before burning
- `ns burn` (no arg) defaults to the last pulled card instance
- `ns burn <card_code>` burns the exact referenced dupe (code examples: `0`, `a`, `10`)
- `ns trade <player> <card_code> <amount>` transfers the exact referenced dupe and dough
- `ns cooldown [player]` shows correct drop cooldown status for self/target
- `ns info` shows correct dough/married display
- `ns help` displays grouped command sections with descriptions
- `ns dbexport` and `ns dbreset` work for owner
