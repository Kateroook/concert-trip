"""Селектори одного продавця. Читає збережений знімок сторінки, не живий сайт."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from concertrip.config import ROOT
from concertrip.domain import RawEvent
from concertrip.normalize.country import normalize_country

SOURCE_ID = "ebilet"
FIXTURE = ROOT / "data" / "fixtures" / "ebilet" / "listing.html"

_STATUSES = {"available", "limited", "low", "sold_out", "unknown"}


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def parse_listing(html: str, source_id: str = SOURCE_ID) -> list[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[RawEvent] = []
    for node in soup.select("article.event"):
        external_id = (node.get("data-id") or "").strip()
        artists = [el.get_text(strip=True) for el in node.select(".artist") if el.get_text(strip=True)]
        venue = node.select_one(".venue")
        city = node.select_one(".city")
        country = node.select_one(".country")
        when = node.select_one("time.date")
        event_date = _date(when.get("datetime") if when else None)
        iso_country = normalize_country(country.get_text(strip=True) if country else None)
        if not external_id or not artists or event_date is None or not iso_country:
            continue
        if venue is None or city is None or not venue.get_text(strip=True) or not city.get_text(strip=True):
            continue
        tickets = [el.get_text(strip=True) for el in node.select(".ticket") if el.get_text(strip=True)]
        status_node = node.select_one(".status")
        status = (status_node.get_text(strip=True).lower() if status_node else "unknown")
        if status not in _STATUSES:
            status = "unknown"
        link = node.select_one("a.buy")
        on_sale = node.select_one(".on-sale")
        presale = node.select_one(".presale")
        lineup = [el.get_text(strip=True) for el in node.select(".lineup li") if el.get_text(strip=True)]
        festival = node.get("data-festival") == "1"
        events.append(
            RawEvent(
                source_id=source_id,
                external_id=external_id,
                artist_names=artists,
                venue=venue.get_text(strip=True),
                city=city.get_text(strip=True),
                country=iso_country,
                event_date=event_date,
                ticket_types_raw=tickets,
                on_sale_date=_date(on_sale.get("datetime") if on_sale else None),
                presale_date=_date(presale.get("datetime") if presale else None),
                status=status,
                url=link.get("href", "").strip() if link else "",
                is_festival=festival,
                lineup=lineup or None,
            )
        )
    return events


class SiteRulesSource:
    source_id = SOURCE_ID

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or FIXTURE)

    def fetch(self, since: date) -> list[RawEvent]:
        if not self.path.exists():
            return []
        events = parse_listing(self.path.read_text(encoding="utf-8"))
        return [event for event in events if event.event_date >= since]


def main() -> None:
    print(f"ebilet: {len(SiteRulesSource().fetch(date.min))}")
