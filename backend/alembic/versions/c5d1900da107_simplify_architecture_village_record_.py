"""simplify_architecture_village_record_details

Revision ID: c5d1900da107
Revises: 75bfba57fa08
Create Date: 2026-09-27 13:26:17.162901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d1900da107'
down_revision: Union[str, Sequence[str], None] = '75bfba57fa08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to simplified village-level record details architecture."""
    # 1. Drop old acquisition tables in reverse dependency order
    old_tables = [
        "search_job_registrations",
        "pdf_tasks",
        "parties",
        "properties",
        "registrations",
        "offices",
        "parser_runs",
        "source_request_ledger",
        "artifacts",
        "search_jobs",
        "bulk_fetch_jobs",
        "ingestion_runs",
        "network_state",
        "worker_health",
    ]
    for table_name in old_tables:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

    # 2. Create minimal village fetch execution tracking table
    op.create_table(
        "village_fetches",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("village_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="QUEUED", nullable=False),
        sa.Column("current_search_value", sa.String(length=64), nullable=True),
        sa.Column("processed_search_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unique_records_saved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicates_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_village_fetches_village_id", "village_fetches", ["village_id"], unique=False)
    op.create_index("ix_village_fetches_status", "village_fetches", ["status"], unique=False)

    # 3. Create primary record_details table
    op.create_table(
        "record_details",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("village_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("sr_no", sa.String(length=64), nullable=True),
        sa.Column("doc_no", sa.String(length=128), nullable=False),
        sa.Column("doc_type", sa.String(length=255), nullable=True),
        sa.Column("office", sa.String(length=255), nullable=True),
        sa.Column("date", sa.String(length=64), nullable=True),
        sa.Column("seller", sa.Text(), nullable=True),
        sa.Column("buyer", sa.Text(), nullable=True),
        sa.Column("other_info", sa.Text(), nullable=True),
        sa.Column("indexii_url", sa.Text(), nullable=True),
        sa.Column("source_query", sa.String(length=128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_record_details_village_id", "record_details", ["village_id"], unique=False)
    op.create_index("ix_record_details_village_year", "record_details", ["village_id", "year"], unique=False)
    op.create_index("ix_record_details_doc_no", "record_details", ["doc_no"], unique=False)
    op.execute(
        "CREATE UNIQUE INDEX uq_record_details_village_doc ON record_details (village_id, year, doc_no, COALESCE(office, ''))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("record_details")
    op.drop_table("village_fetches")
