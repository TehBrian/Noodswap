# Noodswap

Discord trading-card style bot using `discord.py`.

## Quick start

1. Create and activate a Python environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your token (never commit secrets):
   - Local dev:
   ```bash
   export DISCORD_TOKEN=your-token
   ```
   - Optional top.gg vote verification and rewards:
   ```bash
   export TOPGG_API_TOKEN=your-topgg-api-token
   export TOPGG_BOT_ID=your-discord-bot-id
   ```
   `TOPGG_API_TOKEN` is required for vote verification (`top.gg` API v1). `TOPGG_BOT_ID` is optional and only used if the bot id cannot be resolved at runtime for the vote-link URL.
   - Production (recommended): inject secret from your platform secret manager as either `DISCORD_TOKEN` or a mounted file path in `DISCORD_TOKEN_FILE`.
4. Run:
   ```bash
   python bot.py
   ```

## Deployment (Docker + GitHub Actions)

### What is included

- CI: `.github/workflows/ci.yml` runs compile, migration smoke, and unit tests on push/PR.
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
sudo -u noodswap-user bash -lc 'cd /home/noodswap-user/noodswap/deploy && cp .env.example .env && cp runtime.env.example runtime.env && mkdir -p assets/card_images assets/fonts'
```

Set required values:

- `deploy/.env`: `IMAGE_REPOSITORY=ghcr.io/tehbrian/noodswap`
- `deploy/runtime.env`: `DISCORD_TOKEN=<your-token>` (raw token only, no quotes)

If startup fails with `401 Unauthorized` / `Improper token has been passed`, verify `deploy/runtime.env` contains a current bot token with no surrounding quotes and no extra whitespace.

Optional runtime values:

- `TOPGG_API_TOKEN`
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

Full Actions deploy instructions: `docs/deploy-github-actions.md`.

### Persistence notes

- SQLite DB: `deploy/assets/noodswap.db`
- Cached card images: `deploy/assets/card_images`
- Deploys run from GitHub-hosted runners to Ubuntu via SSH
- Deploy/update does not transfer DB contents between machines/paths; it reuses whatever already exists at `deploy/assets/noodswap.db` on the target host.

### Upgrade note: legacy `deploy/data` installs

If your host still has runtime state in `deploy/data`, run this once before deploy:

```bash
cd deploy
mkdir -p assets
if [ -d data ] && [ ! -e assets/.migrated-from-data ]; then
   cp -an data/. assets/
   touch assets/.migrated-from-data
fi
```

`deploy/update.sh` also includes a legacy fallback migration path for older layouts.

### Discord developer portal requirements

This bot uses privileged intents. Enable these for your application in Discord Developer Portal:

- Message Content Intent
- Server Members Intent

## Commands (prefixes: `ns ` and short `n`, both case-insensitive)

- `ns info [player]` / `ns i [player]` — show your stats or another player's stats (mention/username).
- `ns leaderboard` / `ns le` — show a paginated player leaderboard with criteria dropdown (`cards`, `wishes`, `dough`, `starter`, `collection value`).
- `ns collection [player]` / `ns c [player]` — show your collection or another player's collection with interactive sorting and gallery toggle (defaults to yourself).
- `ns cards` / `ns ca` — show all available cards with interactive sorting (wishes, rarity, series, base value, alphabetical; default alphabetical), plus a gallery toggle for one-card image mode.
- `ns lookup <card_id|card_code|query>` / `ns l <card_id|card_code|query>` — show base card details, or exact dupe details when a card code is provided.
- `ns lookuphd <card_id|card_code|query>` / `ns lhd <card_id|card_code|query>` — same as lookup, but renders the card image at `1000x1400`.
- `ns help` / `ns h` — show command help.
- `ns drop` / `ns d` — open a drop with 3 random cards; anyone can claim unclaimed cards via buttons.
- `ns vote` / `ns v` — open the top.gg vote page and claim `starter` reward when your vote is detected.
- `ns cooldown [player]` / `ns cd [player]` — show drop (6m), pull (4m), and vote reward (24h) cooldowns for yourself or another player.
- `ns burn [card_code]` / `ns b [card_code]` — burn a specific dupe for dough (randomized around base). If omitted, defaults to your most recently pulled card. Burn is blocked for cards in locked tags.
- `ns morph [card_code]` / `ns mo [card_code]` — pay 20% of card value (rounded up) to apply a random visual morph; currently supports `black_and_white`.
- `ns frame [card_code]` / `ns fr [card_code]` — pay 20% of card value (rounded up) to apply a random cosmetic frame from available overlays (`buttery`, `gilded`, `drizzled`) in `deploy/assets/frame_overlays/`.
- `ns font [card_code]` / `ns fo [card_code]` — pay 20% of card value (rounded up) to apply a random cosmetic font (`serif`, `mono`, `storybook`, `spooky`, `pixel`, `playful`). `Classic` is now the default baseline style (not a modifier).
- `ns trade <player> <card_code> <amount>` / `ns t ...` — offer a specific dupe-for-dough trade.
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
- `ns marry [card_code]` / `ns m [card_code]` — marry a specific owned dupe by code.
- `ns divorce` / `ns dv` — divorce your currently married card.

### Owner-only admin commands

- `ns dbexport` — upload the SQLite file (`noodswap.db`) to Discord.
- `ns dbreset` — delete all persisted player/card data.

### Optional: local card image cache (recommended)

Drop preview image composition uses a lazy cache at runtime:

- If an image exists in `deploy/assets/card_images/manifest.json`, it uses local bytes.
- If missing, it fetches once from the source URL, saves it to `deploy/assets/card_images/`, updates the manifest, and reuses local cache on later drops.

You can also pre-warm the full cache in advance to avoid first-hit fetches:

```bash
.venv/bin/python scripts/cache_card_images.py
```

This writes files into `deploy/assets/card_images/` and a manifest at `deploy/assets/card_images/manifest.json`.

### Optional: generation economy report

To compare your target inverse-value generation odds (`tau`) against the live inventory snapshot:

```bash
.venv/bin/python scripts/generation_economy_report.py --tau 1.0 --active-days 7
```

Machine-readable output is available with `--json`.

## Notes / current limitations

- Data is persisted in local SQLite (`deploy/assets/noodswap.db`) by default.
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
- `burn` includes an explicit confirm/cancel interaction before destruction.

## Architecture

- `bot.py` — thin launcher.
- `noodswap/app.py` — bot creation, intents, startup wiring.
- `noodswap/commands.py` — Discord command handlers (presentation layer).
- `noodswap/views.py` — interactive button views for drops/trades.
- `noodswap/presentation.py` — shared embed styling helpers.
- `noodswap/storage.py` — SQLite persistence functions (domain/data layer).
- `noodswap/cards.py` — card catalog and card-related logic.
- `noodswap/rarities.py` — rarity weights.
- `noodswap/settings.py` — global config constants.
- `noodswap/utils.py` — shared utility helpers.

## Future work (important)

- Expand DB migration/versioning support (currently startup version table + step migrations only).
- Add stronger locking/transaction strategy for high-concurrency workloads.
- Migrate to slash commands/app commands while keeping prefix aliases if desired.
- Add anti-abuse checks (alt farming, suspicious transfer patterns).
- Add paginated collection views and richer card metadata/assets.
- Automate runtime state operations for production deploys: scheduled SQLite backups to remote storage, restore-on-empty bootstrap for `deploy/assets/noodswap.db`, and first-run card-image cache bootstrap from a published artifact.
