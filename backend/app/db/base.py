# Import all the models, so that Base has them before being imported by Alembic
from app.core.database import Base

from app.models.location import State, District, Taluka, Village
from app.models.system import NetworkConfig
from app.models.record_detail import RecordDetail
from app.models.village_fetch import VillageFetch, VillageFetchStatus
