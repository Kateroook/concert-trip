"""Сховище, збір, список, стрічка, черга, фестиваль, поїздка."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from concertrip.availability import check_availability, simulate_restock
from concertrip.collect import collect
from concertrip.domain import RawEvent
from concertrip.feed import query_feed
from concertrip.ingest import ingest_events
from concertrip.models import (
    Alert,
    Artist,
    AvailabilitySnapshot,
    Event,
    SourceRun,
    TicketTypeRow,
    Venue,
    WatchEvent,
    WatchItem,
)
from concertrip.notify.telegram_bot import deliver_queued, in_quiet_hours
from concertrip.prefs import set_pref
from concertrip.ranking.festival import score_lineup
from concertrip.ranking.urgency import score_urgency
from concertrip.sources.jsonld import JsonLdSource, parse_html
from concertrip.sources.local_parser import parse_listing
from concertrip.sources.registry import local_sources
from concertrip.sources.seed import SeedSource
from concertrip.sources.ticketmaster import TicketmasterSource, parse_payload
from concertrip.trip import estimate_trip
from concertrip.watchlist import follow_name, set_watch_event

ROOT = Path(__file__).resolve().parent.parent


def test_round_trip_every_table(session):
    artist = Artist(name="Idles", normalized_name="idles", genres="post punk")
    session.add(artist)
    session.flush()
    venue = Venue(name="Stodola", city="Warsaw", country="PL", capacity=2000)
    session.add(venue)
    session.flush()
    event = Event(
        source_id="seed",
        external_id="round",
        venue_id=venue.id,
        event_date=date(2027, 5, 1),
        status="unknown",
        url="https://example.org/round",
    )
    session.add(event)
    session.flush()
    session.add(TicketTypeRow(event_id=event.id, raw_name="Płyta", normalized_type="standing", is_vip=False))
    session.add(WatchItem(artist_id=artist.id))
    session.add(WatchEvent(event_id=event.id, ticket_type_filter="standing"))
    session.add(Alert(event_id=event.id, kind="availability", body="тест", status="queued"))
    session.add(AvailabilitySnapshot(event_id=event.id, status="unknown"))
    session.add(SourceRun(source_id="seed", events_found=1))
    session.commit()
    assert session.get(Event, event.id).external_id == "round"
    assert session.query(Alert).count() == 1


def test_seed_has_300_events_offline():
    events = SeedSource().fetch(date(2026, 11, 1))
    assert len(events) == 300
    assert {event.country for event in events} >= {"GB", "NL", "DE", "FR", "PL"}


def test_dedup_and_three_local_sources(session):
    runs = collect(session, local_sources())
    assert {run.source_id for run in runs} == {"seed", "jsonld", "ebilet"}
    first = session.query(Event).count()
    assert first > 300
    again = collect(session, local_sources())
    assert session.query(Event).count() == first
    assert all(run.errors is None or run.errors.startswith("пропущено") for run in again)


def test_jsonld_and_listing_parse_saved_pages():
    html = (ROOT / "data" / "fixtures" / "jsonld" / "events.html").read_text(encoding="utf-8")
    events = parse_html(html)
    assert len(events) >= 20
    assert any(event.is_festival for event in events)
    listing = (ROOT / "data" / "fixtures" / "ebilet" / "listing.html").read_text(encoding="utf-8")
    parsed = parse_listing(listing)
    assert len(parsed) == 20
    assert parsed[0].country == "DE" or parsed[0].country in {"GB", "NL", "DE", "FR", "PL"}


def test_robots_disallow_skips_live_url():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /secret\n")
        raise AssertionError("сторінку не мали читати")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = JsonLdSource(paths=[], urls=["http://tickets.test/secret/show"], client=client, delay=0)
    assert source.fetch(date(2026, 1, 1)) == []


def test_ticketmaster_parses_fixture_without_network():
    payload = {
        "_embedded": {
            "events": [
                {
                    "id": "vv1",
                    "name": "Radiohead",
                    "url": "https://example.org/tm",
                    "dates": {"start": {"localDate": "2027-06-01"}, "status": {"code": "onsale"}},
                    "sales": {"public": {"startDateTime": "2026-09-01T10:00:00Z"}},
                    "_embedded": {
                        "venues": [
                            {
                                "name": "The O2",
                                "city": {"name": "London"},
                                "country": {"countryCode": "GB"},
                            }
                        ],
                        "attractions": [{"name": "Radiohead"}],
                    },
                },
                {
                    "id": "skip-me",
                    "name": "No date",
                    "dates": {"start": {}, "status": {"code": "onsale"}},
                    "_embedded": {"venues": [{"name": "X", "city": {"name": "Paris"}, "country": {"countryCode": "FR"}}]},
                },
            ]
        },
        "page": {"totalPages": 1},
    }
    events = parse_payload(payload)
    assert len(events) == 1
    assert events[0].on_sale_date == date(2026, 9, 1)
    assert events[0].country == "GB"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("ConcerTrip")
        assert request.url.params["apikey"] == "test-key"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "ConcerTrip/0.1"})
    found = TicketmasterSource(api_key="test-key", countries=("GB",), client=client, delay=0, pages=1).fetch(
        date(2026, 1, 1)
    )
    assert [event.external_id for event in found] == ["vv1"]
    assert TicketmasterSource(api_key="", client=client, delay=0).fetch(date(2026, 1, 1)) == []


def test_watchlist_filter_and_mark(session):
    ingest_events(
        session,
        [
            RawEvent(
                source_id="seed",
                external_id="a",
                artist_names=["Radiohead"],
                venue="The O2",
                city="London",
                country="GB",
                event_date=date(2027, 6, 1),
                ticket_types_raw=["Standing - General Admission"],
                on_sale_date=None,
                presale_date=None,
                status="available",
                url="https://example.org/a",
            ),
            RawEvent(
                source_id="seed",
                external_id="b",
                artist_names=["Someone Else"],
                venue="Olympia",
                city="Paris",
                country="FR",
                event_date=date(2027, 6, 2),
                ticket_types_raw=["Place assise"],
                on_sale_date=None,
                presale_date=None,
                status="available",
                url="https://example.org/b",
            ),
        ],
    )
    follow_name(session, "Radiohead")
    standing = query_feed(session, ticket_type="standing", today=date(2026, 11, 1))
    assert [event.external_id for event in standing] == ["a"]
    mine = query_feed(session, watchlist_only=True, today=date(2026, 11, 1))
    assert [event.external_id for event in mine] == ["a"]
    event = mine[0]
    set_watch_event(session, event.id, "standing")
    assert session.query(WatchEvent).one().ticket_type_filter == "standing"


def test_simulated_restock_queues_alert_and_retries(session):
    ingest_events(
        session,
        [
            RawEvent(
                source_id="seed",
                external_id="restock",
                artist_names=["Idles"],
                venue="Stodola",
                city="Warsaw",
                country="PL",
                event_date=date(2027, 3, 4),
                ticket_types_raw=["Płyta stojąca"],
                on_sale_date=date(2026, 9, 1),
                presale_date=None,
                status="sold_out",
                url="https://example.org/idles",
            )
        ],
    )
    event = session.query(Event).one()
    set_watch_event(session, event.id, "standing")
    alert = simulate_restock(session, event.id)
    assert alert is not None
    assert "КВИТКИ" in alert.body
    assert alert.status == "queued"
    assert check_availability(session) == []

    set_pref(session, "telegram_chat_id", "42")
    set_pref(session, "quiet_start", "23")
    set_pref(session, "quiet_end", "8")
    night = datetime(2026, 11, 16, 23, 30, tzinfo=timezone.utc)
    assert in_quiet_hours(night, 23, 8)
    assert deliver_queued(session, lambda chat, text: None, now=night) == 0

    noon = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)

    def fail(chat, text):
        raise RuntimeError("мережа")

    assert deliver_queued(session, fail, now=noon) == 0
    assert deliver_queued(session, fail, now=noon) == 0
    assert deliver_queued(session, fail, now=noon) == 0
    failed = session.get(Alert, alert.id)
    assert failed.status == "failed"
    assert failed.attempts == 3


def test_urgency_and_trip_do_not_invent(session):
    venue = Venue(name="Невідома зала", city="Nowhereville", country="PL", capacity=None)
    session.add(venue)
    session.flush()
    event = Event(
        source_id="seed",
        external_id="u",
        venue_id=venue.id,
        event_date=date(2027, 12, 1),
        status="available",
        url="",
    )
    session.add(event)
    session.commit()
    urgency = score_urgency(event, None, today=date(2026, 11, 16))
    assert urgency.level == "low"
    assert "Замало даних" in urgency.text
    assert estimate_trip("Kyiv", "Nowhereville") is None
    assert estimate_trip("Kyiv", "London") == (150, 420)


def test_one_beloved_artist_is_not_averaged_away():
    beloved = Artist(id=1, name="Radiohead", normalized_name="radiohead", genres="alternative")
    neutral = Artist(id=2, name="Neutral", normalized_name="neutral", genres=None)
    fine = Artist(id=3, name="Fine", normalized_name="fine", genres="alternative")
    by_key = {"radiohead": beloved, "neutral": neutral, "fine": fine}
    one = score_lineup(["Radiohead", *["Neutral"] * 20], by_key, {1}, {"alternative"}, set())
    assert one is not None and one.anchor == 1 and one.justified
    assert one.coverage < 0.2
    many = score_lineup(["Fine"] * 30, by_key, {1}, {"alternative"}, set())
    assert many is not None and many.anchor == 0 and not many.justified
    assert many.coverage == 1


