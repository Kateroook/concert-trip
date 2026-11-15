"""Клієнт Discovery API Ticketmaster. Без ключа повертає порожній список."""

from __future__ import annotations

import time
from datetime import date, datetime

import httpx

from concertrip.config import settings
from concertrip.domain import RawEvent
from concertrip.normalize.country import normalize_country

SOURCE_ID = "ticketmaster"
API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

_STATUS = {
    "onsale": "available",
    "offsale": "unknown",
    "rescheduled": "unknown",
    "postponed": "unknown",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_payload(payload: dict, source_id: str = SOURCE_ID) -> list[RawEvent]:
    embedded = payload.get("_embedded") or {}
    events = []
    for node in embedded.get("events") or []:
        parsed = _parse_event(node, source_id)
        if parsed is not None:
            events.append(parsed)
    return events


def _parse_event(node: dict, source_id: str) -> RawEvent | None:
    dates = node.get("dates") or {}
    start = dates.get("start") or {}
    event_date = _parse_date(start.get("localDate"))
    status_code = ((dates.get("status") or {}).get("code") or "").lower()
    if status_code in {"cancelled", "canceled"} or event_date is None:
        return None
    venues = ((node.get("_embedded") or {}).get("venues") or [])
    if not venues:
        return None
    venue = venues[0]
    country = normalize_country(((venue.get("country") or {}).get("countryCode")))
    city = ((venue.get("city") or {}).get("name") or "").strip()
    venue_name = (venue.get("name") or "").strip()
    if not country or not city or not venue_name:
        return None
    attractions = (node.get("_embedded") or {}).get("attractions") or []
    names = [a.get("name", "").strip() for a in attractions if a.get("name")]
    title = (node.get("name") or "").strip()
    classifications = node.get("classifications") or []
    genre_names = []
    for item in classifications:
        for key in ("genre", "subGenre", "segment"):
            block = item.get(key) or {}
            if block.get("name"):
                genre_names.append(str(block["name"]).lower())
    is_festival = "festival" in " ".join(genre_names) or "festival" in title.lower()
    if is_festival:
        artist_names = [title or (names[0] if names else "")]
        lineup = names or None
    else:
        artist_names = names or ([title] if title else [])
        lineup = None
    if not artist_names or not artist_names[0]:
        return None
    sales = node.get("sales") or {}
    public = sales.get("public") or {}
    on_sale = _parse_date(public.get("startDateTime"))
    presales = sales.get("presales") or []
    presale = None
    if presales and isinstance(presales[0], dict):
        presale = _parse_date(presales[0].get("startDateTime"))
    status = _STATUS.get(status_code, "unknown")
    if status == "cancelled":
        return None
    return RawEvent(
        source_id=source_id,
        external_id=str(node.get("id") or ""),
        artist_names=artist_names,
        venue=venue_name,
        city=city,
        country=country,
        event_date=event_date,
        ticket_types_raw=[],
        on_sale_date=on_sale,
        presale_date=presale,
        status=status,
        url=str(node.get("url") or ""),
        is_festival=is_festival,
        lineup=lineup,
    )


class TicketmasterSource:
    source_id = SOURCE_ID

    def __init__(
        self,
        api_key: str | None = None,
        countries: tuple[str, ...] | None = None,
        client: httpx.Client | None = None,
        delay: float | None = None,
        pages: int = 2,
    ) -> None:
        self.api_key = settings.ticketmaster_api_key if api_key is None else api_key
        self.countries = settings.countries if countries is None else countries
        self.client = client
        self.delay = settings.request_delay_seconds if delay is None else delay
        self.pages = pages

    def fetch(self, since: date) -> list[RawEvent]:
        if not self.api_key:
            return []
        client = self.client or httpx.Client(
            headers={"User-Agent": settings.http_user_agent},
            timeout=20.0,
        )
        close = self.client is None
        found: list[RawEvent] = []
        try:
            for country in self.countries:
                for page in range(self.pages):
                    if self.delay:
                        time.sleep(self.delay)
                    response = client.get(
                        API_URL,
                        params={
                            "apikey": self.api_key,
                            "countryCode": country,
                            "classificationName": "music",
                            "startDateTime": datetime.combine(since, datetime.min.time()).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                            "size": "100",
                            "page": str(page),
                            "sort": "date,asc",
                        },
                    )
                    if response.status_code == 429:
                        break
                    if response.status_code != 200:
                        break
                    payload = response.json()
                    batch = parse_payload(payload)
                    found.extend(batch)
                    page_info = payload.get("page") or {}
                    total_pages = int(page_info.get("totalPages") or 1)
                    if page + 1 >= total_pages or not batch:
                        break
        finally:
            if close:
                client.close()
        deduped: dict[str, RawEvent] = {}
        for event in found:
            if event.external_id and event.event_date >= since:
                deduped[event.external_id] = event
        return list(deduped.values())


def main() -> None:
    events = TicketmasterSource().fetch(date.today())
    print(f"ticketmaster: {len(events)}")
