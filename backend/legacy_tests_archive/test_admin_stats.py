from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_admin_stats_endpoint():
    response = client.get("/api/v1/admin/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check top level keys
    expected_keys = [
        "registrations",
        "pdf_tasks",
        "parties",
        "properties",
        "artifacts",
        "search_jobs",
        "bulk_fetch_jobs"
    ]
    for key in expected_keys:
        assert key in data
        assert "total" in data[key]
        assert isinstance(data[key]["total"], int)
        
    # Check by_status dictionaries
    assert isinstance(data["registrations"].get("by_status"), dict)
    assert isinstance(data["pdf_tasks"].get("by_status"), dict)
