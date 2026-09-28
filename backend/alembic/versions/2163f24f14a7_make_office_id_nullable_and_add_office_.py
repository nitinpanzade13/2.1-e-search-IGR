"""Make office_id nullable and add office_name_raw

Revision ID: 2163f24f14a7
Revises: 64cba9a76567
Create Date: 2026-09-04 16:11:59.736291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2163f24f14a7'
down_revision: Union[str, Sequence[str], None] = '64cba9a76567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('registrations', 'office_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('registrations', sa.Column('office_name_raw', sa.String(), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('registrations', 'office_name_raw')
    op.alter_column('registrations', 'office_id', existing_type=sa.UUID(), nullable=False)
