from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check_v1():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "igr-e-search-api"}

def test_records_stats_summary():
    response = client.get("/api/v1/records/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_records" in data
    assert "total_village_fetches" in data
