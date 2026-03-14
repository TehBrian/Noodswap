# Architecture

This document describes the current runtime architecture of Noodswap.

## Layering overview

Noodswap is structured in a pragmatic layered style:

Presentation layer:
  - `bot/commands.py` (thin prefix command registration entrypoint)
  - `bot/commands_social.py` / `bot/commands_catalog.py` / `bot/commands_economy.py` / `bot/commands_gambling.py` / `bot/commands_admin.py` (domain command registrars)
  - `bot/command_utils.py` (shared command helper layer)
  - `bot/views/` (button interactions: drop/trade/burn confirm + trait confirms)
  - `bot/presentation.py` (shared embed styles + reusable command description formatting)
- Use-case/service layer:
  - `bot/services.py` (command-facing orchestration for drop/burn/marry/divorce/trade prep)
- Domain/config layer:
  - `bot/cards/` (catalog, pull/generation helpers, burn value logic)
  - `bot/card_search.py` (card search + dupe code parsing helpers used by `cards.py` wrappers)
  - `bot/card_economy.py` (generation/value/payout + rarity-odds helpers used by `cards.py` wrappers)
  - `bot/images.py` (local card image lookup + card render pipeline)
  - `bot/morphs.py` / `bot/frames.py` / `bot/fonts.py` (trait option metadata + normalization)
  - `bot/rarities.py` (rarity weight constants)
  - `bot/settings.py` (global settings/constants)
  - `bot/utils.py` (small utility helpers)
- Data/persistence layer:
  - `bot/storage.py` (SQLite data operations)
  - `bot/migrations.py` (schema versioning + startup migration steps)
  - `bot/repositories.py` (repository-style SQL boundaries used by `storage.py`)
- Application bootstrap:
  - `bot/main.py` (thin launcher)
  - `bot/app.py` (bot factory, intents, startup)

## Cross-cutting concerns

- Centralized command error handling is in `bot/app.py` (`on_command_error`).
- Shared operational constants are in `bot/settings.py` (cooldowns, timeouts, generation bounds).
- Interaction button disable behavior is encapsulated per-view in `bot/views/` modules.
- Card visual customization flows are instance-based (`morph_key`, `frame_key`, `font_key`) and resolved through `bot/images.py` during render.

## Startup flow

1. `python -m bot.main`
2. `bot/main.py` calls `bot.app.main()`
3. `main()` resolves token from `DISCORD_TOKEN` or `DISCORD_TOKEN_FILE`
4. `main()` calls `storage.init_db()`
5. `create_bot()` builds the `commands.Bot`, registers handlers, and returns bot
6. Bot starts and begins handling prefix commands and interaction callbacks

## Command + interaction flow

### Drop flow

1. User runs `ns drop`
2. Command checks cooldown from the player's last drop timestamp (`players.last_pull_at` column)
3. Command calls `cards.make_drop_choices(3)` to generate three `(card_id, generation)` offers
4. Message is sent with embed + `DropView` buttons
5. On button click, selected card instance is persisted into `card_instances`

### Trade flow

1. User runs `ns trade <player> <card_id> <amount>`
2. Command validates ownership and constructs `TradeView`
3. Buyer accepts/denies via interaction
4. On accept, storage layer transfers one card instance and dough atomically within one DB transaction scope

### Traits flow (`morph` / `frame` / `font`)

1. User runs `ns morph|frame|font <card_id>`
2. Command resolves target instance and proposed trait roll via service layer
3. Confirmation view presents before/after preview
4. On confirm, storage persists per-instance trait key and applies dough charge atomically

## Ownership model

The live model is instance-based:

- Every owned card copy has a unique `instance_id`
- Every copy has a `generation`
- `generation` is not part of card catalog metadata; it is per-instance state

## Catalog and drop odds

- Card drop weights in `bot/rarities.py` are defined per-rarity, not per-card.
- When building drop candidates, per-card weights are normalized by the count of cards within each rarity so that adding more cards to a rarity does not change that rarity's effective pull odds — each individual card in a larger rarity bucket becomes proportionally less likely to appear.
- As a result, tuning `RARITY_WEIGHTS` purely controls rarity-tier odds regardless of catalog size imbalances.

Selection rules currently implemented:

- `marry <card_id>` targets the exact referenced dupe
- `burn <card_id>` targets the exact referenced dupe
- `trade <card_id>` targets the exact referenced dupe
- arg-less `marry`/`burn` default to the last pulled card instance

## Presentation contract

All user-visible command and interaction messages are embed-based and should use:

- `bot.presentation.italy_embed()`
- `bot.presentation.italy_marry_embed()` for marriage/divorce flows
- Italy themed colors (`ITALY_RED`, `ITALY_PINK`)

When adding new user-facing output, keep this consistent.

## Why this split helps agents

- Catalog changes are isolated to one file
- Probability tuning is isolated to one file
- Data safety logic is isolated to one file
- Command orchestration changes are isolated to `services.py`
- UX text/formatting changes are isolated to `presentation.py`
- Discord wiring changes are isolated to `commands*.py` / `views/`
- New commands can reuse the existing service boundaries quickly

## Phase 3 achieved layout (non-breaking)

Stage 3 completed this layout while preserving stable public imports.

- Views split target:
  - `bot/views/help.py`
  - `bot/views/drop.py`
  - `bot/views/trade.py`
  - `bot/views/confirmations.py` (burn/morph/frame/font)
  - `bot/views/catalog.py` (cards/collection/wishlist paged views)
  - `bot/views/pagination.py` (shared pagination components)
  - `bot/views/__init__.py` re-exporting current symbols used by command registrar modules
- Cards split target:
  - `bot/cards/catalog.py` (load/validate catalog + series + image map)
  - `bot/cards/search.py` (query + lookup helpers)
  - `bot/cards/display.py` (display labels + code formatting)
  - `bot/cards/economy.py` (generation/value/payout helpers)
  - `bot/cards/__init__.py` re-exporting legacy `bot.cards` API during migration
- Storage/repository boundary target:
  - `storage.py` owns transaction scope and domain invariants for multi-step operations.
  - `repositories.py` owns direct SQL statements and row-shape translation.
  - Avoid adding new one-line pass-through wrappers in `storage.py` when repository call sites are sufficient.
