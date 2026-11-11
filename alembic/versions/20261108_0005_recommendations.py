"""Add recommendation feedback and embedding caches.

Revision ID: 20261108_0005
Revises: 20261108_0004
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0005"
down_revision: Union[str, None] = "20261108_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    op.create_table(
        "user_artist_follows",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("artist_id", uuid_type, nullable=False),
        sa.Column("priority", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], name="fk_user_artist_follows_artist_id_artists"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_artist_follows_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_artist_follows"),
        sa.UniqueConstraint("user_id", "artist_id", name="uq_user_artist_follows_identity"),
    )
    op.create_index("ix_user_artist_follows_user_priority", "user_artist_follows", ["user_id", "priority"])

    op.create_table(
        "user_event_actions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_user_event_actions_event_id_events", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_event_actions_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_event_actions"),
        sa.UniqueConstraint("user_id", "event_id", "action", name="uq_user_event_actions_identity"),
    )
    op.create_index("ix_user_event_actions_user", "user_event_actions", ["user_id"])

    op.create_table(
        "event_embeddings",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("event_id", uuid_type, nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_embeddings_event_id_events", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_event_embeddings"),
        sa.UniqueConstraint("event_id", name="uq_event_embeddings_event_id"),
    )

    op.create_table(
        "user_profile_embeddings",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_profile_embeddings_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_profile_embeddings"),
        sa.UniqueConstraint("user_id", name="uq_user_profile_embeddings_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_profile_embeddings")
    op.drop_table("event_embeddings")
    op.drop_index("ix_user_event_actions_user", table_name="user_event_actions")
    op.drop_table("user_event_actions")
    op.drop_index("ix_user_artist_follows_user_priority", table_name="user_artist_follows")
    op.drop_table("user_artist_follows")
