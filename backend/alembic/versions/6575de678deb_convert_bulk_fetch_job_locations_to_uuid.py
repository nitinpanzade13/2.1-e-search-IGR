"""convert_bulk_fetch_job_locations_to_uuid

Revision ID: 6575de678deb
Revises: e79aca856c14
Create Date: 2026-09-25 18:38:49.781765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6575de678deb'
down_revision: Union[str, Sequence[str], None] = 'e79aca856c14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('ALTER TABLE bulk_fetch_jobs ALTER COLUMN district_id TYPE UUID USING district_id::uuid')
    op.execute('ALTER TABLE bulk_fetch_jobs ALTER COLUMN taluka_id TYPE UUID USING taluka_id::uuid')
    op.execute('ALTER TABLE bulk_fetch_jobs ALTER COLUMN village_id TYPE UUID USING village_id::uuid')
    
    op.create_index(op.f('ix_bulk_fetch_jobs_district_id'), 'bulk_fetch_jobs', ['district_id'], unique=False)
    op.create_index(op.f('ix_bulk_fetch_jobs_taluka_id'), 'bulk_fetch_jobs', ['taluka_id'], unique=False)
    op.create_index(op.f('ix_bulk_fetch_jobs_village_id'), 'bulk_fetch_jobs', ['village_id'], unique=False)
    
    op.create_foreign_key('fk_bulk_fetch_jobs_district_id', 'bulk_fetch_jobs', 'districts', ['district_id'], ['id'])
    op.create_foreign_key('fk_bulk_fetch_jobs_taluka_id', 'bulk_fetch_jobs', 'talukas', ['taluka_id'], ['id'])
    op.create_foreign_key('fk_bulk_fetch_jobs_village_id', 'bulk_fetch_jobs', 'villages', ['village_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_bulk_fetch_jobs_village_id', 'bulk_fetch_jobs', type_='foreignkey')
    op.drop_constraint('fk_bulk_fetch_jobs_taluka_id', 'bulk_fetch_jobs', type_='foreignkey')
    op.drop_constraint('fk_bulk_fetch_jobs_district_id', 'bulk_fetch_jobs', type_='foreignkey')
    
    op.drop_index(op.f('ix_bulk_fetch_jobs_village_id'), table_name='bulk_fetch_jobs')
    op.drop_index(op.f('ix_bulk_fetch_jobs_taluka_id'), table_name='bulk_fetch_jobs')
    op.drop_index(op.f('ix_bulk_fetch_jobs_district_id'), table_name='bulk_fetch_jobs')

    op.execute('ALTER TABLE bulk_fetch_jobs ALTER COLUMN village_id TYPE VARCHAR USING village_id::text')
    op.execute('ALTER TABLE bulk_fetch_jobs ALTER COLUMN taluka_id TYPE VARCHAR USING taluka_id::text')
    op.execute('ALTER TABLE bulk_fetch_jobs ALTER COLUMN district_id TYPE VARCHAR USING district_id::text')
