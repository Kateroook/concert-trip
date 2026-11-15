"""Три рівні терміновості і пояснення, з чого вони склались."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from concertrip.models import Event
from concertrip.reference import BIG_CITIES, city_key

_SEGMENTS = {"low": 1, "medium": 2, "high": 3}
_LABELS = {"low": "низька", "medium": "помірна", "high": "висока"}


@dataclass(frozen=True)
class Urgency:
    level: str
    points: int
    text: str

    @property
    def segments(self) -> int:
        return _SEGMENTS[self.level]

    @property
    def label(self) -> str:
        return _LABELS[self.level]


def score_urgency(event: Event, popularity: int | None = None, today: date | None = None) -> Urgency:
    today = today or date.today()
    points = 0
    reasons: list[str] = []
    capacity = event.venue.capacity if event.venue is not None else None
    if capacity is not None:
        if capacity <= 2500:
            points += 2
            reasons.append("мала зала, квитки зазвичай зникають швидко")
        elif capacity <= 8000:
            points += 1
            reasons.append("зала середнього розміру")
    if popularity is not None:
        if popularity >= 75:
            points += 2
            reasons.append("висока популярність артиста")
        elif popularity >= 45:
            points += 1
            reasons.append("помітна популярність артиста")
    if event.venue is not None and city_key(event.venue.city) in BIG_CITIES:
        points += 1
        reasons.append("велике місто, попит вищий")
    days = (event.event_date - today).days
    if days < 0:
        return Urgency("low", 0, "Подія вже минула.")
    if days <= 14:
        points += 2
        reasons.append("до події лишилось менше двох тижнів")
    elif days <= 45:
        points += 1
        reasons.append("подія в найближчі тижні")
    if points >= 5:
        level = "high"
        lead = "Варто вирішувати зараз"
    elif points >= 3:
        level = "medium"
        lead = "Є час, але не відкладай надовго"
    else:
        level = "low"
        lead = "Можна не кидати всі справи"
    if not reasons:
        text = "Замало даних про залу, популярність і термін, тож оцінка низька."
    else:
        text = f"{lead}: " + "; ".join(reasons) + "."
    return Urgency(level, points, text)


def best_popularity(event: Event) -> int | None:
    values = [
        link.artist.popularity
        for link in event.artists_link
        if link.artist is not None and link.artist.popularity is not None
    ]
    if not values:
        return None
    return max(values)
