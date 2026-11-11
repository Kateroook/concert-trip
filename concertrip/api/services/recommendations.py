import hashlib
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from concertrip.api.schemas import EventItem, RecommendationItem
from concertrip.config import settings
from concertrip.models import (
    Event,
    EventEmbedding,
    MusicPreference,
    User,
    UserArtistFollow,
    UserProfileEmbedding,
)


class RecommendationError(RuntimeError):
    pass


MIN_SEMANTIC_SIMILARITY = 0.35


def _model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RecommendationError("sentence-transformers is not installed") from error
    return SentenceTransformer(settings.recommendation_model)


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize(vector: list[float]) -> list[float]:
    length = sum(value * value for value in vector) ** 0.5
    if not length:
        return vector
    return [value / length for value in vector]


def _weighted_mean(vectors: list[list[float]], weights: list[float]) -> list[float]:
    if not vectors:
        return []
    total_weight = sum(weights) or 1.0
    result = [0.0] * len(vectors[0])
    for vector, weight in zip(vectors, weights):
        for index, value in enumerate(vector):
            result[index] += value * weight / total_weight
    return _normalize(result)


def _profile_inputs(
    session: Session, user: User
) -> tuple[list[str], list[float], list[dict], set[str], set[str]]:
    preferences = session.scalars(
        select(MusicPreference).where(MusicPreference.user_id == user.id)
    ).all()
    follows = session.scalars(
        select(UserArtistFollow).options(selectinload(UserArtistFollow.artist)).where(
            UserArtistFollow.user_id == user.id,
            UserArtistFollow.is_active.is_(True),
        )
    ).all()
    texts: list[str] = []
    weights: list[float] = []
    identity: list[dict] = []
    artist_names: set[str] = set()
    genres: set[str] = set()
    for preference in preferences:
        preference_genres = {
            value.casefold() for value in (preference.genres or {}).get("values", [])
        }
        genres.update(preference_genres)
        genre_text = ", ".join(sorted(preference_genres))
        texts.append(f"{preference.artist_name}. {genre_text}".strip())
        weights.append(float(preference.weight))
        artist_names.add(" ".join(preference.artist_name.casefold().split()))
        identity.append(
            {
                "provider_artist_id": preference.provider_artist_id,
                "artist_name": preference.artist_name,
                "genres": sorted(preference_genres),
                "source": preference.source,
                "time_range": preference.time_range,
                "weight": str(preference.weight),
            }
        )
    for follow in follows:
        texts.append(follow.artist.name)
        weights.append(float(follow.priority))
        artist_names.add(" ".join(follow.artist.name.casefold().split()))
        identity.append({"follow_artist_id": str(follow.artist_id), "priority": str(follow.priority)})
    return texts, weights, identity, artist_names, genres


def _get_profile_vector(session: Session, user: User) -> list[float]:
    texts, weights, identity, _, _ = _profile_inputs(session, user)
    if not texts:
        raise RecommendationError("No music preferences or followed artists found")
    source_hash = _hash_payload({"version": "music-only-v3", "identity": identity})
    cached = session.scalar(
        select(UserProfileEmbedding).where(UserProfileEmbedding.user_id == user.id)
    )
    if cached and cached.model_name == settings.recommendation_model and cached.source_hash == source_hash:
        return cached.vector
    vectors = _model().encode(texts, normalize_embeddings=True).tolist()
    profile_vector = _weighted_mean(vectors, weights)
    if cached is None:
        cached = UserProfileEmbedding(user_id=user.id, model_name=settings.recommendation_model, source_hash=source_hash, vector=profile_vector)
    else:
        cached.model_name = settings.recommendation_model
        cached.source_hash = source_hash
        cached.vector = profile_vector
    session.add(cached)
    session.flush()
    return profile_vector


def _event_text(event: Event) -> str:
    genres = _event_genres(event)
    genre_text = ", ".join(sorted(genres)) if genres else "music"
    return f"{event.artist.name}. {genre_text}".strip()


def _scale_similarity(similarity: float) -> float:
    clamped = max(0.2, min(0.75, similarity))
    return (clamped - 0.2) / 0.55


def _event_genres(event: Event) -> set[str]:
    classifications = (event.raw_payload or {}).get("classifications") or []
    genres: set[str] = set()
    for classification in classifications:
        for key in ("segment", "genre", "subGenre"):
            value = (classification.get(key) or {}).get("name")
            if value:
                genres.add(value.casefold())
    return genres


def _event_item(event: Event) -> EventItem:
    option = event.ticket_options[0] if event.ticket_options else None
    return EventItem(
        id=event.id,
        artist=event.artist.name,
        venue=event.venue.name,
        city=event.venue.city,
        country=event.venue.country_code,
        eventDate=event.event_date.date() if event.event_date else None,
        onSaleDate=event.on_sale_at.date() if event.on_sale_at else None,
        dateStatus=event.date_status,
        ticketType=option.raw_label if option else "Unknown",
        status=event.status,
        url=event.url,
    )


def get_recommendations(session: Session, user: User, limit: int = 20) -> list[RecommendationItem]:
    profile_vector = _get_profile_vector(session, user)
    _, _, _, preferred_artist_names, preferred_genres = _profile_inputs(session, user)
    events = session.scalars(
        select(Event)
        .options(selectinload(Event.artist), selectinload(Event.venue), selectinload(Event.ticket_options))
        .order_by(Event.event_date.asc())
    ).unique().all()
    follows = {
        follow.artist_id: float(follow.priority)
        for follow in session.scalars(
            select(UserArtistFollow).where(
                UserArtistFollow.user_id == user.id,
                UserArtistFollow.is_active.is_(True),
            )
        ).all()
    }
    candidates: list[tuple[float, RecommendationItem]] = []
    model = None
    for event in events:
        text = _event_text(event)
        source_hash = _hash_payload({"text": text})
        embedding = session.scalar(
            select(EventEmbedding).where(EventEmbedding.event_id == event.id)
        )
        if embedding is None or embedding.model_name != settings.recommendation_model or embedding.source_hash != source_hash:
            if model is None:
                model = _model()
            vector = _normalize(model.encode([text], normalize_embeddings=True).tolist()[0])
            if embedding is None:
                embedding = EventEmbedding(event_id=event.id, model_name=settings.recommendation_model, source_hash=source_hash, vector=vector)
            else:
                embedding.model_name = settings.recommendation_model
                embedding.source_hash = source_hash
                embedding.vector = vector
            session.add(embedding)
        else:
            vector = embedding.vector
        similarity = sum(left * right for left, right in zip(profile_vector, vector))
        normalized_event_artist = " ".join(event.artist.name.casefold().split())
        exact_artist_match = normalized_event_artist in preferred_artist_names
        genre_overlap = preferred_genres.intersection(_event_genres(event))
        follow_priority = follows.get(event.artist_id, 0.0)
        semantic_threshold = MIN_SEMANTIC_SIMILARITY if preferred_genres else 0.55
        # if (
        #     not exact_artist_match
        #     and not follow_priority
        #     and not genre_overlap
        #     and similarity < semantic_threshold
        # ):
        #     continue
        similarity_score = _scale_similarity(similarity)
        if exact_artist_match:
            score = 0.95 + min(follow_priority / 10.0, 1.0) * 0.05
        else:
            genre_bonus = min(len(genre_overlap) * 0.1, 0.15)
            score = min(0.92, similarity_score * 0.75 + genre_bonus + min(follow_priority / 10.0, 1.0) * 0.2)
        if event.status in {"canceled", "offsale", "sold_out"}:
            score *= 0.5
        reasons = []
        if follow_priority:
            reasons.append("You explicitly follow this artist")
        if exact_artist_match:
            reasons.append("Matches an artist from your Spotify profile")
        if genre_overlap:
            reasons.append(f"Matches your preferred genre: {sorted(genre_overlap)[0]}")
        if similarity >= semantic_threshold and not exact_artist_match:
            reasons.append("Artist and event are close to your music profile")
        if event.status not in {"canceled", "offsale", "sold_out"}:
            reasons.append("Tickets appear available")
        candidates.append((score, RecommendationItem(event=_event_item(event), score=score, reasons=reasons)))
    session.commit()
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    return [item for _, item in candidates[:limit]]
