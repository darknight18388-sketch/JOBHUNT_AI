"""add jobs.country

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("country", sa.String(8), nullable=False, server_default=""))
    op.create_index("ix_jobs_country", "jobs", ["country"])


def downgrade():
    op.drop_index("ix_jobs_country", table_name="jobs")
    op.drop_column("jobs", "country")
