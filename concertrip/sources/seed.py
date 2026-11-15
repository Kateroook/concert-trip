"""Імпорт резервного набору подій із CSV. Мережа не потрібна."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from concertrip.config import settings
from concertrip.domain import RawEvent
from concertrip.normalize.country import normalize_country

SOURCE_ID = "seed"


def _date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _split(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def parse_csv(text: str, source_id: str = SOURCE_ID) -> list[RawEvent]:
    rows = csv.DictReader(text.splitlines())
    events: list[RawEvent] = []
    for row in rows:
        event_date = _date(row.get("event_date", ""))
        country = normalize_country(row.get("country", ""))
        artists = _split(row.get("artists") or row.get("artist") or "")
        external_id = (row.get("external_id") or "").strip()
        if not event_date or not country or not artists or not external_id:
            continue
        status = (row.get("status") or "unknown").strip().lower()
        if status not in {"available", "limited", "low", "sold_out", "unknown"}:
            status = "unknown"
        events.append(
            RawEvent(
                source_id=source_id,
                external_id=external_id,
                artist_names=artists,
                venue=(row.get("venue") or "").strip(),
                city=(row.get("city") or "").strip(),
                country=country,
                event_date=event_date,
                ticket_types_raw=_split(row.get("ticket_types") or row.get("ticket_type_raw") or ""),
                on_sale_date=_date(row.get("on_sale_date", "")),
                presale_date=_date(row.get("presale_date", "")),
                status=status,
                url=(row.get("url") or "").strip(),
                is_festival=(row.get("is_festival") or "").strip() in {"1", "true", "yes"},
                lineup=_split(row.get("lineup") or "") or None,
            )
        )
    return events


class SeedSource:
    source_id = SOURCE_ID

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or settings.seed_csv)

    def fetch(self, since: date) -> list[RawEvent]:
        if not self.path.exists():
            return []
        events = parse_csv(self.path.read_text(encoding="utf-8"))
        return [event for event in events if event.event_date >= since and event.venue and event.city]


def main() -> None:
    events = SeedSource().fetch(date.min)
    print(f"seed: {len(events)}")
