# Noodswap

Discord trading-card style bot using `discord.py`.

## Quick start

1. Create and activate a Python environment.
2. Install dependencies:
   ```bash
   uv sync
   ```
   For development checks (including `ruff`), install dev dependencies:
   ```bash
   uv sync --group dev
   ```
3. Set your token (never commit secrets):
   - Local dev:
   ```bash
   export DISCORD_TOKEN=your-token
   ```
   - Optional top.gg vote verification and rewards:
   ```bash
   export TOPGG_WEBHOOK_SECRET=your-topgg-webhook-secret
   export TOPGG_BOT_ID=your-discord-bot-id
   ```
   `TOPGG_WEBHOOK_SECRET` must match the Authorization value configured in your bot's webhook settings on top.gg. `TOPGG_BOT_ID` is optional and only used if the bot id cannot be resolved at runtime for the vote-link URL.
   - Production (recommended): inject secret from your platform secret manager as either `DISCORD_TOKEN` or a mounted file path in `DISCORD_TOKEN_FILE`.
4. Initialize local runtime state:
   ```bash
   uv run python scripts/init_runtime.py
   ```
5. Run:
   ```bash
   uv run python -m bot.main
   ```

## Deployment (Docker + GitHub Actions)

### What is included

- CI: `.github/workflows/ci.yml` runs `ruff`, compile, migration smoke, and unit tests on push/PR.
- CD image publish: `.github/workflows/cd.yml` builds and pushes GHCR images after CI passes on `main`.
- Host deploy: `.github/workflows/deploy.yml` runs on GitHub-hosted runners and deploys to Ubuntu over SSH, pinned to commit SHA image tags.

### Local Docker smoke test

```bash
docker build -t noodswap:local .
docker run --rm -e DISCORD_TOKEN=your-token noodswap:local
```

### Server setup (one time)

Use a deploy path such as `/home/noodswap-user/noodswap` owned by a dedicated Linux user named `noodswap-user`.

```bash
sudo useradd --system --create-home --home-dir /home/noodswap-user --shell /usr/sbin/nologin noodswap-user
sudo -u noodswap-user mkdir -p /home/noodswap-user/noodswap
sudo -u noodswap-user bash -lc 'cd /home/noodswap-user/bot/deploy && cp .env.example .env && cp runtime.env.example runtime.env && mkdir -p ../runtime/db ../runtime/card_images ../runtime/logs'
```

Set required values:

- `deploy/.env`: `IMAGE_REPOSITORY=ghcr.io/tehbrian/noodswap`
- `deploy/runtime.env`: `DISCORD_TOKEN=<your-token>` (raw token only, no quotes)

If startup fails with `401 Unauthorized` / `Improper token has been passed`, verify `deploy/runtime.env` contains a current bot token with no surrounding quotes and no extra whitespace.

Optional runtime values:

- `TOPGG_WEBHOOK_SECRET`
- `TOPGG_BOT_ID`

### Manual deploy/update

```bash
sudo -u noodswap-user bash -lc 'cd /home/noodswap-user/noodswap && ./deploy/update.sh'
```

### GitHub Actions deploy minimum setup

- Add required repository secrets for SSH deploy:
   - `DEPLOY_HOST`
   - `DEPLOY_SSH_USER`
   - `DEPLOY_SSH_PRIVATE_KEY`
   - `DEPLOY_SSH_KNOWN_HOSTS`
-   - `DEPLOY_SSH_PORT`
- Add required Actions variables:
   - `DEPLOY_PATH=/home/noodswap-user/noodswap`
   - `DEPLOY_AS_USER=noodswap-user`
   - `DEPLOY_IMAGE_REPOSITORY=ghcr.io/tehbrian/noodswap`
- Add required Actions secrets for GHCR reads:
   - `GHCR_READONLY_USERNAME`
   - `GHCR_READONLY_TOKEN`

Behavior notes:

- Deploy resolves target SHA and deploys `IMAGE_REPOSITORY:<that-sha>`.
- The workflow waits for that exact GHCR tag to become available before running the deploy step, avoiding stale `latest` races.
- After deploy, workflow verifies `noodswap-bot` is running and that its configured image exactly equals `IMAGE_REPOSITORY:<that-sha>`.
- `deploy/update.sh` now performs a runtime writability preflight and fails before container startup if `runtime/{db,card_images,logs}` is not writable.
- Production compose includes a SQLite healthcheck (`PRAGMA quick_check`) against `runtime/db/bot.db`.

Full Actions deploy instructions: `docs/deploy-github-actions.md`.

### Persistence notes

- SQLite DB: `runtime/db/bot.db`
- Cached card images: `runtime/card_images`
- Seed fixtures live under `assets/` and can initialize fresh runtime directories.
- Immutable render assets (fonts, frames) live under `assets/` and are baked into the image.
- Deploys run from GitHub-hosted runners to Ubuntu via SSH
- Deploy/update does not transfer DB contents between machines/paths; it reuses whatever already exists under `runtime/` on the target host.

### Discord developer portal requirements

This bot uses privileged intents. Enable these for your application in Discord Developer Portal:

- Message Content Intent
- Server Members Intent

## Commands (prefixes: `ns ` and short `n`, both case-insensitive)

- `ns info [player]` / `ns i [player]` — show your info or another player's info (mention/username).
- `ns leaderboard` / `ns le` — show a paginated player leaderboard with criteria dropdown (`cards`, `wishes`, `dough`, `starter`, `collection value`).
- `ns collection [player]` / `ns c [player]` — show your collection or another player's collection with interactive sorting and gallery toggle (defaults to yourself).
- `ns dupes [player]` / `ns ds [player]` — show only duplicated card instances from a collection, with the same sorting as collection plus generation and actual value.
- `ns cards` / `ns ca` — show all available cards with interactive sorting (wishes, rarity, series, base value, alphabetical; default alphabetical), plus a gallery toggle for one-card image mode.
- `ns lookup <card_id|card_code|query>` / `ns l <card_id|card_code|query>` — show base card details, or exact dupe details when a card code is provided.
- `ns lookuphd <card_id|card_code|query>` / `ns lhd <card_id|card_code|query>` — same as lookup, but renders the card image at `1000x1400`.
- `ns help` / `ns h` — show command help.
- `ns drop` / `ns d` — open a drop with 3 random cards; anyone can claim unclaimed cards via buttons. If drop cooldown is active, one `drop ticket` is auto-consumed instead.
- `ns buy drop [quantity]` — buy drop tickets using `starter` (cost: 1 starter per ticket; default quantity is 1).
- `ns slots` / `ns sl` — spin 3 food reels; 2 matches award 200-400 dough, and 3 matches award 800-1200 dough plus 1-3 `starter`.
- `ns flip <stake>` / `ns f <stake>` — coin flip wager with 46% win / 54% lose odds; heads wins `+stake`, tails loses `-stake` (2m cooldown).
- `ns vote` / `ns v` — open the top.gg vote page; rewards are registered automatically when top.gg sends the webhook event.
- `ns cooldown [player]` / `ns cd [player]` — show drop (6m), pull (4m), flip (2m), slots (22m), and monopoly (11m) cooldowns for yourself or another player.
- `ns burn [targets...]` / `ns b [targets...]` — burn one or more targets for dough. Supports card codes/IDs plus selectors `t:<tag_name>` and `f:<folder_name>`. If any selected card is in a locked tag or locked folder, the entire burn is blocked.
- `ns gift dough <player> <dough>` / `ns gift d <player> <dough>` — send dough directly to another player.
- `ns gift starter <player> <starter>` / `ns gift s <player> <starter>` — send starter directly to another player.
- `ns gift drop <player> <tickets>` — send drop tickets directly to another player.
- `ns gift card <player> <card_code>` / `ns gift c <player> <card_code>` — send one owned card copy directly to another player.
- `ns morph [card_code]` / `ns mo [card_code]` — pay 20% of card value (rounded up) to apply a random morph; currently supports `black_and_white`.
- `ns frame [card_code]` / `ns fr [card_code]` — pay 20% of card value (rounded up) to apply a random frame from available frames (`buttery`, `gilded`, `drizzled`) in `assets/frames/`.
- `ns font [card_code]` / `ns fo [card_code]` — pay 20% of card value (rounded up) to apply a random font (`serif`, `mono`, `storybook`, `spooky`, `pixel`, `playful`). `Classic` is now the default baseline style (not a trait modifier).
- `ns trade <player> <card_code> <mode> <amount|req_card_code>` / `ns t ...` — offer a dupe trade; mode selects payment type (`dough`, `starter`, `drop` (aliases: `ticket`/`tickets`/`drop_tickets`), or `card` for card-swap).
- `ns team` / `ns tm` — team command group.
- `ns team add <team_name>` / `ns team a <team_name>` — create a team (max 32 chars, normalized lowercase).
- `ns team remove <team_name>` / `ns team r <team_name>` — delete one of your teams.
- `ns team list` / `ns team l` — list your teams and card counts.
- `ns team assign <team_name> <card_code>` / `ns team as ...` — assign one owned card instance to a team.
- `ns team unassign <team_name> <card_code>` / `ns team u ...` — remove a card instance from a team.
- `ns team cards <team_name>` / `ns team c <team_name>` — view a team's cards.
- `ns team active [team_name]` — show current active team, or set one for battles.
- `ns battle <player> <stake>` / `ns bt ...` — propose a stake battle; challenged player can accept or deny.
- `ns wish` / `ns w` — wishlist command group.
- `ns wish add <card_id>` / `ns wish a <card_id>` / `ns w add <card_id>` / `ns w a <card_id>` / `ns wa <card_id>` — add a card to your wishlist.
- `ns wish remove <card_id>` / `ns wish r <card_id>` / `ns w remove <card_id>` / `ns w r <card_id>` / `ns wr <card_id>` — remove a card from your wishlist.
- `ns wish list [player]` / `ns wish l [player]` / `ns w list [player]` / `ns w l [player]` / `ns wl [player]` — show a wishlist (defaults to yourself).
- `ns tag` / `ns tg` — tag command group.
- `ns tag add <tag_name>` / `ns tag a <tag_name>` — create a personal tag collection.
- `ns tag remove <tag_name>` / `ns tag r <tag_name>` — delete one of your tags.
- `ns tag list` / `ns tag l` — list your tags, lock status, and card counts.
- `ns tag lock <tag_name>` / `ns tag unlock <tag_name>` — toggle burn protection for that tag.
- `ns tag assign <tag_name> <card_code>` / `ns tag as ...` — tag one of your owned dupes.
- `ns tag unassign <tag_name> <card_code>` / `ns tag u ...` — remove a card from a tag.
- `ns tag cards <tag_name>` / `ns tag c <tag_name>` — list cards in a specific tag.
- `ns folder` / `ns fd` — folder command group.
- `ns folder add <folder_name> [emoji]` / `ns folder a ...` — create a personal folder with optional emoji (default `📁`).
- `ns folder remove <folder_name>` / `ns folder r ...` — delete one of your folders.
- `ns folder list` / `ns folder l` — list your folders, emoji, lock status, and card counts.
- `ns folder lock <folder_name>` / `ns folder unlock <folder_name>` — toggle burn protection for that folder.
- `ns folder assign <folder_name> <card_code>` / `ns folder as ...` — place one owned card instance into a folder (moves it if it already had one).
- `ns folder unassign <folder_name> <card_code>` / `ns folder u ...` — remove a card from that folder.
- `ns folder cards <folder_name>` / `ns folder c <folder_name>` — list cards in a specific folder.
- `ns folder emoji <folder_name> <emoji>` / `ns folder e ...` — update a folder's emoji.
- `ns marry [card_code]` / `ns m [card_code]` — marry a specific owned dupe by code.
- `ns divorce` / `ns dv` — divorce your currently married card.

### Owner-only admin commands

- `ns dbexport` — upload the SQLite file (`bot.db`) to Discord.
- `ns dbreset` — delete all persisted player/card data.

### Optional: runtime asset initialization

Card rendering is local-only and expects runtime assets under `runtime/`.

- Local development: run `uv run python scripts/init_runtime.py` to replace `runtime/card_images/`, `runtime/fonts/`, and `runtime/frames/` from `assets/` seeds.
- Production deploy: `deploy/update.sh` seeds `runtime/card_images/` from `assets/card_images/` when the runtime image directory is empty.

The local image manifest lives at `runtime/card_images/manifest.json`.

### Optional: generation economy report

To compare your target inverse-value generation odds (`tau`) against the live inventory snapshot:

```bash
uv run python scripts/generation_economy_report.py --tau 1.0 --active-days 7
```

Machine-readable output is available with `--json`.

## Notes / current limitations

- Data is persisted in local SQLite (`runtime/db/bot.db`) by default.
- `.env` files are gitignored; keep real tokens only in untracked local env files or deployment secret managers.
- No anti-abuse logging or sharding yet.
- Alias conflict in the original spec (`d` for both `drop` and `divorce`) is resolved as:
  - `d` for `drop`
  - `dv` for `divorce`
- Card catalog is a constant dict in code for now, including `series` values (`noodle`, `grain`, `ingredient`, `cheese`, `wine`, `bread`, `entree`, `dessert`).
- Card ownership is instance-based: each acquired card gets a generated `G-####` value (1-2000), where lower generations are rarer.
- Generation rolls are sampled with a right-skewed beta distribution (`betavariate(1.6, 1.04)`) scaled to the 1-2000 range, making low-generation pulls ~1 in 48k while maintaining a stable median around 1270.
- Drop buttons use card names for readability.
- Each drop card can only be claimed once; claimed cards are locked to their claimant.
- Drop preview generation prefers locally cached images when available.
- User-facing dupe actions (`burn`, `marry`, `trade`) accept standalone card `Code` (e.g. `0`, `a`, `10`, `#10`) and target that exact copy.
- Catalog `ID` (e.g. `SPG`) is internal/base-card identity used in storage/catalog logic.
- **DUPE CARDS have CODES. BASE CARDS have IDS.**
- Player state is global across all guilds: inventories, dough, marriages, and wishlist are shared across every server where the bot is installed.
- `starter` is a higher-tier currency earned from verified top.gg votes.
- `drop tickets` are a consumable currency that bypasses `drop` cooldown when used automatically.
- `burn` includes an explicit confirm/cancel interaction before destruction.
- Team capacity is capped at 3 cards per team, and battles consume each player's active team.
- Battles are turn-based (`Attack`, `Defend`, `Switch`, `Surrender`) and include miss chance, effectiveness multipliers by series, and roll variance.

## Architecture

- `bot/main.py` — thin launcher.
- `bot/app.py` — bot creation, intents, startup wiring.
- `bot/commands.py` — Discord command handlers (presentation layer).
- `bot/views/` — interactive button views for drops/trades and pagination helpers.
- `bot/presentation.py` — shared embed styling helpers.
- `bot/storage.py` — SQLite persistence functions (domain/data layer).
- `bot/cards/` — card catalog and card-related logic.
- `bot/rarities.py` — rarity weights.
- `bot/settings.py` — global config constants.
- `bot/utils.py` — shared utility helpers.

## Future work (important)

- Expand DB migration/versioning support (currently startup version table + step migrations only).
- Add stronger locking/transaction strategy for high-concurrency workloads.
- Migrate to slash commands/app commands while keeping prefix aliases if desired.
- Add anti-abuse checks (alt farming, suspicious transfer patterns).
- Add paginated collection views and richer card metadata/assets.
- Automate runtime state operations for production deploys: scheduled SQLite backups to remote storage, restore-on-empty bootstrap for `runtime/db/bot.db`, and first-run card-image cache bootstrap from a published artifact.
