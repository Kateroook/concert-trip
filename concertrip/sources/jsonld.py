"""Збір подій із schema.org/Event JSON-LD. Без правил під конкретний сайт."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from concertrip.config import ROOT, settings
from concertrip.domain import RawEvent
from concertrip.normalize.country import normalize_country

SOURCE_ID = "jsonld"
FIXTURE_DIR = ROOT / "data" / "fixtures" / "jsonld"

_AVAILABILITY = {
    "instock": "available",
    "limitedavailability": "limited",
    "soldout": "sold_out",
    "outofstock": "sold_out",
    "preorder": "unknown",
    "presale": "unknown",
    "in stock": "available",
}


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _availability(value) -> str | None:
    if not isinstance(value, str):
        return None
    key = value.rstrip("/").split("/")[-1].lower()
    return _AVAILABILITY.get(key)


def _country_city_venue(node: dict) -> tuple[str | None, str, str]:
    location = node.get("location")
    if isinstance(location, list):
        location = location[0] if location else None
    if not isinstance(location, dict):
        return None, "", ""
    venue = location.get("name") or ""
    address = location.get("address")
    city = ""
    country = None
    if isinstance(address, dict):
        city = address.get("addressLocality") or ""
        raw_country = address.get("addressCountry")
        if isinstance(raw_country, dict):
            raw_country = raw_country.get("name") or raw_country.get("addressCountry")
        country = normalize_country(str(raw_country)) if raw_country else None
    return country, str(city), str(venue)


def _performers(node: dict) -> list[str]:
    raw = node.get("performer")
    if raw is None:
        raw = node.get("performers")
    names: list[str] = []
    for item in _as_list(raw):
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]).strip())
    return names


def _walk(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _walk(item)
        return
    if not isinstance(payload, dict):
        return
    graph = payload.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            yield from _walk(item)
    types = _as_list(payload.get("@type"))
    interesting = {"Event", "MusicEvent", "Festival", "MusicFestival"}
    if any(isinstance(t, str) and t in interesting for t in types):
        yield payload


def parse_html(html: str, source_id: str = SOURCE_ID, external_prefix: str = "") -> list[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[RawEvent] = []
    seen: set[str] = set()
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _walk(payload):
            event = _node_to_event(node, source_id, external_prefix)
            if event is None or event.external_id in seen:
                continue
            seen.add(event.external_id)
            events.append(event)
    return events


def _node_to_event(node: dict, source_id: str, external_prefix: str) -> RawEvent | None:
    event_date = _parse_date(node.get("startDate"))
    country, city, venue = _country_city_venue(node)
    performers = _performers(node)
    if event_date is None or not country or not city or not venue:
        return None
    types = [t for t in _as_list(node.get("@type")) if isinstance(t, str)]
    offers = [o for o in _as_list(node.get("offers")) if isinstance(o, dict)]
    ticket_types = [str(o["name"]).strip() for o in offers if o.get("name")]
    status = "unknown"
    on_sale = None
    presale = None
    url = str(node.get("url") or "")
    for offer in offers:
        mapped = _availability(str(offer.get("availability") or ""))
        if mapped and status == "unknown":
            status = mapped
        if not url and offer.get("url"):
            url = str(offer["url"])
        valid = _parse_date(offer.get("validFrom"))
        kind = _availability(str(offer.get("availability") or ""))
        if valid and kind == "unknown" and "pre" in str(offer.get("availability") or "").lower():
            presale = valid
        elif valid and on_sale is None:
            on_sale = valid
    is_festival = any(t in {"Festival", "MusicFestival"} for t in types) or len(performers) >= 4
    title = str(node.get("name") or (performers[0] if performers else "")).strip()
    if not title and not performers:
        return None
    external_id = str(node.get("@id") or node.get("url") or f"{title}-{event_date.isoformat()}")
    if external_prefix:
        external_id = f"{external_prefix}:{external_id}"
    if is_festival:
        artist_names = [title]
        lineup = performers or None
    else:
        artist_names = performers or [title]
        lineup = None
    return RawEvent(
        source_id=source_id,
        external_id=external_id[:128],
        artist_names=artist_names,
        venue=venue,
        city=city,
        country=country,
        event_date=event_date,
        ticket_types_raw=ticket_types,
        on_sale_date=on_sale,
        presale_date=presale,
        status=status,
        url=url,
        is_festival=is_festival,
        lineup=lineup,
    )


class JsonLdSource:
    source_id = SOURCE_ID

    def __init__(
        self,
        paths: list[Path] | None = None,
        urls: list[str] | None = None,
        client: httpx.Client | None = None,
        delay: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.paths = list(paths if paths is not None else _default_paths())
        self.urls = list(urls if urls is not None else settings.jsonld_urls)
        self.client = client
        self.delay = settings.request_delay_seconds if delay is None else delay
        self.user_agent = user_agent or settings.http_user_agent
        self._robots: dict[str, RobotFileParser | None] = {}

    def fetch(self, since: date) -> list[RawEvent]:
        events: list[RawEvent] = []
        for path in self.paths:
            if path.exists():
                events.extend(parse_html(path.read_text(encoding="utf-8")))
        if self.urls:
            client = self.client or httpx.Client(
                headers={"User-Agent": self.user_agent},
                timeout=20.0,
                follow_redirects=True,
            )
            close = self.client is None
            try:
                for url in self.urls:
                    if not self._allowed(client, url):
                        continue
                    if self.delay:
                        time.sleep(self.delay)
                    response = client.get(url)
                    if response.status_code == 200:
                        events.extend(parse_html(response.text))
            finally:
                if close:
                    client.close()
        return [event for event in events if event.event_date >= since]

    def _allowed(self, client: httpx.Client, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(client, origin)
        parser = self._robots[origin]
        if parser is None:
            return False
        return parser.can_fetch(self.user_agent, url)

    def _load_robots(self, client: httpx.Client, origin: str) -> RobotFileParser | None:
        try:
            response = client.get(f"{origin}/robots.txt")
        except httpx.HTTPError:
            return None
        if response.status_code != 200 or not response.text.strip():
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser


def _default_paths() -> list[Path]:
    if not FIXTURE_DIR.exists():
        return []
    return sorted(FIXTURE_DIR.glob("*.html"))
