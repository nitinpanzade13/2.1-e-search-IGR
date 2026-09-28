import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# The db_session fixture is now replaced by the central db fixture in tests.
from app.location_master.importer import LocationImporter, IgrLocationClient

@pytest.fixture
def db_session(db):
    # We must start with clean tables for tests so they don't fail due to existing MH state
    from app.models.location import State, District, Taluka, Village
    from app.models.village_fetch import VillageFetch
    from app.models.record_detail import RecordDetail
    
    db.rollback()
    
    db.query(RecordDetail).delete()
    db.query(VillageFetch).delete()
    db.query(Village).delete()
    db.query(Taluka).delete()
    db.query(District).delete()
    db.query(State).delete()
    db.commit()
    
    yield db
from app.location_master.importer import LocationImporter, IgrLocationClient

class MockLocationClient(IgrLocationClient):
    def __init__(self):
        super().__init__()
        self.district_requests = 0
        self.taluka_requests = 0
        self.village_requests = 0

    def get_districts(self):
        self.district_requests += 1
        return [{"dist_code": "23", "mdist_name": "Pune"}]

    def get_talukas(self, district_id):
        self.taluka_requests += 1
        if district_id == "23":
            return [{"taluka_code": "1", "mtaluka_name": "Haveli"}]
        return []

    def get_villages(self, district_id, taluka_id):
        self.village_requests += 1
        if district_id == "23" and taluka_id == "1":
            # The API returns them as a list, index matters
            return [
                {"am_mareaname": "Dummy Village 1"},
                {"am_mareaname": "Kharadi"},
                {"am_mareaname": "Dummy Village 3"}
            ]
        return []

def test_importer_dry_run(db_session):
    importer = LocationImporter(db_session, dry_run=True)
    importer.client = MockLocationClient()
    
    summary = importer.run()
    
    assert summary.states_processed == 1
    assert summary.districts_processed == 1
    assert summary.talukas_processed == 1
    assert summary.villages_processed == 3
    
    # In dry-run with empty DB, it should pretend to insert
    assert summary.inserted == 6 # 1 state + 1 dist + 1 taluka + 3 vill
    assert summary.updated == 0
    assert summary.district_requests == 1
    assert summary.taluka_requests == 1
    assert summary.village_requests == 1
    assert summary.total_http_requests == 3

def test_importer_idempotent_insert(db_session):
    importer = LocationImporter(db_session, dry_run=False)
    importer.client = MockLocationClient()
    
    # First run
    summary1 = importer.run()
    assert summary1.inserted == 6
    assert summary1.unchanged == 0
    
    # Second run
    importer.client = MockLocationClient()
    importer.summary.inserted = 0 # reset summary
    importer.summary.updated = 0
    importer.summary.unchanged = 0
    summary2 = importer.run()
    
    assert summary2.inserted == 0
    assert summary2.updated == 0
    assert summary2.unchanged == 6 # all 6 exist
