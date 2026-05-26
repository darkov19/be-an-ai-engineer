import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import psycopg

@pytest.mark.asyncio
async def test_get_profile_exists(app, client):
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    
    updated_at_val = datetime.now(timezone.utc)
    mock_cur.fetchone.return_value = {
        "id": 1,
        "skills": ["React", "TypeScript"],
        "seniority": "Senior",
        "tech_stack": ["FastAPI", "PostgreSQL"],
        "years_of_experience": 5,
        "geo_preference": "Remote",
        "updated_at": updated_at_val
    }
    
    mock_conn.cursor = MagicMock()
    mock_conn.cursor.return_value = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
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
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    
    updated_at_val = datetime.now(timezone.utc)
    # First fetch returns None, next fetch returns seeded row
    mock_cur.fetchone.side_effect = [
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
    
    mock_conn.cursor = MagicMock()
    mock_conn.cursor.return_value = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
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
    assert mock_cur.execute.call_count >= 2

@pytest.mark.asyncio
async def test_update_profile_success(app, client):
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    
    updated_at_val = datetime.now(timezone.utc)
    mock_cur.fetchone.return_value = {
        "id": 1,
        "skills": ["Python", "Docker"],
        "seniority": "Lead",
        "tech_stack": ["FastAPI", "Kubernetes"],
        "years_of_experience": 8,
        "geo_preference": "USA",
        "updated_at": updated_at_val
    }
    
    mock_conn.cursor = MagicMock()
    mock_conn.cursor.return_value = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
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
    mock_pool = MagicMock()
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
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    
    mock_cur.execute.side_effect = psycopg.OperationalError("Database connection lost")
    
    mock_conn.cursor = MagicMock()
    mock_conn.cursor.return_value = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
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
