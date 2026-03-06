import json
import random
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict

from .rarities import RARITY_WEIGHTS
from .settings import CARD_IMAGE_CACHE_MANIFEST, GENERATION_MAX, GENERATION_MIN


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
    "IMM": {"name": "Immortal Garlic Loaf", "series": "bread", "rarity": "mythic", "base_value": 230},
    "SDM": {"name": "Semolina Bread", "series": "bread", "rarity": "common", "base_value": 10},
    "MKB": {"name": "Milk Bread", "series": "bread", "rarity": "common", "base_value": 9},
    "CRB": {"name": "Crusty Roll", "series": "bread", "rarity": "common", "base_value": 9},
    "BUN": {"name": "Brioche Bun", "series": "bread", "rarity": "common", "base_value": 10},
    "CRO": {"name": "Crostini", "series": "bread", "rarity": "uncommon", "base_value": 15},
    "GRI": {"name": "Grissini", "series": "bread", "rarity": "uncommon", "base_value": 16},
    "PTS": {"name": "Pane Toscano", "series": "bread", "rarity": "uncommon", "base_value": 17},
    "FCC": {"name": "Focaccia al Formaggio", "series": "bread", "rarity": "rare", "base_value": 29},
    "RSF": {"name": "Rosemary Sea-Salt Focaccia", "series": "bread", "rarity": "rare", "base_value": 30},
    "RDB": {"name": "Rustic Durum Boule", "series": "bread", "rarity": "epic", "base_value": 44},
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
    "RCO": {"name": "Ricotta", "series": "cheese", "rarity": "common", "base_value": 9},
    "SCA": {"name": "Scamorza", "series": "cheese", "rarity": "common", "base_value": 10},
    "CAC": {"name": "Caciocavallo", "series": "cheese", "rarity": "common", "base_value": 10},
    "STR": {"name": "Stracciatella", "series": "cheese", "rarity": "uncommon", "base_value": 16},
    "PDM": {"name": "Provola del Monaco", "series": "cheese", "rarity": "rare", "base_value": 17},
    "MFL": {"name": "Mozzarella Fior di Latte", "series": "cheese", "rarity": "uncommon", "base_value": 17},
    "CAT": {"name": "Caciotta al Tartufo", "series": "cheese", "rarity": "epic", "base_value": 29},
    "RBL": {"name": "Robiola", "series": "cheese", "rarity": "rare", "base_value": 30},
    "GPR": {"name": "Grana Riserva", "series": "cheese", "rarity": "epic", "base_value": 45},
    "IMB": {"name": "Imperial Burrata", "series": "cheese", "rarity": "mythic", "base_value": 236},
    "BIS": {"name": "Biscotti", "series": "dessert", "rarity": "common", "base_value": 10},
    "AFF": {"name": "Affogato", "series": "dessert", "rarity": "rare", "base_value": 18},
    "CNO": {"name": "Cannoli", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "GEL": {"name": "Gelato", "series": "dessert", "rarity": "uncommon", "base_value": 16},
    "PCT": {"name": "Panna Cotta", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "TIR": {"name": "Tiramisu", "series": "dessert", "rarity": "rare", "base_value": 30},
    "CHL": {"name": "Chocolate Lasagna", "series": "dessert", "rarity": "rare", "base_value": 43},
    "SFL": {"name": "Sfogliatella", "series": "dessert", "rarity": "epic", "base_value": 44},
    "ZAB": {"name": "Zabaglione", "series": "dessert", "rarity": "epic", "base_value": 45},
    "AMB": {"name": "Ambrosia Tiramisu", "series": "dessert", "rarity": "mythic", "base_value": 236},
    "BRW": {"name": "Brownie", "series": "dessert", "rarity": "common", "base_value": 9},
    "CHK": {"name": "Chocolate Chip Cookie", "series": "dessert", "rarity": "common", "base_value": 10},
    "SCK": {"name": "Sugar Cookie", "series": "dessert", "rarity": "common", "base_value": 8},
    "OMC": {"name": "Oatmeal Cookie", "series": "dessert", "rarity": "common", "base_value": 8},
    "LMB": {"name": "Lemon Bar", "series": "dessert", "rarity": "common", "base_value": 9},
    "RKT": {"name": "Rice Krispie Treat", "series": "dessert", "rarity": "common", "base_value": 9},
    "APL": {"name": "Apple Pie", "series": "dessert", "rarity": "common", "base_value": 10},
    "CRP": {"name": "Cherry Pie", "series": "dessert", "rarity": "common", "base_value": 10},
    "BPD": {"name": "Banana Pudding", "series": "dessert", "rarity": "common", "base_value": 9},
    "DNT": {"name": "Donut", "series": "dessert", "rarity": "common", "base_value": 8},
    "FDG": {"name": "Fudge", "series": "dessert", "rarity": "common", "base_value": 9},
    "BCP": {"name": "Banana Cream Pie", "series": "dessert", "rarity": "common", "base_value": 10},
    "CUP": {"name": "Cupcake", "series": "dessert", "rarity": "common", "base_value": 9},
    "CHR": {"name": "Churro", "series": "dessert", "rarity": "common", "base_value": 10},
    "BLD": {"name": "Blondie", "series": "dessert", "rarity": "uncommon", "base_value": 15},
    "MCR": {"name": "Macaron", "series": "dessert", "rarity": "rare", "base_value": 17},
    "ECL": {"name": "Eclair", "series": "dessert", "rarity": "uncommon", "base_value": 16},
    "PRL": {"name": "Profiterole", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "CBB": {"name": "Berry Cobbler", "series": "dessert", "rarity": "uncommon", "base_value": 15},
    "BNS": {"name": "Bread Pudding", "series": "dessert", "rarity": "uncommon", "base_value": 16},
    "FYG": {"name": "Frozen Yogurt", "series": "dessert", "rarity": "common", "base_value": 16},
    "PSC": {"name": "Popsicle", "series": "dessert", "rarity": "common", "base_value": 14},
    "ICS": {"name": "Ice Cream Sandwich", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "SND": {"name": "Sundae", "series": "dessert", "rarity": "uncommon", "base_value": 17},
    "MLS": {"name": "Milkshake", "series": "dessert", "rarity": "uncommon", "base_value": 16},
    "CHS": {"name": "Cheesecake", "series": "dessert", "rarity": "rare", "base_value": 27},
    "NYC": {"name": "New York Cheesecake", "series": "dessert", "rarity": "rare", "base_value": 30},
    "RVC": {"name": "Red Velvet Cake", "series": "dessert", "rarity": "rare", "base_value": 29},
    "BAK": {"name": "Baklava", "series": "dessert", "rarity": "rare", "base_value": 28},
    "MCI": {"name": "Mochi Ice Cream", "series": "dessert", "rarity": "rare", "base_value": 29},
    "TRM": {"name": "Tres Leches Cake", "series": "dessert", "rarity": "rare", "base_value": 30},
    "CBR": {"name": "Creme Brulee", "series": "dessert", "rarity": "rare", "base_value": 31},
    "GLS": {"name": "Gelato Sundae", "series": "dessert", "rarity": "rare", "base_value": 32},
    "BSC": {"name": "Basque Cheesecake", "series": "dessert", "rarity": "epic", "base_value": 43},
    "BTA": {"name": "Baked Alaska", "series": "dessert", "rarity": "epic", "base_value": 46},
    "GFL": {"name": "Gelato Flight", "series": "dessert", "rarity": "epic", "base_value": 45},
    "MTC": {"name": "Matcha Cheesecake", "series": "dessert", "rarity": "epic", "base_value": 44},
    "LVC": {"name": "Lava Cake", "series": "dessert", "rarity": "epic", "base_value": 45},
    "GLC": {"name": "Golden Cheesecake", "series": "dessert", "rarity": "mythic", "base_value": 234},
    "NIT": {"name": "Nitrogen Gelato", "series": "dessert", "rarity": "divine", "base_value": 238},
    "MBS": {"name": "Meatball Sub", "series": "entree", "rarity": "common", "base_value": 18},
    "PNI": {"name": "Panini", "series": "entree", "rarity": "common", "base_value": 19},
    "PZA": {"name": "Pizza", "series": "entree", "rarity": "common", "base_value": 18},
    "ARB": {"name": "Arancini", "series": "entree", "rarity": "rare", "base_value": 31},
    "ALF": {"name": "Chicken Alfredo", "series": "entree", "rarity": "rare", "base_value": 30},
    "CKP": {"name": "Chicken Parmesan", "series": "entree", "rarity": "rare", "base_value": 31},
    "RIS": {"name": "Risotto", "series": "entree", "rarity": "rare", "base_value": 30},
    "OSB": {"name": "Osso Buco", "series": "entree", "rarity": "epic", "base_value": 47},
    "OXT": {"name": "Oxtail Ragu", "series": "entree", "rarity": "epic", "base_value": 46},
    "CAG": {"name": "Chicken Alfredo Garlic Bread", "series": "entree", "rarity": "legendary", "base_value": 224},
    "GNP": {"name": "Gnocchi al Pesto", "series": "entree", "rarity": "common", "base_value": 11},
    "EPA": {"name": "Eggplant Parmigiana", "series": "entree", "rarity": "uncommon", "base_value": 18},
    "VSL": {"name": "Veal Saltimbocca", "series": "entree", "rarity": "uncommon", "base_value": 19},
    "PLF": {"name": "Polenta ai Funghi", "series": "entree", "rarity": "uncommon", "base_value": 17},
    "BFL": {"name": "Bistecca Fiorentina", "series": "entree", "rarity": "rare", "base_value": 30},
    "LAV": {"name": "Linguine alle Vongole", "series": "entree", "rarity": "rare", "base_value": 31},
    "SCP": {"name": "Seafood Cioppino", "series": "entree", "rarity": "rare", "base_value": 32},
    "TRR": {"name": "Truffle Risotto", "series": "entree", "rarity": "epic", "base_value": 46},
    "LGP": {"name": "Lobster Gnocchi Piccata", "series": "entree", "rarity": "epic", "base_value": 47},
    "RMF": {"name": "Royal Milanese Feast", "series": "entree", "rarity": "divine", "base_value": 238},
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
    "SPN": {"name": "Spinach Noodles", "series": "noodles", "rarity": "common", "base_value": 9},
    "BLN": {"name": "Black Garlic Noodles", "series": "noodles", "rarity": "common", "base_value": 10},
    "TAJ": {"name": "Tajarin", "series": "noodles", "rarity": "common", "base_value": 11},
    "CPR": {"name": "Cappellini Rustica", "series": "noodles", "rarity": "common", "base_value": 9},
    "UDC": {"name": "Udon Carbonara", "series": "noodles", "rarity": "uncommon", "base_value": 17},
    "RGN": {"name": "Ragu Noodles", "series": "noodles", "rarity": "uncommon", "base_value": 16},
    "SFN": {"name": "Saffron Noodles", "series": "noodles", "rarity": "uncommon", "base_value": 17},
    "LBN": {"name": "Lobster Bisque Noodles", "series": "noodles", "rarity": "epic", "base_value": 30},
    "TRN": {"name": "Truffle Noodles", "series": "noodles", "rarity": "epic", "base_value": 31},
    "GTN": {"name": "Golden Truffle Noodles", "series": "noodles", "rarity": "epic", "base_value": 45},
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
    "GNO": {"name": "Gnocchi", "series": "pasta", "rarity": "uncommon", "base_value": 26},
    "LAS": {"name": "Lasagna", "series": "pasta", "rarity": "uncommon", "base_value": 25},
    "MAN": {"name": "Manicotti", "series": "pasta", "rarity": "rare", "base_value": 27},
    "PAP": {"name": "Pappardelle", "series": "pasta", "rarity": "rare", "base_value": 28},
    "STP": {"name": "Strozzapreti", "series": "pasta", "rarity": "rare", "base_value": 29},
    "TRO": {"name": "Trofie", "series": "pasta", "rarity": "rare", "base_value": 30},
    "CAN": {"name": "Cannelloni", "series": "pasta", "rarity": "epic", "base_value": 42},
    "TOR": {"name": "Tortellini", "series": "pasta", "rarity": "epic", "base_value": 40},
    "BLA": {"name": "Black Truffle Ravioli", "series": "pasta", "rarity": "legendary", "base_value": 218},
    "WHT": {"name": "White Truffle Tagliolini", "series": "pasta", "rarity": "mythic", "base_value": 235},
    "MLF": {"name": "Mafaldine", "series": "pasta", "rarity": "common", "base_value": 10},
    "DTV": {"name": "Ditaloni Verdi", "series": "pasta", "rarity": "common", "base_value": 9},
    "SLA": {"name": "Sicilian Linguine Arc", "series": "pasta", "rarity": "common", "base_value": 10},
    "CPN": {"name": "Campanelle", "series": "pasta", "rarity": "uncommon", "base_value": 16},
    "LUM": {"name": "Lumache", "series": "pasta", "rarity": "uncommon", "base_value": 15},
    "TBB": {"name": "Trofie al Burro", "series": "pasta", "rarity": "uncommon", "base_value": 17},
    "SFR": {"name": "Saffron Ravioli", "series": "pasta", "rarity": "epic", "base_value": 30},
    "PRC": {"name": "Porcini Ravioli", "series": "pasta", "rarity": "rare", "base_value": 31},
    "BLP": {"name": "Black Pepper Pappardelle", "series": "pasta", "rarity": "epic", "base_value": 46},
    "CSP": {"name": "Crown Stuffed Pasta", "series": "pasta", "rarity": "divine", "base_value": 239},
    "CHB": {"name": "Chardonnay", "series": "wine", "rarity": "common", "base_value": 11},
    "CNT": {"name": "Chianti", "series": "wine", "rarity": "common", "base_value": 11},
    "LAM": {"name": "Lambrusco", "series": "wine", "rarity": "common", "base_value": 11},
    "MER": {"name": "Merlot", "series": "wine", "rarity": "common", "base_value": 11},
    "PIN": {"name": "Pinot Noir", "series": "wine", "rarity": "common", "base_value": 10},
    "PRO": {"name": "Prosecco", "series": "wine", "rarity": "common", "base_value": 10},
    "RIO": {"name": "Rioja", "series": "wine", "rarity": "uncommon", "base_value": 17},
    "SOV": {"name": "Sauvignon Blanc", "series": "wine", "rarity": "uncommon", "base_value": 16},
    "BAR": {"name": "Barolo", "series": "wine", "rarity": "epic", "base_value": 30},
    "NEB": {"name": "Nebbiolo", "series": "wine", "rarity": "rare", "base_value": 31},
    "BRU": {"name": "Brunello", "series": "wine", "rarity": "epic", "base_value": 47},
    "CHA": {"name": "Champagne", "series": "wine", "rarity": "epic", "base_value": 47},
    "FRC": {"name": "Franciacorta", "series": "wine", "rarity": "epic", "base_value": 46},
    "ICE": {"name": "Icewine", "series": "wine", "rarity": "epic", "base_value": 48},
    "AMS": {"name": "Amarone Riserva", "series": "wine", "rarity": "legendary", "base_value": 228},
    "RWB": {"name": "Royal Wine Barrique", "series": "wine", "rarity": "mythic", "base_value": 237},
    "VDT": {"name": "Vino da Tavola", "series": "wine", "rarity": "common", "base_value": 10},
    "FRZ": {"name": "Frizzante Bianco", "series": "wine", "rarity": "common", "base_value": 11},
    "RSR": {"name": "Rosso Riserva", "series": "wine", "rarity": "rare", "base_value": 17},
    "PGR": {"name": "Pinot Grigio Riserva", "series": "wine", "rarity": "uncommon", "base_value": 16},
    "VSC": {"name": "Vin Santo Classico", "series": "wine", "rarity": "uncommon", "base_value": 18},
    "BRS": {"name": "Barbaresco", "series": "wine", "rarity": "rare", "base_value": 30},
    "SUT": {"name": "Super Tuscan", "series": "wine", "rarity": "epic", "base_value": 31},
    "AGL": {"name": "Aglianico", "series": "wine", "rarity": "rare", "base_value": 29},
    "MCB": {"name": "Metodo Classico Brut", "series": "wine", "rarity": "epic", "base_value": 47},
    "EMV": {"name": "Emperor's Vineyard", "series": "wine", "rarity": "celestial", "base_value": 240},
    "EXB": {"name": "Exotic Butters", "series": "dessert", "rarity": "celestial", "base_value": 241},
}


RARITY_VALUE_BANDS: dict[str, tuple[int, int]] = {
    "common": (0, 30),
    "uncommon": (45, 90),
    "rare": (120, 180),
    "epic": (220, 260),
    "legendary": (280, 320),
    "mythic": (340, 390),
    "divine": (420, 470),
    "celestial": (520, 560),
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
    return f"assets/card_images/{card_id}.img"


def _read_local_image_manifest() -> dict[str, dict[str, str | int]]:
    try:
        parsed = json.loads(CARD_IMAGE_CACHE_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(parsed, dict):
        return {}

    manifest: dict[str, dict[str, str | int]] = {}
    for card_id, value in parsed.items():
        if isinstance(card_id, str) and isinstance(value, dict):
            manifest[card_id] = value
    return manifest


def _build_local_card_image_map() -> dict[str, str]:
    manifest_data = _read_local_image_manifest()
    relative_base = Path("assets") / "card_images"
    mapped: dict[str, str] = {}

    for card_id in CARD_CATALOG:
        entry = manifest_data.get(card_id)
        if isinstance(entry, dict):
            file_name = entry.get("file")
            if isinstance(file_name, str) and file_name:
                mapped[card_id] = str(relative_base / file_name)
                continue

        candidates = sorted(CARD_IMAGE_CACHE_MANIFEST.parent.glob(f"{card_id}.*"))
        if candidates:
            mapped[card_id] = str(relative_base / candidates[0].name)

    return mapped


CARD_IMAGE_URLS: dict[str, str] = _build_local_card_image_map()


for _card_id, _card in CARD_CATALOG.items():
    _card["image"] = _card.get("image") or CARD_IMAGE_URLS.get(_card_id) or default_card_image(_card_id)


def _validate_no_remote_image_paths() -> None:
    remote_ids = [
        card_id
        for card_id, card in CARD_CATALOG.items()
        if isinstance(card.get("image"), str) and card["image"].startswith(("http://", "https://"))
    ]
    if remote_ids:
        raise RuntimeError(
            "Remote image URLs are not allowed in local-only mode for: " + ", ".join(sorted(remote_ids))
        )


_validate_no_remote_image_paths()


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


def search_card_ids(query: str, *, include_series: bool = False) -> list[str]:
    cleaned_query = query.strip().casefold()
    if not cleaned_query:
        return []

    exact_name_matches: list[str] = []
    prefix_name_matches: list[str] = []
    contains_name_matches: list[str] = []
    exact_series_matches: list[str] = []
    prefix_series_matches: list[str] = []
    contains_series_matches: list[str] = []

    for card_id, card in CARD_CATALOG.items():
        card_name = card["name"]
        normalized_name = card_name.casefold()
        if normalized_name == cleaned_query:
            exact_name_matches.append(card_id)
        elif normalized_name.startswith(cleaned_query):
            prefix_name_matches.append(card_id)
        elif cleaned_query in normalized_name:
            contains_name_matches.append(card_id)

        if include_series:
            normalized_series = card["series"].casefold()
            if normalized_series == cleaned_query:
                exact_series_matches.append(card_id)
            elif normalized_series.startswith(cleaned_query):
                prefix_series_matches.append(card_id)
            elif cleaned_query in normalized_series:
                contains_series_matches.append(card_id)

    key = lambda cid: (CARD_CATALOG[cid]["name"].casefold(), cid)

    ordered_groups = [
        sorted(exact_name_matches, key=key),
        sorted(prefix_name_matches, key=key),
        sorted(contains_name_matches, key=key),
    ]
    if include_series:
        ordered_groups.extend(
            [
                sorted(exact_series_matches, key=key),
                sorted(prefix_series_matches, key=key),
                sorted(contains_series_matches, key=key),
            ]
        )

    seen: set[str] = set()
    results: list[str] = []
    for group in ordered_groups:
        for card_id in group:
            if card_id in seen:
                continue
            seen.add(card_id)
            results.append(card_id)
    return results


def search_card_ids_by_name(query: str) -> list[str]:
    return search_card_ids(query)


def card_code(card_id: str, dupe_code: str) -> str:
    return dupe_code.strip().lower()


def split_card_code(raw_code: str) -> str | None:
    cleaned = raw_code.strip()
    if not cleaned:
        return None

    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
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
        f"**{card['name']}** • (`{card_id}`) "
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
    x = random.betavariate(1.6, 1.04)
    return int(max(GENERATION_MIN, min(GENERATION_MAX, GENERATION_MAX * x)))


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
    return 1.0 + (2 * progress ** 2) + (9 * progress ** 9) + (49 * progress ** 49)


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
