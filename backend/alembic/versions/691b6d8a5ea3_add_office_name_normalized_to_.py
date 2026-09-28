"""Add office_name_normalized to registrations

Revision ID: 691b6d8a5ea3
Revises: 2163f24f14a7
Create Date: 2026-09-06 11:23:01.935975

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '691b6d8a5ea3'
down_revision: Union[str, Sequence[str], None] = '2163f24f14a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('registrations', sa.Column('office_name_normalized', sa.String(), nullable=True))
    op.create_index(op.f('ix_registrations_office_name_normalized'), 'registrations', ['office_name_normalized'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_registrations_office_name_normalized'), table_name='registrations')
    op.drop_column('registrations', 'office_name_normalized')
