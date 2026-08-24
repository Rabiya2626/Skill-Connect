"""add booking approval state and notification session links

Revision ID: 2e0eae4b912f
Revises: c286e8854ae2
Create Date: 2026-07-30 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2e0eae4b912f"
down_revision = "c286e8854ae2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE sessions MODIFY COLUMN status "
        "ENUM('pending', 'confirmed', 'completed', 'cancelled', 'no_show') NOT NULL"
    )
    op.add_column("notifications", sa.Column("session_id", sa.Integer(), nullable=True))
    op.create_index("ix_notifications_session_id", "notifications", ["session_id"])
    op.create_foreign_key(
        "fk_notifications_session_id", "notifications", "sessions", ["session_id"], ["id"]
    )


def downgrade():
    op.execute("UPDATE sessions SET status = 'cancelled' WHERE status = 'pending'")
    op.drop_constraint("fk_notifications_session_id", "notifications", type_="foreignkey")
    op.drop_index("ix_notifications_session_id", table_name="notifications")
    op.drop_column("notifications", "session_id")
    op.execute(
        "ALTER TABLE sessions MODIFY COLUMN status "
        "ENUM('confirmed', 'completed', 'cancelled', 'no_show') NOT NULL"
    )
