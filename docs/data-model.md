# Data Model

This document describes persistent storage for Noodswap.

## Database

- Engine: SQLite
- File location: `runtime/db/noodswap.db`
- Access: through functions in `noodswap/storage.py`

## Tables

### players

Primary key:
- `(guild_id, user_id)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `dough INTEGER NOT NULL DEFAULT 0`
- `starter INTEGER NOT NULL DEFAULT 0`
- `drop_tickets INTEGER NOT NULL DEFAULT 0`
- `votes INTEGER NOT NULL DEFAULT 0`
- `last_drop_at REAL NOT NULL DEFAULT 0` (tracks last `drop` command usage timestamp)
- `last_pull_at REAL NOT NULL DEFAULT 0` (tracks last successful drop-card claim timestamp)
- `last_vote_reward_at REAL NOT NULL DEFAULT 0` (tracks last successful starter claim from top.gg vote)
- `last_slots_at REAL NOT NULL DEFAULT 0` (tracks last successful `slots` spin timestamp)
- `married_card_id TEXT`
- `married_instance_id INTEGER` (current marriage reference)
- `last_dropped_instance_id INTEGER` (stores last pulled instance for arg-less `burn`/`marry`)
- `active_team_name TEXT` (currently selected team for battles)

Purpose:
- Player economy and cooldown state in the global Noodswap scope
- Includes standard (`dough`) and higher-tier currencies (`starter`, `drop_tickets`)
- Tracks cumulative successful top.gg vote rewards (`votes`)
- Marriage linkage to a specific owned card instance

### card_instances

Primary key:
- `instance_id INTEGER PRIMARY KEY AUTOINCREMENT`

Columns:
- `instance_id`
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `card_id TEXT NOT NULL`
- `generation INTEGER NOT NULL`
- `dupe_code TEXT` (base36 dupe identifier, globally unique)
- `morph_key TEXT` (optional per-instance visual modifier)
- `frame_key TEXT` (optional per-instance frame modifier)
- `font_key TEXT` (optional per-instance font modifier)

Purpose:
- Tracks each owned copy as a distinct instance
- Stores generation per copy

Indexes:
- `idx_card_instances_owner(guild_id, user_id, card_id, generation)`
- `idx_card_instances_dupe_code(dupe_code)` (unique where `dupe_code` is not null)

### schema_migrations

Columns:
- `version INTEGER NOT NULL`

Purpose:
- Tracks the current applied DB schema version.
- Maintained as a single-row table by `init_db()`.

### wishlist_cards

Primary key:
- `(guild_id, user_id, card_id)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `card_id TEXT NOT NULL`

Purpose:
- Stores each player's wishlisted base card IDs in global scope
- Supports `wish add/remove` command flows

### player_tags

Primary key:
- `(guild_id, user_id, tag_name)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `tag_name TEXT NOT NULL`
- `is_locked INTEGER NOT NULL DEFAULT 0` (`0` unlocked, `1` locked)

Purpose:
- Stores each player's personal tag collections in global scope
- `is_locked = 1` marks a protected collection whose cards cannot be burned

### card_instance_tags

Primary key:
- `(guild_id, user_id, instance_id, tag_name)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `instance_id INTEGER NOT NULL`
- `tag_name TEXT NOT NULL`

Purpose:
- Links owned card instances to player tag collections
- Supports many-to-many tagging (a card can have multiple tags)

### player_folders

Primary key:
- `(guild_id, user_id, folder_name)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `folder_name TEXT NOT NULL`
- `emoji TEXT NOT NULL` (default `📁`)
- `is_locked INTEGER NOT NULL DEFAULT 0` (`0` unlocked, `1` locked)

Purpose:
- Stores each player's personal card folders in global scope
- `is_locked = 1` marks a protected folder whose cards cannot be burned

### card_instance_folders

Primary key:
- `(guild_id, user_id, instance_id)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `instance_id INTEGER NOT NULL`
- `folder_name TEXT NOT NULL`

Purpose:
- Links each owned card instance to at most one player folder
- Supports one-folder-per-instance assignment with move-on-reassign semantics

### player_teams

Primary key:
- `(guild_id, user_id, team_name)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `team_name TEXT NOT NULL`
- `created_at REAL NOT NULL DEFAULT 0`

Purpose:
- Stores named teams owned by players
- Teams are used as battle rosters and active battle loadout selection

### team_members

Primary key:
- `(guild_id, user_id, team_name, instance_id)`

Columns:
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `team_name TEXT NOT NULL`
- `instance_id INTEGER NOT NULL`
- `created_at REAL NOT NULL DEFAULT 0`

Purpose:
- Links owned card instances to player teams
- Supports many-to-many assignment across teams (same instance may appear in multiple teams)

### battle_sessions

Primary key:
- `battle_id INTEGER PRIMARY KEY AUTOINCREMENT`

Columns:
- `battle_id`
- `guild_id INTEGER NOT NULL`
- `challenger_id INTEGER NOT NULL`
- `challenged_id INTEGER NOT NULL`
- `stake INTEGER NOT NULL`
- `status TEXT NOT NULL` (e.g. `pending`, `active`, `denied`)
- `challenger_team_name TEXT NOT NULL`
- `challenged_team_name TEXT NOT NULL`
- `created_at REAL NOT NULL DEFAULT 0`
- `accepted_at REAL`
- `finished_at REAL`
- `acting_user_id INTEGER`
- `turn_number INTEGER NOT NULL DEFAULT 1`
- `winner_user_id INTEGER`
- `last_action TEXT`

Purpose:
- Tracks battle proposal lifecycle and active battle session state
- Supports one pending/active battle per player rule checks

### battle_combatants

Primary key:
- `(battle_id, side, slot_index)`

Columns:
- `battle_id INTEGER NOT NULL`
- `guild_id INTEGER NOT NULL`
- `user_id INTEGER NOT NULL`
- `side TEXT NOT NULL` (`challenger` or `challenged`)
- `slot_index INTEGER NOT NULL`
- `instance_id INTEGER NOT NULL`
- `card_id TEXT NOT NULL`
- `generation INTEGER NOT NULL`
- `dupe_code TEXT NOT NULL`
- `max_hp INTEGER NOT NULL`
- `current_hp INTEGER NOT NULL`
- `is_active INTEGER NOT NULL DEFAULT 0`
- `is_defending INTEGER NOT NULL DEFAULT 0`
- `is_knocked_out INTEGER NOT NULL DEFAULT 0`

Purpose:
- Persists per-card battle combat state for each session.
- Tracks active card, HP, defend stance, and KO state across turns/timeouts.

## Migration behavior

`init_db()` performs versioned startup migration:

1. Ensures `schema_migrations` exists and has one row.
2. Reads current schema version.
3. Applies ordered migrations up to `TARGET_SCHEMA_VERSION`.
4. Updates stored `schema_migrations.version` after each migration step.

Current migration set:
- `v1`:
	- Ensures core tables and indexes exist (`players`, `card_instances`).
	- Ensures `players.married_instance_id` and `players.last_dropped_instance_id` exist.
- `v2`:
	- Adds `wishlist_cards` table and owner index.
- `v3`:
	- Adds `card_instances.dupe_code`.
	- Backfills existing rows with sequential base36 ids per guild.
	- Enforces unique per-guild dupe ids with `idx_card_instances_dupe_code`.
- `v4`:
	- Normalizes all persisted data into global scope (`guild_id = 0`).
	- Merges per-user player rows across guilds into one global player row.
	- Reassigns `dupe_code` globally across all instances using ascending base36.
	- Enforces global `dupe_code` uniqueness.
- `v5`:
	- Ensures `card_instances.dupe_code` exists and is indexed.
	- Rebuilds duplicate-code uniqueness index as `idx_card_instances_dupe_code`.
- `v6`:
	- Adds `players.last_drop_at` and resets `players.last_pull_at` to support split drop vs pull cooldown tracking.
- `v7`:
	- Adds `card_instances.morph_key` to persist per-instance visual morph state.
- `v8`:
	- Adds `player_tags` for per-player tag collections and lock state.
	- Adds `card_instance_tags` for per-instance tag assignment.
- `v9`:
	- Adds `card_instances.frame_key` to persist per-instance visual frame state.
- `v10`:
	- Adds `card_instances.font_key` to persist per-instance visual font state.
- `v11`:
	- Reserved migration step (no schema changes).
- `v12`:
	- Adds `players.starter` for top.gg vote rewards.
	- Adds `players.last_vote_reward_at` for vote reward cooldown tracking.
- `v13`:
	- Adds `players.last_slots_at` for slots cooldown tracking.
- `v14`:
	- Adds `players.active_team_name` for active battle team selection.
	- Adds `player_teams` and `team_members` for team management.
	- Adds `battle_sessions` for battle proposal/state tracking.
- `v15`:
	- Adds `players.last_flip_at` for flip cooldown tracking.
- `v16`:
	- Adds `battle_combatants` for persisted turn-based combat state.
- `v17`:
	- Adds `players.drop_tickets` for drop-cooldown bypass purchases/consumption.
- `v18`:
	- Adds `player_folders` for per-player folder collections, emojis, and lock state.
	- Adds `card_instance_folders` for one-folder-per-instance assignment.
- `v19`:
	- Adds `players.votes` for cumulative successful top.gg vote claims.

Notes:
- Startup migration is in-code (`noodswap/migrations.py`) and invoked by `storage.init_db()` using incremental version checks.
- Existing DB files are upgraded in place when the bot starts.

## Domain invariants

1. Ownership is global (shared across all guilds).
2. Ownership is instance-based (not quantity blob semantics).
3. Lower generation means rarer copy.
4. Marriage points to a specific instance (`married_instance_id`).
5. Trade/burn/marry selection policies rely on generation ordering.
6. New generations are assigned by a right-skewed beta draw (`betavariate(1.6, 1.04)`) scaled to the configured generation bounds, making high generation values far more common than low generation values (gen-1 ≈ 1 in 48k).

## Identity terminology (critical)

- BASE CARDS have IDS (catalog identity like `SPG`).
- DUPE CARDS have CODES (owned-copy identity like `0`, `a`, `10`).
- Never use base ID and dupe code interchangeably in UX, storage, or command args.

## Selection policies

- `marry <card_code>`: targets the exact referenced instance
- `burn <card_code>`: targets the exact referenced instance
	- Burn is blocked if the referenced instance belongs to any locked tag or locked folder.
- `trade <card_code>`: transfers the exact referenced instance
- card code format is standalone base36 (`0-9a-z`) with optional leading `#` and without card-id prefix
- arg-less `marry` / `burn`: default to the last pulled instance (`last_dropped_instance_id` column)
- per-instance generation is sampled in `cards.random_generation()` using a right-skewed beta distribution and scaled to `[GENERATION_MIN, GENERATION_MAX]`

## Terminology (explicit)

- DUPE CARDS have CODES (`dupe_code`, e.g. `0`, `a`, `10`, `#10`).
- BASE CARDS have IDS (`card_id`, e.g. `SPG`, `PEN`).
- Treat these as different concepts in commands, storage, and documentation.

## Operational caveats

- SQLite writes are local and single-process oriented.
- Critical multi-step writes use `BEGIN IMMEDIATE` to reduce race windows.
- Connection lock wait is configured via `DB_LOCK_TIMEOUT_SECONDS` in `noodswap/settings.py`.
- If adding high-frequency multi-step operations, use explicit transactions carefully.
