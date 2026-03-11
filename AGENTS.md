# AGENTS.md

This file is the primary handoff guide for AI coding agents working on Noodswap.

## 1) Project Snapshot

- **Project:** `Noodswap` (Discord bot, `discord.py`)
- **Runtime:** Python 3.14+ (currently validated on 3.14.3)
- **Entrypoint:** `bot.py` (thin launcher)
- **Main package:** `noodswap/`
- **State storage:** Local SQLite database (`runtime/db/noodswap.db` by default)
- **Command prefix:** `ns `

## 2) Fast Onboarding Checklist

1. Read `README.md` for usage-level behavior.
2. Read `docs/README.md` for architecture and subsystem links.
3. Read `docs/data-model.md` before changing inventory/marry/trade/burn logic.
4. Run syntax validation:
   - `.venv/bin/python -m py_compile bot.py noodswap/*.py scripts/*.py tests/*.py`
   - `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - SQLite guardrail is enforced by `tests/test_sqlite_guardrails.py` (no raw `with sqlite3.connect(...) as conn:`).
5. If changing command output, read `docs/commands-and-ux.md` (embed style contract).

## 3) Architecture Map

- `bot.py`: bootstrap only (`from noodswap.app import main`)
- `noodswap/app.py`: bot creation, intents, startup lifecycle, command registration
- `noodswap/commands.py`: thin command registration entrypoint
- `noodswap/command_utils.py`: shared command helper functions/constants used by registrars
- `noodswap/commands_social.py`: social/player-facing command registrar (`wish/tag/folder/team/battle/cooldown/leaderboard/info`)
- `noodswap/commands_catalog.py`: catalog/discovery command registrar (`buy/cards/lookup/vote/help`)
- `noodswap/commands_economy.py`: economy command registrar (`drop/marry/divorce/collection/burn/morph/frame/font/trade/gift`)
- `noodswap/commands_gambling.py`: gambling command registrar (`slots/flip/monopoly`)
- `noodswap/commands_admin.py`: owner/admin command registrar (`dbexport/dbreset`)
- `noodswap/services.py`: command-facing use-case orchestration (`drop/burn/marry/divorce/trade` prep/exec)
- `noodswap/views/`: interactive `discord.ui.View` flows (drop/trade/burn-confirm)
- `noodswap/presentation.py`: shared embed style + reusable command description formatting helpers
- `noodswap/cards/`: card catalog + generation/pull/burn helper functions
- `noodswap/rarities.py`: rarity weights used in pull selection
- `noodswap/storage.py`: SQLite domain persistence operations
- `noodswap/migrations.py`: SQLite schema versioning and startup migration steps
- `noodswap/repositories.py`: repository-style DB access helpers used by storage facade
- `noodswap/settings.py`: constants (`PULL_COOLDOWN_SECONDS`, `COMMAND_PREFIX`, `DB_PATH`)
- `noodswap/utils.py`: utility helpers (`format_cooldown`)

## 4) Critical Invariants (Do Not Break)

1. **Card instances are per-copy**, not quantity blobs.
   - Each owned card copy has its own `instance_id` and `generation`.
2. **Generation semantics:**
   - `generation` is assigned at drop offer time and persisted when claimed.
   - Lower generation = rarer.
3. **Selection policy (current):**
   - `burn` and `trade` remove/sell highest generation copy (least rare).
   - `marry` picks lowest generation copy (rarest).
4. **Global scoping:**
   - Economy and ownership data is global across all guilds (`guild_id` is normalized to global scope in storage).
5. **Presentation contract:**
   - All user-facing responses should be embeds.
   - Use `italy_embed` for general flows and `italy_marry_embed` for marriage flows.

## 5) Data Model Summary

Primary tables (see `docs/data-model.md` for details):
- `players(guild_id, user_id, dough, last_pull_at, married_instance_id, married_card_id, last_dropped_instance_id)` (`last_dropped_instance_id` stores the last pulled instance)
- `card_instances(instance_id, guild_id, user_id, card_id, generation)`

Migration behavior in `init_db()`:
- Uses `schema_migrations` table to track current schema version.
- Applies ordered migration steps up to `TARGET_SCHEMA_VERSION`.
- Current `v1` ensures required columns and required core tables.

## 6) High-Risk Change Areas

- `noodswap/storage.py`: ownership, marriage integrity, and trade safety.
- `noodswap/migrations.py`: migration safety/versioning and schema transition behavior.
- `noodswap/repositories.py`: SQL behavior changes affecting ownership/trade/marriage semantics.
- `noodswap/views/`: interaction race conditions and timeout behavior.
- `noodswap/commands.py`: UX consistency, embeds, and argument handling.
- `noodswap/cards/`: catalog IDs and rarity/value consistency.

## 7) Agent Change Protocol

When making non-trivial changes:
1. Update code in the correct module boundary.
2. Update docs in `docs/` and `README.md` if behavior changed.
3. Run compile validation.
4. Check diagnostics.
5. Record notable constraints/decisions in `docs/roadmap-and-known-issues.md`.

## 8) Common Tasks

- **Add card:** add metadata in `noodswap/data/cards.json`, then run `.venv/bin/python scripts/rebalance_base_values.py --mode missing` to fill only absent base values.
   - Keep image paths under `runtime/card_images`; image files can be populated later.
   - General flow: add card metadata -> run missing-only rebalance -> skip image creation for now.
- **Tune pull odds:** edit `RARITY_WEIGHTS` in `noodswap/rarities.py`.
- **Change cooldown:** edit `PULL_COOLDOWN_SECONDS` in `noodswap/settings.py`.
- **Adjust embed theme:** edit `ITALY_RED` and helper in `noodswap/presentation.py`.

## 9) Current Known Gaps

- Migration framework is minimal (in-code steps only; no standalone migration files or downgrade path yet).
- Concurrency is improved with `BEGIN IMMEDIATE`, but further hardening/retry strategy is still valuable under heavy contention.
- Prefix commands only; no slash command migration yet.
- Tests exist, but coverage is still partial and focused on storage/services/views hot paths.

## 10) Deferred Refactor Stages (To-Do)

Stages 1 and 3 are complete. Remaining deferred stages are:

1. **Stage 2 — Storage boundary split**
   - Separate migration logic from general data access.
   - Add repository-style boundaries with stable call surface.
2. **Stage 4 — Presentation expansion**
   - Continue centralizing repeated embed/description assembly and add formatter tests.

## 11) If You Are the Next Agent

Start with:
- `docs/README.md`
- `docs/development-runbook.md`
- `docs/data-model.md`

Then inspect the exact subsystem you intend to modify.
