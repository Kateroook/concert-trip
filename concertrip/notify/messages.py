"""Тексти сповіщень українською."""

from __future__ import annotations

from concertrip.models import Event
from concertrip.prefs import origin_city
from concertrip.ranking.urgency import best_popularity, score_urgency
from concertrip.trip import format_trip

_TICKET = {
    "standing": "стоячі",
    "seated": "сидячі",
    "other": "інше",
    "any": "будь-який тип",
}


def ticket_label(value: str) -> str:
    return _TICKET.get(value, value)


def headline(event: Event) -> str:
    if not event.artists_link:
        return "Подія"
    ordered = sorted(event.artists_link, key=lambda link: link.position)
    return ordered[0].raw_name


def availability_message(session, event: Event, ticket_filter: str) -> str:
    urgency = score_urgency(event, best_popularity(event))
    when = event.event_date.strftime("%d.%m.%Y")
    city = event.venue.city if event.venue is not None else ""
    lines = [
        "КВИТКИ З’ЯВИЛИСЬ",
        headline(event),
        f"{city} · {when}",
        f"Тип: {ticket_label(ticket_filter)}",
        f"Терміновість: {urgency.label} — {urgency.text}",
        format_trip(origin_city(session), city),
    ]
    if event.url:
        lines.append(event.url)
    return "\n".join(lines)


def lineup_message(event: Event, score) -> str:
    when = event.event_date.strftime("%d.%m.%Y")
    city = event.venue.city if event.venue is not None else ""
    lines = [
        "ЛАЙНАП ЗМІНИВСЯ",
        headline(event),
        f"{city} · {when}",
        f"Якір: {score.anchor_text}",
        f"Покриття: {score.coverage_text}",
        f"Штраф: {score.penalty_text}",
        "Це три окремі числа, не середнє.",
    ]
    if event.url:
        lines.append(event.url)
    return "\n".join(lines)
