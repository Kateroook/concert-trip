"""Точність витягу на збережених анонсах і політика непевних дат."""

from __future__ import annotations

import json
from pathlib import Path

from concertrip.extract import extract_announcement, from_model_payload

FOLDER = Path(__file__).resolve().parent / "fixtures" / "announcements"
FIELDS = ("artist", "venue", "city", "country", "event_date", "on_sale_date", "status", "url")


def test_saved_pages_accuracy():
    correct = 0
    total = 0
    pages = sorted(FOLDER.glob("*.txt"))
    assert len(pages) == 20
    for path in pages:
        gold = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        got = extract_announcement(path.read_text(encoding="utf-8"))
        actual = {
            "artist": got.artist_names[0] if got.artist_names else None,
            "venue": got.venue,
            "city": got.city,
            "country": got.country,
            "event_date": got.event_date.isoformat() if got.event_date else None,
            "on_sale_date": got.on_sale_date.isoformat() if got.on_sale_date else None,
            "status": got.status,
            "url": got.url,
        }
        for field in FIELDS:
            total += 1
            correct += actual[field] == gold[field]
    accuracy = correct / total
    assert accuracy >= 0.8


def test_low_confidence_on_sale_is_not_stored():
    vague = from_model_payload(
        {
            "artist_names": ["Radiohead"],
            "event_date": "2027-06-01",
            "on_sale_date": "2026-01-01",
            "confidence": {"event_date": 0.95, "artist": 0.9, "on_sale_date": 0.4},
        }
    )
    assert vague.event_date is not None
    assert vague.on_sale_date is None
    assert "on_sale_date" in vague.low_confidence

    missing = from_model_payload({"on_sale_date": "2026-05-01", "event_date": "2027-06-01"})
    assert missing.on_sale_date is None
    assert missing.event_date is None
