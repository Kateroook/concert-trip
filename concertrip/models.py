"""Доменные SQLAlchemy-модели event-core ConcerTrip."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from concertrip.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    events = relationship("Event", back_populates="source")
    ticket_options = relationship("EventTicketOption", back_populates="source")


class Artist(TimestampMixin, Base):
    __tablename__ = "artists"
    __table_args__ = (Index("ix_artists_normalized_name", "normalized_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    musicbrainz_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=True)

    events = relationship("Event", back_populates="artist")


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"
    __table_args__ = (
        Index("ix_venues_lookup", "normalized_name", "city", "country_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=True)

    events = relationship("Event", back_populates="venue")


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_events_source_external"),
        Index("ix_events_date", "event_date"),
        Index("ix_events_status_date", "status", "event_date"),
        Index("ix_events_artist_date", "artist_id", "event_date"),
        Index("ix_events_venue_date", "venue_id", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artists.id"), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    on_sale_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)

    source = relationship("Source", back_populates="events")
    artist = relationship("Artist", back_populates="events")
    venue = relationship("Venue", back_populates="events")
    ticket_options = relationship(
        "EventTicketOption",
        back_populates="event", cascade="all, delete-orphan"
    )


class EventTicketOption(TimestampMixin, Base):
    __tablename__ = "event_ticket_options"
    __table_args__ = (
        Index("ix_ticket_options_event_status", "event_id", "availability_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    raw_label: Mapped[str] = mapped_column(String(300), nullable=False)
    ticket_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_vip: Mapped[bool] = mapped_column(default=False, nullable=False)
    availability_status: Mapped[str] = mapped_column(String(50), nullable=False)
    price_min: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    price_max: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    event = relationship("Event", back_populates="ticket_options")
    source = relationship("Source", back_populates="ticket_options")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    verification_tokens = relationship(
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    device_name: Mapped[str] = mapped_column(String(120), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class EmailVerificationToken(TimestampMixin, Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (Index("ix_email_verification_tokens_hash", "token_hash", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="verification_tokens")