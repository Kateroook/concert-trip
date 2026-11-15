"""Зведення імені артиста до ключа, за яким шукаємо дублікати.

MusicBrainz не викликаємо: без мережі ідентифікатор лишається порожнім.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_artist_name(name: str) -> str:
    text = (name or "").strip().lower().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    return text
