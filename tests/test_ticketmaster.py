import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from concertrip.db import Base
from concertrip.models import Artist, Event, EventTicketOption, Source, Venue
from concertrip.sources.ticketmaster import (
    TicketmasterClient,
    TicketmasterError,
    parse_event,
    parse_page,
    upsert_event,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ticketmaster" / "events_page.json"


def test_parse_page_maps_confirmed_and_tba_events():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events = parse_page(payload)

    assert len(events) == 2
    confirmed, tba = events
    assert confirmed.external_id == "tm-confirmed-001"
    assert confirmed.artist_external_id == "tm-artist-001"
    assert confirmed.country_code == "GB"
    assert confirmed.date_status == "confirmed"
    assert confirmed.event_date is not None
    assert len(confirmed.price_ranges) == 2
    assert confirmed.price_ranges[0].currency == "GBP"
    assert tba.date_status == "tba"
    assert tba.event_date is None


def test_parse_page_skips_malformed_event():
    payload = {"_embedded": {"events": [{"id": "missing-venue"}]}}
    assert parse_page(payload) == []


def test_client_paginates_and_sends_ticketmaster_params():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    with TicketmasterClient(
        "secret-key",
        transport=httpx.MockTransport(handler),
        sleep=lambda _delay: None,
    ) as client:
        events = list(client.iter_events(("GB",), minimum_events=2))

    assert len(events) == 2
    query = dict(requests[0].url.params)
    assert query["apikey"] == "secret-key"
    assert query["countryCode"] == "GB"
    assert query["page"] == "0"
    assert query["size"] == "100"
    assert query["classificationName"] == "music"


def test_client_retries_429_then_succeeds():
    calls = 0
    sleeps = []
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json=payload)

    with TicketmasterClient(
        "secret-key",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    ) as client:
        events = list(client.iter_events(("GB",), minimum_events=1))

    assert events
    assert calls == 2
    assert sleeps


def test_client_does_not_retry_invalid_key():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"fault": {"faultstring": "Invalid ApiKey"}})

    with TicketmasterClient(
        "bad-key",
        transport=httpx.MockTransport(handler),
        sleep=lambda _delay: None,
    ) as client:
        with pytest.raises(TicketmasterError, match="rejected"):
            list(client.iter_events(("GB",), minimum_events=1))

    assert calls == 1


def test_upsert_is_idempotent_and_preserves_price_ranges(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    incoming = parse_page(payload)[0]
    engine = create_engine(f"sqlite:///{tmp_path / 'ticketmaster.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with Session(engine) as session:
        source = Source(code="ticketmaster", name="Ticketmaster Discovery")
        session.add(source)
        session.flush()
        assert upsert_event(session, source, incoming) is True
        session.commit()
        assert upsert_event(session, source, incoming) is False
        session.commit()
        assert session.scalar(select(func.count(Event.id))) == 1
        assert session.scalar(select(func.count(EventTicketOption.id))) == 2
        assert session.scalar(select(func.count(Artist.id))) == 1
        assert session.scalar(select(func.count(Venue.id))) == 1
