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
        self.execute_calls = []

    def cursor(self, *args, **kwargs):
        cur = MockCursor(self.fetch_val)
        self.cursors.append(cur)
        return cur

    async def execute(self, query, vars=None):
        self.execute_calls.append((query, vars))

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

class MockHealthCursor:
    def __init__(self, corpus_size, eval_accuracy, latest_ingest_status):
        self.corpus_size = corpus_size
        self.eval_accuracy = eval_accuracy
        self.latest_ingest_status = latest_ingest_status
        self.query_count = 0
        self.execute_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_calls.append((query, vars))

    async def fetchone(self):
        self.query_count += 1
        if self.query_count == 1:
            return (self.corpus_size,)
        elif self.query_count == 2:
            return (self.eval_accuracy,)
        elif self.query_count == 3:
            return (self.latest_ingest_status,)
        return None

class MockHealthConnection:
    def __init__(self, corpus_size, eval_accuracy, latest_ingest_status):
        self.corpus_size = corpus_size
        self.eval_accuracy = eval_accuracy
        self.latest_ingest_status = latest_ingest_status
        self.cursors = []

    def cursor(self, *args, **kwargs):
        cur = MockHealthCursor(self.corpus_size, self.eval_accuracy, self.latest_ingest_status)
        self.cursors.append(cur)
        return cur

class MockHealthPool:
    def __init__(self, corpus_size, eval_accuracy, latest_ingest_status):
        self.corpus_size = corpus_size
        self.eval_accuracy = eval_accuracy
        self.latest_ingest_status = latest_ingest_status
        self.connections = []

    async def __aenter__(self):
        conn = MockHealthConnection(self.corpus_size, self.eval_accuracy, self.latest_ingest_status)
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
async def test_health_check_nominal_state(app, client):
    mock_pool = MockHealthPool(150, 0.85, "success")
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["corpus_size"] == 150
    assert payload["data"]["eval_accuracy"] == 0.85
    assert payload["data"]["system_state"] == "nominal"
    assert payload["data"]["warning_mode"] is False

@pytest.mark.asyncio
async def test_health_check_warning_state(app, client):
    mock_pool = MockHealthPool(50, 0.85, "success")
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["system_state"] == "warning"
    assert payload["data"]["warning_mode"] is True

@pytest.mark.asyncio
async def test_health_check_locked_state_both_breached(app, client):
    mock_pool = MockHealthPool(50, 0.65, "success")
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["system_state"] == "locked"
    assert payload["data"]["warning_mode"] is False

@pytest.mark.asyncio
async def test_health_check_locked_state_zero_jobs(app, client):
    mock_pool = MockHealthPool(0, 0.90, "success")
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["system_state"] == "locked"

@pytest.mark.asyncio
async def test_health_check_locked_state_failed_ingest(app, client):
    mock_pool = MockHealthPool(150, 0.90, "failure")
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["system_state"] == "locked"

@pytest.mark.asyncio
async def test_health_check_locked_state_non_success_ingest(app, client):
    mock_pool = MockHealthPool(150, 0.90, "running")
    app.state.pool = mock_pool

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["system_state"] == "locked"

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


@pytest.mark.asyncio
async def test_record_cockpit_access_success(app, client):
    mock_pool = MockPool((1,))
    app.state.pool = mock_pool

    response = await client.post("/api/v1/cockpit/access")
    assert response.status_code == 201
    assert response.json()["ok"] is True
    assert len(mock_pool.connections) == 1
    assert "INSERT INTO cockpit_access_logs" in mock_pool.connections[0].execute_calls[0][0]


@pytest.mark.asyncio
async def test_record_cockpit_access_db_error_returns_structured_500(app, client):
    class MockFailConnection(MockConnection):
        async def execute(self, query, vars=None):
            raise psycopg.OperationalError("insert failed")

    class MockFailPool(MockPool):
        async def __aenter__(self):
            conn = MockFailConnection(self.fetch_val)
            self.connections.append(conn)
            return conn

    mock_pool = MockFailPool((1,))
    app.state.pool = mock_pool

    response = await client.post("/api/v1/cockpit/access")
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] is True
    assert payload["code"] == "DB_CONNECTION_ERROR"
    assert "detail" in payload
