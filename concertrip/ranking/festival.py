"""Три окремі числа для фестивалю. Середнє навмисно не існує."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.models import Alert, Artist, Event, FestivalSnapshot, utcnow
from concertrip.normalize.artists import normalize_artist_name
from concertrip.prefs import unwanted_genres
from concertrip.watchlist import liked_genre_set, watch_id_set

ANCHOR_THRESHOLD = 0.8


@dataclass(frozen=True)
class FestivalScore:
    anchor: float
    coverage: float
    penalty: float
    enjoyed: int
    unwanted_count: int
    total: int
    anchor_text: str
    coverage_text: str
    penalty_text: str

    @property
    def justified(self) -> bool:
        # Один улюблений артист виправдовує поїздку сам. Середнє це ламає.
        return self.anchor >= ANCHOR_THRESHOLD


def score_lineup(
    names: list[str],
    artists_by_key: dict[str, Artist],
    watch_ids: set[int],
    liked: set[str],
    unwanted: set[str],
) -> FestivalScore | None:
    cleaned = [name.strip() for name in names if name and name.strip()]
    if not cleaned:
        return None
    enjoyed = 0
    penalised = 0
    anchor = 0.0
    for name in cleaned:
        artist = artists_by_key.get(normalize_artist_name(name))
        genres = _genres(artist)
        on_list = artist is not None and artist.id in watch_ids
        if on_list:
            anchor = 1.0
            enjoyed += 1
        elif genres & liked and not (genres & unwanted):
            enjoyed += 1
        if genres & unwanted:
            penalised += 1
    total = len(cleaned)
    coverage = enjoyed / total
    penalty = penalised / total
    if anchor >= ANCHOR_THRESHOLD:
        anchor_text = "У лайнапі є артист із твого списку. Цього досить, щоб їхати."
    else:
        anchor_text = "У лайнапі немає артиста, за яким ти стежиш."
    coverage_text = f"{enjoyed} з {total} артистів тобі близькі."
    penalty_text = f"{penalised} з {total} у жанрах, які ти не хочеш."
    return FestivalScore(
        anchor=anchor,
        coverage=coverage,
        penalty=penalty,
        enjoyed=enjoyed,
        unwanted_count=penalised,
        total=total,
        anchor_text=anchor_text,
        coverage_text=coverage_text,
        penalty_text=penalty_text,
    )


def score_event(session: Session, event: Event) -> FestivalScore | None:
    if not event.is_festival or not event.lineup_json:
        return None
    try:
        names = json.loads(event.lineup_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(names, list):
        return None
    keys = [normalize_artist_name(str(name)) for name in names]
    artists = session.scalars(select(Artist).where(Artist.normalized_name.in_(keys))).all() if keys else []
    by_key = {artist.normalized_name: artist for artist in artists}
    return score_lineup(names, by_key, watch_id_set(session), liked_genre_set(session), unwanted_genres(session))


def recompute_festivals(session: Session) -> list[Alert]:
    from concertrip.notify.messages import lineup_message

    created: list[Alert] = []
    events = session.scalars(select(Event).where(Event.is_festival.is_(True))).all()
    for event in events:
        score = score_event(session, event)
        if score is None:
            continue
        previous = session.scalar(
            select(FestivalSnapshot)
            .where(FestivalSnapshot.event_id == event.id)
            .order_by(FestivalSnapshot.id.desc())
        )
        session.add(
            FestivalSnapshot(
                event_id=event.id,
                anchor=score.anchor,
                coverage=score.coverage,
                penalty=score.penalty,
            )
        )
        crossed = previous is not None and previous.anchor < ANCHOR_THRESHOLD <= score.anchor
        if crossed:
            created.append(
                Alert(
                    event_id=event.id,
                    kind="lineup",
                    body=lineup_message(event, score),
                    status="queued",
                )
            )
    session.add_all(created)
    session.commit()
    return created


def _genres(artist: Artist | None) -> set[str]:
    if artist is None or not artist.genres:
        return set()
    return {part.strip().lower() for part in artist.genres.split(",") if part.strip()}
