"""Збирає резервний CSV, знімки сторінок і 20 анонсів для офлайн-тестів."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from concertrip.reference import ARTIST_NAMES, VENUES

ROOT = Path(__file__).resolve().parent.parent
rng_seed = 31


def main() -> None:
    rows = _seed_rows()
    path = ROOT / "data" / "seed_events.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "external_id",
                "artists",
                "venue",
                "city",
                "country",
                "event_date",
                "ticket_types",
                "on_sale_date",
                "presale_date",
                "status",
                "url",
                "is_festival",
                "lineup",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    _jsonld()
    _ebilet()
    _announcements()
    print(f"seed {len(rows)}")


def _seed_rows() -> list[dict]:
    tickets = [
        "Standing - General Admission|Stalls Reserved Seat",
        "Płyta stojąca|Miejsca siedzące",
        "Stehplatz Innenraum|Sitzplatz Rang",
        "Fosse Or|Place assise",
        "Golden Circle Standing",
        "VIP Lounge|Standing - General Admission",
    ]
    statuses = ["available", "limited", "low", "sold_out"]
    start = date(2026, 12, 1)
    concert_venues = [v for v in VENUES if v[0] not in {"Victoria Park", "Larmer Tree Gardens", "Evenemententerrein", "Ferropolis", "Domaine national", "Lotnisko Gdynia"}]
    rows = []
    for index in range(288):
        venue = concert_venues[index % len(concert_venues)]
        artist = ARTIST_NAMES[index % len(ARTIST_NAMES)]
        artists = artist
        if index % 11 == 0:
            artists = f"{artist}|{ARTIST_NAMES[(index + 7) % len(ARTIST_NAMES)]}"
        event_date = start + timedelta(days=(index * 3) % 340)
        roll = index % 10
        if roll < 7:
            on_sale = date(2026, 6, 1) + timedelta(days=index % 50)
            status = statuses[index % 4]
            presale = (on_sale - timedelta(days=7)).isoformat() if index % 5 == 0 else ""
            on_sale_s = on_sale.isoformat()
        elif roll < 9:
            on_sale_s = (date(2027, 1, 10) + timedelta(days=index % 20)).isoformat()
            status = "unknown"
            presale = ""
        else:
            on_sale_s = ""
            status = "unknown"
            presale = ""
        rows.append(
            {
                "external_id": f"seed-{index + 1:03d}",
                "artists": artists,
                "venue": venue[0],
                "city": venue[1],
                "country": venue[2],
                "event_date": event_date.isoformat(),
                "ticket_types": tickets[index % len(tickets)],
                "on_sale_date": on_sale_s,
                "presale_date": presale,
                "status": status,
                "url": f"https://example.org/seed/seed-{index + 1:03d}",
                "is_festival": "0",
                "lineup": "",
            }
        )
    festivals = [
        ("Open'er", "Lotnisko Gdynia", "Gdynia", "PL"),
        ("Lowlands", "Evenemententerrein", "Biddinghuizen", "NL"),
        ("Melt", "Ferropolis", "Grafenhainichen", "DE"),
        ("Rock en Seine", "Domaine national", "Saint-Cloud", "FR"),
        ("End of the Road", "Larmer Tree Gardens", "Salisbury", "GB"),
        ("All Points East", "Victoria Park", "London", "GB"),
    ]
    for index, fest in enumerate(festivals):
        for copy in range(2):
            number = 289 + index * 2 + copy
            lineup = [ARTIST_NAMES[(index * 3 + offset + copy) % len(ARTIST_NAMES)] for offset in range(8)]
            rows.append(
                {
                    "external_id": f"seed-{number:03d}",
                    "artists": fest[0],
                    "venue": fest[1],
                    "city": fest[2],
                    "country": fest[3],
                    "event_date": (date(2027, 6, 1) + timedelta(days=20 * index + 40 * copy)).isoformat(),
                    "ticket_types": "Standing - General Admission|Stalls Reserved Seat",
                    "on_sale_date": "2026-11-01",
                    "presale_date": "",
                    "status": "available" if copy == 0 else "low",
                    "url": f"https://example.org/seed/seed-{number:03d}",
                    "is_festival": "1",
                    "lineup": "|".join(lineup),
                }
            )
    return rows


def _jsonld() -> None:
    blocks = []
    for index in range(20):
        venue = VENUES[index % 10]
        artist = ARTIST_NAMES[index]
        blocks.append(
            f"""<script type="application/ld+json">
{{
  "@type": "MusicEvent",
  "@id": "jsonld-{index + 1:03d}",
  "name": "{artist}",
  "startDate": "2027-0{(index % 8) + 1}-15",
  "url": "https://example.org/jsonld/jsonld-{index + 1:03d}",
  "performer": {{"@type": "MusicGroup", "name": "{artist}"}},
  "location": {{
    "@type": "Place",
    "name": "{venue[0]}",
    "address": {{"addressLocality": "{venue[1]}", "addressCountry": "{venue[2]}"}}
  }},
  "offers": {{
    "@type": "Offer",
    "name": "Standing - General Admission",
    "availability": "https://schema.org/InStock",
    "validFrom": "2026-10-01",
    "url": "https://example.org/jsonld/jsonld-{index + 1:03d}"
  }}
}}
</script>"""
        )
    blocks.append(
        """<script type="application/ld+json">
{
  "@type": "MusicFestival",
  "@id": "jsonld-fest",
  "name": "Markup Fest",
  "startDate": "2027-07-20",
  "url": "https://example.org/jsonld/fest",
  "performer": [
    {"@type": "MusicGroup", "name": "Idles"},
    {"@type": "MusicGroup", "name": "Wet Leg"},
    {"@type": "MusicGroup", "name": "Slowdive"},
    {"@type": "MusicGroup", "name": "Bicep"}
  ],
  "location": {
    "@type": "Place",
    "name": "Victoria Park",
    "address": {"addressLocality": "London", "addressCountry": "GB"}
  },
  "offers": {"@type": "Offer", "name": "Fosse Or", "availability": "https://schema.org/LimitedAvailability"}
}
</script>"""
    )
    folder = ROOT / "data" / "fixtures" / "jsonld"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "events.html").write_text("<html><body>" + "\n".join(blocks) + "</body></html>", encoding="utf-8")


def _ebilet() -> None:
    articles = []
    for index in range(20):
        venue = VENUES[10 + (index % 10)]
        artist = ARTIST_NAMES[20 + index]
        articles.append(
            f"""<article class="event" data-id="eb-{index + 1:03d}">
  <h2 class="artist">{artist}</h2>
  <span class="venue">{venue[0]}</span>
  <span class="city">{venue[1]}</span>
  <span class="country">{venue[2]}</span>
  <time class="date" datetime="2027-05-{(index % 27) + 1:02d}"></time>
  <span class="ticket">Płyta stojąca</span>
  <span class="ticket">Miejsca siedzące</span>
  <span class="status">available</span>
  <time class="on-sale" datetime="2026-09-15"></time>
  <a class="buy" href="https://example.org/ebilet/eb-{index + 1:03d}">купити</a>
</article>"""
        )
    folder = ROOT / "data" / "fixtures" / "ebilet"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "listing.html").write_text("<html><body>" + "\n".join(articles) + "</body></html>", encoding="utf-8")


def _announcements() -> None:
    folder = ROOT / "tests" / "fixtures" / "announcements"
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(20):
        artist = ARTIST_NAMES[index]
        venue = VENUES[index]
        on_sale = None if index >= 18 else f"2026-09-{(index % 27) + 1:02d}"
        event_date = f"2027-0{(index % 8) + 1}-20"
        status = ["available", "low", "sold_out", "unknown"][index % 4]
        url = f"https://example.org/pages/{index + 1:02d}"
        if index < 10:
            sale_line = "none" if on_sale is None else on_sale
            text = (
                f"ARTIST: {artist}\nVENUE: {venue[0]}\nCITY: {venue[1]}\nCOUNTRY: {venue[2]}\n"
                f"DATE: {event_date}\nTICKETS: Standing - General Admission\n"
                f"ON_SALE: {sale_line}\nSTATUS: {status}\nURL: {url}\n"
            )
        else:
            sale = "On sale: not announced." if on_sale is None else f"On sale: {on_sale}."
            text = (
                f"{artist} at {venue[0]} in {venue[1]}, {venue[2]} on {event_date}. "
                f"Tickets: Standing - General Admission. {sale} Status: {status}. {url}\n"
            )
        (folder / f"{index + 1:02d}.txt").write_text(text, encoding="utf-8")
        (folder / f"{index + 1:02d}.json").write_text(
            json.dumps(
                {
                    "artist": artist,
                    "venue": venue[0],
                    "city": venue[1],
                    "country": venue[2],
                    "event_date": event_date,
                    "on_sale_date": on_sale,
                    "status": status,
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
