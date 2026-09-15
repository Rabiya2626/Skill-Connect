"""add platform reports

Revision ID: e9a1c467d213
Revises: d68af4ca0983
"""
from alembic import op
import sqlalchemy as sa

revision = "e9a1c467d213"
down_revision = "d68af4ca0983"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reported_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id")),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.Enum("low", "medium", "high"), nullable=False),
        sa.Column("status", sa.Enum("open", "in_review", "resolved", "dismissed"), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    op.create_index("ix_reports_reported_user_id", "reports", ["reported_user_id"])
    op.create_index("ix_reports_session_id", "reports", ["session_id"])


def downgrade():
    op.drop_index("ix_reports_session_id", table_name="reports")
    op.drop_index("ix_reports_reported_user_id", table_name="reports")
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_table("reports")
