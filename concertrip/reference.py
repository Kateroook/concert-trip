"""Локальні довідники: зали, жанри, зони для оцінки поїздки.

Цифри тут не виводяться з анонсу. Немає запису — поле лишається порожнім.
"""

from __future__ import annotations

import re
import unicodedata

# name, city, country, capacity
VENUES: list[tuple[str, str, str, int]] = [
    ("Co-op Live", "Manchester", "GB", 23000),
    ("The O2", "London", "GB", 20000),
    ("Alexandra Palace", "London", "GB", 10400),
    ("Roundhouse", "London", "GB", 3300),
    ("Barrowland", "Glasgow", "GB", 1900),
    ("Utilita Arena", "Birmingham", "GB", 15800),
    ("Victoria Park", "London", "GB", 40000),
    ("Larmer Tree Gardens", "Salisbury", "GB", 15000),
    ("Rotterdam Ahoy", "Rotterdam", "NL", 15000),
    ("AFAS Live", "Amsterdam", "NL", 6000),
    ("Ziggo Dome", "Amsterdam", "NL", 17000),
    ("Paradiso", "Amsterdam", "NL", 1500),
    ("Evenemententerrein", "Biddinghuizen", "NL", 55000),
    ("Lanxess Arena", "Koeln", "DE", 20000),
    ("Columbiahalle", "Berlin", "DE", 3500),
    ("Velodrom", "Berlin", "DE", 12000),
    ("Elbphilharmonie", "Hamburg", "DE", 2100),
    ("Olympiahalle", "Munich", "DE", 15000),
    ("Ferropolis", "Grafenhainichen", "DE", 20000),
    ("Accor Arena", "Paris", "FR", 20300),
    ("Olympia", "Paris", "FR", 2000),
    ("Zenith", "Paris", "FR", 6300),
    ("Le Transbordeur", "Lyon", "FR", 1300),
    ("Domaine national", "Saint-Cloud", "FR", 30000),
    ("COS Torwar", "Warsaw", "PL", 7000),
    ("Stodola", "Warsaw", "PL", 2000),
    ("Tauron Arena", "Krakow", "PL", 15000),
    ("Ergo Arena", "Gdansk", "PL", 15000),
    ("Lotnisko Gdynia", "Gdynia", "PL", 40000),
]

VENUE_CAPACITY: dict[tuple[str, str, str], int] = {
    (name, city, country): capacity for name, city, country, capacity in VENUES
}

# Нормалізоване ім'я -> один основний жанр. Невідомих тут немає навмисно.
ARTIST_GENRES: dict[str, str] = {
    "tame impala": "psychedelic",
    "radiohead": "alternative",
    "bjork": "art pop",
    "rosalia": "flamenco",
    "fontaines dc": "post punk",
    "idles": "post punk",
    "wet leg": "indie",
    "bon iver": "indie",
    "charli xcx": "pop",
    "fred again": "electronic",
    "bicep": "electronic",
    "moderat": "electronic",
    "nils frahm": "contemporary classical",
    "khruangbin": "psychedelic",
    "little simz": "hip hop",
    "slowdive": "shoegaze",
    "beach house": "dream pop",
    "phoenix": "indie",
    "justice": "electronic",
    "caribou": "electronic",
    "four tet": "electronic",
    "jamie xx": "electronic",
    "peggy gou": "electronic",
    "overmono": "electronic",
    "parcels": "indie",
    "smile": "alternative",
    "warpaint": "indie",
    "blood orange": "rnb",
    "fka twigs": "art pop",
    "arca": "electronic",
    "caroline polachek": "pop",
    "yves tumor": "experimental",
    "squid": "post punk",
    "dry cleaning": "post punk",
    "yard act": "post punk",
    "confidence man": "dance",
    "turnstile": "hardcore",
    "black country new road": "post punk",
    "kim gordon": "alternative",
    "mount kimbie": "electronic",
}

ARTIST_NAMES: list[str] = [
    "Tame Impala",
    "Radiohead",
    "Bjork",
    "Rosalia",
    "Fontaines DC",
    "Idles",
    "Wet Leg",
    "Bon Iver",
    "Charli XCX",
    "Fred again",
    "Bicep",
    "Moderat",
    "Nils Frahm",
    "Khruangbin",
    "Little Simz",
    "Slowdive",
    "Beach House",
    "Phoenix",
    "Justice",
    "Caribou",
    "Four Tet",
    "Jamie xx",
    "Peggy Gou",
    "Overmono",
    "Parcels",
    "The Smile",
    "Warpaint",
    "Blood Orange",
    "FKA twigs",
    "Arca",
    "Caroline Polachek",
    "Yves Tumor",
    "Squid",
    "Dry Cleaning",
    "Yard Act",
    "Confidence Man",
    "Turnstile",
    "Black Country New Road",
    "Kim Gordon",
    "Mount Kimbie",
]

# Зона міста для статичної таблиці вартості. 0 — Україна, далі на захід.
ZONES: dict[str, int] = {
    "kyiv": 0,
    "warsaw": 1,
    "krakow": 1,
    "gdansk": 1,
    "gdynia": 1,
    "berlin": 2,
    "hamburg": 2,
    "munich": 2,
    "koeln": 2,
    "grafenhainichen": 2,
    "amsterdam": 3,
    "rotterdam": 3,
    "biddinghuizen": 3,
    "paris": 4,
    "lyon": 4,
    "saint cloud": 4,
    "london": 5,
    "manchester": 5,
    "birmingham": 5,
    "glasgow": 5,
    "salisbury": 5,
}

# Пара зон (менша, більша) -> (нижня, верхня) межа в євро.
TRIP_RANGES: dict[tuple[int, int], tuple[int, int]] = {
    (0, 1): (40, 140),
    (0, 2): (90, 280),
    (0, 3): (110, 320),
    (0, 4): (120, 360),
    (0, 5): (150, 420),
    (1, 2): (40, 160),
    (1, 3): (50, 190),
    (1, 4): (70, 220),
    (1, 5): (90, 280),
    (2, 3): (40, 160),
    (2, 4): (60, 200),
    (2, 5): (80, 260),
    (3, 4): (50, 190),
    (3, 5): (70, 240),
    (4, 5): (70, 250),
}

BIG_CITIES = {
    "london",
    "paris",
    "berlin",
    "amsterdam",
    "warsaw",
    "manchester",
    "hamburg",
    "munich",
    "koeln",
    "rotterdam",
    "krakow",
}

ORIGIN_CITIES: list[tuple[str, str]] = [
    ("Kyiv", "Київ"),
    ("Warsaw", "Варшава"),
    ("Krakow", "Краків"),
    ("Berlin", "Берлін"),
    ("Amsterdam", "Амстердам"),
    ("Paris", "Париж"),
    ("London", "Лондон"),
]


def city_key(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("ł", "l")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text
