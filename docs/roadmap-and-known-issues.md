# Roadmap and Known Issues

## Current known issues / gaps

1. Migration framework is minimal
- `schema_migrations` + in-code step migrations now exist in `init_db()`.
- Still missing richer migration ergonomics (standalone migration files and downgrade strategy).

2. Concurrency/race handling is basic
- Critical writes now use `BEGIN IMMEDIATE` to reduce race windows.
- Further hardening is still recommended for very high-concurrency workloads and long-running transactions.

3. Prefix command architecture only
- Slash commands are not implemented yet.
- A migration path should preserve existing UX where possible.

4. Test coverage is still limited
- `unittest` coverage now exists for `storage` migration/selection/failure semantics, `services` orchestration flows, and core `views` interaction guard + timeout behavior.
- Test tasks now run on the workspace venv interpreter where `discord.py` is installed, so `views` tests execute in normal development flow.
- Broader command UX paths and economy invariants still need coverage.

5. Catalog balance is manual
- Rarity/value balancing currently hand-tuned.
- Could add tooling for expected value simulation.

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

6. top.gg push vote confirmations
- Add a signed top.gg webhook endpoint for vote events (no polling loop).
- Verify webhook secret header before processing payloads.
- Auto-claim vote rewards from webhook events using existing cooldown safeguards.
- Document deployment requirements (public HTTPS route, secret config, reverse-proxy wiring).

7. Deploy-state automation
- Add automated SQLite backup/restore workflow (scheduled backup to remote object storage + restore-on-empty bootstrap for `deploy/assets/noodswap.db`).
- Publish/import a versioned card-image cache artifact so new hosts can bootstrap `deploy/assets/card_images` without manual copy steps.

## Refactor backlog (staged)

Status: Stage 1 is complete. Stages below are intentionally deferred for later.

### Stage 2 — Storage boundary split
- Extract migration logic from `storage.py` into a dedicated migration module while preserving current startup behavior.
- Introduce repository-oriented functions (players/card_instances/trades) behind a stable facade.
- Add migration-version edge case tests and transaction boundary tests.

### Stage 3 — View callback slimming
- Move remaining callback orchestration from `views.py` into `services.py` use-cases.
- Keep `views.py` focused on Discord interaction authorization, lifecycle, and response wiring.
- Add focused tests around resolved-click and timeout transitions per view.

### Stage 4 — Presentation expansion and consistency
- Continue centralizing repeated embed description assembly into `presentation.py` helpers.
- Add small presenter unit tests for deterministic formatting of high-use descriptions.
- Keep command handlers thin and primarily responsible for routing and dependency wiring.

## Decision log (recent)

- Started Stage 3 callback slimming by moving drop-claim, trade accept/deny, and cosmetic roll-confirm execution into `services.py` (`execute_drop_claim`, `resolve_trade_offer`, `resolve_morph_roll`, `resolve_frame_roll`, `resolve_font_roll`) and updating `views.py` callbacks to delegate to those use-cases.
- Added follow-up roadmap item to automate deploy-state bootstrap (SQLite backup/restore and card-image cache artifact import) so host migrations do not require manual DB/image copy steps.
- Added `leaderboard` / `le` with invoker-scoped pagination + criterion dropdown (`Cards`, `Wishes`, `Dough`, `Starter`, `Collection Value`) to rank players by global player metrics.
- Added `vote` / `v` command with top.gg link-button UX, top.gg API vote verification (`TOPGG_API_TOKEN` + `TOPGG_BOT_ID`), and `starter` reward claims with a 24-hour cooldown surfaced in both `info` and `cooldown`.
- Planned follow-up: switch vote confirmation from pull-based checks to top.gg push webhooks so rewards can be granted immediately after vote events.
- Changed `help` to send a brief bot overview plus an invoker-scoped category dropdown (`Overview`, `Economy`, `Cosmetics`, `Wishlist`, `Tags`, `Relationship`, `Owner-only`) that edits the same embed to the selected command page.
- Added `frame` / `fr` confirmation flow with before/after transition previews and per-instance frame persistence (`card_instances.frame_key`), initially shipping a `buttery` golden dripping-border frame.
- Expanded frame cosmetics to support multiple overlay-backed frame keys (`buttery`, `gilded`, `drizzled`) and added a parallel `font` / `fo` confirmation flow with per-instance font persistence (`card_instances.font_key`).
- Added per-player tag collections (`player_tags` + `card_instance_tags`) with commands for create/delete/list/lock/unlock/assign/unassign/cards, and enforced burn protection for instances attached to any locked tag.
- Added `morph` / `mo` confirmation flow with before/after transition previews (`before -> after`), and ensured morph persistence + dough charge happen only on explicit confirmation.
- Expanded morph cosmetics with additional visual variants (`inverse`, `tint_rose`, `tint_aqua`, `tint_lime`, `upside_down`) while keeping the same random-roll + confirmation UX.
- Added more tint morph variants (`tint_warm`, `tint_cool`, `tint_violet`) and tuned tint strengths to keep each color treatment visually distinct.
- Changed drop claiming to be contestable: any user can claim any unclaimed drop card, each card can only be claimed once, and drops remain active until timeout (or all cards are claimed).
- Reduced pull cooldown from 6 minutes to 4 minutes and updated cooldown messaging to use pull terminology.
- Added a shared card-render pipeline (`noodswap/images.py`) that normalizes card output to portrait `5:7`, applies rounded rarity-based borders, and routes both single-card embeds and drop-preview composites through the same renderer to support future dupe-specific visual customization.
- Changed `cards.random_generation()` from triangular mode-at-max selection to a right-skewed beta roll, iteratively tuning parameters from initial (`betavariate(5.2, 1.8)`) through refinement steps to final (`betavariate(1.6, 1.04)`), empirically validated at n=5M to observe stable quantiles and gen-1 frequency (~105 per 5M pulls, 1 in ~48k).
- Added `scripts/generation_economy_report.py` to report inverse-value (`tau`) target odds versus current owned-inventory snapshot metrics (`gen=1`, `<=10`, `<=100`, `<=500`, expected pulls, and top-end supply per 1k active pullers).
- Standardized dupe-code input parsing to accept an optional leading `#` (for example, `10` and `#10` now resolve to the same owned instance) across burn/trade/marry/lookup paths.
- Added sortable + gallery-capable collection embeds (`collection`) using the same interaction pattern as catalog/wishlist/lookup while preserving per-instance card display.
- Added `Actual Value` sort mode to duplicate-instance collection views and switched `tag cards` to the same sortable collection UI so tagged dupes can be ordered by computed per-instance value.
- Added a `Gallery` toggle to sortable card-list embeds (`cards`, `wish list`, and multi-result `lookup`) to switch between paginated list mode and one-card image mode while keeping navigation controls.
- Applied the same sortable-card dropdown interaction pattern to `wish list` and multi-result `lookup` embeds (`Rarity`, `Series`, `Base Value`, `Alphabetical`).
- Added a sort-mode dropdown to the `cards` catalog embed with `Rarity`, `Series`, `Base Value`, and `Alphabetical` modes, while keeping wishlist counts visible per entry.
- Switched embeds and drop-preview loading to local-only card images (attach local file when present; no remote URL fallback at runtime), replaced card image URL mappings in code with manifest-driven local paths, and added `scripts/export_card_image_url_backup.py` + `scripts/cache_card_images_from_backup.py` for URL backup and staged local cache hydration.
- Added `tests/test_sqlite_guardrails.py` to enforce explicit sqlite connection closing and prevent future raw `with sqlite3.connect(...) as conn:` regressions.
- Introduced `repositories.py` and refactored `storage.py` into a stable facade that delegates player/card/wishlist/trade SQL operations to repository-style boundaries.
- Split migration responsibilities out of `storage.py` into `migrations.py` and kept `storage.init_db()` as the single startup entry point.
- Hardened startup secret handling to accept `DISCORD_TOKEN` or `DISCORD_TOKEN_FILE`, replaced `.env.example` with a placeholder token value, and added `.gitignore` rules to keep real `.env` files out of git.
 - Reworked burn RNG to roll a per-burn payout band between 5% and 20% of computed value, display it as an absolute `±N` range at confirmation, and apply final RNG within that fixed range on confirm.
- Fixed `remove_card_from_player()` to clear `last_dropped_instance_id` when the pointed instance is removed.
- Added `tests/test_views.py` for interaction authorization/resolution and timeout behavior checks for `DropView` and `TradeView`.
- Expanded `tests/test_storage.py` to cover trade failure behavior (missing seller card / insufficient buyer dough) and marriage uniqueness edge cases.
- Added initial `unittest` suite in `tests/test_storage.py` covering migration behavior and generation-selection rules for marry/burn/trade.
- Added `scripts/migration_smoke.py` for quick validation of fresh-init and legacy-backfill migration behavior.
- Added explicit schema version tracking via `schema_migrations` and versioned startup migration flow in `init_db()`.
- Moved from quantity-owned cards to instance-based ownership.
- Added per-instance generations (`G-####`, range 1-2000).
- Standardized user messaging to Italy-themed embeds (`italy_embed` + `italy_marry_embed`).
- Modularized codebase into package-based subsystems.
- Added burn confirmation flow and default burn target from last pulled card.
- Added `image` metadata to cards with default placeholder URLs (`https://placehold.co/...`) and wired card images into drop/marry/divorce/burn/info embeds.
- Normalized per-card drop weights by rarity counts so effective rarity odds stay balanced as catalog composition changes.
