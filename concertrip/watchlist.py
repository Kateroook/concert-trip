"""Список артистів і позначені події."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.models import Artist, WatchEvent, WatchItem, utcnow
from concertrip.normalize.artists import normalize_artist_name
from concertrip.reference import ARTIST_GENRES


def watch_id_set(session: Session) -> set[int]:
    return set(session.scalars(select(WatchItem.artist_id)).all())


def liked_genre_set(session: Session) -> set[str]:
    genres: set[str] = set()
    items = session.scalars(select(WatchItem)).all()
    for item in items:
        if item.artist and item.artist.genres:
            genres.update(part.strip().lower() for part in item.artist.genres.split(",") if part.strip())
    return genres


def list_watch(session: Session) -> list[WatchItem]:
    return list(session.scalars(select(WatchItem).order_by(WatchItem.created_at)).all())


def follow_name(
    session: Session,
    name: str,
    *,
    spotify_id: str | None = None,
    popularity: int | None = None,
    genres: list[str] | None = None,
) -> Artist | None:
    normalized = normalize_artist_name(name)
    if not normalized:
        return None
    artist = session.scalar(select(Artist).where(Artist.normalized_name == normalized))
    if artist is None:
        artist = Artist(name=name.strip(), normalized_name=normalized, genres=ARTIST_GENRES.get(normalized))
        session.add(artist)
        session.flush()
    if spotify_id:
        artist.spotify_id = spotify_id
    if popularity is not None:
        artist.popularity = popularity
    if genres:
        artist.genres = ",".join(genres)
    elif not artist.genres and normalized in ARTIST_GENRES:
        artist.genres = ARTIST_GENRES[normalized]
    existing = session.scalar(select(WatchItem).where(WatchItem.artist_id == artist.id))
    if existing is None:
        session.add(WatchItem(artist_id=artist.id, created_at=utcnow()))
    session.commit()
    from concertrip.ranking.festival import recompute_festivals

    recompute_festivals(session)
    return artist


def unfollow(session: Session, artist_id: int) -> None:
    item = session.scalar(select(WatchItem).where(WatchItem.artist_id == artist_id))
    if item is not None:
        session.delete(item)
        session.commit()
    from concertrip.ranking.festival import recompute_festivals

    recompute_festivals(session)


def set_watch_event(session: Session, event_id: int, ticket_type: str) -> WatchEvent:
    row = session.scalar(select(WatchEvent).where(WatchEvent.event_id == event_id))
    if row is None:
        row = WatchEvent(event_id=event_id, ticket_type_filter=ticket_type, created_at=utcnow())
        session.add(row)
    else:
        row.ticket_type_filter = ticket_type
    session.commit()
    return row


def clear_watch_event(session: Session, event_id: int) -> None:
    row = session.scalar(select(WatchEvent).where(WatchEvent.event_id == event_id))
    if row is not None:
        session.delete(row)
        session.commit()


def watched_event_ids(session: Session) -> dict[int, str]:
    rows = session.scalars(select(WatchEvent)).all()
    return {row.event_id: row.ticket_type_filter for row in rows}
