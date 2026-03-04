# Architecture

This document describes the current runtime architecture of Noodswap.

## Layering overview

Noodswap is structured in a pragmatic layered style:

- Presentation layer:
  - `noodswap/commands.py` (prefix command handlers)
  - `noodswap/views.py` (button interactions: drop/trade/burn confirm)
  - `noodswap/presentation.py` (shared embed styles + reusable command description formatting)
- Use-case/service layer:
  - `noodswap/services.py` (command-facing orchestration for drop/burn/marry/divorce/trade prep)
- Domain/config layer:
  - `noodswap/cards.py` (catalog, pull/generation helpers, burn value logic)
  - `noodswap/rarities.py` (rarity weight constants)
  - `noodswap/settings.py` (global settings/constants)
  - `noodswap/utils.py` (small utility helpers)
- Data/persistence layer:
  - `noodswap/storage.py` (SQLite schema, migration, data operations)
- Application bootstrap:
  - `bot.py` (thin launcher)
  - `noodswap/app.py` (bot factory, intents, startup)

## Cross-cutting concerns

- Centralized command error handling is in `noodswap/app.py` (`on_command_error`).
- Shared operational constants are in `noodswap/settings.py` (cooldowns, timeouts, generation bounds).
- Interaction button disable behavior is encapsulated per-view in `noodswap/views.py`.

## Startup flow

1. `python bot.py`
2. `bot.py` calls `noodswap.app.main()`
3. `main()` loads `DISCORD_TOKEN`
4. `main()` calls `storage.init_db()`
5. `create_bot()` builds the `commands.Bot`, registers handlers, and returns bot
6. Bot starts and begins handling prefix commands and interaction callbacks

## Command + interaction flow

### Drop flow

1. User runs `ns drop`
2. Command checks cooldown from `players.last_pull_at`
3. Command calls `cards.make_drop_choices(3)` to generate three `(card_id, generation)` offers
4. Message is sent with embed + `DropView` buttons
5. On button click, selected card instance is persisted into `card_instances`

### Trade flow

1. User runs `ns trade <player> <card_code> <amount>`
2. Command validates ownership and constructs `TradeView`
3. Buyer accepts/denies via interaction
4. On accept, storage layer transfers one card instance and dough atomically within one DB transaction scope

## Ownership model

The live model is instance-based:

- Every owned card copy has a unique `instance_id`
- Every copy has a `generation`
- `generation` is not part of card catalog metadata; it is per-instance state

Selection rules currently implemented:

- `marry <card_code>` targets the exact referenced dupe
- `burn <card_code>` targets the exact referenced dupe
- `trade <card_code>` targets the exact referenced dupe
- arg-less `marry`/`burn` default to the last pulled card instance

## Presentation contract

All user-visible command and interaction messages are embed-based and should use:

- `noodswap.presentation.italy_embed()`
- `noodswap.presentation.italy_marry_embed()` for marriage/divorce flows
- Italy themed colors (`ITALY_RED`, `ITALY_PINK`)

When adding new user-facing output, keep this consistent.

## Why this split helps agents

- Catalog changes are isolated to one file
- Probability tuning is isolated to one file
- Data safety logic is isolated to one file
- Command orchestration changes are isolated to `services.py`
- UX text/formatting changes are isolated to `presentation.py`
- Discord wiring changes are isolated to `commands.py` / `views.py`
- New commands can reuse the existing service boundaries quickly
