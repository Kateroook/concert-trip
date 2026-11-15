"""Стрічка подій: фільтри і порядок за списком відстеження."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from concertrip.models import Event, EventArtist, TicketTypeRow, Venue
from concertrip.ranking.score import relevance
from concertrip.watchlist import liked_genre_set, watch_id_set


def query_feed(
    session: Session,
    *,
    country: str | None = None,
    ticket_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    watchlist_only: bool = False,
    source_id: str | None = None,
    today: date | None = None,
) -> list[Event]:
    today = today or date.today()
    stmt = (
        select(Event)
        .join(Venue)
        .options(
            selectinload(Event.venue),
            selectinload(Event.artists_link).selectinload(EventArtist.artist),
            selectinload(Event.ticket_types),
        )
        .where(Event.event_date >= (date_from or today))
    )
    if date_to is not None:
        stmt = stmt.where(Event.event_date <= date_to)
    if country:
        stmt = stmt.where(Venue.country == country)
    if source_id:
        stmt = stmt.where(Event.source_id == source_id)
    if ticket_type:
        stmt = stmt.where(
            Event.id.in_(
                select(TicketTypeRow.event_id).where(TicketTypeRow.normalized_type == ticket_type)
            )
        )
    events = list(session.scalars(stmt).unique().all())
    watch_ids = watch_id_set(session)
    if watchlist_only:
        events = [event for event in events if {link.artist_id for link in event.artists_link} & watch_ids]
    liked = liked_genre_set(session)
    events.sort(key=lambda event: (relevance(event, watch_ids, liked, today), -event.event_date.toordinal()), reverse=True)
    return events
