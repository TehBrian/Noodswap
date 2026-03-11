from __future__ import annotations

from dataclasses import dataclass
import random

from .cards import CARD_CATALOG, random_card_id


RARITY_EPIC_OR_HIGHER = {"epic", "legendary", "mythical", "divine", "celestial"}


@dataclass(frozen=True)
class MonopolySpace:
    position: int
    name: str
    kind: str
    emoji: str
    rarity: str | None = None


@dataclass(frozen=True)
class MonopolyCard:
    text: str
    dough_delta: int = 0
    starter_delta: int = 0
    drop_tickets_delta: int = 0
    move_to: int | None = None
    go_to_jail: bool = False
    reset_random_cooldown: bool = False


# 8 rarities map to the 8 standard Monopoly color groups in low->high order.
RARITY_GROUP_ORDER = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "legendary",
    "mythical",
    "divine",
    "celestial",
)


BOARD_SPACES: tuple[MonopolySpace, ...] = (
    MonopolySpace(0, "GO", "go", "➡️"),
    MonopolySpace(1, "Truffle Alley", "property", "🟫", "common"),
    MonopolySpace(2, "Community Charcuterie", "community", "🧺"),
    MonopolySpace(3, "Bruschetta Block", "property", "🟫", "common"),
    MonopolySpace(4, "Cheese Tax", "tax", "💸"),
    MonopolySpace(5, "Panini Plaza", "property", "🟦", "uncommon"),
    MonopolySpace(6, "Gnocchi Gardens", "property", "🟦", "uncommon"),
    MonopolySpace(7, "Cheese Chance", "chance", "❓"),
    MonopolySpace(8, "Cannoli Court", "property", "🟦", "uncommon"),
    MonopolySpace(9, "Pesto Park", "property", "🩷", "rare"),
    MonopolySpace(10, "Mpreg Square", "mpreg", "🤰"),
    MonopolySpace(11, "Limoncello Lane", "property", "🩷", "rare"),
    MonopolySpace(12, "Polenta Point", "property", "🩷", "rare"),
    MonopolySpace(13, "Arrabbiata Avenue", "property", "🩷", "rare"),
    MonopolySpace(14, "Ravioli Row", "property", "🟧", "epic"),
    MonopolySpace(15, "Parm Pier", "property", "🟧", "epic"),
    MonopolySpace(16, "Cheese Chance", "chance", "❓"),
    MonopolySpace(17, "Community Charcuterie", "community", "🧺"),
    MonopolySpace(18, "Lasagna Loop", "property", "🟧", "epic"),
    MonopolySpace(19, "Mortadella Mile", "property", "🟥", "legendary"),
    MonopolySpace(20, "Free Parking", "free_parking", "🅿️"),
    MonopolySpace(21, "Porcini Place", "property", "🟥", "legendary"),
    MonopolySpace(22, "Cheese Chance", "chance", "❓"),
    MonopolySpace(23, "Panna Cotta Path", "property", "🟥", "legendary"),
    MonopolySpace(24, "Tagliatelle Terrace", "property", "🟨", "mythical"),
    MonopolySpace(25, "Burrata Boulevard", "property", "🟨", "mythical"),
    MonopolySpace(26, "Tiramisu Turn", "property", "🟨", "mythical"),
    MonopolySpace(27, "Vesuvio Vista", "property", "🟩", "divine"),
    MonopolySpace(28, "Gelato Galleria", "property", "🟩", "divine"),
    MonopolySpace(29, "Truffle Tower", "property", "🟩", "divine"),
    MonopolySpace(30, "Go To Jail", "go_to_jail", "❌"),
    MonopolySpace(31, "Imperial Risotto", "property", "🔷", "celestial"),
    MonopolySpace(32, "Doge Deli", "property", "🔷", "celestial"),
    MonopolySpace(33, "Community Charcuterie", "community", "🧺"),
    MonopolySpace(34, "Celestial Cacio", "property", "🔷", "celestial"),
    MonopolySpace(35, "Cheese Chance", "chance", "❓"),
    MonopolySpace(36, "Cheese Chance", "chance", "❓"),
    MonopolySpace(37, "Parmesan Palace", "property", "🔷", "celestial"),
    MonopolySpace(38, "Cheese Tax", "tax", "💸"),
    MonopolySpace(39, "Noodle Nebula", "property", "🔷", "celestial"),
)


COMMUNITY_CHARCUTERIE_CARDS: tuple[MonopolyCard, ...] = (
    MonopolyCard("Local nonna adopts you for Sunday dinner. Collect 700 dough.", dough_delta=700),
    MonopolyCard("Your focaccia starter went viral. Collect 850 dough.", dough_delta=850),
    MonopolyCard("You won best pesto swirl in town. Collect 600 dough.", dough_delta=600),
    MonopolyCard("Cheese wheel raffle winner. Collect 900 dough.", dough_delta=900),
    MonopolyCard("A kind barista comped your espresso cart. Collect 500 dough.", dough_delta=500),
    MonopolyCard("You hosted a pasta masterclass. Collect 1000 dough.", dough_delta=1000),
    MonopolyCard("Mamma mailed emergency biscotti funds. Collect 450 dough.", dough_delta=450),
    MonopolyCard("You found a truffle under your scooter. Collect 1100 dough.", dough_delta=1100),
    MonopolyCard("Your ravioli tutorial got sponsored. Collect 750 dough.", dough_delta=750),
    MonopolyCard("Town festival gave you a sauce grant. Collect 800 dough.", dough_delta=800),
    MonopolyCard("A parmesan wheel rolled to your doorstep. Collect 650 dough.", dough_delta=650),
    MonopolyCard("You catered an opera intermission. Collect 950 dough.", dough_delta=950),
    MonopolyCard("A chef borrowed your zester and paid rent. Collect 550 dough.", dough_delta=550),
    MonopolyCard("You sold limoncello pops at sunrise. Collect 500 dough.", dough_delta=500),
    MonopolyCard("Your gnocchi cloud art trended. Collect 700 dough.", dough_delta=700),
    MonopolyCard("Grand opening ribbon-cutting bonus. Collect 900 dough.", dough_delta=900),
    MonopolyCard("A mozzarella moon blessed your pantry. Collect 1200 dough.", dough_delta=1200),
    MonopolyCard("You taught toddlers to roll cannoli. Collect 650 dough.", dough_delta=650),
    MonopolyCard("Secret tiramisu investor appears. Collect 1300 dough.", dough_delta=1300),
    MonopolyCard("A vineyard sent gratitude crates. Collect 1000 dough.", dough_delta=1000),
    MonopolyCard("Basil crop looked immaculate. Collect 550 dough.", dough_delta=550),
    MonopolyCard("Your apron got a museum grant. Collect 750 dough.", dough_delta=750),
    MonopolyCard("You won the marinara marathon. Collect 1000 dough.", dough_delta=1000),
    MonopolyCard("Neighborhood pasta swap success. Collect 600 dough.", dough_delta=600),
    MonopolyCard("You received a lucky olive branch. Collect 700 dough.", dough_delta=700),
    MonopolyCard("A food critic left a giant tip. Collect 1400 dough.", dough_delta=1400),
    MonopolyCard("Street accordionist paid royalties. Collect 500 dough.", dough_delta=500),
    MonopolyCard("You discovered premium semolina stock. Collect 800 dough.", dough_delta=800),
    MonopolyCard("A tiny trattoria bought your recipe. Collect 900 dough.", dough_delta=900),
    MonopolyCard("You won regional garlic games. Collect 950 dough.", dough_delta=950),
    MonopolyCard("A Ferris wheel of provolone paid dividends. Collect 1100 dough.", dough_delta=1100),
    MonopolyCard("You found your lucky wooden spoon. Collect 650 dough.", dough_delta=650),
    MonopolyCard("Community bake sale overperformed. Collect 700 dough.", dough_delta=700),
    MonopolyCard("Chef internship stipend arrived. Collect 500 dough.", dough_delta=500),
    MonopolyCard("Late-night carbonara hotline bonus. Collect 850 dough.", dough_delta=850),
    MonopolyCard("A sommelier funded your menu redesign. Collect 1200 dough.", dough_delta=1200),
    MonopolyCard("Pantry insurance paid out generously. Collect 1000 dough.", dough_delta=1000),
    MonopolyCard("A golden ladle ceremony honored you. Gain 1 drop ticket.", drop_tickets_delta=1),
    MonopolyCard("VIP pasta pass unlocked. Gain 1 drop ticket.", drop_tickets_delta=1),
    MonopolyCard("You inherited a sacred sourdough starter. Gain 1 starter.", starter_delta=1),
)


CHEESE_CHANCE_CARDS: tuple[MonopolyCard, ...] = (
    MonopolyCard("You spilled truffle oil on your taxes. Lose 800 dough.", dough_delta=-800),
    MonopolyCard("A raccoon stole your ravioli tray. Lose 600 dough.", dough_delta=-600),
    MonopolyCard("Emergency cheese import tariff. Lose 900 dough.", dough_delta=-900),
    MonopolyCard("You over-salted a wedding buffet. Lose 1000 dough.", dough_delta=-1000),
    MonopolyCard("Pasta machine repair bill arrived. Lose 700 dough.", dough_delta=-700),
    MonopolyCard("A parmesan avalanche wrecked your cart. Lose 1200 dough.", dough_delta=-1200),
    MonopolyCard("Your chef hat flew into traffic. Lose 500 dough.", dough_delta=-500),
    MonopolyCard("Kitchen inspection found chaos. Lose 850 dough.", dough_delta=-850),
    MonopolyCard("You paid premium olive oil penalties. Lose 650 dough.", dough_delta=-650),
    MonopolyCard("Cursed cannoli cream incident. Lose 750 dough.", dough_delta=-750),
    MonopolyCard("You tipped every gondolier at once. Lose 1100 dough.", dough_delta=-1100),
    MonopolyCard("Burnt basil compensation payout. Lose 550 dough.", dough_delta=-550),
    MonopolyCard("Your pasta press jammed at dinner rush. Lose 950 dough.", dough_delta=-950),
    MonopolyCard("A mozzarella heist struck overnight. Lose 1300 dough.", dough_delta=-1300),
    MonopolyCard("You paid hush money for bad tiramisu. Lose 700 dough.", dough_delta=-700),
    MonopolyCard("Go directly to jail. Do not pass GO.", go_to_jail=True),
    MonopolyCard("Carb-speeding ticket: go to jail immediately.", go_to_jail=True),
    MonopolyCard("Inspector reset one of your command cooldowns.", reset_random_cooldown=True),
    MonopolyCard("You forgot to preheat. Random cooldown reset.", reset_random_cooldown=True),
    MonopolyCard("Soggy pizza scandal. Random cooldown reset.", reset_random_cooldown=True),
    MonopolyCard("Market stampede delayed your schedule. Random cooldown reset.", reset_random_cooldown=True),
    MonopolyCard("A sourdough mishap consumed your starter. Lose 1 starter.", starter_delta=-1),
    MonopolyCard("You misplaced your drop voucher. Lose 1 drop ticket.", drop_tickets_delta=-1),
    MonopolyCard("Truffle futures crashed. Lose 900 dough.", dough_delta=-900),
    MonopolyCard("Advance to GO and collect 4000 dough.", move_to=0, dough_delta=4000),
    MonopolyCard("Advance to Free Parking.", move_to=20),
    MonopolyCard("Advance to Truffle Alley.", move_to=1),
    MonopolyCard("Advance to Noodle Nebula.", move_to=39),
    MonopolyCard("Advance to Porcini Place.", move_to=21),
    MonopolyCard("Advance to Burrata Boulevard.", move_to=25),
    MonopolyCard("Advance to Gelato Galleria.", move_to=28),
    MonopolyCard("Advance to Celestial Cacio.", move_to=34),
    MonopolyCard("You won a midnight cookoff. Gain 900 dough.", dough_delta=900),
    MonopolyCard("A hidden cellar paid royalties. Gain 800 dough.", dough_delta=800),
    MonopolyCard("Neighborhood praised your lasagna. Gain 600 dough.", dough_delta=600),
    MonopolyCard("Your espresso cart had a miracle shift. Gain 750 dough.", dough_delta=750),
    MonopolyCard("Mysterious benefactor mailed flour futures. Gain 1200 dough.", dough_delta=1200),
    MonopolyCard("A local angel investor funded you. Gain 1000 dough.", dough_delta=1000),
    MonopolyCard("You found a bonus drop voucher. Gain 1 drop ticket.", drop_tickets_delta=1),
    MonopolyCard("Legendary spoon blessing. Gain 1 starter.", starter_delta=1),
)


def roll_dice() -> tuple[int, int, bool]:
    die_a = random.randint(1, 6)
    die_b = random.randint(1, 6)
    return die_a, die_b, die_a == die_b


def board_space(position: int) -> MonopolySpace:
    return BOARD_SPACES[position % len(BOARD_SPACES)]


def draw_community_charcuterie() -> MonopolyCard:
    return random.choice(COMMUNITY_CHARCUTERIE_CARDS)


def draw_cheese_chance() -> MonopolyCard:
    return random.choice(CHEESE_CHANCE_CARDS)


def random_epic_or_better_card_id() -> str:
    for _ in range(500):
        candidate = random_card_id()
        rarity = str(CARD_CATALOG[candidate]["rarity"]).lower()
        if rarity in RARITY_EPIC_OR_HIGHER:
            return candidate

    fallback = [card_id for card_id, data in CARD_CATALOG.items() if str(data["rarity"]).lower() in RARITY_EPIC_OR_HIGHER]
    return random.choice(fallback)


def render_board(player_position: int) -> str:
    size = 11
    grid = [["   " for _ in range(size)] for _ in range(size)]

    perimeter_map: dict[int, tuple[int, int]] = {}

    top_positions = list(range(20, 31))
    for col, pos in enumerate(top_positions):
        perimeter_map[pos] = (0, col)

    right_positions = list(range(31, 40))
    for idx, pos in enumerate(right_positions, start=1):
        perimeter_map[pos] = (idx, 10)

    bottom_positions = list(range(0, 11))
    for col, pos in enumerate(reversed(bottom_positions)):
        perimeter_map[pos] = (10, col)

    left_positions = list(range(11, 20))
    for idx, pos in enumerate(left_positions, start=1):
        perimeter_map[pos] = (10 - idx, 0)

    for space in BOARD_SPACES:
        row_col = perimeter_map.get(space.position)
        if row_col is None:
            continue
        row, col = row_col
        marker = "👤" if space.position == player_position else "·"
        grid[row][col] = f"{space.emoji}{marker}"

    lines = [" ".join(row) for row in grid]
    lines.append("")
    lines.append("Legend: ➡️ GO, 💸 Cheese Tax, 🧺 Community Charcuterie, ❓ Cheese Chance, 🅿️ Free Parking, ❌ Go To Jail, 🤰 Mpreg")
    lines.append("Property tiers: 🟫 common, 🟦 uncommon, 🩷 rare, 🟧 epic, 🟥 legendary, 🟨 mythical, 🟩 divine, 🔷 celestial")
    return "\n".join(lines)
