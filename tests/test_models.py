from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from concertrip.db import Base
from concertrip.models import Artist, Event, EventTicketOption, Source, Venue


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    @sqlalchemy_event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def make_event(session: Session, external_id: str = "seed-001") -> Event:
    source = Source(code=f"seed-{external_id}", name="Seed")
    artist = Artist(name="Tame Impala", normalized_name="tame impala")
    venue = Venue(
        name="The O2",
        normalized_name="the o2",
        city="London",
        country_code="GB",
    )
    concert = Event(
        source=source,
        artist=artist,
        venue=venue,
        external_id=external_id,
        event_date=datetime(2027, 6, 1, tzinfo=timezone.utc),
        status="available",
        url="https://example.org/event",
    )
    concert.ticket_options.append(
        EventTicketOption(
            source=source,
            raw_label="Standing - General Admission",
            ticket_type="standing",
            availability_status="available",
        )
    )
    session.add(concert)
    session.commit()
    return concert


def test_event_graph_and_ticket_option_cascade(session):
    concert = make_event(session)

    stored = session.scalar(select(Event).where(Event.external_id == "seed-001"))
    assert stored is not None
    assert stored.artist.name == "Tame Impala"
    assert stored.ticket_options[0].ticket_type == "standing"

    session.delete(stored)
    session.commit()
    assert session.scalar(select(EventTicketOption.id)) is None


def test_external_id_is_unique_per_source(session):
    make_event(session, "same-id")
    with pytest.raises(IntegrityError):
        make_event(session, "same-id")
    session.rollback()


def test_nullable_event_fields_are_optional(session):
    concert = make_event(session)
    assert concert.on_sale_at is None
    assert concert.title is None
    assert concert.raw_payload is None
