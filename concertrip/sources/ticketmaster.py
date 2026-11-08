"""Клієнт і імпортер Ticketmaster Discovery API v2."""

from __future__ import annotations

import argparse
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterator, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.config import settings
from concertrip.db import SessionLocal
from concertrip.models import Artist, Event, EventTicketOption, Source, Venue

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

API_PATH = "/discovery/v2/events.json"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class TicketmasterError(RuntimeError):
    pass


class TicketmasterMappingError(TicketmasterError):
    pass


@dataclass(frozen=True)
class PriceRange:
    minimum: Optional[Decimal]
    maximum: Optional[Decimal]
    currency: Optional[str]
    external_key: str


@dataclass(frozen=True)
class TicketmasterEvent:
    external_id: str
    title: str
    artist_name: str
    artist_external_id: Optional[str]
    venue_name: str
    venue_external_id: Optional[str]
    city: str
    country_code: str
    address: Optional[str]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    event_date: Optional[datetime]
    date_status: str
    on_sale_at: Optional[datetime]
    status: str
    url: str
    price_ranges: tuple[PriceRange, ...]
    raw_payload: dict


@dataclass(frozen=True)
class SyncStats:
    countries: int
    pages: int
    received: int
    parsed: int
    created: int
    updated: int
    skipped: int
    errors: int


def _parse_datetime(value: Optional[str], timezone_name: Optional[str] = None) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed
    if timezone_name:
        try:
            return parsed.replace(tzinfo=ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            logger.warning("Unknown Ticketmaster timezone %s; using UTC", timezone_name)
    return parsed.replace(tzinfo=timezone.utc)


def _parse_local_start(start: dict, timezone_name: Optional[str]) -> tuple[Optional[datetime], str]:
    if start.get("dateTBA"):
        return None, "tba"
    if start.get("dateTBD"):
        return None, "tbd"
    local_date = start.get("localDate")
    if not local_date:
        return None, "unknown"
    if start.get("dateTime"):
        return _parse_datetime(start["dateTime"], timezone_name), "confirmed"
    local_time = start.get("localTime") or "00:00:00"
    return _parse_datetime(f"{local_date}T{local_time}", timezone_name), "confirmed"


def _decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception as error:
        raise TicketmasterMappingError(f"Invalid price value: {value!r}") from error


def _parse_price_ranges(values: object) -> tuple[PriceRange, ...]:
    if not isinstance(values, list):
        return ()
    ranges = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            continue
        currency = value.get("currency")
        ranges.append(
            PriceRange(
                minimum=_decimal(value.get("min")),
                maximum=_decimal(value.get("max")),
                currency=str(currency).upper() if currency else None,
                external_key=f"price:{index}:{currency or 'unknown'}".lower(),
            )
        )
    return tuple(ranges)


def parse_event(payload: dict) -> TicketmasterEvent:
    event_id = payload.get("id")
    if not event_id:
        raise TicketmasterMappingError("Event has no id")

    embedded = payload.get("_embedded") or {}
    attractions = embedded.get("attractions") or []
    venues = embedded.get("venues") or []
    if not attractions or not attractions[0].get("name"):
        raise TicketmasterMappingError(f"Event {event_id} has no attraction")
    if not venues or not venues[0].get("name"):
        raise TicketmasterMappingError(f"Event {event_id} has no venue")

    attraction = attractions[0]
    venue = venues[0]
    address = venue.get("address") or {}
    city = venue.get("city") or {}
    country = venue.get("country") or {}
    location = venue.get("location") or {}
    dates = payload.get("dates") or {}
    start = dates.get("start") or {}
    event_date, date_status = _parse_local_start(start, dates.get("timezone"))
    status = str((dates.get("status") or {}).get("code") or "unknown").lower()
    status = "canceled" if status == "cancelled" else status
    sales = dates.get("sales") or {}
    public_sale = sales.get("public") or {}

    try:
        latitude = _decimal(location.get("latitude"))
        longitude = _decimal(location.get("longitude"))
    except TicketmasterMappingError:
        latitude = longitude = None

    return TicketmasterEvent(
        external_id=str(event_id),
        title=str(payload.get("name") or attraction["name"]),
        artist_name=str(attraction["name"]),
        artist_external_id=attraction.get("id"),
        venue_name=str(venue["name"]),
        venue_external_id=venue.get("id"),
        city=str(city.get("name") or "Unknown"),
        country_code=str(country.get("countryCode") or "").upper(),
        address=address.get("line1"),
        latitude=latitude,
        longitude=longitude,
        event_date=event_date,
        date_status=date_status,
        on_sale_at=_parse_datetime(public_sale.get("startDateTime")),
        status=status,
        url=str(payload.get("url") or ""),
        price_ranges=_parse_price_ranges(payload.get("priceRanges")),
        raw_payload=payload,
    )


def parse_page(payload: dict) -> list[TicketmasterEvent]:
    raw_events = (payload.get("_embedded") or {}).get("events") or []
    parsed = []
    for raw_event in raw_events:
        try:
            parsed.append(parse_event(raw_event))
        except TicketmasterMappingError:
            logger.exception("Skipping malformed Ticketmaster event")
    return parsed


class TicketmasterClient:
    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 20.0,
        transport: Optional[httpx.BaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise TicketmasterError("TICKETMASTER_API_KEY is not configured")
        self._client = httpx.Client(
            base_url="https://app.ticketmaster.com",
            timeout=timeout,
            transport=transport,
        )
        self._api_key = api_key
        self._sleep = sleep
        self._max_retries = max_retries
        self._last_request_at = 0.0
        self.pages_requested = 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TicketmasterClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < 0.2:
            self._sleep(0.2 - elapsed)
        self._last_request_at = time.monotonic()

    def _get_page(self, params: dict[str, object]) -> dict:
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            self.pages_requested += 1
            try:
                response = self._client.get(API_PATH, params={**params, "apikey": self._api_key})
            except httpx.RequestError as error:
                if attempt >= self._max_retries:
                    raise TicketmasterError("Ticketmaster request failed") from error
                self._sleep((2**attempt) * 0.5 + random.uniform(0, 0.2))
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else (2**attempt) * 0.5
                self._sleep(delay + random.uniform(0, 0.2))
                continue
            if response.status_code == 401:
                raise TicketmasterError("Ticketmaster rejected the API key")
            if response.status_code >= 400:
                raise TicketmasterError(f"Ticketmaster request failed ({response.status_code})")
            try:
                return response.json()
            except ValueError as error:
                raise TicketmasterError("Ticketmaster returned invalid JSON") from error
        raise TicketmasterError("Ticketmaster request exhausted retries")

    def iter_events(
        self,
        countries: tuple[str, ...],
        *,
        minimum_events: int = 200,
        page_size: int = 100,
    ) -> Iterator[TicketmasterEvent]:
        seen_ids: set[str] = set()
        for country in countries:
            page = 0
            while len(seen_ids) < minimum_events:
                payload = self._get_page(
                    {
                        "countryCode": country,
                        "classificationName": "music",
                        "source": "ticketmaster",
                        "size": min(page_size, 100),
                        "page": page,
                        "sort": "date,asc",
                        "includeTBA": "yes",
                        "includeTBD": "yes",
                    }
                )
                events = parse_page(payload)
                if not events:
                    break
                for event in events:
                    if event.external_id not in seen_ids:
                        seen_ids.add(event.external_id)
                        yield event
                page_info = payload.get("page") or {}
                if page + 1 >= int(page_info.get("totalPages", page + 1)):
                    break
                if page * min(page_size, 100) >= 1000:
                    break
                page += 1


def _normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _get_or_create_artist(session: Session, event: TicketmasterEvent) -> Artist:
    artist = None
    if event.artist_external_id:
        artist = session.scalar(select(Artist).where(Artist.ticketmaster_id == event.artist_external_id))
    if artist is None:
        artist = session.scalar(
            select(Artist).where(Artist.normalized_name == _normalize_name(event.artist_name))
        )
    if artist is None:
        artist = Artist(name=event.artist_name, normalized_name=_normalize_name(event.artist_name))
        session.add(artist)
    artist.name = event.artist_name
    if event.artist_external_id:
        artist.ticketmaster_id = event.artist_external_id
    return artist


def _get_or_create_venue(session: Session, event: TicketmasterEvent) -> Venue:
    venue = None
    if event.venue_external_id:
        venue = session.scalar(select(Venue).where(Venue.ticketmaster_id == event.venue_external_id))
    if venue is None:
        venue = session.scalar(
            select(Venue).where(
                Venue.normalized_name == _normalize_name(event.venue_name),
                Venue.city == event.city,
                Venue.country_code == event.country_code,
            )
        )
    if venue is None:
        venue = Venue(
            name=event.venue_name,
            normalized_name=_normalize_name(event.venue_name),
            city=event.city,
            country_code=event.country_code,
        )
        session.add(venue)
    venue.name = event.venue_name
    venue.address = event.address
    venue.latitude = event.latitude
    venue.longitude = event.longitude
    if event.venue_external_id:
        venue.ticketmaster_id = event.venue_external_id
    return venue


def upsert_event(session: Session, source: Source, incoming: TicketmasterEvent) -> bool:
    artist = _get_or_create_artist(session, incoming)
    venue = _get_or_create_venue(session, incoming)
    event = session.scalar(
        select(Event).where(Event.source_id == source.id, Event.external_id == incoming.external_id)
    )
    created = event is None
    if event is None:
        event = Event(source=source, external_id=incoming.external_id, url=incoming.url, status=incoming.status)
        session.add(event)
    event.artist = artist
    event.venue = venue
    event.title = incoming.title
    event.event_date = incoming.event_date
    event.date_status = incoming.date_status
    event.on_sale_at = incoming.on_sale_at
    event.status = incoming.status
    event.url = incoming.url
    event.raw_payload = incoming.raw_payload
    session.flush()

    ranges = incoming.price_ranges or (PriceRange(None, None, None, "default"),)
    for price_range in ranges:
        option = session.scalar(
            select(EventTicketOption).where(
                EventTicketOption.event_id == event.id,
                EventTicketOption.source_id == source.id,
                EventTicketOption.external_key == price_range.external_key,
            )
        )
        if option is None:
            option = EventTicketOption(
                event=event,
                source=source,
                external_key=price_range.external_key,
                raw_label="Ticketmaster price range",
                ticket_type="unknown",
                is_vip=False,
            )
        option.price_min = price_range.minimum
        option.price_max = price_range.maximum
        option.currency = price_range.currency
        option.availability_status = incoming.status
        option.url = incoming.url
        session.add(option)
    return created


def sync_ticketmaster(
    *,
    countries: tuple[str, ...] = settings.countries,
    minimum_events: int = 200,
    session_factory: Callable[[], Session] = SessionLocal,
) -> SyncStats:
    stats = SyncStats(len(countries), 0, 0, 0, 0, 0, 0, 0)
    with TicketmasterClient(settings.ticketmaster_api_key) as client, session_factory() as session:
        source = session.scalar(select(Source).where(Source.code == "ticketmaster"))
        if source is None:
            source = Source(code="ticketmaster", name="Ticketmaster Discovery")
            session.add(source)
            session.flush()
        for incoming in client.iter_events(countries, minimum_events=minimum_events):
            stats = SyncStats(
                stats.countries,
                stats.pages,
                stats.received + 1,
                stats.parsed + 1,
                stats.created,
                stats.updated,
                stats.skipped,
                stats.errors,
            )
            try:
                with session.begin_nested():
                    created = upsert_event(session, source, incoming)
                stats = SyncStats(
                    stats.countries,
                    stats.pages,
                    stats.received,
                    stats.parsed,
                    stats.created + int(created),
                    stats.updated + int(not created),
                    stats.skipped,
                    stats.errors,
                )
            except Exception:
                logger.exception("Could not upsert Ticketmaster event %s", incoming.external_id)
                stats = SyncStats(
                    stats.countries,
                    stats.pages,
                    stats.received,
                    stats.parsed,
                    stats.created,
                    stats.updated,
                    stats.skipped + 1,
                    stats.errors + 1,
                )
        session.commit()
        return SyncStats(
            stats.countries,
            client.pages_requested,
            stats.received,
            stats.parsed,
            stats.created,
            stats.updated,
            stats.skipped,
            stats.errors,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync events from Ticketmaster Discovery API")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse without writing to the database")
    parser.add_argument("--minimum-events", type=int, default=200)
    parser.add_argument("--country", action="append", dest="countries")
    args = parser.parse_args()
    logging.basicConfig(level=settings.log_level)
    countries = tuple(args.countries or settings.countries)
    if args.dry_run:
        with TicketmasterClient(settings.ticketmaster_api_key) as client:
            count = sum(1 for _ in client.iter_events(countries, minimum_events=args.minimum_events))
        logger.info("Ticketmaster dry run parsed %s events", count)
        return
    stats = sync_ticketmaster(countries=countries, minimum_events=args.minimum_events)
    logger.info("Ticketmaster sync completed: %s", stats)


if __name__ == "__main__":
    main()
