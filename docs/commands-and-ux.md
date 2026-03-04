# Commands and UX

This document defines behavior and presentation for commands and interaction flows.

## Prefix

- Prefix: `ns `

## Command list

- `info [player]` / `i [player]`
- `collection [player]` / `c [player]`
- `cards` / `ca`
- `lookup <card_id|card_code|query>` / `l <card_id|card_code|query>`
- `help` / `h`
- `drop` / `d`
- `cooldown [player]` / `cd [player]`
- `burn [card_code]` / `b [card_code]`
- `trade <player> <card_code> <amount>` / `t ...`
- `wish` / `w`
- `wish add <card_id>` / `wish a <card_id>` / `w add <card_id>` / `w a <card_id>` / `wa <card_id>`
- `wish remove <card_id>` / `wish r <card_id>` / `w remove <card_id>` / `w r <card_id>` / `wr <card_id>`
- `wish list [player]` / `wish l [player]` / `w list [player]` / `w l [player]` / `wl [player]`
- `marry [card_code]` / `m [card_code]`
- `divorce` / `dv`
- owner-only: `dbexport`, `dbreset`

## Embed style contract

All user-facing responses should be embeds with:

- helper: `italy_embed(title, description="")` for general flows
- helper: `italy_marry_embed(title, description="")` for marriage/divorce flows
- colors defined in `noodswap/presentation.py`

This includes:
- success responses
- validation errors
- cooldown messages
- interaction responses
- interaction timeout updates

## Drop UX

- Shows 3 random offers
- Each offer line format is: `**CARD_NAME** • (ID: CARD_ID) [Series] (Rarity) • **G-####** (Base: **N** dough)`
- Drop response is a single embed with one combined preview image showing all 3 offered cards
- Buttons are labeled with **card names** (not IDs)
- Buttons are private-action restricted to command invoker
- After pull, original drop offer remains visible (buttons disabled) and a separate pulled-card embed is posted
- On timeout, buttons are disabled and a separate expiry embed is posted

## Burn UX

Burn flow:

- `burn` with no argument targets the player's most recently pulled card instance
- `burn <card_code>` targets that exact dupe code
- card code format is standalone base36 (examples: `0`, `a`, `10`)
- Burn always requires confirm/cancel interaction before destruction
- Burn payout includes a generation multiplier (lower generation = higher payout)
- Multiplier curve uses progress^7 scaling with a max of x70.00 (generation 1 = x70.00)
- Burn RNG range is randomized per burn between 5% and 20% of computed value
- Burn confirmation shows the concrete absolute payout range as `Value ± N` (not as a percent)

Burn result format should remain:

- Title: `**Burn**`
- Description lines:
  - `Name: **...**`
  - `Series: **...**`
  - `**CARD_NAME** • (Code: CARD_ID-DUPE_CODE) [Series] (Rarity) • **G-####** (Value: **N** dough)`
  - blank spacer line
  - payout line (`dough`)
  - generation multiplier line (`x..`)
  - base + value + RNG lines
- Burn confirmation and burn result both display the target card image

Card identity terms:

- `ID` means base catalog card identity (internal/base concept)
- `Code` means a specific owned dupe reference (user-facing, e.g. `0`, `a`, `10`)
- DUPE CARDS have CODES.
- BASE CARDS have IDS.

## Card text format

- Card references in embeds should use this shared display style:
  - base card: `**CARD_NAME** • (ID: CARD_ID) [Series] (Rarity) (Base: **N** dough)`
  - dupe card: `**CARD_NAME** • (Code: DUPE_CODE) [Series] (Rarity) • **G-####** (Value: **N** dough)`

## Trade UX

- Offer message is embed + buttons
- Accept/deny edits same message into final state embed
- Trade result should include card instance/generation when available
- Trade player argument supports direct mention (e.g. `@Friend`) or exact username

## Wishlist UX

- `wish add <card_id>` / `w add <card_id>` adds a base card id to the invoker's wishlist
- `wish remove <card_id>` / `w remove <card_id>` removes a base card id from the invoker's wishlist
- `wish list` / `w list` returns the invoker's wishlist as embed lines
- `wish list` / `w list` includes a sort dropdown with modes: `Wishes`, `Rarity`, `Series`, `Base Value`, `Alphabetical`
- default sort mode is `Alphabetical`
- includes a `Gallery` toggle that switches to one-card-per-page image mode while keeping page navigation
- `wa <card_id>`, `wr <card_id>`, and `wl` are shortcuts for add/remove/list
- Unknown card ids return a validation error embed

## Lookup UX

- Multi-match lookup results are shown in a paginated embed with a sort dropdown
- Sort modes are: `Wishes`, `Rarity`, `Series`, `Base Value`, `Alphabetical`
- default sort mode is `Alphabetical`
- includes a `Gallery` toggle that switches to one-card-per-page image mode while keeping page navigation

## Cards Catalog UX

- `cards` / `ca` shows all available catalog cards
- Catalog includes a sort dropdown with modes: `Wishes`, `Rarity`, `Series`, `Base Value`, `Alphabetical`
- Default sort mode is `Alphabetical`
- includes a `Gallery` toggle that switches to one-card-per-page image mode while keeping page navigation
- View is paginated with four buttons: `First Page`, `Previous Page`, `Next Page`, `Last Page`

## Lookup UX

- `lookup` accepts a base `card_id`, an exact dupe `card_code`, or a name/series query
- If input exactly matches an existing `card_code`, show dupe-card output (`Code`, `G-####`, and computed `Value`)
- If no exact dupe code is found, fall back to base card lookup behavior (`card_id` match, then name/series search)
- Entries include wishlist counts regardless of selected sort mode

## Info UX

Shows:
- total cards
- dough
- total wishes
- married card instance display
- if married, show the married card image
- Optional player argument supports mention (e.g. `@Friend`) or exact username

## Cooldown UX

- `cooldown [player]` / `cd [player]` shows drop cooldown status for yourself or another player
- Uses **drop cooldown** terminology (not pull cooldown)

## Marriage UX

- `marry` with no argument targets the player's most recently pulled card instance
- `marry <card_code>` targets that exact owned dupe code
- card code format is standalone base36 (examples: `0`, `a`, `10`)
- `marry` success responses display the selected card image
- `divorce` success responses display the divorced card image

## Collection UX

- Render one line per owned card instance (no grouping)
- Keep duplicate copies visible as separate entries
- Include each dupe's `Code` (e.g. `0`, `a`, `10`)

## Interaction constraints

- Unauthorized users should get ephemeral embed errors
- Resolved interactions should reject repeated clicks
