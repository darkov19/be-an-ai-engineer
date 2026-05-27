import pytest
from datetime import datetime, timezone
import psycopg

class MockCursor:
    def __init__(self, fetch_results):
        if isinstance(fetch_results, list):
            self.fetch_results = list(fetch_results)
        else:
            self.fetch_results = [fetch_results]
        self.execute_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_calls.append((query, vars))

    async def fetchone(self):
        if self.fetch_results:
            return self.fetch_results.pop(0)
        return None

class MockConnection:
    def __init__(self, fetch_results):
        self.fetch_results = fetch_results
        self.cursors = []

    def cursor(self, *args, **kwargs):
        cur = MockCursor(self.fetch_results)
        self.cursors.append(cur)
        return cur

class MockPool:
    def __init__(self, fetch_results):
        self.fetch_results = fetch_results
        self.connections = []

    async def __aenter__(self):
        conn = MockConnection(self.fetch_results)
        self.connections.append(conn)
        return conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def connection(self):
        return self

@pytest.mark.asyncio
async def test_get_profile_exists(app, client):
    updated_at_val = datetime.now(timezone.utc)
    profile_data = {
        "id": 1,
        "skills": ["React", "TypeScript"],
        "seniority": "Senior",
        "tech_stack": ["FastAPI", "PostgreSQL"],
        "years_of_experience": 5,
        "geo_preference": "Remote",
        "updated_at": updated_at_val
    }
    mock_pool = MockPool(profile_data)
    app.state.pool = mock_pool

    response = await client.get("/api/v1/profiles/current")
    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == 1
    assert payload["skills"] == ["React", "TypeScript"]
    assert payload["seniority"] == "Senior"
    assert payload["tech_stack"] == ["FastAPI", "PostgreSQL"]
    assert payload["years_of_experience"] == 5
    assert payload["geo_preference"] == "Remote"
    assert "updated_at" in payload

    # Assert Cache-Control headers are present
    assert response.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"

@pytest.mark.asyncio
async def test_get_profile_not_exists_auto_create(app, client):
    updated_at_val = datetime.now(timezone.utc)
    fetch_results = [
        None,
        {
            "id": 1,
            "skills": [],
            "seniority": None,
            "tech_stack": [],
            "years_of_experience": 0,
            "geo_preference": None,
            "updated_at": updated_at_val
        }
    ]
    mock_pool = MockPool(fetch_results)
    app.state.pool = mock_pool

    response = await client.get("/api/v1/profiles/current")
    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == 1
    assert payload["skills"] == []
    assert payload["seniority"] is None
    assert payload["tech_stack"] == []
    assert payload["years_of_experience"] == 0
    assert payload["geo_preference"] is None

    # Check that insert was called
    assert len(mock_pool.connections[0].cursors[0].execute_calls) >= 2

@pytest.mark.asyncio
async def test_update_profile_success(app, client):
    updated_at_val = datetime.now(timezone.utc)
    profile_data = {
        "id": 1,
        "skills": ["Python", "Docker"],
        "seniority": "Lead",
        "tech_stack": ["FastAPI", "Kubernetes"],
        "years_of_experience": 8,
        "geo_preference": "USA",
        "updated_at": updated_at_val
    }
    mock_pool = MockPool(profile_data)
    app.state.pool = mock_pool

    payload = {
        "skills": ["Python", "Docker"],
        "seniority": "Lead",
        "tech_stack": ["FastAPI", "Kubernetes"],
        "years_of_experience": 8,
        "geo_preference": "USA"
    }
    response = await client.put("/api/v1/profiles/current", json=payload)
    assert response.status_code == 200

    result = response.json()
    assert result["id"] == 1
    assert result["skills"] == ["Python", "Docker"]
    assert result["seniority"] == "Lead"
    assert result["years_of_experience"] == 8
    assert result["geo_preference"] == "USA"

@pytest.mark.asyncio
async def test_update_profile_validation_failure(app, client):
    # Setup pool but we expect it not to hit db due to validation failure
    mock_pool = MockPool(None)
    app.state.pool = mock_pool

    # Negative years of experience should trigger validation error
    payload = {
        "skills": ["Python"],
        "seniority": "Lead",
        "tech_stack": ["FastAPI"],
        "years_of_experience": -5,
        "geo_preference": "USA"
    }
    response = await client.put("/api/v1/profiles/current", json=payload)
    assert response.status_code == 422

    result = response.json()
    assert result["error"] is True
    assert result["code"] == "VALIDATION_ERROR"
    assert "years_of_experience" in result["detail"]

@pytest.mark.asyncio
async def test_update_profile_database_error(app, client):
    class MockErrorCursor(MockCursor):
        async def execute(self, query, vars=None):
            raise psycopg.OperationalError("Database connection lost")

    class MockErrorConnection(MockConnection):
        def cursor(self, *args, **kwargs):
            return MockErrorCursor([])

    class MockErrorPool(MockPool):
        async def __aenter__(self):
            return MockErrorConnection([])

    mock_pool = MockErrorPool([])
    app.state.pool = mock_pool

    payload = {
        "skills": ["Python"],
        "seniority": "Lead",
        "tech_stack": ["FastAPI"],
        "years_of_experience": 5,
        "geo_preference": "USA"
    }
    response = await client.put("/api/v1/profiles/current", json=payload)
    # The operational error should trigger the database exception handler in main.py
    assert response.status_code == 500

    result = response.json()
    assert result["error"] is True
    assert result["code"] == "DB_CONNECTION_ERROR"
