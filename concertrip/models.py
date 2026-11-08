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
    ticketmaster_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)

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
    ticketmaster_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)

    events = relationship("Event", back_populates="venue")


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_events_source_external"),
        Index("ix_events_date", "event_date"),
        Index("ix_events_status_date", "status", "event_date"),
        Index("ix_events_date_status", "date_status", "event_date"),
        Index("ix_events_artist_date", "artist_id", "event_date"),
        Index("ix_events_venue_date", "venue_id", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artists.id"), nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    date_status: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)
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
        UniqueConstraint("event_id", "source_id", "external_key", name="uq_ticket_options_external"),
        Index("ix_ticket_options_event_status", "event_id", "availability_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_key: Mapped[str] = mapped_column(String(200), nullable=True)
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
    external_accounts = relationship(
        "ExternalAccount", back_populates="user", cascade="all, delete-orphan"
    )
    spotify_oauth_states = relationship(
        "SpotifyOAuthState", back_populates="user", cascade="all, delete-orphan"
    )
    music_preferences = relationship(
        "MusicPreference", back_populates="user", cascade="all, delete-orphan"
    )
    artist_follows = relationship(
        "UserArtistFollow", back_populates="user", cascade="all, delete-orphan"
    )
    event_actions = relationship(
        "UserEventAction", back_populates="user", cascade="all, delete-orphan"
    )
    profile_embedding = relationship(
        "UserProfileEmbedding", back_populates="user", cascade="all, delete-orphan", uselist=False
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


class ExternalAccount(TimestampMixin, Base):
    __tablename__ = "external_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_external_accounts_user_provider"),
        UniqueConstraint("provider", "provider_account_id", name="uq_external_accounts_provider_account"),
        Index("ix_external_accounts_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(200), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[str] = mapped_column(String(1000), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="connected", nullable=False)

    user = relationship("User", back_populates="external_accounts")


class SpotifyOAuthState(TimestampMixin, Base):
    __tablename__ = "spotify_oauth_states"
    __table_args__ = (Index("ix_spotify_oauth_states_hash", "state_hash", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="spotify_oauth_states")


class MusicPreference(TimestampMixin, Base):
    __tablename__ = "music_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider", "provider_artist_id", "source", "time_range",
            name="uq_music_preferences_identity",
        ),
        Index("ix_music_preferences_user_weight", "user_id", "weight"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artists.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_artist_id: Mapped[str] = mapped_column(String(200), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    time_range: Mapped[str] = mapped_column(String(30), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    genres: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = relationship("User", back_populates="music_preferences")
    artist = relationship("Artist")


class UserArtistFollow(TimestampMixin, Base):
    __tablename__ = "user_artist_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "artist_id", name="uq_user_artist_follows_identity"),
        Index("ix_user_artist_follows_user_priority", "user_id", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artists.id"), nullable=False)
    priority: Mapped[Decimal] = mapped_column(Numeric(8, 5), default=Decimal("3.0"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="artist_follows")
    artist = relationship("Artist")


class UserEventAction(TimestampMixin, Base):
    __tablename__ = "user_event_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", "action", name="uq_user_event_actions_identity"),
        Index("ix_user_event_actions_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)

    user = relationship("User", back_populates="event_actions")
    event = relationship("Event")


class EventEmbedding(TimestampMixin, Base):
    __tablename__ = "event_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    event = relationship("Event")


class UserProfileEmbedding(TimestampMixin, Base):
    __tablename__ = "user_profile_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    user = relationship("User", back_populates="profile_embedding")