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
- `morph [card_code]` / `mo [card_code]`
- `frame [card_code]` / `fr [card_code]`
- `font [card_code]` / `fo [card_code]`
- `trade <player> <card_code> <amount>` / `t ...`
- `wish` / `w`
- `wish add <card_id>` / `wish a <card_id>` / `w add <card_id>` / `w a <card_id>` / `wa <card_id>`
- `wish remove <card_id>` / `wish r <card_id>` / `w remove <card_id>` / `w r <card_id>` / `wr <card_id>`
- `wish list [player]` / `wish l [player]` / `w list [player]` / `w l [player]` / `wl [player]`
- `marry [card_code]` / `m [card_code]`
- `divorce` / `dv`
- owner-only: `dbexport`, `dbreset`

## Help UX

- `help` / `h` opens a brief bot overview embed instead of a full command dump
- Help embed includes a category dropdown for command pages
- Categories are: `Overview`, `Economy`, `Cosmetics`, `Wishlist`, `Tags`, `Relationship`, `Owner-only`
- Selecting a category edits the same message to show that category's commands
- Help dropdown interactions are restricted to the command invoker

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

## Card image presentation

- Wherever a card image is shown (single-card embeds and drop previews), render through the shared card-image pipeline in `noodswap/images.py`.
- Per-instance morph state (`card_instances.morph_key`) must be applied when rendering owned-instance images.
- Per-instance frame state (`card_instances.frame_key`) must be applied when rendering owned-instance images.
- Per-instance font state (`card_instances.font_key`) must be applied when rendering owned-instance images.
- Initial morph behavior: `black_and_white` converts card art to grayscale while preserving existing overlay text and rarity border treatment.
- Supported frame keys are `buttery`, `gilded`, and `drizzled`.
- All three frame overlays are currently bundled.
- `gilded` and `drizzled` are temporary placeholders until distinct overlay art is added.
- `Classic` is the default baseline style and is not a cosmetic modifier.
- Initial selectable font set includes `serif`, `mono`, `storybook`, `spooky`, `pixel`, and `playful`.
- Frame overlays are loaded from `assets/frame_overlays/<frame_key>.png` (or `.webp`) and composited over the rendered card.
- Rendered card frame is normalized to a portrait `2.5:3.5` aspect ratio (`5:7`).
- Cards use a rounded outer frame and rounded inner art window.
- Border color is rarity-driven:
  - `common`: brown
  - `uncommon`: gray
  - `rare`: light purple
  - `epic`: orange
  - `legendary`: light blue
  - `mythic`: dark purple
  - `divine`: yellow
  - `celestial`: bright near-white blue

## Drop UX

- Shows 3 random offers
- Each offer line format is: `**CARD_NAME** • (ID: CARD_ID) [Series] (Rarity) • **G-####** (Base: **N** dough)`
- Drop response is a single embed with one combined preview image showing all 3 offered cards
- Buttons are labeled with **card names** (not IDs)
- Any player can claim any unclaimed card from the drop
- Each card button can be claimed only once; once claimed, that button is disabled
- A drop remains active until timeout or until all cards are claimed
- Each successful claim posts a separate pulled-card embed
- On timeout, buttons are disabled and a separate expiry embed is posted

## Burn UX

Burn flow:

- `burn` with no argument targets the player's most recently pulled card instance
- `burn <card_code>` targets that exact dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
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

## Morph UX

- `morph` with no argument targets the player's most recently pulled card instance
- `morph <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- morph selection is random from available morphs
- morph cost is `20%` of the target card's computed value (`card_value`), rounded up to the nearest whole dough
- if a card already has the rolled morph, the command returns an error and does not charge dough
- morph now uses a confirmation step: initial response shows `before -> after` preview and cost, and only `Confirm Morph` applies the change
- successful morph confirmations display the same `before -> after` image and show cost + remaining dough

## Frame UX

- `frame` with no argument targets the player's most recently pulled card instance
- `frame <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- frame selection is random from available frames
- frame cost is `20%` of the target card's computed value (`card_value`), rounded up to the nearest whole dough
- if a card already has the rolled frame, the command returns an error and does not charge dough
- frame uses a confirmation step: initial response shows `before -> after` preview and cost, and only `Confirm Frame` applies the change
- successful frame confirmations display the same `before -> after` image and show cost + remaining dough

## Font UX

- `font` with no argument targets the player's most recently pulled card instance
- `font <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- font selection is random from available fonts
- font cost is `20%` of the target card's computed value (`card_value`), rounded up to the nearest whole dough
- if a card already has the rolled font, the command returns an error and does not charge dough
- font uses a confirmation step: initial response shows `before -> after` preview and cost, and only `Confirm Font` applies the change
- successful font confirmations display the same `before -> after` image and show cost + remaining dough

Card identity terms:

- `ID` means base catalog card identity (internal/base concept)
- `Code` means a specific owned dupe reference (user-facing, e.g. `0`, `a`, `10`, `#10`)
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

- `cooldown [player]` / `cd [player]` shows both drop and pull cooldown status for yourself or another player
- Drop cooldown is 6 minutes and applies to `ns drop`
- Pull cooldown is 4 minutes and applies to claiming cards from drops
- Embed title format is `{Player}'s Cooldowns`

## Marriage UX

- `marry` with no argument targets the player's most recently pulled card instance
- `marry <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- `marry` success responses display the selected card image
- `divorce` success responses display the divorced card image

## Collection UX

- Render one line per owned card instance (no grouping)
- Keep duplicate copies visible as separate entries
- Include each dupe's `Code` (e.g. `0`, `a`, `10`, `#10`)
- Includes a sort dropdown with modes: `Wishes`, `Rarity`, `Series`, `Base Value`, `Alphabetical`
- Default sort mode is `Alphabetical`
- Includes a `Gallery` toggle that switches to one-card-per-page image mode while keeping page navigation

## Interaction constraints

- Unauthorized users should get ephemeral embed errors
- Resolved interactions should reject repeated clicks
