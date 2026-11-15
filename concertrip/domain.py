"""Спільна форма події, яку повертає кожне джерело."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawEvent:
    source_id: str
    external_id: str
    artist_names: list[str]
    venue: str
    city: str
    country: str
    event_date: date
    ticket_types_raw: list[str]
    on_sale_date: date | None
    presale_date: date | None
    status: str
    url: str
    is_festival: bool = False
    lineup: list[str] | None = None
    low_confidence: list[str] = field(default_factory=list)
