# Commands and UX

This document defines behavior and presentation for commands and interaction flows.

## Prefix

- Prefix: `ns `

## Command list

- `info [player]` / `i [player]`
- `leaderboard` / `le`
- `collection [player]` / `c [player]`
- `cards` / `ca`
- `lookup <card_id|card_code|query>` / `l <card_id|card_code|query>`
- `lookuphd <card_id|card_code|query>` / `lhd <card_id|card_code|query>`
- `help` / `h`
- `drop` / `d`
- `slots` / `sl`
- `flip <stake> [heads|tails]` / `f <stake> [heads|tails]`
- `vote` / `v`
- `cooldown [player]` / `cd [player]`
- `burn [targets...]` / `b [targets...]`
- `gift` / `g`
- `gift dough <player> <dough>` / `gift d <player> <dough>`
- `gift starter <player> <starter>` / `gift s <player> <starter>`
- `gift drop <player> <tickets>`
- `gift card <player> <card_code>` / `gift c <player> <card_code>`
- `morph [card_code]` / `mo [card_code]`
- `frame [card_code]` / `fr [card_code]`
- `font [card_code]` / `fo [card_code]`
- `trade <player> <card_code> <mode> <amount|req_card_code>` / `t ...`
- `team` / `tm`
- `team add <team_name>` / `team a <team_name>`
- `team remove <team_name>` / `team r <team_name>`
- `team list` / `team l`
- `team assign <team_name> <card_code>` / `team as ...`
- `team unassign <team_name> <card_code>` / `team u ...`
- `team cards <team_name>` / `team c <team_name>`
- `team active [team_name]`
- `folder` / `fd`
- `folder add <folder_name> [emoji]` / `folder a ...`
- `folder remove <folder_name>` / `folder r ...`
- `folder list` / `folder l`
- `folder lock <folder_name>` / `folder unlock <folder_name>`
- `folder assign <folder_name> <card_code>` / `folder as ...`
- `folder unassign <folder_name> <card_code>` / `folder u ...`
- `folder cards <folder_name>` / `folder c ...`
- `folder emoji <folder_name> <emoji>` / `folder e ...`
- `battle <player> <stake>` / `bt ...`
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
- Categories are: `Overview`, `Economy`, `Traits`, `Wishlist`, `Tags`, `Relationship`, `Owner-only`
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
- command syntax/parser errors (include both the concrete error reason and full command usage)
- cooldown messages
- interaction responses
- interaction timeout updates

## Card image presentation

- Wherever a card image is shown (single-card embeds and drop previews), render through the shared card-image pipeline in `noodswap/images.py`.
- Per-instance morph state (`card_instances.morph_key`) must be applied when rendering owned-instance images.
- Per-instance frame state (`card_instances.frame_key`) must be applied when rendering owned-instance images.
- Per-instance font state (`card_instances.font_key`) must be applied when rendering owned-instance images.
- Current morph set includes `black_and_white`, `inverse`, `tint_rose`, `tint_aqua`, `tint_lime`, `tint_warm`, `tint_cool`, `tint_violet`, and `upside_down`.
- Tint morphs blend the card art toward a target color, while `upside_down` rotates the rendered card art by 180 degrees.
- Supported frame keys are `buttery`, `gilded`, and `drizzled`.
- All three frames are currently bundled.
- `gilded` and `drizzled` are temporary placeholders until distinct frame art is added.
- `Classic` is the default baseline style and is not a trait modifier.
- Initial selectable font set includes `serif`, `mono`, `storybook`, `spooky`, `pixel`, and `playful`.
- Frames are loaded from `assets/frames/<frame_key>.png` (or `.webp`) by default and composited over the rendered card.
- Rendered card canvas is normalized to a portrait `2.5:3.5` aspect ratio (`5:7`).
- Default rendered card canvas is `350x490` (`5:7`) for lower processing cost.
- `lookuphd` renders at `1000x1400` (`5:7`) for high-detail output on demand.
- The in-canvas card body is rendered at `5:7` to match standard trading-card proportions while preserving border margin.
- Cards use a rounded outer border and rounded inner art window.
- Border color is rarity-driven:
  - `common`: white
  - `uncommon`: brown
  - `rare`: purple
  - `epic`: orange
  - `legendary`: red
  - `mythical`: green
  - `divine`: yellow
  - `celestial`: blue

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
- `burn` accepts one or many targets in the same command
- card targets can be provided as a card code (for an exact dupe) or as a base card id (burns the highest-generation owned copy)
- tag targets are provided as `t:<tag_name>`
- folder targets are provided as `f:<folder_name>`
- all selected targets are confirmed together and listed individually in the confirmation embed
- if any selected target is protected by locked tags or a locked folder, the full burn is blocked and no cards are burned
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

## Flip UX

- `flip <stake>` requires a positive integer stake
- `flip <stake> [heads|tails]` accepts an optional side call
- side call aliases `h`/`t` are accepted
- flip uses a 2-minute per-player cooldown
- outcome odds are fixed at 46% win (`Heads`) and 54% loss (`Tails`)
- on win, player gains `+stake` dough (net)
- on loss, player loses `-stake` dough (net)
- insufficient-dough responses should report stake and current balance
- flip responses use the standard `italy_embed` style
- successful flips use a delayed reveal: initial embed shows a randomized "coin is ..." suspense line, then edits to reveal the result after 3 seconds

## Gift UX

- `gift dough <player> <dough>` sends dough immediately
- `gift starter <player> <starter>` sends starter immediately
- `gift drop <player> <tickets>` sends drop tickets immediately
- `gift card <player> <card_code>` sends one owned card copy immediately
- player argument supports mention or exact username resolution
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- gifting to yourself is blocked
- gifting to bots is blocked
- sender must have enough balance for dough/starter/drop gifts
- sender must own the provided card code for card gifts
- gift response embed shows the gifted card image as a top-right thumbnail when available

## Morph UX

- `morph` with no argument targets the player's most recently pulled card instance
- `morph <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- morph selection is random from available morphs
- morph cost is `20%` of the target card's computed value (`card_value`), rounded up to the nearest whole dough
- morph uses a hidden-roll confirmation step: initial response shows current style and `before -> ?` preview, and only `Confirm Morph` rolls and applies the result
- successful morph confirmations reveal the rolled style and display the final `before -> after` image plus cost + remaining dough
- if no different morph outcome is available for that instance, preparation returns an error and no confirmation is shown
- morph confirmation timeout only disables buttons; the original confirmation embed is not replaced

## Frame UX

- `frame` with no argument targets the player's most recently pulled card instance
- `frame <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- frame selection is random from available frames
- frame cost is `20%` of the target card's computed value (`card_value`), rounded up to the nearest whole dough
- frame uses a hidden-roll confirmation step: initial response shows current style and `before -> ?` preview, and only `Confirm Frame` rolls and applies the result
- successful frame confirmations reveal the rolled style and display the final `before -> after` image plus cost + remaining dough
- if no different frame outcome is available for that instance, preparation returns an error and no confirmation is shown
- frame confirmation timeout only disables buttons; the original confirmation embed is not replaced

## Font UX

- `font` with no argument targets the player's most recently pulled card instance
- `font <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- font selection is random from available fonts
- font cost is `20%` of the target card's computed value (`card_value`), rounded up to the nearest whole dough
- font uses a hidden-roll confirmation step: initial response shows current style and `before -> ?` preview, and only `Confirm Font` rolls and applies the result
- successful font confirmations reveal the rolled style and display the final `before -> after` image plus cost + remaining dough
- if no different font outcome is available for that instance, preparation returns an error and no confirmation is shown
- font confirmation timeout only disables buttons; the original confirmation embed is not replaced

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
- Trade mode is the third argument and selects what the buyer pays:
  - `dough` — buyer pays dough (`ns trade @Player 0 dough 500`)
  - `starter` — buyer pays starter currency (`ns trade @Player 0 starter 10`)
  - `drop` — buyer pays drop tickets (`ns trade @Player 0 drop 2`)
    - Aliases: `ticket`, `tickets`, `drop_tickets`
  - `card` — card-for-card swap; buyer pays a specific dupe they own (`ns trade @Player 0 card #5`)
- For `card` mode, both users must own their respective card at accept time; either side losing ownership between offer and accept causes the trade to fail
- Card mode clears marriage and last-pulled state for swapped instances on both sides
- Invalid/unknown mode shows a validation error listing all valid modes

## Team UX

- Team names are normalized to lowercase and limited to 32 chars.
- Team membership is per-instance (uses card code ownership checks).
- Team capacity is limited to `3` cards.
- A player can have multiple teams.
- `team active <team_name>` sets the team used for battles.
- `team active` (without team name) shows the current active team.

## Battle UX

- `battle <player> <stake>` creates a proposal requiring challenged player accept/deny.
- Stake must be at least `1` dough.
- Both players must have an active team with at least one card.
- Both players must have enough dough for the stake at proposal and accept time.
- A player can only be in one pending/active battle at a time.
- Proposal timeout is `60` seconds.
- On acceptance, both players are charged the stake and battle state is initialized from active teams.
- Turn timeout is `45` seconds; timeout auto-skips the current turn.
- Turn actions: `Attack`, `Defend`, `Switch`, `Surrender`.
- `Switch` currently auto-selects the first available alive reserve card.
- Winner receives the full stake pot (`2x stake`).

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
- starter
- drop tickets
- total wishes
- married card instance display
- if married, show the married card image
- Optional player argument supports mention (e.g. `@Friend`) or exact username

## Drop Ticket UX

- `buy drop [quantity]` purchases drop tickets using `starter`
- Cost is `1 starter` per ticket
- Default quantity is `1`
- `drop` auto-consumes exactly `1` ticket when drop cooldown is active
- auto-ticket use bypasses drop cooldown for that attempt only and does not modify cooldown timestamps

## Leaderboard UX

- `leaderboard` / `le` shows a paginated leaderboard of players
- Includes criteria dropdown options: `Cards`, `Wishes`, `Dough`, `Starter`, `Collection Value`
- Each leaderboard row shows the selected criterion value for the ranked player
- Footer format: `Page X/Y • Ranked by <Criterion>`
- Leaderboard interactions are restricted to the command invoker

## Cooldown UX

- `cooldown [player]` / `cd [player]` shows drop, pull, slots, flip, and monopoly cooldown status for yourself or another player
- Drop cooldown is 6 minutes and applies to `ns drop`
- Pull cooldown is 4 minutes and applies to claiming cards from drops
- Slots cooldown is 22 minutes and applies to `ns slots`
- Flip cooldown is 2 minutes and applies to `ns flip`
- Monopoly cooldown is 11 minutes and applies to `ns monopoly roll`
- Embed title format is `{Player}'s Cooldowns`

## Slots UX

- `slots` / `s` spins 3 side-by-side food emoji reels in a single embed message
- Reels should animate via rapid embed edits before finalizing the result
- Matching exactly 2 reels rewards `dough` in the range `200..400`
- A jackpot requires all 3 reels to match the same emoji
- Jackpot rewards `800..1200` `dough` plus `starter` in the range `1..3`
- `slots` uses a 22-minute cooldown

## Vote UX

- `vote` / `v` sends an embed with top.gg voting info and a link button
- if top.gg API v1 verification is configured, running `vote` after voting attempts to claim `starter` immediately
- successful claim grants `starter`
- if no recent vote is detected by top.gg, command should instruct user to vote and retry
- if top.gg API config is missing, command still sends the vote link and a player-facing retry hint without deployment/config details

## Marriage UX

- `marry` with no argument targets the player's most recently pulled card instance
- `marry <card_code>` targets that exact owned dupe code
- card code format is standalone base36 with optional leading `#` (examples: `0`, `a`, `10`, `#10`)
- `marry` success responses display the selected card image
- `divorce` success responses display the divorced card image

## Collection UX

- Render one line per owned card instance (no grouping)
- Keep duplicate copies visible as separate entries
- Show folder emoji (if assigned) first, then lock marker next to instances protected by at least one locked tag or locked folder
- Include each dupe's `Code` (e.g. `0`, `a`, `10`, `#10`)
- Includes a sort dropdown with modes: `Generation`, `Wishes`, `Rarity`, `Series`, `Base Value`, `Actual Value`, `Alphabetical`
- Default sort mode is `Alphabetical`
- Includes a `Gallery` toggle that switches to one-card-per-page image mode while keeping page navigation

## Tags UX

- `tag cards <tag_name>` shows tagged card instances in a sortable, paginated embed
- Sort modes are: `Generation`, `Wishes`, `Rarity`, `Series`, `Base Value`, `Actual Value`, `Alphabetical`
- `Actual Value` uses per-instance computed card value (`card_value`), so generation differences affect order

## Folders UX

- Folder names are normalized to lowercase and limited to 32 chars.
- Folder emoji defaults to `📁` and can be changed with `folder emoji`.
- Folder assignment is per-instance and one-to-one (a card instance can belong to at most one folder).
- Assigning a card to a different folder moves it from its previous folder.
- Locked folders apply burn protection the same as locked tags.

## Interaction constraints

- Unauthorized users should get ephemeral embed errors
- Resolved interactions should reject repeated clicks
