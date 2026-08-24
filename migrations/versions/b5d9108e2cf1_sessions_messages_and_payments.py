"""add rescheduling, messaging, payments, and review responses

Revision ID: b5d9108e2cf1
Revises: 7f32e142ac90
"""
from alembic import op
import sqlalchemy as sa

revision = "b5d9108e2cf1"
down_revision = "7f32e142ac90"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("reschedule_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("proposed_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.Enum("pending", "accepted", "declined"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reschedule_requests_session_id", "reschedule_requests", ["session_id"])
    op.create_table("messages",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_table("payments",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False, unique=True),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_reference", sa.String(length=255)), sa.Column("status", sa.Enum("pending", "paid", "refunded", "failed"), nullable=False),
        sa.Column("receipt_number", sa.String(length=80), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table("review_responses",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("feedback_id", sa.Integer(), sa.ForeignKey("feedback.id"), nullable=False, unique=True),
        sa.Column("responder_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table("review_responses")
    op.drop_table("payments")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_reschedule_requests_session_id", table_name="reschedule_requests")
    op.drop_table("reschedule_requests")
