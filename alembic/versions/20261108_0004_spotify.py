"""Add Spotify integrations and music preferences.

Revision ID: 20261108_0004
Revises: 20261108_0003
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0004"
down_revision: Union[str, None] = "20261108_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)

    op.create_table(
        "external_accounts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_account_id", sa.String(length=200), nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=4096), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.String(length=1000), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_external_accounts_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_external_accounts"),
        sa.UniqueConstraint("user_id", "provider", name="uq_external_accounts_user_provider"),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_external_accounts_provider_account"),
    )
    op.create_index("ix_external_accounts_user", "external_accounts", ["user_id"])

    op.create_table(
        "spotify_oauth_states",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_spotify_oauth_states_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_spotify_oauth_states"),
    )
    op.create_index("ix_spotify_oauth_states_hash", "spotify_oauth_states", ["state_hash"], unique=True)

    op.create_table(
        "music_preferences",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("artist_id", uuid_type, nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_artist_id", sa.String(length=200), nullable=False),
        sa.Column("artist_name", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("time_range", sa.String(length=30), nullable=False),
        sa.Column("weight", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"], name="fk_music_preferences_artist_id_artists"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_music_preferences_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_music_preferences"),
        sa.UniqueConstraint(
            "user_id", "provider", "provider_artist_id", "source", "time_range",
            name="uq_music_preferences_identity",
        ),
    )
    op.create_index("ix_music_preferences_user_weight", "music_preferences", ["user_id", "weight"])


def downgrade() -> None:
    op.drop_index("ix_music_preferences_user_weight", table_name="music_preferences")
    op.drop_table("music_preferences")
    op.drop_index("ix_spotify_oauth_states_hash", table_name="spotify_oauth_states")
    op.drop_table("spotify_oauth_states")
    op.drop_index("ix_external_accounts_user", table_name="external_accounts")
    op.drop_table("external_accounts")
