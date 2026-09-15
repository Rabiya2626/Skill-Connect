"""remove_tutor_approval_flag

Revision ID: 7d7b2a6f0ef2
Revises: e9a1c467d213
Create Date: 2026-09-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7d7b2a6f0ef2"
down_revision = "e9a1c467d213"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tutors", schema=None) as batch_op:
        batch_op.drop_column("approved_by_admin")


def downgrade():
    with op.batch_alter_table("tutors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("approved_by_admin", sa.Boolean(), nullable=True))
        batch_op.execute(sa.text("UPDATE tutors SET approved_by_admin = 1"))
        batch_op.alter_column("approved_by_admin", nullable=False)
