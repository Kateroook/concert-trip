"""Підключення до SQLite і створення таблиць."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from concertrip.config import settings


class Base(DeclarativeBase):
    pass


def _sqlite_path(url: str) -> Path | None:
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url == "sqlite://":
        return None
    raw = url[len(prefix):]
    if raw == ":memory:" or raw.startswith("file:"):
        return None
    return Path(raw)


def make_engine(url: str | None = None):
    url = url or settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        path = _sqlite_path(url)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(bind=None) -> None:
    from concertrip import models  # noqa: F401  реєструє таблиці

    Base.metadata.create_all(bind or engine)


@contextmanager
def session_scope(bind=None):
    factory = sessionmaker(bind=bind or engine, expire_on_commit=False, future=True)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
