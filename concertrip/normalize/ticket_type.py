"""CT-31. Класифікація типів квитків за правилами.

Назви секторів у продавців різних країн не збігаються, тому перед
порівнянням із правилами рядок зводиться до спільного вигляду, а потім
перевіряється за словником відповідностей.

Результат: TicketType (STANDING, SEATED, OTHER, UNKNOWN) і ознака VIP.
VIP не є окремим типом, бо буває і стоячий, і сидячий: це додаткова
характеристика поверх основного типу.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class TicketType(str, Enum):
    STANDING = "standing"   # танцпол, фан-зона
    SEATED = "seated"       # сидячі місця
    OTHER = "other"         # ложа, бар, паркінг, кемпінг тощо
    UNKNOWN = "unknown"     # правило не спрацювало


@dataclass(frozen=True)
class Classification:
    ticket_type: TicketType
    is_vip: bool
    matched_rule: str

    def __str__(self) -> str:
        vip = " + VIP" if self.is_vip else ""
        return f"{self.ticket_type.value}{vip}"


def normalize(raw: str) -> str:
    """Знижує регістр, прибирає діакритику й зайві символи.

    Польське 'płyta' і 'plyta', французьке 'numérotée' і 'numerotee'
    мають зводитись до одного рядка, інакше словник доведеться писати
    двічі для кожної мови.
    """
    text = raw.lower().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Порядок має значення: перевіряється зверху вниз, перше влучання виграє.
# Спершу йдуть точні багатослівні вирази, потім окремі слова.
RULES: list[tuple[str, TicketType, list[str]]] = [
    (
        "сидячі місця, явна вказівка",
        TicketType.SEATED,
        [
            "miejsca siedzace", "sektor siedzacy", "siedzace", "trybuna",
            "sitzplatz", "sitzplaetze", "sitzplatze", "rang", "block",
            "place assise", "places assises", "numerotee", "numerotees",
            "seated", "seating", "reserved seat", "grandstand", "balcony",
            "stalls", "circle", "tier",
            "sidyachi", "sydiachi", "misce", "miscya", "amfiteatr",
            "ryad", "ryadu",
        ],
    ),
    (
        "стояча зона, явна вказівка",
        TicketType.STANDING,
        [
            "plyta", "plyta stojaca", "sektor stojacy", "strefa stojaca",
            "stojacy", "stojaca", "przed sceną", "przed scena",
            "stehplatz", "stehplaetze", "stehplatze", "innenraum",
            "fosse", "fosse or", "debout", "parterre debout",
            "standing", "general admission", "ga", "floor", "pit",
            "front of stage", "early entry",
            "tantspol", "tanzpol", "fan zona", "fanzona", "fan zone",
            "tancpol", "tancyuvalnyi mardanchyk",
        ],
    ),
    (
        "інші категорії",
        TicketType.OTHER,
        [
            "loza", "lozha", "box", "skybox", "suite", "lounge",
            "parking", "camping", "kemping", "shuttle", "wardrobe",
            "merch", "bar", "restauracja", "hospitality",
        ],
    ),
]

VIP_MARKERS = ["vip", "premium", "golden circle", "gold circle", "early access", "meet and greet", "meet greet"]

# Українські й польські слова з літерами, які не зводяться транслітерацією.
CYRILLIC_MAP = {
    "танцпол": "tantspol",
    "танцювальний майданчик": "tancyuvalnyi mardanchyk",
    "фан-зона": "fan zona",
    "фанзона": "fanzona",
    "фан зона": "fan zona",
    "сидячі": "sidyachi",
    "сидяче": "sidyachi",
    "місце": "misce",
    "місця": "miscya",
    "ряд": "ryad",
    "сектор": "sektor",
    "амфітеатр": "amfiteatr",
    "ложа": "lozha",
    "балкон": "balcony",
    "партер": "parterre",
}


def _transliterate(text: str) -> str:
    for src, dst in CYRILLIC_MAP.items():
        text = text.replace(src, dst)
    return text


def classify(raw: str) -> Classification:
    """Повертає тип квитка за назвою сектора."""
    if not raw or not raw.strip():
        return Classification(TicketType.UNKNOWN, False, "порожній рядок")

    text = normalize(_transliterate(raw.lower()))
    is_vip = any(re.search(rf"\b{re.escape(m)}\b", text) for m in VIP_MARKERS)

    # "партер" окремо: у залі з кріслами це сидячі місця, у клубі - стоячі.
    # Без контексту майданчика вважаємо сидячими, бо так частіше.
    if re.search(r"\bparterre\b", text) and not re.search(r"\bdebout\b", text):
        return Classification(TicketType.SEATED, is_vip, "партер без позначки стоячих")

    # Перебираємо всі правила й беремо найдовший збіг. Перше влучання тут не
    # годиться: у рядку "Golden Circle Standing" коротке "circle" вказує на
    # сидячі місця, а довше "standing" - на стоячу зону, і праве саме довше.
    best: tuple[int, TicketType, str] | None = None
    for rule_name, ticket_type, patterns in RULES:
        for pattern in patterns:
            if re.search(rf"\b{re.escape(pattern)}\b", text):
                if best is None or len(pattern) > best[0]:
                    best = (len(pattern), ticket_type, f"{rule_name}: {pattern}")

    if best is not None:
        return Classification(best[1], is_vip, best[2])

    if is_vip:
        return Classification(TicketType.OTHER, True, "лише позначка VIP")

    return Classification(TicketType.UNKNOWN, False, "жодне правило не спрацювало")
