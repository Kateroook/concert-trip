from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from concertrip.config import settings
from concertrip.db import Base
from concertrip.models import Artist, Event, EventTicketOption, MusicPreference, Source, User, Venue
from concertrip.api.services import recommendations


class Encoded:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class FakeModel:
    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for text in texts:
            vectors.append([1.0, 0.0, 0.0] if "Tame" in text else [0.0, 1.0, 0.0])
        return Encoded(vectors)


def test_recommendations_use_weighted_profile_and_cache(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'recommendations.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="recommend@example.com", password_hash="hash", is_verified=True)
        source = Source(code="test", name="Test")
        tame = Artist(name="Tame Impala", normalized_name="tame impala")
        other = Artist(name="Other Artist", normalized_name="other artist")
        venue = Venue(name="The O2", normalized_name="the o2", city="London", country_code="GB")
        session.add_all([user, source, tame, other, venue])
        session.flush()
        session.add(
            MusicPreference(
                user_id=user.id,
                artist_id=tame.id,
                provider="spotify",
                provider_artist_id="spotify-tame",
                artist_name="Tame Impala",
                source="top_artists",
                time_range="long_term",
                weight=1.0,
                genres={"values": ["psychedelic rock"]},
            )
        )
        session.add_all(
            [
                Event(
                    source=source,
                    artist=tame,
                    venue=venue,
                    external_id="tame-event",
                    title="Tame Impala Live",
                    event_date=datetime(2027, 5, 28, tzinfo=timezone.utc),
                    status="onsale",
                    url="https://example.org/tame",
                ),
                Event(
                    source=source,
                    artist=other,
                    venue=venue,
                    external_id="other-event",
                    title="Other Artist Live",
                    event_date=datetime(2027, 6, 1, tzinfo=timezone.utc),
                    status="onsale",
                    url="https://example.org/other",
                ),
            ]
        )
        session.commit()
        object.__setattr__(settings, "recommendation_model", "fake-model")
        monkeypatch.setattr(recommendations, "_model", lambda: FakeModel())

        first = recommendations.get_recommendations(session, user, limit=2)
        second = recommendations.get_recommendations(session, user, limit=2)

        assert first[0].event.artist == "Tame Impala"
        assert len(first) == 1
        assert first[0].score >= 0.95
        assert first[0].reasons
        assert [item.event.id for item in first] == [item.event.id for item in second]
