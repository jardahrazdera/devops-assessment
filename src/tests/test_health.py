from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

def test_health_endpoint():
    """Test health check returns 200 and correct structure"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "service" in data

def test_health_response_time():
    """Test health check responds quickly"""
    import time
    start = time.time()
    client.get("/health")
    duration = time.time() - start
    assert duration < 1.0  # Should respond in less than 1 second
