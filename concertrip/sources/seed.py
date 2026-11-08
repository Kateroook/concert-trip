"""Імпорт резервного набору подій із CSV."""

from __future__ import annotations

import csv
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.config import settings
from concertrip.db import SessionLocal
from concertrip.models import Artist, Event, EventTicketOption, Source, Venue
from concertrip.normalize.ticket_type import classify

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportResult:
    rows_seen: int
    events_created: int
    events_updated: int
    rows_skipped: int


def _normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _get_or_create_artist(session: Session, name: str) -> Artist:
    normalized_name = _normalize_name(name)
    artist = session.scalar(select(Artist).where(Artist.normalized_name == normalized_name))
    if artist is None:
        artist = Artist(name=name, normalized_name=normalized_name)
        session.add(artist)
    return artist


def _get_or_create_venue(session: Session, name: str, city: str, country: str) -> Venue:
    normalized_name = _normalize_name(name)
    venue = session.scalar(
        select(Venue).where(
            Venue.normalized_name == normalized_name,
            Venue.city == city,
            Venue.country_code == country,
        )
    )
    if venue is None:
        venue = Venue(
            name=name,
            normalized_name=normalized_name,
            city=city,
            country_code=country,
        )
        session.add(venue)
    return venue


def import_seed(
    csv_path: Path = settings.seed_csv,
    session_factory: Callable[[], Session] = SessionLocal,
) -> ImportResult:
    """Імпортує CSV і безпечно повторює імпорт без дублікатів."""
    result = ImportResult(0, 0, 0, 0)

    with session_factory() as session:
        source = session.scalar(select(Source).where(Source.code == "seed"))
        if source is None:
            source = Source(code="seed", name="Seed data")
            session.add(source)
            session.flush()

        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row_number, row in enumerate(reader, start=2):
                result = ImportResult(
                    result.rows_seen + 1,
                    result.events_created,
                    result.events_updated,
                    result.rows_skipped,
                )
                try:
                    external_id = (row.get("external_id") or "").strip()
                    required = ("artist", "venue", "city", "country", "event_date", "url")
                    if not external_id or any(not (row.get(field) or "").strip() for field in required):
                        raise ValueError("missing required field")

                    artist = _get_or_create_artist(session, row["artist"].strip())
                    venue = _get_or_create_venue(
                        session,
                        row["venue"].strip(),
                        row["city"].strip(),
                        row["country"].strip().upper(),
                    )
                    event = session.scalar(
                        select(Event).where(
                            Event.source_id == source.id,
                            Event.external_id == external_id,
                        )
                    )
                    classification = classify(row.get("ticket_type_raw", ""))
                    event_values = {
                        "artist": artist,
                        "venue": venue,
                        "external_id": external_id,
                        "title": row["artist"].strip(),
                        "event_date": _parse_date(row["event_date"].strip()),
                        "on_sale_at": _parse_date(row["on_sale_date"].strip())
                        if (row.get("on_sale_date") or "").strip()
                        else None,
                        "status": row.get("status", "unknown").strip() or "unknown",
                        "url": row["url"].strip(),
                    }
                    if event is None:
                        event = Event(source=source, **event_values)
                        session.add(event)
                        session.flush()
                        result = ImportResult(
                            result.rows_seen,
                            result.events_created + 1,
                            result.events_updated,
                            result.rows_skipped,
                        )
                    else:
                        for field, value in event_values.items():
                            setattr(event, field, value)
                        result = ImportResult(
                            result.rows_seen,
                            result.events_created,
                            result.events_updated + 1,
                            result.rows_skipped,
                        )

                    raw_label = row.get("ticket_type_raw", "").strip() or "Unknown"
                    option = session.scalar(
                        select(EventTicketOption).where(
                            EventTicketOption.event_id == event.id,
                            EventTicketOption.raw_label == raw_label,
                        )
                    )
                    option_values = {
                        "source": source,
                        "raw_label": raw_label,
                        "ticket_type": classification.ticket_type.value,
                        "is_vip": classification.is_vip,
                        "availability_status": event.status,
                        "url": event.url,
                    }
                    if option is None:
                        event.ticket_options.append(EventTicketOption(**option_values))
                    else:
                        for field, value in option_values.items():
                            setattr(option, field, value)
                except (KeyError, ValueError):
                    logger.exception("Skipping seed row %s", row_number)
                    result = ImportResult(
                        result.rows_seen,
                        result.events_created,
                        result.events_updated,
                        result.rows_skipped + 1,
                    )

        session.commit()
    return result


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    result = import_seed()
    logger.info(
        "Seed import completed: rows=%s created=%s updated=%s skipped=%s",
        result.rows_seen,
        result.events_created,
        result.events_updated,
        result.rows_skipped,
    )


if __name__ == "__main__":
    main()
