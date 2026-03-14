from pathlib import Path
import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(values)


DROP_COOLDOWN_SECONDS = 6 * 60
PULL_COOLDOWN_SECONDS = 2 * 60 + 30
SLOTS_COOLDOWN_SECONDS = 11 * 60
FLIP_COOLDOWN_SECONDS = 15
FLIP_WIN_PROBABILITY = 0.46
FLIP_WIN_PAYOUT_MULTIPLIER_NUMERATOR = 7
FLIP_WIN_PAYOUT_MULTIPLIER_DENOMINATOR = 10
FLIP_LOSS_POT_CONTRIBUTION_NUMERATOR = 15
FLIP_LOSS_POT_CONTRIBUTION_DENOMINATOR = 100
MONOPOLY_ROLL_COOLDOWN_SECONDS = 3 * 60 + 30
MONOPOLY_BOARD_SIZE = 40
MONOPOLY_GO_REWARD_DOUGH = 2000
MONOPOLY_TOMATO_TAX_PERCENT = 7
MONOPOLY_TRUFFLE_TAX_PERCENT = 16
MONOPOLY_JAIL_FINE_DOUGH = 1200
MONOPOLY_JAIL_FINE_POT_CONTRIBUTION_NUMERATOR = 5
MONOPOLY_JAIL_FINE_POT_CONTRIBUTION_DENOMINATOR = 10
MONOPOLY_TAX_POT_CONTRIBUTION_NUMERATOR = 2
MONOPOLY_TAX_POT_CONTRIBUTION_DENOMINATOR = 10
MONOPOLY_NEGATIVE_CHANCE_POT_CONTRIBUTION_NUMERATOR = 4
MONOPOLY_NEGATIVE_CHANCE_POT_CONTRIBUTION_DENOMINATOR = 10
MONOPOLY_PROPERTY_RENT_PERCENT = 100
MONOPOLY_PROPERTY_CONVENIENCE_FEE_PERCENT = 13
MONOPOLY_PROPERTY_CONVENIENCE_FEE_POT_CONTRIBUTION_NUMERATOR = 1
MONOPOLY_PROPERTY_CONVENIENCE_FEE_POT_CONTRIBUTION_DENOMINATOR = 10
OVEN_TRANSACTION_FEE_NUMERATOR = 3
OVEN_TRANSACTION_FEE_DENOMINATOR = 100
OVEN_TRANSACTION_FEE_POT_CONTRIBUTION_NUMERATOR = 2
OVEN_TRANSACTION_FEE_POT_CONTRIBUTION_DENOMINATOR = 10
STARTING_DOUGH = 0
STARTING_STARTER = 0
VOTE_STARTER_REWARD = 3
COMMAND_PREFIX = "ns "
SHORT_COMMAND_PREFIX = "n"
DROP_CHOICES_COUNT = 3
DROP_TIMEOUT_SECONDS = 45
TRADE_TIMEOUT_SECONDS = 90
BATTLE_PROPOSAL_TIMEOUT_SECONDS = 60
BATTLE_TURN_TIMEOUT_SECONDS = 45
BURN_CONFIRM_TIMEOUT_SECONDS = 30
TRAIT_ROLL_TIMEOUT_SECONDS = 120
TEAM_MAX_CARDS = 3
GENERATION_MIN = 1
GENERATION_MAX = 2000
DB_LOCK_TIMEOUT_SECONDS = 5.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


RUNTIME_DIR = _resolve_path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "runtime")))
DB_PATH = _resolve_path(os.getenv("SQLITE_PATH", str(RUNTIME_DIR / "db" / "noodswap.db")))
CARD_IMAGE_DIR = _resolve_path(os.getenv("IMAGE_DIR", str(RUNTIME_DIR / "card_images")))
CARD_IMAGE_MANIFEST = CARD_IMAGE_DIR / "manifest.json"
CARD_FONTS_DIR = _resolve_path(os.getenv("FONTS_DIR", str(RUNTIME_DIR / "fonts")))
FRAMES_DIR = _resolve_path(os.getenv("FRAMES_DIR", str(RUNTIME_DIR / "frames")))

TOPGG_WEBHOOK_SECRET = os.getenv("TOPGG_WEBHOOK_SECRET", "").strip()
TOPGG_BOT_ID = os.getenv("TOPGG_BOT_ID", "").strip()
TOPGG_WEBHOOK_HOST = os.getenv("TOPGG_WEBHOOK_HOST", "0.0.0.0").strip() or "0.0.0.0"
TOPGG_WEBHOOK_PORT = _env_int("TOPGG_WEBHOOK_PORT", 8080)
TOPGG_WEBHOOK_PATH = os.getenv("TOPGG_WEBHOOK_PATH", "/noodswap/topgg-vote-webhook").strip()
TOPGG_WEBHOOK_MAX_BODY_BYTES = _env_int("TOPGG_WEBHOOK_MAX_BODY_BYTES", 16 * 1024)
TOPGG_WEBHOOK_REQUIRE_JSON_CONTENT_TYPE = _env_bool("TOPGG_WEBHOOK_REQUIRE_JSON_CONTENT_TYPE", True)
TOPGG_WEBHOOK_ALLOWED_IPS = _env_csv("TOPGG_WEBHOOK_ALLOWED_IPS")

# Card body height / width ratio used by the in-canvas renderer.
# 1.4 corresponds to a standard 5:7 (width:height) card body ratio.
CARD_BODY_ASPECT_RATIO = 1.4

PAGINATION_FIRST_EMOJI = "<:ns_left_double:1479310540554768485>"
PAGINATION_PREVIOUS_EMOJI = "<:ns_left_arrow:1479310649270997152>"
PAGINATION_NEXT_EMOJI = "<:ns_right_arrow:1479310677100200098>"
PAGINATION_LAST_EMOJI = "<:ns_right_double:1479310578202705951>"
