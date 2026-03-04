import random
from collections import Counter
from typing import NotRequired, TypedDict

from .rarities import RARITY_WEIGHTS
from .settings import GENERATION_MAX, GENERATION_MIN


class CardData(TypedDict):
    name: str
    series: str
    rarity: str
    base_value: int
    image: NotRequired[str]


CARD_CATALOG: dict[str, CardData] = {
    "BGL": {"name": "Bagel", "series": "bread", "rarity": "common", "base_value": 11},
    "BAG": {"name": "Baguette", "series": "bread", "rarity": "common", "base_value": 9},
    "BOL": {"name": "Bolillo", "series": "bread", "rarity": "common", "base_value": 10},
    "BRI2": {"name": "Brioche", "series": "bread", "rarity": "common", "base_value": 11},
    "PIT": {"name": "Pita", "series": "bread", "rarity": "common", "base_value": 10},
    "RYE": {"name": "Rye", "series": "bread", "rarity": "common", "base_value": 10},
    "SOU": {"name": "Sourdough", "series": "bread", "rarity": "common", "base_value": 10},
    "BRE": {"name": "Breadsticks", "series": "bread", "rarity": "uncommon", "base_value": 15},
    "CHI": {"name": "Ciabatta", "series": "bread", "rarity": "uncommon", "base_value": 15},
    "FOC": {"name": "Focaccia", "series": "bread", "rarity": "uncommon", "base_value": 16},
    "GAR": {"name": "Garlic Bread", "series": "bread", "rarity": "uncommon", "base_value": 17},
    "PRE": {"name": "Pretzel", "series": "bread", "rarity": "uncommon", "base_value": 16},
    "PUM": {"name": "Pumpernickel", "series": "bread", "rarity": "uncommon", "base_value": 16},
    "SCI": {"name": "Schiacciata", "series": "bread", "rarity": "uncommon", "base_value": 17},
    "BAT": {"name": "Batard", "series": "bread", "rarity": "rare", "base_value": 28},
    "GKN": {"name": "Garlic Knot", "series": "bread", "rarity": "rare", "base_value": 29},
    "PAN": {"name": "Panettone", "series": "bread", "rarity": "epic", "base_value": 45},
    "TRG": {"name": "Truffle Garlic Bread", "series": "bread", "rarity": "epic", "base_value": 47},
    "GRA": {"name": "Golden Grain Loaf", "series": "bread", "rarity": "legendary", "base_value": 220},
    "IMM": {"name": "Immortal Garlic Loaf", "series": "bread", "rarity": "legendary", "base_value": 230},
    "CHD": {"name": "Cheddar", "series": "cheese", "rarity": "common", "base_value": 10},
    "COL": {"name": "Colby", "series": "cheese", "rarity": "common", "base_value": 10},
    "MON": {"name": "Monterey Jack", "series": "cheese", "rarity": "common", "base_value": 10},
    "MOZ": {"name": "Mozzerella", "series": "cheese", "rarity": "common", "base_value": 9},
    "PRV": {"name": "Provolone", "series": "cheese", "rarity": "common", "base_value": 10},
    "ASI": {"name": "Asiago", "series": "cheese", "rarity": "uncommon", "base_value": 16},
    "BRI": {"name": "Brie", "series": "cheese", "rarity": "uncommon", "base_value": 17},
    "CHJ": {"name": "Cheddar Jack", "series": "cheese", "rarity": "uncommon", "base_value": 16},
    "FON": {"name": "Fontina", "series": "cheese", "rarity": "uncommon", "base_value": 16},
    "GOU": {"name": "Gouda", "series": "cheese", "rarity": "uncommon", "base_value": 17},
    "HAV": {"name": "Havarti", "series": "cheese", "rarity": "uncommon", "base_value": 15},
    "MAS": {"name": "Mascarpone", "series": "cheese", "rarity": "uncommon", "base_value": 17},
    "SWS": {"name": "Swiss", "series": "cheese", "rarity": "uncommon", "base_value": 14},
    "GOR": {"name": "Gorgonzola", "series": "cheese", "rarity": "rare", "base_value": 30},
    "GRN": {"name": "Grana Padano", "series": "cheese", "rarity": "rare", "base_value": 31},
    "PEC": {"name": "Pecorino", "series": "cheese", "rarity": "rare", "base_value": 29},
    "ROM": {"name": "Romano", "series": "cheese", "rarity": "rare", "base_value": 28},
    "SHC": {"name": "Sharp Cheddar", "series": "cheese", "rarity": "rare", "base_value": 27},
    "TAL": {"name": "Taleggio", "series": "cheese", "rarity": "rare", "base_value": 29},
    "BRC": {"name": "Burrata", "series": "cheese", "rarity": "epic", "base_value": 44},
    "ESC": {"name": "Extra Sharp Cheddar", "series": "cheese", "rarity": "epic", "base_value": 43},
    "PAR": {"name": "Parmigiano Reggiano", "series": "cheese", "rarity": "epic", "base_value": 45},
    "RCT": {"name": "Ricotta Salata", "series": "cheese", "rarity": "epic", "base_value": 45},
    "TRF": {"name": "Truffle Pecorino", "series": "cheese", "rarity": "epic", "base_value": 46},
    "GOL": {"name": "Golden Parm Wheel", "series": "cheese", "rarity": "legendary", "base_value": 225},
    "BIS": {"name": "Biscotti", "series": "dessert", "rarity": "common", "base_value": 10},
    "AFF": {"name": "Affogato", "series": "dessert", "rarity": "uncommon", "base_value": 18},
    "CNO": {"name": "Cannoli", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "GEL": {"name": "Gelato", "series": "dessert", "rarity": "uncommon", "base_value": 16},
    "PCT": {"name": "Panna Cotta", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "TIR": {"name": "Tiramisu", "series": "dessert", "rarity": "rare", "base_value": 30},
    "CHL": {"name": "Chocolate Lasagna", "series": "dessert", "rarity": "epic", "base_value": 43},
    "SFL": {"name": "Sfogliatella", "series": "dessert", "rarity": "epic", "base_value": 44},
    "ZAB": {"name": "Zabaglione", "series": "dessert", "rarity": "epic", "base_value": 45},
    "AMB": {"name": "Ambrosia Tiramisu", "series": "dessert", "rarity": "legendary", "base_value": 236},
    "MBS": {"name": "Meatball Sub", "series": "entree", "rarity": "uncommon", "base_value": 18},
    "PNI": {"name": "Panini", "series": "entree", "rarity": "uncommon", "base_value": 19},
    "PZA": {"name": "Pizza", "series": "entree", "rarity": "uncommon", "base_value": 18},
    "ARB": {"name": "Arancini", "series": "entree", "rarity": "rare", "base_value": 31},
    "ALF": {"name": "Chicken Alfredo", "series": "entree", "rarity": "rare", "base_value": 30},
    "CKP": {"name": "Chicken Parmesan", "series": "entree", "rarity": "rare", "base_value": 31},
    "RIS": {"name": "Risotto", "series": "entree", "rarity": "rare", "base_value": 30},
    "OSB": {"name": "Osso Buco", "series": "entree", "rarity": "epic", "base_value": 47},
    "OXT": {"name": "Oxtail Ragu", "series": "entree", "rarity": "epic", "base_value": 46},
    "CAG": {"name": "Chicken Alfredo Garlic Bread", "series": "entree", "rarity": "legendary", "base_value": 224},
    "ANG": {"name": "Angel Hair", "series": "noodles", "rarity": "common", "base_value": 10},
    "BCT": {"name": "Bucatini", "series": "noodles", "rarity": "common", "base_value": 10},
    "CAP": {"name": "Capellini", "series": "noodles", "rarity": "common", "base_value": 9},
    "DTP": {"name": "Ditalini", "series": "noodles", "rarity": "common", "base_value": 9},
    "EGG": {"name": "Egg Noodles", "series": "noodles", "rarity": "common", "base_value": 11},
    "FAR": {"name": "Farfalle", "series": "noodles", "rarity": "common", "base_value": 10},
    "FUS": {"name": "Fusilli", "series": "noodles", "rarity": "common", "base_value": 8},
    "LIN": {"name": "Linguine", "series": "noodles", "rarity": "common", "base_value": 9},
    "MAC": {"name": "Macaroni", "series": "noodles", "rarity": "common", "base_value": 9},
    "PEN": {"name": "Penne", "series": "noodles", "rarity": "common", "base_value": 8},
    "RAM": {"name": "Ramen", "series": "noodles", "rarity": "common", "base_value": 11},
    "RIC": {"name": "Rice Noodles", "series": "noodles", "rarity": "common", "base_value": 11},
    "ROT": {"name": "Rotini", "series": "noodles", "rarity": "common", "base_value": 9},
    "SOB": {"name": "Soba", "series": "noodles", "rarity": "common", "base_value": 10},
    "SPG": {"name": "Spaghetti", "series": "noodles", "rarity": "common", "base_value": 8},
    "UDO": {"name": "Udon", "series": "noodles", "rarity": "common", "base_value": 10},
    "VER": {"name": "Vermicelli", "series": "noodles", "rarity": "common", "base_value": 9},
    "CHM": {"name": "Chow Mein", "series": "noodles", "rarity": "uncommon", "base_value": 17},
    "LOM": {"name": "Lo Mein", "series": "noodles", "rarity": "uncommon", "base_value": 16},
    "YAK": {"name": "Yakisoba", "series": "noodles", "rarity": "uncommon", "base_value": 16},
    "NOO": {"name": "Nood God", "series": "noodles", "rarity": "legendary", "base_value": 215},
    "CON": {"name": "Conchiglie", "series": "pasta", "rarity": "common", "base_value": 11},
    "ZIT": {"name": "Ziti", "series": "pasta", "rarity": "common", "base_value": 10},
    "CPL": {"name": "Cappelletti", "series": "pasta", "rarity": "uncommon", "base_value": 16},
    "GEM": {"name": "Gemelli", "series": "pasta", "rarity": "uncommon", "base_value": 16},
    "ORC": {"name": "Orecchiette", "series": "pasta", "rarity": "uncommon", "base_value": 15},
    "PCH": {"name": "Paccheri", "series": "pasta", "rarity": "uncommon", "base_value": 17},
    "RAV": {"name": "Ravioli", "series": "pasta", "rarity": "uncommon", "base_value": 14},
    "RCA": {"name": "Ricotta Cavatelli", "series": "pasta", "rarity": "uncommon", "base_value": 17},
    "RIG": {"name": "Rigatoni", "series": "pasta", "rarity": "uncommon", "base_value": 17},
    "TAG": {"name": "Tagliatelle", "series": "pasta", "rarity": "uncommon", "base_value": 15},
    "AGN": {"name": "Agnolotti", "series": "pasta", "rarity": "rare", "base_value": 30},
    "ANO": {"name": "Anolini", "series": "pasta", "rarity": "rare", "base_value": 31},
    "CAS": {"name": "Casarecce", "series": "pasta", "rarity": "rare", "base_value": 29},
    "GNO": {"name": "Gnocchi", "series": "pasta", "rarity": "rare", "base_value": 26},
    "LAS": {"name": "Lasagna", "series": "pasta", "rarity": "rare", "base_value": 25},
    "MAN": {"name": "Manicotti", "series": "pasta", "rarity": "rare", "base_value": 27},
    "PAP": {"name": "Pappardelle", "series": "pasta", "rarity": "rare", "base_value": 28},
    "STP": {"name": "Strozzapreti", "series": "pasta", "rarity": "rare", "base_value": 29},
    "TRO": {"name": "Trofie", "series": "pasta", "rarity": "rare", "base_value": 30},
    "CAN": {"name": "Cannelloni", "series": "pasta", "rarity": "epic", "base_value": 42},
    "TOR": {"name": "Tortellini", "series": "pasta", "rarity": "epic", "base_value": 40},
    "BLA": {"name": "Black Truffle Ravioli", "series": "pasta", "rarity": "legendary", "base_value": 218},
    "WHT": {"name": "White Truffle Tagliolini", "series": "pasta", "rarity": "legendary", "base_value": 235},
    "CHB": {"name": "Chardonnay", "series": "wine", "rarity": "common", "base_value": 11},
    "CNT": {"name": "Chianti", "series": "wine", "rarity": "common", "base_value": 11},
    "LAM": {"name": "Lambrusco", "series": "wine", "rarity": "common", "base_value": 11},
    "MER": {"name": "Merlot", "series": "wine", "rarity": "common", "base_value": 11},
    "PIN": {"name": "Pinot Noir", "series": "wine", "rarity": "common", "base_value": 10},
    "PRO": {"name": "Prosecco", "series": "wine", "rarity": "common", "base_value": 10},
    "RIO": {"name": "Rioja", "series": "wine", "rarity": "uncommon", "base_value": 17},
    "SOV": {"name": "Sauvignon Blanc", "series": "wine", "rarity": "uncommon", "base_value": 16},
    "BAR": {"name": "Barolo", "series": "wine", "rarity": "rare", "base_value": 30},
    "NEB": {"name": "Nebbiolo", "series": "wine", "rarity": "rare", "base_value": 31},
    "BRU": {"name": "Brunello", "series": "wine", "rarity": "epic", "base_value": 47},
    "CHA": {"name": "Champagne", "series": "wine", "rarity": "epic", "base_value": 47},
    "FRC": {"name": "Franciacorta", "series": "wine", "rarity": "epic", "base_value": 46},
    "ICE": {"name": "Icewine", "series": "wine", "rarity": "epic", "base_value": 48},
    "AMS": {"name": "Amarone Riserva", "series": "wine", "rarity": "legendary", "base_value": 228},
    "RWB": {"name": "Royal Wine Barrique", "series": "wine", "rarity": "legendary", "base_value": 237},
}


RARITY_VALUE_BANDS: dict[str, tuple[int, int]] = {
    "common": (0, 30),
    "uncommon": (45, 90),
    "rare": (120, 180),
    "epic": (220, 260),
    "legendary": (280, 300),
}


def _rebalance_card_values() -> None:
    for rarity, (low, high) in RARITY_VALUE_BANDS.items():
        rarity_card_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if card["rarity"] == rarity
        ]
        if not rarity_card_ids:
            continue

        ranked_card_ids = sorted(
            rarity_card_ids,
            key=lambda card_id: (int(CARD_CATALOG[card_id]["base_value"]), card_id),
        )

        if len(ranked_card_ids) == 1:
            CARD_CATALOG[ranked_card_ids[0]]["base_value"] = low
            continue

        span = high - low
        last_idx = len(ranked_card_ids) - 1
        for idx, card_id in enumerate(ranked_card_ids):
            base_value = int(round(low + (span * idx / last_idx)))
            CARD_CATALOG[card_id]["base_value"] = base_value


_rebalance_card_values()


def default_card_image(card_id: str) -> str:
    return f"https://placehold.co/600x400/png?text={card_id}"


CARD_IMAGE_URLS: dict[str, str] = {
    "ALF": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Fettuccine_Alfredo.JPG/960px-Fettuccine_Alfredo.JPG",
    "AMS": "https://upload.wikimedia.org/wikipedia/commons/1/1c/Amarone_BMK.jpg",
    "ANG": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Capelli_angelo_front.jpg/960px-Capelli_angelo_front.jpg",
    "ASI": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Asiago_-_2615694751.jpg/960px-Asiago_-_2615694751.jpg",
    "BAG": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Baguettes%2C_Paris%2C_France_-_panoramio.jpg/960px-Baguettes%2C_Paris%2C_France_-_panoramio.jpg",
    "BAR": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Cascin_Adelaide_Barolo_%26_decanter.jpg/960px-Cascin_Adelaide_Barolo_%26_decanter.jpg",
    "BAT": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Compleat_Wheat_Sourdough_B%C3%A2tard.jpg",
    "BCT": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Bucatini.jpg/960px-Bucatini.jpg",
    "BLA": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg/960px-Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg",
    "BRC": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Burrata2.jpg/960px-Burrata2.jpg",
    "BRI": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Brie_01.jpg/960px-Brie_01.jpg",
    "BRI2": "https://upload.wikimedia.org/wikipedia/commons/4/4a/Brioche.jpg",
    "CAG": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Fettuccine_Alfredo.JPG/960px-Fettuccine_Alfredo.JPG",
    "CAN": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Cannelloni2.png/960px-Cannelloni2.png",
    "CKP": "https://commons.wikimedia.org/wiki/Special:FilePath/Chicken_parmigiana.jpg",
    "CHA": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Glass_of_champagne.jpg/960px-Glass_of_champagne.jpg",
    "CHB": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Chablis_bottle_and_wine.jpg",
    "CHD": "https://upload.wikimedia.org/wikipedia/commons/1/18/Somerset-Cheddar.jpg",
    "CHI": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Ciabatta_cut.JPG/960px-Ciabatta_cut.JPG",
    "CHJ": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/CoJack.jpg/960px-CoJack.jpg",
    "COL": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Colby_Cheese.jpg/960px-Colby_Cheese.jpg",
    "CPL": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/02_Cappelletti_-_Cappellacci_-_Pasta_ripiena_-_Cucina_tipica_-_Ferrara.jpg/960px-02_Cappelletti_-_Cappellacci_-_Pasta_ripiena_-_Cucina_tipica_-_Ferrara.jpg",
    "DTP": "https://upload.wikimedia.org/wikipedia/commons/6/6a/Ditalini-230.jpg",
    "ESC": "https://upload.wikimedia.org/wikipedia/commons/1/18/Somerset-Cheddar.jpg",
    "FAR": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Farfalle_Pasta.JPG/960px-Farfalle_Pasta.JPG",
    "FOC": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Focaccia_with_Crumb.jpg/960px-Focaccia_with_Crumb.jpg",
    "FUS": "https://upload.wikimedia.org/wikipedia/commons/f/f7/Fusilli_tricolore_-_close_up.jpg",
    "GAR": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Garlicbread.jpg/960px-Garlicbread.jpg",
    "GEL": "https://commons.wikimedia.org/wiki/Special:FilePath/Gelato_in_Italy.jpg",
    "GKN": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Garlic_knots.jpg/960px-Garlic_knots.jpg",
    "GNO": "https://upload.wikimedia.org/wikipedia/commons/8/86/Gnocchi_di_ricotta_burro_e_salvia.jpg",
    "GOL": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Parmigiano_Reggiano%2C_Italien%2C_Europ%C3%A4ische_Union.jpg/960px-Parmigiano_Reggiano%2C_Italien%2C_Europ%C3%A4ische_Union.jpg",
    "GOU": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Chesses_gouda_affinage.JPG/960px-Chesses_gouda_affinage.JPG",
    "GRA": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Korb_mit_Br%C3%B6tchen.JPG/960px-Korb_mit_Br%C3%B6tchen.JPG",
    "HAV": "https://upload.wikimedia.org/wikipedia/commons/f/f9/Cream_havarti_on_bread.jpg",
    "ICE": "https://upload.wikimedia.org/wikipedia/commons/9/9b/Ice_wine_minibottle.jpg",
    "IMM": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Garlicbread.jpg/960px-Garlicbread.jpg",
    "LAS": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Lasagna_bolognese.jpg/960px-Lasagna_bolognese.jpg",
    "LIN": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Linguine.jpg/960px-Linguine.jpg",
    "MAC": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Macaroni2.jpg/960px-Macaroni2.jpg",
    "MAN": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/EMS-109321-Manicotti-rule..JPG/960px-EMS-109321-Manicotti-rule..JPG",
    "MER": "https://upload.wikimedia.org/wikipedia/commons/7/77/Canadian_Cab-merlot_blend.JPG",
    "MBS": "https://commons.wikimedia.org/wiki/Special:FilePath/Mmm..._Meatball_sub_with_marinara_sauce,_mozzarella,_and_roasted_peppers_(6432603233).jpg",
    "MON": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Vella_Cheese_Young_Jack_%28cropped%29.jpg/960px-Vella_Cheese_Young_Jack_%28cropped%29.jpg",
    "MOZ": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Mozzarella_di_bufala3.jpg/960px-Mozzarella_di_bufala3.jpg",
    "NOO": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Touched_by_His_Noodly_Appendage_HD.jpg/960px-Touched_by_His_Noodly_Appendage_HD.jpg",
    "ORC": "https://upload.wikimedia.org/wikipedia/commons/8/8d/Orecchiette_carbonara.jpg",
    "PAN": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Panettone_-_Nicolettone_2017_-_IMG_7085_%2831752542285%29.jpg/960px-Panettone_-_Nicolettone_2017_-_IMG_7085_%2831752542285%29.jpg",
    "PAP": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/Pappardelle.jpg/960px-Pappardelle.jpg",
    "PAR": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Parmigiano_Reggiano%2C_Italien%2C_Europ%C3%A4ische_Union.jpg/960px-Parmigiano_Reggiano%2C_Italien%2C_Europ%C3%A4ische_Union.jpg",
    "PEC": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/A_Pecorino_cheese_plate_at_Hong_Kong.jpg/960px-A_Pecorino_cheese_plate_at_Hong_Kong.jpg",
    "PEN": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Pennelisce_closeup.png/960px-Pennelisce_closeup.png",
    "PNI": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/Panini_01.jpg/960px-Panini_01.jpg",
    "PIN": "https://upload.wikimedia.org/wikipedia/commons/1/19/Pinot_Noir_being_poured_into_a_wine_glass.jpg",
    "PRV": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Provolone_watermelon_shape.jpg/960px-Provolone_watermelon_shape.jpg",
    "PUM": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Pumpernickel.jpg/960px-Pumpernickel.jpg",
    "PZA": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Supreme_pizza.jpg/960px-Supreme_pizza.jpg",
    "RAV": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg/960px-Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg",
    "RCA": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Cavatelli.jpg",
    "RIO": "https://upload.wikimedia.org/wikipedia/commons/8/81/Rioja_alavesa_wine.jpg",
    "ROM": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Romano%2C_3_Months_%287005123366%29.jpg/960px-Romano%2C_3_Months_%287005123366%29.jpg",
    "ROT": "https://upload.wikimedia.org/wikipedia/commons/a/a8/Rotini_pasta.jpg",
    "RIS": "https://commons.wikimedia.org/wiki/Special:FilePath/Lemon_Pea_Risotto.jpg",
    "RYE": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Ear_of_rye.jpg/960px-Ear_of_rye.jpg",
    "SHC": "https://upload.wikimedia.org/wikipedia/commons/1/18/Somerset-Cheddar.jpg",
    "SOU": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Home_made_sour_dough_bread.jpg/960px-Home_made_sour_dough_bread.jpg",
    "SOV": "https://upload.wikimedia.org/wikipedia/commons/b/ba/Sauvignon_blanc_wine.jpg",
    "SPG": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/92/Spaghettoni.jpg/960px-Spaghettoni.jpg",
    "SWS": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Marche-aux-puces-Lausanne-004.jpg/960px-Marche-aux-puces-Lausanne-004.jpg",
    "TAG": "https://upload.wikimedia.org/wikipedia/commons/6/67/Nests_of_tagliatelle_bolognesi.jpg",
    "TIR": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Tiramisu_-_Raffaele_Diomede.jpg/960px-Tiramisu_-_Raffaele_Diomede.jpg",
    "TOR": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Tortellini_Bolognesi.jpg/960px-Tortellini_Bolognesi.jpg",
    "CHL": "https://i.pinimg.com/736x/b2/d4/14/b2d4142c7011caf548fbade4e83d8c59.jpg",
    "TRF": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/Pecorino_romano_cheese.jpg/960px-Pecorino_romano_cheese.jpg",
    "TRG": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Garlicbread.jpg/960px-Garlicbread.jpg",
    "VER": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/92/Spaghettoni.jpg/960px-Spaghettoni.jpg",
    "CAP": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Capelli_angelo_front.jpg/960px-Capelli_angelo_front.jpg",
    "UDO": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Miso_udon.jpg/960px-Miso_udon.jpg",
    "SOB": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Zaru_soba_by_jenh_via_flickr.jpg/960px-Zaru_soba_by_jenh_via_flickr.jpg",
    "RAM": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Ramen_with_chashu_and_egg.jpg/960px-Ramen_with_chashu_and_egg.jpg",
    "EGG": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Fusilli_tricolore_-_close_up.jpg/960px-Fusilli_tricolore_-_close_up.jpg",
    "RIC": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Fusilli_tricolore_-_close_up.jpg/960px-Fusilli_tricolore_-_close_up.jpg",
    "YAK": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Yakisoba_at_Festival.jpg/960px-Yakisoba_at_Festival.jpg",
    "LOM": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Lo_mein.jpg/960px-Lo_mein.jpg",
    "CHM": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Chow_mein_1_by_gryffindor.jpg/960px-Chow_mein_1_by_gryffindor.jpg",
    "ZIT": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Pennelisce_closeup.png/960px-Pennelisce_closeup.png",
    "CON": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Farfalle_Pasta.JPG/960px-Farfalle_Pasta.JPG",
    "GEM": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Farfalle_Pasta.JPG/960px-Farfalle_Pasta.JPG",
    "RIG": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Pennelisce_closeup.png/960px-Pennelisce_closeup.png",
    "PCH": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Pennelisce_closeup.png/960px-Pennelisce_closeup.png",
    "STP": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/Pappardelle.jpg/960px-Pappardelle.jpg",
    "CAS": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/Pappardelle.jpg/960px-Pappardelle.jpg",
    "TRO": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Nests_of_tagliatelle_bolognesi.jpg/960px-Nests_of_tagliatelle_bolognesi.jpg",
    "AGN": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg/960px-Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg",
    "ANO": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg/960px-Flickr_-_cyclonebill_-_Ravioli_med_skinke_og_asparges_i_mascarponecreme.jpg",
    "WHT": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Nests_of_tagliatelle_bolognesi.jpg/960px-Nests_of_tagliatelle_bolognesi.jpg",
    "BOL": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Baguettes%2C_Paris%2C_France_-_panoramio.jpg/960px-Baguettes%2C_Paris%2C_France_-_panoramio.jpg",
    "PIT": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Home_made_sour_dough_bread.jpg/960px-Home_made_sour_dough_bread.jpg",
    "BGL": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Baguettes%2C_Paris%2C_France_-_panoramio.jpg/960px-Baguettes%2C_Paris%2C_France_-_panoramio.jpg",
    "BRE": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Garlicbread.jpg/960px-Garlicbread.jpg",
    "PRE": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Pretzel_01.jpg/960px-Pretzel_01.jpg",
    "SCI": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Focaccia_with_Crumb.jpg/960px-Focaccia_with_Crumb.jpg",
    "ARB": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Arancini_di_riso.jpg/960px-Arancini_di_riso.jpg",
    "OXT": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Supreme_pizza.jpg/960px-Supreme_pizza.jpg",
    "OSB": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Supreme_pizza.jpg/960px-Supreme_pizza.jpg",
    "BIS": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Almond_biscotti.jpg/960px-Almond_biscotti.jpg",
    "CNO": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Cannoli.jpg/960px-Cannoli.jpg",
    "PCT": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Panna_cotta_with_strawberries.jpg/960px-Panna_cotta_with_strawberries.jpg",
    "AFF": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Affogato.jpg/960px-Affogato.jpg",
    "SFL": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Sfogliatella_napoletana.jpg/960px-Sfogliatella_napoletana.jpg",
    "ZAB": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Tiramisu_-_Raffaele_Diomede.jpg/960px-Tiramisu_-_Raffaele_Diomede.jpg",
    "AMB": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Tiramisu_-_Raffaele_Diomede.jpg/960px-Tiramisu_-_Raffaele_Diomede.jpg",
    "FON": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Asiago_-_2615694751.jpg/960px-Asiago_-_2615694751.jpg",
    "MAS": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Brie_01.jpg/960px-Brie_01.jpg",
    "TAL": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Chesses_gouda_affinage.JPG/960px-Chesses_gouda_affinage.JPG",
    "GOR": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Chesses_gouda_affinage.JPG/960px-Chesses_gouda_affinage.JPG",
    "GRN": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Parmigiano_Reggiano%2C_Italien%2C_Europ%C3%A4ische_Union.jpg/960px-Parmigiano_Reggiano%2C_Italien%2C_Europ%C3%A4ische_Union.jpg",
    "RCT": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Mozzarella_di_bufala3.jpg/960px-Mozzarella_di_bufala3.jpg",
    "PRO": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Glass_of_champagne.jpg/960px-Glass_of_champagne.jpg",
    "CNT": "https://upload.wikimedia.org/wikipedia/commons/8/81/Rioja_alavesa_wine.jpg",
    "LAM": "https://upload.wikimedia.org/wikipedia/commons/7/77/Canadian_Cab-merlot_blend.JPG",
    "NEB": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Cascin_Adelaide_Barolo_%26_decanter.jpg/960px-Cascin_Adelaide_Barolo_%26_decanter.jpg",
    "FRC": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Glass_of_champagne.jpg/960px-Glass_of_champagne.jpg",
    "BRU": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Cascin_Adelaide_Barolo_%26_decanter.jpg/960px-Cascin_Adelaide_Barolo_%26_decanter.jpg",
    "RWB": "https://upload.wikimedia.org/wikipedia/commons/1/1c/Amarone_BMK.jpg",
}


def _validate_explicit_images() -> None:
    missing_explicit_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if not card.get("image") and card_id not in CARD_IMAGE_URLS
    ]
    if missing_explicit_ids:
        raise RuntimeError(
            "Missing explicit card images for: " + ", ".join(sorted(missing_explicit_ids))
        )


_validate_explicit_images()


for _card_id, _card in CARD_CATALOG.items():
    _card["image"] = _card.get("image") or CARD_IMAGE_URLS.get(_card_id) or default_card_image(_card_id)


def _validate_no_fallback_images() -> None:
    fallback_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if card.get("image") == default_card_image(card_id)
    ]
    if fallback_ids:
        raise RuntimeError(
            "Fallback placeholder image in use for: " + ", ".join(sorted(fallback_ids))
        )


_validate_no_fallback_images()


RARITY_CARD_COUNTS = Counter(card["rarity"] for card in CARD_CATALOG.values())
NORMALIZED_RARITY_WEIGHTS = {
    rarity: weight / RARITY_CARD_COUNTS[rarity]
    for rarity, weight in RARITY_WEIGHTS.items()
    if RARITY_CARD_COUNTS.get(rarity, 0) > 0
}


def effective_rarity_odds() -> dict[str, float]:
    weighted_totals = {
        rarity: NORMALIZED_RARITY_WEIGHTS[rarity] * RARITY_CARD_COUNTS[rarity]
        for rarity in NORMALIZED_RARITY_WEIGHTS
    }
    grand_total = sum(weighted_totals.values())
    if grand_total <= 0:
        return {rarity: 0.0 for rarity in weighted_totals}
    return {rarity: weighted_totals[rarity] / grand_total for rarity in weighted_totals}


def target_rarity_odds() -> dict[str, float]:
    active_weights = {
        rarity: weight
        for rarity, weight in RARITY_WEIGHTS.items()
        if RARITY_CARD_COUNTS.get(rarity, 0) > 0
    }
    total_weight = sum(active_weights.values())
    if total_weight <= 0:
        return {rarity: 0.0 for rarity in active_weights}
    return {rarity: active_weights[rarity] / total_weight for rarity in active_weights}


def normalize_card_id(card_id: str) -> str:
    return card_id.strip().upper()


def search_card_ids_by_name(query: str) -> list[str]:
    cleaned_query = query.strip().casefold()
    if not cleaned_query:
        return []

    exact_name_matches: list[str] = []
    prefix_name_matches: list[str] = []
    contains_name_matches: list[str] = []

    for card_id, card in CARD_CATALOG.items():
        card_name = card["name"]
        normalized_name = card_name.casefold()
        if normalized_name == cleaned_query:
            exact_name_matches.append(card_id)
        elif normalized_name.startswith(cleaned_query):
            prefix_name_matches.append(card_id)
        elif cleaned_query in normalized_name:
            contains_name_matches.append(card_id)

    key = lambda cid: (CARD_CATALOG[cid]["name"].casefold(), cid)
    return sorted(exact_name_matches, key=key) + sorted(prefix_name_matches, key=key) + sorted(contains_name_matches, key=key)


def card_code(card_id: str, dupe_code: str) -> str:
    return dupe_code.strip().lower()


def split_card_code(raw_code: str) -> str | None:
    cleaned = raw_code.strip()
    if not cleaned:
        return None

    dupe_code = cleaned.lower()

    if not all(char.isdigit() or ("a" <= char <= "z") for char in dupe_code):
        return None

    return dupe_code


def generation_label(generation: int) -> str:
    return f"G-{generation}"


def proper_case(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())


def card_base_value(card_id: str) -> int:
    return int(CARD_CATALOG[card_id]["base_value"])


def card_value(card_id: str, generation: int) -> int:
    base_value = card_base_value(card_id)
    multiplier = generation_value_multiplier(generation)
    return max(1, int(round(base_value * multiplier)))


def card_base_display(card_id: str) -> str:
    card = CARD_CATALOG[card_id]
    return (
        f"**{card['name']}** · (`{card_id}`) "
        f"[{proper_case(card['series'])}] ({proper_case(card['rarity'])}) "
        f"(Base: **{card_base_value(card_id)}** dough)"
    )


def card_dupe_display(card_id: str, generation: int, dupe_code: str | None = None) -> str:
    card = CARD_CATALOG[card_id]
    dupe_code_text = card_code(card_id, dupe_code) if dupe_code is not None else "?"
    return (
        f"`#{dupe_code_text}` **{card['name']}** • (`{card_id}`) "
        f"[{proper_case(card['series'])}] ({proper_case(card['rarity'])}) "
        f"• **{generation_label(generation)}** (Value: **{card_value(card_id, generation)}** dough)"
    )


def card_image_url(card_id: str) -> str:
    card = CARD_CATALOG[card_id]
    return card.get("image") or default_card_image(card_id)


def random_card_id() -> str:
    card_ids = list(CARD_CATALOG.keys())
    weights = [
        NORMALIZED_RARITY_WEIGHTS.get(CARD_CATALOG[cid]["rarity"], 1.0)
        for cid in card_ids
    ]
    return random.choices(card_ids, weights=weights, k=1)[0]


def random_generation() -> int:
    return int(random.triangular(GENERATION_MIN, GENERATION_MAX, GENERATION_MAX))


def make_drop_choices(size: int = 3) -> list[tuple[str, int]]:
    if size >= len(CARD_CATALOG):
        card_ids = random.sample(list(CARD_CATALOG.keys()), len(CARD_CATALOG))
        return [(card_id, random_generation()) for card_id in card_ids]

    chosen: set[str] = set()
    while len(chosen) < size:
        chosen.add(random_card_id())
    return [(card_id, random_generation()) for card_id in chosen]


def generation_value_multiplier(generation: int) -> float:
    clamped_generation = max(GENERATION_MIN, min(GENERATION_MAX, generation))
    progress = (GENERATION_MAX - clamped_generation) / (GENERATION_MAX - GENERATION_MIN)
    return 1.0 + (69.0 * (progress ** 7))


def burn_delta_range(value: int) -> int:
    percent = random.randint(5, 20)
    return max(1, int(round(value * (percent / 100.0))))


def get_burn_payout(card_id: str, generation: int, delta_range: int | None = None) -> tuple[int, int, int, int, float, int]:
    base_value = card_base_value(card_id)
    multiplier = generation_value_multiplier(generation)
    value = max(1, int(round(base_value * multiplier)))
    resolved_delta_range = burn_delta_range(value) if delta_range is None else max(1, delta_range)
    delta = random.randint(-resolved_delta_range, resolved_delta_range)
    payout = max(1, value + delta)
    return payout, value, base_value, delta, multiplier, resolved_delta_range
