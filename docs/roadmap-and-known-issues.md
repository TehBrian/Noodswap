# Roadmap and Known Issues

## Current known issues / gaps

1. Migration framework is minimal
- `schema_migrations` + in-code step migrations now exist in `init_db()`.
- A recovery migration now normalizes legacy `card_instances.dupe_code` databases to `card_code` on startup so older persistent runtime volumes can survive schema refactors.
- Still missing richer migration ergonomics (standalone migration files and downgrade strategy).

2. Concurrency/race handling is basic
- Critical writes now use `BEGIN IMMEDIATE` to reduce race windows.
- Further hardening is still recommended for very high-concurrency workloads and long-running transactions.

3. Prefix command architecture only
- Slash commands are not implemented yet.
- A migration path should preserve existing UX where possible.

4. Test coverage is still limited
- `pytest` coverage now exists for `storage` migration/selection/failure semantics, `services` orchestration flows, and core `views` interaction guard + timeout behavior.
- Test tasks now run on the workspace venv interpreter where `discord.py` is installed, so `views` tests execute in normal development flow.
- Broader command UX paths and economy invariants still need coverage.

5. Catalog balance is manual
- Rarity/value balancing currently hand-tuned.
- Could add tooling for expected value simulation.

6. Battle system is in staged rollout
- Team persistence, battle proposal lifecycle, and core turn loop are implemented (`team` commands, proposal accept/deny, attack/defend/switch/surrender, timeout skip).
- Remaining work is primarily UX polish and balancing (action logs, richer visuals, expanded matchup tuning).

## Near-term roadmap

1. Expand migration framework
- Structured migration modules/files
- Startup integrity checks + migration validation tooling
- Optional downgrade/playback strategy for development

2. Add domain-level tests
- storage selection semantics
- generation distribution sanity checks
- payout bounds

3. Add slash command support
- Keep prefix aliases during transition

4. Improve collection UX
- pagination and filtering (series, rarity, generation range)

5. Economy hardening
- anti-abuse controls and audit logging
- add lightweight economy event ledger tables for pull/burn/trade telemetry so balancing reports can use true time-window flow metrics instead of ownership snapshots

6. Deploy-state automation
- Add automated SQLite backup/restore workflow (scheduled backup to remote object storage + restore-on-empty bootstrap for `runtime/db/bot.db`).
- Publish/import a versioned card-image cache artifact so new hosts can bootstrap `runtime/card_images` without manual copy steps.

## Refactor backlog (staged)

Status: Stages 1 and 3 are complete. Remaining deferred stages are Stage 2 and Stage 4.

### Stage 2 — Storage boundary split
- Extract migration logic from `storage.py` into a dedicated migration module while preserving current startup behavior.
- Introduce repository-oriented functions (players/card_instances/trades) behind a stable facade.
- Add migration-version edge case tests and transaction boundary tests.

### Stage 3 — Module boundary hardening (no behavior change)
- Keep this stage refactor-only (no command UX changes, no schema changes, no deploy/tmpfs changes).
- Split `views.py` into domain-focused modules while preserving existing interaction behavior and timeouts.
- Split `cards.py` into catalog-loading, search, and display/value concerns with stable public wrappers.
- Tighten `storage.py` facade scope to transaction/use-case orchestration and keep direct SQL in `repositories.py`.
- Add focused regression tests before each split to lock current behavior.

Stage 3 implementation guide: `docs/refactor-phase-3.md`.

### Stage 4 — Presentation expansion and consistency
- Continue centralizing repeated embed description assembly into `presentation.py` helpers.
- Add small presenter unit tests for deterministic formatting of high-use descriptions.
- Keep command handlers thin and primarily responsible for routing and dependency wiring.

## Decision log (recent)

- Expanded `trade` mode beyond dough-only: `trade <player> <card_code> <mode> <amount|req_card_code>` now supports `dough`, `starter`, `drop` (aliases: `tickets`/`ticket`/`drop_tickets`), and `card` (card-for-card swap where both sides exchange a specific owned dupe). Card mode clears marriage and last-pulled pointers for both transferred instances. Either side losing their card between offer and accept causes a deterministic failure (no partial-fill).
- Reworked `gift` into explicit immediate-transfer subcommands (`ns gift dough <player> <dough>`, `ns gift starter <player> <starter>`, `ns gift drop <player> <tickets>`, and `ns gift card <player> <card_code>`) so runtime behavior and docs align around one-step transfers.
- Finalized command-module split: `bot/commands.py` is now a thin registrar entrypoint delegating to domain modules (`commands_social`, `commands_catalog`, `commands_economy`, `commands_gambling`, `commands_admin`) with shared helpers in `command_utils.py`.
- Updated `wish add`, `tag/folder/team assign`, and `tag/folder/team unassign` to accept multiple space-separated targets with dedupe + mixed-result feedback (including team remaining-slot `before -> after` reporting), and changed batch burn semantics to partial execution (burn eligible targets, report skipped locked/unavailable targets) instead of all-or-nothing lock blocking.
- Added persistent `players.votes` tracking for successful top.gg webhook claims, surfaced the count in `info`, and added `Votes` as a sortable `leaderboard` criterion.
- Added per-player folders (`player_folders` + `card_instance_folders`) with one-folder-per-instance assignment, folder emoji metadata, and lock inheritance that treats locked tags and locked folders as equivalent burn blockers.
- Added `drop tickets` currency with `buy drop [quantity]` starter purchases (1:1 cost), auto-ticket substitution when `drop` is on cooldown (cooldown timestamp unchanged), and info-surface visibility for ticket balances.
- Updated `flip` / `f` UX to support optional side calls (`heads`/`tails`, `h`/`t`) while preserving house-edge odds (46/54) and added a suspense-first reveal flow that posts "The coin is ..." then edits in the result after 3 seconds.
- Updated deploy/runtime bootstrap flow so `deploy/update.sh` now runs `scripts/init_runtime.py` on-host during each deploy, ensuring runtime DB/image/font/frame seeds are initialized before container restart.
- Added `slots` / `s` command with animated 3-reel food-emoji spins, two-match dough payout (`+200..+400`), jackpot payout (`+800..+1200 dough` and `+1..+3 starter`), and a dedicated 22-minute cooldown tracked by `players.last_slots_at`.
- Added `flip` / `f` command with dough wagering, a dedicated 2-minute cooldown (`players.last_flip_at`), and intentional house-edge odds (46% win / 54% lose) to keep long-run expected value negative.
- Started team-battle foundation rollout: added migration `v14` (`players.active_team_name`, `player_teams`, `team_members`, `battle_sessions`), added `team` command group (`add/remove/list/assign/unassign/cards/active`), and added `battle <player> <stake>` proposal flow with accept/deny interaction view and one-open-battle-per-player guard.
- Extended battle implementation with persisted combatant state (`battle_combatants`), stake escrow on accept, turn-resolution storage/services (`attack`/`defend`/`switch`/`surrender`/timeout skip), and live arena interaction view updates per turn.
- Stage 3 kickoff (non-breaking): extracted pagination emoji resolution/constants from `views.py` into `bot/view_pagination.py`, and extracted card display-format helpers into `bot/card_display.py` while keeping `bot.cards` public functions as compatibility wrappers.
- Continued Stage 3 (non-breaking): extracted help interaction classes (`HelpCategorySelect`, `HelpView`) into `bot/view_help.py` and kept `HelpView` available through `bot.views` for existing imports.
- Continued Stage 3 (non-breaking): extracted `DropView` into `bot/view_drop.py` and `TradeView` into `bot/view_trade.py` while keeping both importable from `bot.views`.
- Continued Stage 3 (non-breaking): extracted confirmation interaction classes (`BurnConfirmView`, `MorphConfirmView`, `FrameConfirmView`, `FontConfirmView`) into `bot/view_confirmations.py` and preserved `bot.views` monkeypatch targets used by tests.
- Continued Stage 3 (non-breaking): extracted `CardCatalogView` into `bot/view_catalog.py` and preserved `bot.views` compatibility imports and image payload patch targets.
- Continued Stage 3 (non-breaking): extracted `PaginatedLinesView` and `PlayerLeaderboardView` into `bot/view_text.py` and preserved `bot.views` compatibility imports.
- Continued Stage 3 (non-breaking): extracted `SortableCardListView` and `SortableCollectionView` into `bot/view_sortable_lists.py` and preserved `bot.views` compatibility imports and image payload patch targets.
- Continued Stage 3 (non-breaking): extracted search/code-parsing helpers from `cards.py` into `bot/card_search.py` while keeping `bot.cards` wrappers stable.
- Continued Stage 3 (non-breaking): extracted generation/value/payout + rarity-odds helpers from `cards.py` into `bot/card_economy.py` while keeping `bot.cards` wrappers stable.
- Continued Stage 3 boundary tightening (non-breaking): removed the unused `storage.ensure_player(...)` pass-through wrapper.
- Finalized Stage 3 package layout (non-breaking): converted `bot.cards` and `bot.views` from single-module shims to package paths (`bot/cards/__init__.py`, `bot/views/__init__.py`) and added package submodules (`catalog/search/display/economy` and `help/drop/trade/confirmations/catalog/pagination/sortable_lists/text`).
- Started Stage 3 callback slimming by moving drop-claim, trade accept/deny, and trait roll-confirm execution into `services.py` (`execute_drop_claim`, `resolve_trade_offer`, `resolve_morph_roll`, `resolve_frame_roll`, `resolve_font_roll`) and updating `views.py` callbacks to delegate to those use-cases.
- Completed Stage 3 callback slimming by moving burn confirmation execution into `services.py` (`execute_burn_confirmation`), removing remaining `bot.views` callback indirection in view modules, and updating view tests to patch canonical module-level symbols.
- Added follow-up roadmap item to automate deploy-state bootstrap (SQLite backup/restore and card-image cache artifact import) so host migrations do not require manual DB/image copy steps.
- Added `leaderboard` / `le` with invoker-scoped pagination + criterion dropdown (`Cards`, `Wishes`, `Dough`, `Starter`, `Collection Value`) to rank players by global player metrics.
- Added webhook-only top.gg vote registration with signed event intake and automatic `starter` reward claiming.
- Hardened top.gg webhook intake with optional source IP allowlisting (`TOPGG_WEBHOOK_ALLOWED_IPS`), strict JSON content-type enforcement, and bounded request size controls (`TOPGG_WEBHOOK_MAX_BODY_BYTES`) to reduce spoofing/DoS surface.
- Updated `vote` / `v` command copy to reflect automatic webhook registration and removed pull-based top.gg polling from the command path.
- Removed vote reward gating and removed vote status from `cooldown` UX so vote rewards now claim whenever a vote is detected.
- Changed `help` to send a brief bot overview plus an invoker-scoped category dropdown (`Overview`, `Economy`, `Gambling`, `Battle`, `Traits`, `Wishlist`, `Tags`, `Folders`, `Relationship`) that edits the same embed to the selected command page.
- Updated `scripts/init_runtime.py` to use replacement semantics for seeded runtime assets, refreshing `runtime/card_images/`, `runtime/fonts/`, and `runtime/frames/` from `assets/` on each run.
- Added `frame` / `fr` confirmation flow with before/after transition previews and per-instance frame persistence (`card_instances.frame_key`), initially shipping a `buttery` golden dripping-border frame.
- Expanded frame traits to support multiple overlay-backed frame keys (`buttery`, `gilded`, `drizzled`) and added a parallel `font` / `fo` confirmation flow with per-instance font persistence (`card_instances.font_key`).
- Added per-player tag collections (`player_tags` + `card_instance_tags`) with commands for create/delete/list/lock/unlock/assign/unassign/cards, and enforced burn protection for instances attached to any locked tag.
- Added `morph` / `mo` confirmation flow with before/after transition previews (`before -> after`), and ensured morph persistence + dough charge happen only on explicit confirmation.
- Expanded morph traits with additional visual variants (`inverse`, `tint_rose`, `tint_aqua`, `tint_lime`, `upside_down`) while keeping the same random-roll + confirmation UX.
- Added more tint morph variants (`tint_warm`, `tint_cool`, `tint_violet`) and tuned tint strengths to keep each color treatment visually distinct.
- Started large-scale PIL-first morph expansion with additional procedural families (color/tone, transform, glow/focus, glitch, texture, pattern, edge wear, and themed recipes), and added `docs/morph-expansion-backlog.md` to track deferred animation-first or shader-like variants plus PNG->GIF migration planning.
- Changed drop claiming to be contestable: any user can claim any unclaimed drop card, each card can only be claimed once, and drops remain active until timeout (or all cards are claimed).
- Reduced pull cooldown from 6 minutes to 4 minutes and updated cooldown messaging to use pull terminology.
- Added a shared card-render pipeline (`bot/images.py`) that normalizes card output to portrait `5:7`, applies rounded rarity-based borders, and routes both single-card embeds and drop-preview composites through the same renderer to support future dupe-specific visual customization.
- Changed `cards.random_generation()` from triangular mode-at-max selection to a right-skewed beta roll, iteratively tuning parameters from initial (`betavariate(5.2, 1.8)`) through refinement steps to final (`betavariate(1.6, 1.04)`), empirically validated at n=5M to observe stable quantiles and gen-1 frequency (~105 per 5M pulls, 1 in ~48k).
- Added `scripts/generation_economy_report.py` to report inverse-value (`tau`) target odds versus current owned-inventory snapshot metrics (`gen=1`, `<=10`, `<=100`, `<=500`, expected pulls, and top-end supply per 1k active pullers).
- Replaced beta-based `cards.random_generation()` sampling with an inverse-value discrete sampler (`P(gen) ∝ 1 / generation_multiplier(gen)^0.95`) so generation supply aligns directly with multiplier-driven value.
- Standardized dupe-code input parsing to accept an optional leading `#` (for example, `10` and `#10` now resolve to the same owned instance) across burn/trade/marry/lookup paths.
- Added sortable + gallery-capable collection embeds (`collection`) using the same interaction pattern as catalog/wishlist/lookup while preserving per-instance card display.
- Added `Actual Value` sort mode to duplicate-instance collection views and switched `tag cards` to the same sortable collection UI so tagged cards can be ordered by computed per-instance value.
- Added a `Gallery` toggle to sortable card-list embeds (`cards`, `wish list`, and multi-result `lookup`) to switch between paginated list mode and one-card image mode while keeping navigation controls.
- Applied the same sortable-card dropdown interaction pattern to `wish list` and multi-result `lookup` embeds (`Rarity`, `Series`, `Base Value`, `Alphabetical`).
- Added a sort-mode dropdown to the `cards` catalog embed with `Rarity`, `Series`, `Base Value`, and `Alphabetical` modes, while keeping wishlist counts visible per entry.
- Switched embeds and drop-preview loading to local-only card images (attach local file when present), replaced card image URL mappings in code with manifest-driven local paths, and standardized seed-based runtime image hydration from `assets/card_images/` into `runtime/card_images/`.
- Added `tests/test_sqlite_guardrails.py` to enforce explicit sqlite connection closing and prevent future raw `with sqlite3.connect(...) as conn:` regressions.
- Introduced `repositories.py` and refactored `storage.py` into a stable facade that delegates player/card/wishlist/trade SQL operations to repository-style boundaries.
- Split migration responsibilities out of `storage.py` into `migrations.py` and kept `storage.init_db()` as the single startup entry point.
- Hardened startup secret handling to accept `DISCORD_TOKEN` or `DISCORD_TOKEN_FILE`, replaced `.env.example` with a placeholder token value, and added `.gitignore` rules to keep real `.env` files out of git.
 - Reworked burn RNG to roll a per-burn payout band between 5% and 20% of computed value, display it as an absolute `±N` range at confirmation, and apply final RNG within that fixed range on confirm.
- Fixed `remove_card_from_player()` to clear `last_dropped_instance_id` when the pointed instance is removed.
- Added `tests/test_views.py` for interaction authorization/resolution and timeout behavior checks for `DropView` and `TradeView`.
- Expanded `tests/test_storage.py` to cover trade failure behavior (missing seller card / insufficient buyer dough) and marriage uniqueness edge cases.
- Added initial automated test suite in `tests/test_storage.py` covering migration behavior and generation-selection rules for marry/burn/trade.
- Added `scripts/migration_smoke.py` for quick validation of fresh-init migration behavior.
- Added explicit schema version tracking via `schema_migrations` and versioned startup migration flow in `init_db()`.
- Moved from quantity-owned cards to instance-based ownership.
- Added per-instance generations (`G-####`, range 1-2000).
- Standardized user messaging to Italy-themed embeds (`italy_embed` + `italy_marry_embed`).
- Modularized codebase into package-based subsystems.
- Added burn confirmation flow and default burn target from last pulled card.
- Added `image` metadata to cards with default placeholder URLs (`https://placehold.co/...`) and wired card images into drop/marry/divorce/burn/info embeds.
- Normalized per-card drop weights by rarity counts so effective rarity odds stay balanced as catalog composition changes.
