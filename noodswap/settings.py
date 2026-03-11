from pathlib import Path
import os

DROP_COOLDOWN_SECONDS = 6 * 60
PULL_COOLDOWN_SECONDS = 45
VOTE_COOLDOWN_SECONDS = 24 * 60 * 60
SLOTS_COOLDOWN_SECONDS = 22 * 60
FLIP_COOLDOWN_SECONDS = 10
FLIP_WIN_PROBABILITY = 0.52
STARTING_DOUGH = 0
STARTING_STARTER = 0
VOTE_STARTER_REWARD = 1
COMMAND_PREFIX = "ns "
SHORT_COMMAND_PREFIX = "n"
DROP_CHOICES_COUNT = 3
DROP_TIMEOUT_SECONDS = 45
TRADE_TIMEOUT_SECONDS = 90
BATTLE_PROPOSAL_TIMEOUT_SECONDS = 60
BATTLE_TURN_TIMEOUT_SECONDS = 45
BURN_CONFIRM_TIMEOUT_SECONDS = 30
TEAM_MAX_CARDS = 3
GENERATION_MIN = 1
GENERATION_MAX = 2000
DB_LOCK_TIMEOUT_SECONDS = 5.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


RUNTIME_DIR = _resolve_path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "runtime")))
DB_PATH = _resolve_path(os.getenv("SQLITE_PATH", str(RUNTIME_DIR / "db" / "noodswap.db")))
CARD_IMAGE_DIR = _resolve_path(os.getenv("IMAGE_DIR", str(RUNTIME_DIR / "card_images")))
CARD_IMAGE_MANIFEST = CARD_IMAGE_DIR / "manifest.json"
CARD_FONTS_DIR = _resolve_path(os.getenv("FONTS_DIR", str(RUNTIME_DIR / "fonts")))
FRAME_OVERLAYS_DIR = _resolve_path(
    os.getenv("FRAME_OVERLAYS_DIR", str(RUNTIME_DIR / "frame_overlays"))
)
TOPGG_WEBHOOK_SECRET = os.getenv("TOPGG_WEBHOOK_SECRET", "").strip()
TOPGG_WEBHOOK_HOST = os.getenv("TOPGG_WEBHOOK_HOST", "0.0.0.0").strip() or "0.0.0.0"
TOPGG_WEBHOOK_PORT = int(os.getenv("TOPGG_WEBHOOK_PORT", "8080"))
TOPGG_WEBHOOK_PATH = os.getenv("TOPGG_WEBHOOK_PATH", "/noodswap/topgg-vote-webhook").strip() or "/noodswap/topgg-vote-webhook"
TOPGG_BOT_ID = os.getenv("TOPGG_BOT_ID", "").strip()
TOPGG_WEBHOOK_MAX_BODY_BYTES = max(1024, int(os.getenv("TOPGG_WEBHOOK_MAX_BODY_BYTES", "16384")))
TOPGG_WEBHOOK_REQUIRE_JSON_CONTENT_TYPE = _env_bool("TOPGG_WEBHOOK_REQUIRE_JSON_CONTENT_TYPE", True)
TOPGG_WEBHOOK_ALLOWED_IPS = tuple(
    part.strip() for part in os.getenv("TOPGG_WEBHOOK_ALLOWED_IPS", "").split(",") if part.strip()
)

# Card body height / width ratio used by the in-canvas renderer.
# 1.4 corresponds to a standard 5:7 (width:height) card body ratio.
CARD_BODY_ASPECT_RATIO = 1.4

PAGINATION_FIRST_EMOJI = "<:ns_left_double:1479310540554768485>"
PAGINATION_PREVIOUS_EMOJI = "<:ns_left_arrow:1479310649270997152>"
PAGINATION_NEXT_EMOJI = "<:ns_right_arrow:1479310677100200098>"
PAGINATION_LAST_EMOJI = "<:ns_right_double:1479310578202705951>"
