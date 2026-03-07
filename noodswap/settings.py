from pathlib import Path
import os

DROP_COOLDOWN_SECONDS = 6 * 60
PULL_COOLDOWN_SECONDS = 4 * 60
VOTE_COOLDOWN_SECONDS = 24 * 60 * 60
STARTING_DOUGH = 0
STARTING_STARTER = 0
VOTE_STARTER_REWARD = 1
COMMAND_PREFIX = "ns "
SHORT_COMMAND_PREFIX = "n"
DROP_CHOICES_COUNT = 3
DROP_TIMEOUT_SECONDS = 45
TRADE_TIMEOUT_SECONDS = 90
BURN_CONFIRM_TIMEOUT_SECONDS = 30
GENERATION_MIN = 1
GENERATION_MAX = 2000
DB_PATH = Path(
	os.getenv(
		"NOODSWAP_DB_PATH",
		str(Path(__file__).resolve().parent.parent / "noodswap.db"),
	)
)
DB_LOCK_TIMEOUT_SECONDS = 5.0
CARD_IMAGE_CACHE_DIR = Path(__file__).resolve().parent.parent / "assets" / "card_images"
CARD_IMAGE_CACHE_MANIFEST = CARD_IMAGE_CACHE_DIR / "manifest.json"

# Card body height / width ratio used by the in-canvas renderer.
# 1.4 corresponds to a standard 5:7 (width:height) card body ratio.
CARD_BODY_ASPECT_RATIO = 1.4

PAGINATION_FIRST_EMOJI = "<:ns_left_double:1479310540554768485>"
PAGINATION_PREVIOUS_EMOJI = "<:ns_left_arrow:1479310649270997152>"
PAGINATION_NEXT_EMOJI = "<:ns_right_arrow:1479310677100200098>"
PAGINATION_LAST_EMOJI = "<:ns_right_double:1479310578202705951>"
