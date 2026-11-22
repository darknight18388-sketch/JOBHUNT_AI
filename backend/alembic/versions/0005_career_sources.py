"""career_sources (user-watched company career pages)

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "career_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("ats", sa.String(20), nullable=False),
        sa.Column("token", sa.String(80), nullable=False),
        sa.Column("country", sa.String(8), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=False),
        sa.Column("last_error", sa.String(300), nullable=False),
        sa.Column("last_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_user_id", "url", name="uq_career_owner_url"),
    )
    op.create_index("ix_career_sources_owner_user_id", "career_sources", ["owner_user_id"])


def downgrade():
    op.drop_index("ix_career_sources_owner_user_id", table_name="career_sources")
    op.drop_table("career_sources")
