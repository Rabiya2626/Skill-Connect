"""store generated Jitsi meeting links

Revision ID: d68af4ca0983
Revises: b5d9108e2cf1
"""
from alembic import op
import sqlalchemy as sa

revision = "d68af4ca0983"
down_revision = "b5d9108e2cf1"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sessions", sa.Column("meeting_url", sa.String(length=500), nullable=True))

def downgrade():
    op.drop_column("sessions", "meeting_url")
