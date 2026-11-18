"""job_sources and jobs

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_sources",
        sa.Column("key", sa.String(30), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=False),
        sa.Column("last_error", sa.String(300), nullable=False),
        sa.Column("last_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_key", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("is_remote", sa.Boolean(), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("salary_text", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dedupe_key", sa.String(40), nullable=False),
        sa.UniqueConstraint("source_key", "external_id", name="uq_job_source_ext"),
    )
    op.create_index("ix_jobs_source_key", "jobs", ["source_key"])
    op.create_index("ix_jobs_owner_user_id", "jobs", ["owner_user_id"])
    op.create_index("ix_jobs_posted_at", "jobs", ["posted_at"])
    op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"])


def downgrade():
    for ix in ("ix_jobs_dedupe_key", "ix_jobs_posted_at", "ix_jobs_owner_user_id", "ix_jobs_source_key"):
        op.drop_index(ix, table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("job_sources")
