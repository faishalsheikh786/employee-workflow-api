from fastapi.testclient import TestClient
from app.main import app

def test_health():
    with TestClient(app) as client:
        response = client.get("/api/workflows/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
