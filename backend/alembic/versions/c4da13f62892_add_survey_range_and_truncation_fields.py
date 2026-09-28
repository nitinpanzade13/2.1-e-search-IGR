"""add_survey_range_and_truncation_fields

Revision ID: c4da13f62892
Revises: c5d1900da107
Create Date: 2026-09-27 13:53:13.590192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4da13f62892'
down_revision: Union[str, Sequence[str], None] = 'c5d1900da107'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("record_details", sa.Column("is_truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("record_details", sa.Column("reported_count", sa.Integer(), nullable=True))

    op.add_column("village_fetches", sa.Column("survey_range_start", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("village_fetches", sa.Column("survey_range_end", sa.Integer(), server_default=sa.text("100"), nullable=False))
    op.add_column("village_fetches", sa.Column("truncated_searches_count", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("village_fetches", "truncated_searches_count")
    op.drop_column("village_fetches", "survey_range_end")
    op.drop_column("village_fetches", "survey_range_start")

    op.drop_column("record_details", "reported_count")
    op.drop_column("record_details", "is_truncated")
