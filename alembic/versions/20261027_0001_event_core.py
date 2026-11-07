"""Create event core tables.

Revision ID: 20261027_0001
Revises:
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261027_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    op.create_table(
        "sources",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("code", name="uq_sources_code"),
    )
    op.create_table(
        "artists",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("musicbrainz_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_artists"),
        sa.UniqueConstraint("musicbrainz_id", name="uq_artists_musicbrainz_id"),
    )
    op.create_index("ix_artists_normalized_name", "artists", ["normalized_name"])
    op.create_table(
        "venues",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_venues"),
    )
    op.create_index("ix_venues_lookup", "venues", ["normalized_name", "city", "country_code"])
    op.create_table(
        "events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("artist_id", uuid_type, nullable=False),
        sa.Column("venue_id", uuid_type, nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("on_sale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], name="fk_events_artist_id_artists"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name="fk_events_source_id_sources"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], name="fk_events_venue_id_venues"),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_events_source_external"),
    )
    op.create_index("ix_events_date", "events", ["event_date"])
    op.create_index("ix_events_status_date", "events", ["status", "event_date"])
    op.create_index("ix_events_artist_date", "events", ["artist_id", "event_date"])
    op.create_index("ix_events_venue_date", "events", ["venue_id", "event_date"])
    op.create_table(
        "event_ticket_options",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("raw_label", sa.String(length=300), nullable=False),
        sa.Column("ticket_type", sa.String(length=30), nullable=False),
        sa.Column("is_vip", sa.Boolean(), nullable=False),
        sa.Column("availability_status", sa.String(length=50), nullable=False),
        sa.Column("price_min", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_max", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_ticket_options_event_id_events", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name="fk_event_ticket_options_source_id_sources"),
        sa.PrimaryKeyConstraint("id", name="pk_event_ticket_options"),
    )
    op.create_index(
        "ix_ticket_options_event_status",
        "event_ticket_options",
        ["event_id", "availability_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_options_event_status", table_name="event_ticket_options")
    op.drop_table("event_ticket_options")
    op.drop_index("ix_events_venue_date", table_name="events")
    op.drop_index("ix_events_artist_date", table_name="events")
    op.drop_index("ix_events_status_date", table_name="events")
    op.drop_index("ix_events_date", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_venues_lookup", table_name="venues")
    op.drop_table("venues")
    op.drop_index("ix_artists_normalized_name", table_name="artists")
    op.drop_table("artists")
    op.drop_table("sources")
