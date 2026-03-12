# Stage 3 Refactor Guide (No Behavior Change)

This document defines the execution plan for Stage 3 module-boundary hardening.

## Scope

Included:
- `bot/views/` internal split by interaction domain.
- `bot/cards/` internal split by concern (catalog/search/display/economy).
- `storage.py` and `repositories.py` boundary tightening.

Explicitly excluded:
- No tmpfs changes.
- No deploy topology changes.
- No schema migrations.
- No command UX changes.
- No slash-command migration.

## Completed slices

- Slice 1 (done): extracted pagination emoji resolution/constants into `bot/view_pagination.py`.
- Slice 2 (done): extracted display-format helpers into `bot/card_display.py` with compatibility wrappers on the `bot.cards` import surface.
- Slice 3 (done): extracted `HelpCategorySelect` and `HelpView` into `bot/view_help.py` while preserving `from bot.views import HelpView` compatibility.
- Slice 4 (done): extracted `DropView` into `bot/view_drop.py` while preserving `from bot.views import DropView` compatibility.
- Slice 5 (done): extracted `TradeView` into `bot/view_trade.py` while preserving `from bot.views import TradeView` compatibility.
- Slice 6 (done): extracted burn/morph/frame/font confirmation views into `bot/view_confirmations.py` while preserving imports from `bot.views`.
- Slice 7 (done): extracted `CardCatalogView` into `bot/view_catalog.py` while preserving `from bot.views import CardCatalogView` compatibility.
- Slice 8 (done): extracted `PaginatedLinesView` and `PlayerLeaderboardView` into `bot/view_text.py` while preserving imports from `bot.views`.
- Slice 9 (done): extracted `SortableCardListView` and `SortableCollectionView` into `bot/view_sortable_lists.py` while preserving imports from `bot.views` and existing test monkeypatch targets.
- Slice 10 (done): extracted card search + code-parsing helpers into `bot/card_search.py` with compatibility wrappers retained on the `bot.cards` import surface.
- Slice 11 (done): extracted generation/value/payout + rarity-odds helpers into `bot/card_economy.py` with compatibility wrappers retained on the `bot.cards` import surface.
- Slice 12 (done): removed unused one-line `storage.ensure_player(...)` pass-through wrapper to keep direct repository access out of non-transactional helper exports.
- Slice 13 (done): converted `bot.cards` and `bot.views` to package paths (`bot/cards/__init__.py`, `bot/views/__init__.py`) and added `bot/cards/*` + `bot/views/*` submodule surfaces matching the Stage 3 target layout.
- Slice 14 (done): completed callback slimming by moving burn-confirm execution into `services.py` and switching view callbacks to direct service/image imports (no `bot.views` facade indirection within callback execution paths).

## Preconditions

1. Keep current public imports stable during migration.
2. Add/adjust tests before moving code where behavior is subtle.
3. Move in small slices and run `check:quick` + `check:tests` after each slice.

## Workstreams

## A) Views split

Current pain point:
- Legacy view code was concentrated in one surface and mixed unrelated interaction concerns.

Target structure:
- `bot/views/help.py`
- `bot/views/drop.py`
- `bot/views/trade.py`
- `bot/views/confirmations.py`
- `bot/views/catalog.py`
- `bot/views/pagination.py`
- `bot/views/__init__.py`

Incremental steps:
1. Create `bot/views/` package and move pagination helpers first.
2. Move help views (`HelpView`, `HelpCategorySelect`) next.
3. Move `DropView` and `TradeView` once imports are stable.
4. Move confirmation views (burn/morph/frame/font).
5. Re-export all existing symbols from `bot/views/__init__.py`.
6. Keep legacy import path working in `commands.py` throughout.

Acceptance checks:
- Existing interaction timeouts unchanged.
- Existing resolved-click behavior unchanged.
- `tests/test_views.py` green.

## B) Cards split

Current pain point:
- Legacy card code mixed data loading, search, display formatting, and value-generation logic in one surface.

Target structure:
- `bot/cards/catalog.py`
- `bot/cards/search.py`
- `bot/cards/display.py`
- `bot/cards/economy.py`
- `bot/cards/__init__.py`

Incremental steps:
1. Move pure formatter helpers into `display.py`.
2. Move search/query helpers into `search.py`.
3. Move generation/value/payout math into `economy.py`.
4. Keep catalog load/validation in `catalog.py`.
5. Re-export old API names from `cards/__init__.py` until all imports are updated.

Acceptance checks:
- Card IDs/codes resolve exactly as before.
- Burn payout range calculations unchanged.
- Generation distribution function unchanged.
- `tests/test_cards.py`, `tests/test_services.py`, and `tests/test_commands.py` green.

## C) Storage vs repository boundary

Boundary contract:
- `repositories.py`: direct SQL and row parsing.
- `storage.py`: transaction orchestration and domain invariants.

Incremental steps:
1. Identify one-line pass-through wrappers in `storage.py`.
2. For low-risk read-only paths, switch callers to repository usage where practical.
3. Keep multi-step write flows in `storage.py` with explicit transaction scopes.
4. Add notes when a `storage.py` function remains intentionally as a boundary.

Acceptance checks:
- Trade/marry/burn semantics unchanged.
- Migration startup behavior unchanged.
- `tests/test_storage.py` and `tests/test_sqlite_guardrails.py` green.

## Suggested execution order

1. Views pagination/help extraction.
2. Cards display/search extraction.
3. Storage wrapper reduction (read-only first).
4. Remaining views and cards extraction.

## Validation commands

```bash
uv run python -m py_compile bot/main.py bot/*.py scripts/*.py tests/*.py
uv run python scripts/migration_smoke.py
uv run pytest tests -v --tb=short
```

## Definition of done

1. Legacy single-file modules are reduced to small compatibility shims or removed.
2. Public command behavior remains identical.
3. No deploy/runtime behavior changes introduced in this stage.
4. Documentation (`docs/architecture.md`, this file, and roadmap) matches final structure.
