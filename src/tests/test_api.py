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

def test_get_data_with_redis_cache_hit(mock_db):
    """Test GET /data returns cached data on cache HIT"""
    cursor, conn = mock_db
    cached_data = '{"count": 1, "data": [{"id": 1, "content": {"test": "cached"}}]}'

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        redis_conn.get.return_value = cached_data
        mock_redis.return_value = redis_conn

        response = client.get("/data")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        redis_conn.get.assert_called_once_with("data:all")

def test_get_data_with_redis_cache_miss(mock_db):
    """Test GET /data fetches from DB on cache MISS and caches result"""
    cursor, conn = mock_db
    cursor.fetchall.return_value = [{"id": 1, "content": {"test": "data"}, "timestamp": "2024-01-01"}]

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        redis_conn.get.return_value = None  # Cache MISS
        mock_redis.return_value = redis_conn

        response = client.get("/data")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        redis_conn.setex.assert_called_once()

def test_get_data_redis_unavailable(mock_db):
    """Test GET /data works when Redis is unavailable (graceful degradation)"""
    cursor, conn = mock_db
    cursor.fetchall.return_value = [{"id": 1, "content": {"test": "data"}, "timestamp": "2024-01-01"}]

    with patch('src.app.get_redis_connection') as mock_redis:
        mock_redis.return_value = None  # Redis unavailable

        response = client.get("/data")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

def test_get_data_redis_read_error(mock_db):
    """Test GET /data handles Redis read errors gracefully"""
    cursor, conn = mock_db
    cursor.fetchall.return_value = [{"id": 1, "content": {"test": "data"}, "timestamp": "2024-01-01"}]

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        redis_conn.get.side_effect = Exception("Redis connection error")
        mock_redis.return_value = redis_conn

        response = client.get("/data")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

def test_post_data_invalidates_cache(mock_db):
    """Test POST /data invalidates Redis cache"""
    cursor, conn = mock_db
    test_data = {"message": "test"}
    cursor.fetchone.return_value = {
        "id": 1,
        "content": test_data,
        "timestamp": "2024-01-01T00:00:00"
    }

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        mock_redis.return_value = redis_conn

        response = client.post("/data", json=test_data)
        assert response.status_code == 200
        redis_conn.delete.assert_called_once_with("data:all")

def test_post_data_redis_unavailable(mock_db):
    """Test POST /data works when Redis is unavailable"""
    cursor, conn = mock_db
    test_data = {"message": "test"}
    cursor.fetchone.return_value = {
        "id": 1,
        "content": test_data,
        "timestamp": "2024-01-01T00:00:00"
    }

    with patch('src.app.get_redis_connection') as mock_redis:
        mock_redis.return_value = None  # Redis unavailable

        response = client.post("/data", json=test_data)
        assert response.status_code == 200

def test_get_data_database_unavailable():
    """Test GET /data handles database connection failure"""
    with patch('src.app.get_db_connection') as mock_db:
        mock_db.return_value = None  # Database unavailable

        response = client.get("/data")
        assert response.status_code == 503
        assert "Database connection unavailable" in response.json()["detail"]

def test_post_data_database_unavailable():
    """Test POST /data handles database connection failure"""
    test_data = {"message": "test"}

    with patch('src.app.get_db_connection') as mock_db:
        mock_db.return_value = None  # Database unavailable

        response = client.post("/data", json=test_data)
        assert response.status_code == 503
        assert "Database connection unavailable" in response.json()["detail"]

def test_get_data_redis_write_error(mock_db):
    """Test GET /data handles Redis write (setex) errors gracefully"""
    cursor, conn = mock_db
    cursor.fetchall.return_value = [{"id": 1, "content": {"test": "data"}, "timestamp": "2024-01-01"}]

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        redis_conn.get.return_value = None  # Cache MISS
        redis_conn.setex.side_effect = Exception("Redis write error")  # Write fails
        mock_redis.return_value = redis_conn

        response = client.get("/data")
        assert response.status_code == 200  # Should still succeed
        data = response.json()
        assert data["count"] == 1

def test_post_data_redis_delete_error(mock_db):
    """Test POST /data handles Redis delete errors gracefully"""
    cursor, conn = mock_db
    test_data = {"message": "test"}
    cursor.fetchone.return_value = {
        "id": 1,
        "content": test_data,
        "timestamp": "2024-01-01T00:00:00"
    }

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        redis_conn.delete.side_effect = Exception("Redis delete error")  # Delete fails
        mock_redis.return_value = redis_conn

        response = client.post("/data", json=test_data)
        assert response.status_code == 200  # Should still succeed

def test_post_data_database_error(mock_db):
    """Test POST /data handles database errors with rollback"""
    cursor, conn = mock_db
    test_data = {"message": "test"}
    cursor.execute.side_effect = Exception("Database constraint violation")

    response = client.post("/data", json=test_data)
    assert response.status_code == 500
    conn.rollback.assert_called_once()

def test_get_data_database_query_error(mock_db):
    """Test GET /data handles database query errors"""
    cursor, conn = mock_db
    cursor.execute.side_effect = Exception("Database query error")

    with patch('src.app.get_redis_connection') as mock_redis:
        redis_conn = MagicMock()
        redis_conn.get.return_value = None  # Force DB query
        mock_redis.return_value = redis_conn

        response = client.get("/data")
        assert response.status_code == 500

def test_redis_connection_success():
    """Test Redis connection success path"""
    with patch('redis.from_url') as mock_redis_from_url:
        redis_conn = MagicMock()
        redis_conn.ping.return_value = True
        mock_redis_from_url.return_value = redis_conn

        # Import to trigger connection
        from src.app import get_redis_connection
        result = get_redis_connection()

        assert result is not None
        redis_conn.ping.assert_called_once()

def test_redis_connection_failure():
    """Test Redis connection failure handling"""
    with patch('redis.from_url') as mock_redis_from_url:
        mock_redis_from_url.side_effect = Exception("Redis connection refused")

        # Import to trigger connection
        from src.app import get_redis_connection

        # Reset global redis_client
        import src.app
        src.app.redis_client = None

        result = get_redis_connection()
        assert result is None
