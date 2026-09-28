"""Add CANCELLED to search_job_status_enum

Revision ID: 75bfba57fa08
Revises: 6575de678deb
Create Date: 2026-09-25 19:27:31.392404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75bfba57fa08'
down_revision: Union[str, Sequence[str], None] = '6575de678deb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PostgreSQL cannot add enum values inside a transaction block in older versions, 
    # but Alembic runs in transaction. We use execute with execution_options
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE search_job_status_enum ADD VALUE IF NOT EXISTS 'CANCELLED'")
        op.execute("ALTER TYPE bulk_fetch_job_status_enum ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
