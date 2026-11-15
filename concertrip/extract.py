"""Витяг полів з тексту анонсу. Непевну дату продажу не зберігаємо."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from concertrip.config import settings
from concertrip.normalize.country import normalize_country

CONFIDENCE_FLOOR = 0.7
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_URL = re.compile(r"https?://\S+")
_PROSE = re.compile(
    r"^(?P<artist>.+?) at (?P<venue>.+?) in (?P<city>.+?), (?P<country>[A-Za-z]{2}) on (?P<date>\d{4}-\d{2}-\d{2})\."
)
_STATUSES = {"available", "limited", "low", "sold_out", "unknown"}


@dataclass
class Extraction:
    artist_names: list[str] = field(default_factory=list)
    venue: str | None = None
    city: str | None = None
    country: str | None = None
    event_date: date | None = None
    on_sale_date: date | None = None
    status: str | None = None
    url: str | None = None
    ticket_types_raw: list[str] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    low_confidence: list[str] = field(default_factory=list)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = _DATE.search(value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


def apply_confidence(result: Extraction) -> Extraction:
    """Дата без достатньої впевненості стає порожньою, а не здогадкою."""
    for key in ("event_date", "on_sale_date"):
        if result.confidence.get(key, 0) < CONFIDENCE_FLOOR and getattr(result, key) is not None:
            setattr(result, key, None)
            if key not in result.low_confidence:
                result.low_confidence.append(key)
        elif result.confidence.get(key, 1) < CONFIDENCE_FLOOR and key not in result.low_confidence:
            result.low_confidence.append(key)
    return result


def extract_announcement(text: str) -> Extraction:
    result = Extraction()
    labeled = _labeled(text)
    if labeled:
        result = labeled
    else:
        result = _prose(text)
    return apply_confidence(result)


def _labeled(text: str) -> Extraction | None:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().upper()] = value.strip()
    if "ARTIST" not in fields or "DATE" not in fields:
        return None
    on_sale_raw = fields.get("ON_SALE", "")
    on_sale = None if on_sale_raw.lower() in {"", "none", "not announced"} else _parse_date(on_sale_raw)
    status = fields.get("STATUS", "").lower()
    result = Extraction(
        artist_names=[fields["ARTIST"]] if fields.get("ARTIST") else [],
        venue=fields.get("VENUE") or None,
        city=fields.get("CITY") or None,
        country=normalize_country(fields.get("COUNTRY")),
        event_date=_parse_date(fields.get("DATE")),
        on_sale_date=on_sale,
        status=status if status in _STATUSES else None,
        url=_url(fields.get("URL") or text),
        ticket_types_raw=[fields["TICKETS"]] if fields.get("TICKETS") else [],
        confidence={
            "artist": 0.95,
            "venue": 0.95,
            "city": 0.95,
            "country": 0.95,
            "event_date": 0.95 if _parse_date(fields.get("DATE")) else 0.0,
            "on_sale_date": 0.95 if on_sale or on_sale_raw.lower() in {"none", "not announced"} else 0.0,
            "status": 0.95 if status in _STATUSES else 0.0,
            "url": 0.95,
        },
    )
    return result


def _prose(text: str) -> Extraction:
    result = Extraction(confidence={})
    match = _PROSE.search(text.strip())
    if match:
        result.artist_names = [match.group("artist").strip()]
        result.venue = match.group("venue").strip()
        result.city = match.group("city").strip()
        result.country = normalize_country(match.group("country"))
        result.event_date = _parse_date(match.group("date"))
        for key in ("artist", "venue", "city", "country", "event_date"):
            result.confidence[key] = 0.9
    else:
        result.confidence.update({key: 0.2 for key in ("artist", "venue", "city", "country", "event_date")})
    url = _url(text)
    result.url = url
    result.confidence["url"] = 0.9 if url else 0.0
    status_match = re.search(r"Status:\s*([a-z_]+)", text, re.I)
    if status_match and status_match.group(1).lower() in _STATUSES:
        result.status = status_match.group(1).lower()
        result.confidence["status"] = 0.9
    tickets = re.search(r"Tickets:\s*([^\.\n]+)", text, re.I)
    if tickets:
        result.ticket_types_raw = [tickets.group(1).strip()]
    if re.search(r"on sale:\s*not announced", text, re.I):
        result.on_sale_date = None
        result.confidence["on_sale_date"] = 0.95
    else:
        sale = re.search(r"on sale:\s*(\d{4}-\d{2}-\d{2})", text, re.I)
        if sale:
            result.on_sale_date = _parse_date(sale.group(1))
            result.confidence["on_sale_date"] = 0.9
        else:
            result.confidence["on_sale_date"] = 0.2
    return result


def _url(text: str) -> str | None:
    match = _URL.search(text or "")
    return match.group(0).rstrip(".,)") if match else None


def from_model_payload(payload: dict) -> Extraction:
    """Розбирає JSON моделі. Поле без confidence вважаємо непевним."""
    confidence = {str(k): float(v) for k, v in (payload.get("confidence") or {}).items()}
    for key in ("artist", "venue", "city", "country", "event_date", "on_sale_date", "status", "url"):
        confidence.setdefault(key, 0.5)
    artists = payload.get("artist_names") or []
    if isinstance(artists, str):
        artists = [artists]
    tickets = payload.get("ticket_types") or []
    if isinstance(tickets, str):
        tickets = [tickets]
    status = payload.get("status")
    result = Extraction(
        artist_names=[str(name) for name in artists if str(name).strip()],
        venue=payload.get("venue") or None,
        city=payload.get("city") or None,
        country=normalize_country(payload.get("country")),
        event_date=_parse_date(payload.get("event_date")),
        on_sale_date=_parse_date(payload.get("on_sale_date")),
        status=status if status in _STATUSES else None,
        url=payload.get("url") or None,
        ticket_types_raw=[str(item) for item in tickets if str(item).strip()],
        confidence=confidence,
    )
    return apply_confidence(result)


def extract_with_model(text: str) -> Extraction:
    if not settings.anthropic_api_key:
        raise RuntimeError("немає ключа Anthropic")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=800,
        messages=[{"role": "user", "content": _prompt(text)}],
    )
    raw = "".join(block.text for block in message.content if getattr(block, "text", None))
    return from_model_payload(_load_json(raw))


def _load_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("модель повернула не об’єкт")
    return data


def _prompt(text: str) -> str:
    return (
        "Extract concert fields from the announcement. "
        "Return only JSON with keys artist_names, venue, city, country (ISO-2 or null), "
        "event_date, on_sale_date, status (available|limited|low|sold_out|unknown|null), "
        "url, ticket_types, and confidence (0 to 1 per field). "
        "If a date is not stated, use null and confidence 0. Do not guess a date.\n\n"
        + text
    )
