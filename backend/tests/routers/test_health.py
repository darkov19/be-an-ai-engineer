import pytest
from unittest.mock import AsyncMock, MagicMock
import psycopg

@pytest.mark.asyncio
async def test_health_check_healthy(app, client):
    # Mock connection pool, connection, and cursor
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    
    mock_cur.fetchone.return_value = (1,)
    
    # Setup async context managers
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
    
    # Inject mock pool into app state
    app.state.pool = mock_pool
    
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    
    payload = response.json()
    assert "data" in payload
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["database"] == "connected"
    assert "timestamp" in payload["data"]

@pytest.mark.asyncio
async def test_health_check_database_disconnected(app, client):
    # Mock pool.connection raising an exception to simulate database offline
    mock_pool = MagicMock()
    
    # Simulate a context manager raising an exception on __aenter__
    mock_pool.connection.return_value.__aenter__.side_effect = psycopg.OperationalError("Connection refused")
    
    app.state.pool = mock_pool
    
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    
    payload = response.json()
    assert "data" in payload
    assert payload["data"]["status"] == "unhealthy"
    assert payload["data"]["database"] == "disconnected"
    assert "timestamp" in payload["data"]

@pytest.mark.asyncio
async def test_health_check_query_error(app, client):
    # Mock connection pool, connection, and cursor throwing an error during execution
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    
    mock_cur.execute.side_effect = psycopg.ProgrammingError("Table does not exist")
    
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
    
    app.state.pool = mock_pool
    
    response = await client.get("/api/v1/health")
    assert response.status_code == 500
    
    payload = response.json()
    assert "error" in payload
    assert payload["error"] is True
    assert payload["code"] == "DB_CONNECTION_ERROR"
    assert "detail" in payload
