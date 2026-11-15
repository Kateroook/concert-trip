"""Порядок стрічки. Смак впливає лише на сортування, не на сповіщення."""

from __future__ import annotations

from datetime import date

from concertrip.models import Event


def relevance(
    event: Event,
    watch_ids: set[int],
    liked_genres: set[str],
    today: date | None = None,
) -> float:
    today = today or date.today()
    artist_ids = {link.artist_id for link in event.artists_link}
    score = 100.0 if artist_ids & watch_ids else 0.0
    genres: set[str] = set()
    for link in event.artists_link:
        if link.artist and link.artist.genres:
            genres.update(part.strip().lower() for part in link.artist.genres.split(",") if part.strip())
    score += 15.0 * len(genres & liked_genres)
    days = (event.event_date - today).days
    if 0 <= days <= 21:
        score += 10
    elif 0 <= days <= 60:
        score += 5
    return score
