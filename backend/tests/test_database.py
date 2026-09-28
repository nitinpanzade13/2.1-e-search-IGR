import pytest
import uuid
from datetime import datetime, timezone
from app.core.config import settings

from app.models.location import State, District, Taluka, Village
from app.models.system import NetworkConfig
from app.models.village_fetch import VillageFetch, VillageFetchStatus
from app.models.record_detail import RecordDetail
from sqlalchemy.exc import IntegrityError

def test_test_database_isolation(db):
    """
    Ensure the test database is isolated and not pointing to the main database.
    """
    assert str(db.bind.url).endswith("esearch_igr_test")
    assert "esearch_igr_test" in str(settings.TEST_DATABASE_URL)
    
def test_test_database_isolation_db_name(db):
    from sqlalchemy import text
    db_name = db.execute(text("SELECT current_database();")).scalar()
    assert db_name == "esearch_igr_test"

def test_location_hierarchy(db):
    suffix = str(uuid.uuid4())[:8]
    state = State(source_id=f"S1_{suffix}", name_en=f"Maharashtra_{suffix}")
    district = District(state=state, source_id=f"D1_{suffix}", name_en=f"Pune_{suffix}")
    taluka = Taluka(district=district, source_id=f"T1_{suffix}", name_en=f"Haveli_{suffix}")
    village = Village(taluka=taluka, source_id=f"V1_{suffix}", name_en=f"Kharadi_{suffix}")
    
    db.add(state)
    db.add(district)
    db.add(taluka)
    db.add(village)
    db.flush()
    
    assert village.taluka_id == taluka.id
    assert taluka.district_id == district.id
    assert district.state_id == state.id
    
    db.rollback()

def test_network_config_persistence(db):
    suffix = str(uuid.uuid4())[:8]
    cfg = NetworkConfig(
        interface_name="Wi-Fi",
        profile_name=f"Profile_{suffix}",
        priority=1,
        role="PARKING",
        is_enabled=True
    )
    db.add(cfg)
    db.commit()

    saved = db.query(NetworkConfig).filter_by(profile_name=f"Profile_{suffix}").first()
    assert saved is not None
    assert saved.role == "PARKING"
    assert saved.is_enabled is True

    db.delete(saved)
    db.commit()

def test_village_fetch_and_record_detail(db):
    # 1. Create location hierarchy
    suffix = str(uuid.uuid4())[:8]
    state = State(source_id=f"S_{suffix}", name_en=f"State_{suffix}")
    district = District(state=state, source_id=f"D_{suffix}", name_en=f"District_{suffix}")
    taluka = Taluka(district=district, source_id=f"T_{suffix}", name_en=f"Taluka_{suffix}")
    village = Village(taluka=taluka, source_id=f"V_{suffix}", name_en=f"Village_{suffix}")
    db.add_all([state, district, taluka, village])
    db.flush()

    # 2. Create VillageFetch
    vf = VillageFetch(
        village_id=village.id,
        year=2026,
        current_search_value="1",
        status=VillageFetchStatus.RUNNING.value
    )
    db.add(vf)
    db.flush()
    assert vf.id is not None
    assert vf.status == "RUNNING"

    # 3. Create RecordDetail
    rec = RecordDetail(
        village_id=village.id,
        year=2026,
        doc_no=f"DOC_{suffix}",
        doc_type="खरेदीखत",
        office="दु. नि. हवेली",
        seller="विक्रेता अ",
        buyer="खरेदीदार ब",
        other_info="फ्लॅट क्र. १०१",
        date="15/01/2026",
        indexii_url="/Index2View.aspx?id=123"
    )
    db.add(rec)
    db.commit()

    saved_rec = db.query(RecordDetail).filter_by(village_id=village.id, doc_no=f"DOC_{suffix}").first()
    assert saved_rec is not None
    assert saved_rec.doc_type == "खरेदीखत"
    assert saved_rec.village_id == village.id

    # 4. Test unique constraint on (village_id, year, doc_no, office)
    dup_rec = RecordDetail(
        village_id=village.id,
        year=2026,
        doc_no=f"DOC_{suffix}",
        office="दु. नि. हवेली",
        doc_type="Duplicate"
    )
    db.add(dup_rec)
    with pytest.raises(IntegrityError):
        db.flush()

    db.rollback()