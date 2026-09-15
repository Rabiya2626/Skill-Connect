"""add meeting participation state

Revision ID: 8f0c6a7b1d2e
Revises: 7d7b2a6f0ef2
"""

from alembic import op
import sqlalchemy as sa

revision = "8f0c6a7b1d2e"
down_revision = "7d7b2a6f0ef2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tutor_joined_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("learner_joined_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("tutor_left_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("learner_left_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("both_joined_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("meeting_closed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("meeting_closed_at")
        batch_op.drop_column("both_joined_at")
        batch_op.drop_column("learner_left_at")
        batch_op.drop_column("tutor_left_at")
        batch_op.drop_column("learner_joined_at")
        batch_op.drop_column("tutor_joined_at")