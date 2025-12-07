import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.app import app

client = TestClient(app)

@pytest.fixture
def mock_db():
    """Mock database connection for testing"""
    with patch('src.app.get_db_connection') as mock:
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        mock.return_value = conn
        yield cursor, conn

def test_get_data_empty(mock_db):
    """Test GET /data returns empty list initially"""
    cursor, conn = mock_db
    cursor.fetchall.return_value = []

    response = client.get("/data")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "data" in data
    assert isinstance(data["data"], list)
    assert data["count"] == 0

def test_post_data_success(mock_db):
    """Test POST /data creates new entry"""
    cursor, conn = mock_db
    test_data = {"message": "test", "value": 42}
    cursor.fetchone.return_value = {
        "id": 1,
        "content": test_data,
        "timestamp": "2024-01-01T00:00:00"
    }

    response = client.post("/data", json=test_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "content" in data

def test_post_data_empty(mock_db):
    """Test POST /data rejects empty data"""
    response = client.post("/data", json={})
    assert response.status_code == 400

def test_metrics_endpoint():
    """Test Prometheus metrics endpoint is accessible"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "python_info" in response.text or "http_requests" in response.text
