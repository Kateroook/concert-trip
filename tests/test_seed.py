import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from concertrip.db import Base
from concertrip.models import Event, EventTicketOption
from concertrip.sources.seed import import_seed


@pytest.fixture
def seed_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_seed_import_is_idempotent(seed_db):
    engine, session_factory = seed_db

    first = import_seed(session_factory=session_factory)
    second = import_seed(session_factory=session_factory)

    with Session(engine) as session:
        assert first.events_created == 5
        assert second.events_created == 0
        assert second.events_updated == 5
        assert session.scalar(select(func.count(Event.id))) == 5
        assert session.scalar(select(func.count(EventTicketOption.id))) == 5
