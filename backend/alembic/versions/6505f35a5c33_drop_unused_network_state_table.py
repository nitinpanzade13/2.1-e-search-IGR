"""drop_unused_network_state_table

Revision ID: 6505f35a5c33
Revises: c4da13f62892
Create Date: 2026-09-27 21:13:39.595189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6505f35a5c33'
down_revision: Union[str, Sequence[str], None] = 'c4da13f62892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP TABLE IF EXISTS network_state CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS network_state_id_seq CASCADE")


def downgrade() -> None:
    """Downgrade schema."""
    pass
