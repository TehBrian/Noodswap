# Roadmap and Known Issues

## Current known issues / gaps

1. Migration framework ergonomics are limited
- Schema versioning, 35 ordered in-code migration steps, and a startup recovery migration all exist and work.
- Still missing: a downgrade/playback strategy, standalone migration files, and startup integrity validation tooling.

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

1. Migration ergonomics
- Add a downgrade/playback strategy for development use.
- Add startup integrity validation tooling (schema version verification on boot).

2. Add slash command support
- Keep prefix aliases during transition.

3. Collection filtering
- Pagination and sort modes are already implemented.
- Still missing: filtering by series, rarity, and generation range.

4. Economy hardening
- `vote_events` table exists for vote telemetry; remaining gap is a general economy event ledger (pull/burn/trade rows) for time-window flow metrics.
- Anti-abuse controls beyond cooldowns are not yet implemented.

5. Deploy-state automation
- Add automated SQLite backup/restore workflow (scheduled backup to remote object storage + restore-on-empty bootstrap for `runtime/db/noodswap.db`).
- Publish/import a versioned card-image cache artifact so new hosts can bootstrap `runtime/card_images` without manual copy steps.

## Refactor backlog (staged)

Status: Stages 1, 2, and 3 are complete. Stage 4 remains.

### Stage 4 — Presentation expansion and consistency
- Continue centralizing repeated embed description assembly into `presentation.py` helpers; 15 helpers are already in place, but several command handlers still assemble embeds inline.
- Add small presenter unit tests for deterministic formatting of high-use descriptions.
- Keep command handlers thin and primarily responsible for routing and dependency wiring.
