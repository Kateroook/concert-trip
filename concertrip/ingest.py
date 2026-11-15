"""Нормалізація і запис RawEvent. Джерела сюди не пишуть самі."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.domain import RawEvent
from concertrip.models import Artist, Event, EventArtist, TicketTypeRow, Venue
from concertrip.normalize.artists import normalize_artist_name
from concertrip.normalize.country import normalize_country
from concertrip.normalize.ticket_type import classify
from concertrip.reference import ARTIST_GENRES, VENUE_CAPACITY

STATUSES = {"available", "limited", "low", "sold_out", "unknown"}


@dataclass
class IngestStats:
    upserted: int = 0
    skipped: int = 0


def ingest_events(session: Session, events: list[RawEvent]) -> IngestStats:
    stats = IngestStats()
    seen: set[tuple[str, str]] = set()
    for raw in events:
        key = (raw.source_id, raw.external_id)
        if not raw.external_id or key in seen:
            stats.skipped += 1
            continue
        if _upsert(session, raw):
            seen.add(key)
            stats.upserted += 1
        else:
            stats.skipped += 1
    session.commit()
    return stats


def _upsert(session: Session, raw: RawEvent) -> bool:
    country = normalize_country(raw.country)
    if (
        not country
        or raw.event_date is None
        or not raw.venue
        or not raw.city
        or not any(name.strip() for name in raw.artist_names)
    ):
        return False
    status = raw.status if raw.status in STATUSES else "unknown"
    lineup = [name.strip() for name in (raw.lineup or []) if name.strip()]
    ordered: list[tuple[Artist, str]] = []
    seen_ids: set[int] = set()
    for raw_name in list(raw.artist_names) + lineup:
        artist = _artist(session, raw_name)
        if artist is None or artist.id in seen_ids:
            continue
        seen_ids.add(artist.id)
        ordered.append((artist, raw_name.strip()))
    if not ordered:
        return False
    venue = _venue(session, raw.venue.strip(), raw.city.strip(), country)
    event = session.scalar(
        select(Event).where(Event.source_id == raw.source_id, Event.external_id == raw.external_id)
    )
    lineup_json = json.dumps(lineup, ensure_ascii=False) if lineup else None
    if event is None:
        event = Event(
            source_id=raw.source_id,
            external_id=raw.external_id,
            venue_id=venue.id,
            event_date=raw.event_date,
            on_sale_date=raw.on_sale_date,
            presale_date=raw.presale_date,
            status=status,
            url=raw.url or "",
            is_festival=raw.is_festival,
            lineup_json=lineup_json,
        )
        session.add(event)
        session.flush()
    else:
        event.venue_id = venue.id
        event.event_date = raw.event_date
        event.on_sale_date = raw.on_sale_date
        event.presale_date = raw.presale_date
        event.status = status
        event.url = raw.url or ""
        event.is_festival = raw.is_festival
        event.lineup_json = lineup_json
        event.artists_link.clear()
        event.ticket_types.clear()
        session.flush()

    for position, (artist, raw_name) in enumerate(ordered):
        event.artists_link.append(
            EventArtist(artist_id=artist.id, raw_name=raw_name, position=position)
        )
    for raw_ticket in raw.ticket_types_raw:
        if not raw_ticket.strip():
            continue
        classified = classify(raw_ticket)
        event.ticket_types.append(
            TicketTypeRow(
                raw_name=raw_ticket.strip(),
                normalized_type=classified.ticket_type.value,
                is_vip=classified.is_vip,
            )
        )
    return True


def _venue(session: Session, name: str, city: str, country: str) -> Venue:
    venue = session.scalar(
        select(Venue).where(Venue.name == name, Venue.city == city, Venue.country == country)
    )
    if venue is not None:
        return venue
    venue = Venue(
        name=name,
        city=city,
        country=country,
        capacity=VENUE_CAPACITY.get((name, city, country)),
    )
    session.add(venue)
    session.flush()
    return venue


def _artist(session: Session, raw_name: str) -> Artist | None:
    normalized = normalize_artist_name(raw_name)
    if not normalized:
        return None
    artist = session.scalar(select(Artist).where(Artist.normalized_name == normalized))
    if artist is not None:
        if not artist.genres and normalized in ARTIST_GENRES:
            artist.genres = ARTIST_GENRES[normalized]
        return artist
    artist = Artist(
        name=raw_name.strip(),
        normalized_name=normalized,
        genres=ARTIST_GENRES.get(normalized),
    )
    session.add(artist)
    session.flush()
    return artist
