from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from concertrip.api.schemas import EventItem
from concertrip.models import Artist, Event, Venue


def list_events(
    session: Session,
    *,
    query: Optional[str],
    country: Optional[str],
    status: Optional[str],
    page: int,
    page_size: int,
) -> tuple[list[EventItem], int]:
    statement = (
        select(Event)
        .join(Event.artist)
        .join(Event.venue)
        .options(selectinload(Event.ticket_options))
    )
    if query:
        search = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                Artist.name.ilike(search),
                Venue.name.ilike(search),
                Venue.city.ilike(search),
            )
        )
    if country:
        statement = statement.where(Venue.country_code == country.upper())
    if status:
        statement = statement.where(Event.status == status)

    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = session.scalar(count_statement) or 0
    rows = session.scalars(
        statement.order_by(Event.event_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    items = []
    for event in rows:
        option = event.ticket_options[0] if event.ticket_options else None
        items.append(
            EventItem(
                id=event.id,
                artist=event.artist.name,
                venue=event.venue.name,
                city=event.venue.city,
                country=event.venue.country_code,
                eventDate=event.event_date.date() if event.event_date else None,
                onSaleDate=event.on_sale_at.date() if event.on_sale_at else None,
                dateStatus=event.date_status,
                ticketType=option.raw_label if option else "Unknown",
                status=event.status,
                url=event.url,
            )
        )
    return items, total
