"""Зведення країни до ISO-коду. Невідому назву не вгадуємо."""

from __future__ import annotations

import re

_NAMES = {
    "POLAND": "PL",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "NETHERLANDS": "NL",
    "THE NETHERLANDS": "NL",
    "UNITED KINGDOM": "GB",
    "GREAT BRITAIN": "GB",
    "ENGLAND": "GB",
    "UK": "GB",
}


def normalize_country(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().upper()
    if text in _NAMES:
        return _NAMES[text]
    if re.fullmatch(r"[A-Z]{2}", text):
        return text
    return None
