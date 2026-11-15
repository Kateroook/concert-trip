"""Окрема база в пам’яті, щоб тести не чіпали файл застосунку."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from concertrip.db import init_db, make_engine


@pytest.fixture()
def session():
    engine = make_engine("sqlite://")
    init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = factory()
    try:
        yield db
    finally:
        db.close()
