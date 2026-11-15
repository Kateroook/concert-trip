"""Знімки статусу позначених подій і черга сповіщень."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from concertrip.models import Alert, AvailabilitySnapshot, Event, EventArtist, WatchEvent
from concertrip.notify.messages import availability_message

UNAVAILABLE = {"sold_out", "unknown"}
AVAILABLE = {"available", "limited", "low"}


def filter_matches(event: Event, ticket_filter: str) -> bool:
    if ticket_filter in {"", "any"}:
        return True
    return any(row.normalized_type == ticket_filter for row in event.ticket_types)


def check_availability(session: Session, now: datetime | None = None) -> list[Alert]:
    now = now or datetime.now(timezone.utc)
    created: list[Alert] = []
    watches = session.scalars(select(WatchEvent)).all()
    for watch in watches:
        event = session.scalar(
            select(Event)
            .where(Event.id == watch.event_id)
            .options(
                selectinload(Event.venue),
                selectinload(Event.ticket_types),
                selectinload(Event.artists_link).selectinload(EventArtist.artist),
            )
        )
        if event is None:
            continue
        previous = session.scalar(
            select(AvailabilitySnapshot)
            .where(AvailabilitySnapshot.event_id == event.id)
            .order_by(AvailabilitySnapshot.captured_at.desc())
        )
        session.add(AvailabilitySnapshot(event_id=event.id, status=event.status, captured_at=now))
        became_available = (
            previous is not None
            and previous.status in UNAVAILABLE
            and event.status in AVAILABLE
            and filter_matches(event, watch.ticket_type_filter)
        )
        if not became_available:
            continue
        already = session.scalar(
            select(Alert).where(
                Alert.watch_event_id == watch.id,
                Alert.kind == "availability",
                Alert.status == "queued",
            )
        )
        if already is not None:
            continue
        created.append(
            Alert(
                watch_event_id=watch.id,
                event_id=event.id,
                kind="availability",
                body=availability_message(session, event, watch.ticket_type_filter),
                status="queued",
                created_at=now,
            )
        )
    session.add_all(created)
    session.commit()
    return created


def simulate_restock(session: Session, event_id: int) -> Alert | None:
    event = session.get(Event, event_id)
    if event is None:
        return None
    now = datetime.now(timezone.utc)
    session.add(
        AvailabilitySnapshot(
            event_id=event.id,
            status="sold_out",
            captured_at=now - timedelta(minutes=5),
        )
    )
    event.status = "available"
    session.commit()
    alerts = check_availability(session, now=now)
    for alert in alerts:
        if alert.event_id == event_id:
            return alert
    return None
