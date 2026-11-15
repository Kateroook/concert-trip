"""Таблиці ConcerTrip."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from concertrip.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Artist(Base):
    __tablename__ = "artist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    spotify_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genres: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Venue(Base):
    __tablename__ = "venue"
    __table_args__ = (UniqueConstraint("name", "city", "country"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(2))
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Event(Base):
    __tablename__ = "event"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id"))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    on_sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    presale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    url: Mapped[str] = mapped_column(String(1000), default="")
    is_festival: Mapped[bool] = mapped_column(Boolean, default=False)
    lineup_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    venue: Mapped[Venue] = relationship()
    artists_link: Mapped[list[EventArtist]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    ticket_types: Mapped[list[TicketTypeRow]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventArtist(Base):
    __tablename__ = "event_artist"

    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artist.id"), primary_key=True)
    raw_name: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(Integer, default=0)

    event: Mapped[Event] = relationship(back_populates="artists_link")
    artist: Mapped[Artist] = relationship()


class TicketTypeRow(Base):
    __tablename__ = "ticket_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    raw_name: Mapped[str] = mapped_column(String(300))
    normalized_type: Mapped[str] = mapped_column(String(32))
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)

    event: Mapped[Event] = relationship(back_populates="ticket_types")


class WatchItem(Base):
    __tablename__ = "watch_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artist.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artist: Mapped[Artist] = relationship()


class WatchEvent(Base):
    __tablename__ = "watch_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), unique=True)
    ticket_type_filter: Mapped[str] = mapped_column(String(32), default="any")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    event: Mapped[Event] = relationship()


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_event_id: Mapped[int | None] = mapped_column(ForeignKey("watch_event.id"), nullable=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship()


class AvailabilitySnapshot(Base):
    __tablename__ = "availability_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceRun(Base):
    __tablename__ = "source_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    events_found: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class FestivalSnapshot(Base):
    """Окремі компоненти оцінки. Середнє навмисно не зберігаємо."""

    __tablename__ = "festival_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    anchor: Mapped[float] = mapped_column(Float)
    coverage: Mapped[float] = mapped_column(Float)
    penalty: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
