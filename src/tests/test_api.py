import pytest
from fastapi.testclient import TestClient
from src.app import app, data_store

client = TestClient(app)

def setup_function():
    """Clear data store before each test"""
    data_store.clear()

def test_get_data_empty():
    """Test GET /data returns empty list initially"""
    response = client.get("/data")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "data" in data
    assert isinstance(data["data"], list)
    assert data["count"] == 0

def test_post_data_success():
    """Test POST /data creates new entry"""
    test_data = {"message": "test", "value": 42}
    response = client.post("/data", json=test_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "content" in data
    assert data["content"] == test_data

def test_post_data_empty():
    """Test POST /data rejects empty data"""
    response = client.post("/data", json={})
    assert response.status_code == 400

def test_metrics_endpoint():
    """Test Prometheus metrics endpoint is accessible"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "python_info" in response.text or "http_requests" in response.text
