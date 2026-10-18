"""CT-12. Підключення до бази й моделі.

Заготовка: повні моделі додаються в CT-12. Тут лише створення підключення,
щоб решта модулів уже мала куди звертатися.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from concertrip.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass
