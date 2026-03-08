from pathlib import Path
import os

DROP_COOLDOWN_SECONDS = 6 * 60
PULL_COOLDOWN_SECONDS = 4 * 60
VOTE_COOLDOWN_SECONDS = 24 * 60 * 60
SLOTS_COOLDOWN_SECONDS = 22 * 60
FLIP_COOLDOWN_SECONDS = 2 * 60
FLIP_WIN_PROBABILITY = 0.46
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


RUNTIME_DIR = _resolve_path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "runtime")))
DB_PATH = _resolve_path(os.getenv("SQLITE_PATH", str(RUNTIME_DIR / "db" / "noodswap.db")))
CARD_IMAGE_DIR = _resolve_path(os.getenv("IMAGE_DIR", str(RUNTIME_DIR / "card_images")))
CARD_IMAGE_MANIFEST = CARD_IMAGE_DIR / "manifest.json"
CARD_FONTS_DIR = _resolve_path(os.getenv("FONTS_DIR", str(RUNTIME_DIR / "fonts")))
FRAME_OVERLAYS_DIR = _resolve_path(
    os.getenv("FRAME_OVERLAYS_DIR", str(RUNTIME_DIR / "frame_overlays"))
)

# Card body height / width ratio used by the in-canvas renderer.
# 1.4 corresponds to a standard 5:7 (width:height) card body ratio.
CARD_BODY_ASPECT_RATIO = 1.4

PAGINATION_FIRST_EMOJI = "<:ns_left_double:1479310540554768485>"
PAGINATION_PREVIOUS_EMOJI = "<:ns_left_arrow:1479310649270997152>"
PAGINATION_NEXT_EMOJI = "<:ns_right_arrow:1479310677100200098>"
PAGINATION_LAST_EMOJI = "<:ns_right_double:1479310578202705951>"
