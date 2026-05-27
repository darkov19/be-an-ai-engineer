import pytest
import psycopg

class MockCursor:
    def __init__(self, fetch_val):
        self.fetch_val = fetch_val
        self.execute_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_calls.append((query, vars))

    async def fetchone(self):
        return self.fetch_val

class MockConnection:
    def __init__(self, fetch_val):
        self.fetch_val = fetch_val
        self.cursors = []

    def cursor(self, *args, **kwargs):
        cur = MockCursor(self.fetch_val)
        self.cursors.append(cur)
        return cur

class MockPool:
    def __init__(self, fetch_val):
        self.fetch_val = fetch_val
        self.connections = []

    async def __aenter__(self):
        conn = MockConnection(self.fetch_val)
        self.connections.append(conn)
        return conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def connection(self, *args, **kwargs):
        return self

@pytest.mark.asyncio
async def test_health_check_healthy(app, client):
    # Inject healthy pool
    mock_pool = MockPool((1,))
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
    class MockDisconnectedPool(MockPool):
        async def __aenter__(self):
            raise psycopg.OperationalError("Connection refused")

    mock_pool = MockDisconnectedPool(None)
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
    class MockErrorCursor(MockCursor):
        async def execute(self, query, vars=None):
            raise psycopg.ProgrammingError("Table does not exist")

    class MockErrorConnection(MockConnection):
        def cursor(self, *args, **kwargs):
            return MockErrorCursor(self.fetch_val)

    class MockErrorPool(MockPool):
        async def __aenter__(self):
            return MockErrorConnection(self.fetch_val)

    mock_pool = MockErrorPool(None)
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 500

    payload = response.json()
    assert "error" in payload
    assert payload["error"] is True
    assert payload["code"] == "DB_CONNECTION_ERROR"
    assert "detail" in payload
