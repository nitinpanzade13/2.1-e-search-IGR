import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.models.location import State, District, Taluka, Village

client = TestClient(app)

@pytest.fixture
def dummy_location_data(db):
    suffix = str(uuid4())[:8]
    state1 = State(id=uuid4(), source_id=f"state_{suffix}", name_en=f"Maharashtra_{suffix}", is_active=True, source_system="IGR_MAHARASHTRA")
    db.add(state1)
    db.flush()

    dist1 = District(id=uuid4(), state_id=state1.id, source_id=f"dist1_{suffix}", name_en="छत्रपती संभाजीनगर", is_active=True, source_system="IGR_MAHARASHTRA")
    dist2 = District(id=uuid4(), state_id=state1.id, source_id=f"dist2_{suffix}", name_en="जळगाव", is_active=True, source_system="IGR_MAHARASHTRA")
    db.add(dist1)
    db.add(dist2)
    db.flush()

    tal_kannad = Taluka(id=uuid4(), district_id=dist1.id, source_id=f"tal1_{suffix}", name_en="कन्नड", is_active=True, source_system="IGR_MAHARASHTRA")
    tal_chopada = Taluka(id=uuid4(), district_id=dist2.id, source_id=f"tal2_{suffix}", name_en="चोपडा", is_active=True, source_system="IGR_MAHARASHTRA")
    db.add(tal_kannad)
    db.add(tal_chopada)
    db.flush()

    vil_talner = Village(id=uuid4(), taluka_id=tal_kannad.id, source_id=f"vil1_{suffix}", name_en="तळनेर", is_active=True, source_system="IGR_MAHARASHTRA")
    vil_other = Village(id=uuid4(), taluka_id=tal_chopada.id, source_id=f"vil2_{suffix}", name_en="Other Village", is_active=True, source_system="IGR_MAHARASHTRA")
    db.add(vil_talner)
    db.add(vil_other)
    db.commit()

    yield {
        "dist_sambhajinagar": dist1.id,
        "dist_jalgaon": dist2.id,
        "tal_kannad": tal_kannad.id,
        "tal_chopada": tal_chopada.id,
        "vil_talner": vil_talner.id
    }
    
    db.delete(vil_talner)
    db.delete(vil_other)
    db.delete(tal_kannad)
    db.delete(tal_chopada)
    db.delete(dist1)
    db.delete(dist2)
    db.delete(state1)
    db.commit()

def test_location_hierarchy_isolation(dummy_location_data):
    # Test 1: Fetching Kannad's villages must return 'तळनेर'
    resp = client.get(f"/api/v1/locations/talukas/{dummy_location_data['tal_kannad']}/villages")
    assert resp.status_code == 200
    villages = resp.json()
    assert len(villages) == 1
    assert villages[0]["name_en"] == "तळनेर"

    # Test 2: Fetching Chopada's villages must NOT return 'तळनेर'
    resp2 = client.get(f"/api/v1/locations/talukas/{dummy_location_data['tal_chopada']}/villages")
    assert resp2.status_code == 200
    villages2 = resp2.json()
    assert len(villages2) == 1
    assert villages2[0]["name_en"] == "Other Village"
    assert "तळनेर" not in [v["name_en"] for v in villages2]

def test_invalid_location_hierarchy():
    # Test 5: Invalid parent-child returns 404
    resp = client.get(f"/api/v1/locations/talukas/{uuid4()}/villages")
    assert resp.status_code == 404
