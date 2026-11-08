"""Add Ticketmaster identity and date fields.

Revision ID: 20261108_0003
Revises: 20261108_0002
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261108_0003"
down_revision: Union[str, None] = "20261108_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("artists", sa.Column("ticketmaster_id", sa.String(length=100), nullable=True))
    op.create_index("ix_artists_ticketmaster_id", "artists", ["ticketmaster_id"], unique=True)

    op.add_column("venues", sa.Column("ticketmaster_id", sa.String(length=100), nullable=True))
    op.create_index("ix_venues_ticketmaster_id", "venues", ["ticketmaster_id"], unique=True)

    with op.batch_alter_table("events") as batch_op:
        batch_op.alter_column("event_date", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch_op.add_column(
            sa.Column("date_status", sa.String(length=20), nullable=False, server_default="confirmed")
        )
        batch_op.create_index("ix_events_date_status", ["date_status", "event_date"])

    with op.batch_alter_table("event_ticket_options") as batch_op:
        batch_op.add_column(sa.Column("external_key", sa.String(length=200), nullable=True))
        batch_op.create_unique_constraint(
            "uq_ticket_options_external", ["event_id", "source_id", "external_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("event_ticket_options") as batch_op:
        batch_op.drop_constraint("uq_ticket_options_external", type_="unique")
        batch_op.drop_column("external_key")

    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_index("ix_events_date_status")
        batch_op.drop_column("date_status")
        batch_op.alter_column("event_date", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.drop_index("ix_venues_ticketmaster_id", table_name="venues")
    op.drop_column("venues", "ticketmaster_id")
    op.drop_index("ix_artists_ticketmaster_id", table_name="artists")
    op.drop_column("artists", "ticketmaster_id")