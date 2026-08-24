"""add profile, terms, and skill verification fields

Revision ID: 7f32e142ac90
Revises: 2e0eae4b912f
"""
from alembic import op
import sqlalchemy as sa

revision = "7f32e142ac90"
down_revision = "2e0eae4b912f"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("portfolio_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("certificate_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("user_skills", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("user_skills", "is_verified", server_default=None)

def downgrade():
    op.drop_column("user_skills", "is_verified")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "certificate_url")
    op.drop_column("users", "portfolio_url")
