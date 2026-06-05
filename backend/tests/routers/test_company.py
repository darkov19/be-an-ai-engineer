import pytest
from backend.tests.routers.test_jobs import MockPool

@pytest.mark.asyncio
async def test_get_company_fingerprint_success(app, client):
    # Mock database to return a precomputed fingerprint
    app.state.pool = MockPool(
        [
            [
                {
                    "company_slug": "stripe",
                    "company_name": "Stripe",
                    "role_archetypes": ["Bullet 1", "Bullet 2"],
                    "top_technologies": [{"name": "Python", "count": 5}],
                    "llm_observation": "Observation text",
                    "updated_at": None
                }
            ]
        ]
    )

    response = await client.get("/api/v1/company/stripe")
    assert response.status_code == 200
    data = response.json()
    assert data["company_slug"] == "stripe"
    assert data["company_name"] == "Stripe"
    assert data["role_archetypes"] == ["Bullet 1", "Bullet 2"]
    assert data["top_technologies"] == [{"name": "Python", "count": 5}]
    assert data["llm_observation"] == "Observation text"

@pytest.mark.asyncio
async def test_get_company_fingerprint_not_found(app, client):
    app.state.pool = MockPool([[None]])

    response = await client.get("/api/v1/company/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "COMPANY_NOT_FOUND"

@pytest.mark.asyncio
async def test_get_company_fingerprint_invalid_slug(app, client):
    # Invalid characters
    response = await client.get("/api/v1/company/stripe_test")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "INVALID_COMPANY_SLUG"

    # Caps not allowed per strict regex
    response = await client.get("/api/v1/company/Stripe")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "INVALID_COMPANY_SLUG"

    # Path traversal attempt
    response = await client.get("/api/v1/company/..\\..\\stripe")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "INVALID_COMPANY_SLUG"

    # Encoded trailing newline must not pass the slug allowlist
    response = await client.get("/api/v1/company/stripe%0A")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "INVALID_COMPANY_SLUG"

@pytest.mark.asyncio
async def test_get_company_fingerprint_database_error(app, client):
    # Simulate DB error
    app.state.pool = MockPool([], execute_error=RuntimeError("Connection lost"))

    response = await client.get("/api/v1/company/stripe")
    assert response.status_code == 500
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "INTERNAL_SERVER_ERROR"
    # Verify exact SQL error details are not exposed to the client
    assert "Connection lost" not in data["detail"]
    assert "Database query execution failure" in data["detail"]
