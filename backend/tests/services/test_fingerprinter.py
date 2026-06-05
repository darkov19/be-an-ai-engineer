import pytest
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.fingerprinter import generate_fingerprint_data, write_static_html

class AsyncContextManagerMock:
    def __init__(self, mock_obj):
        self.mock_obj = mock_obj

    async def __aenter__(self):
        return self.mock_obj

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_generate_fingerprint_data_no_jobs():
    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = AsyncContextManagerMock(mock_cursor)

    mock_pool = MagicMock()
    mock_pool.connection.return_value = AsyncContextManagerMock(mock_conn)

    with pytest.raises(ValueError) as excinfo:
        await generate_fingerprint_data(mock_pool, "stripe")
    assert "No extracted job postings found for company" in str(excinfo.value)

@pytest.mark.asyncio
@patch("backend.services.fingerprinter.check_hermes_proxy_health", new_callable=AsyncMock)
@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_generate_fingerprint_data_success(mock_post, mock_health):
    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = ("Stripe",)
    mock_cursor.fetchall.return_value = [
        {
            "company": "Stripe",
            "title": "Staff AI Engineer",
            "skills": ["Python", "PyTorch"],
            "tech_stack": ["Python", "PyTorch", "PostgreSQL"],
            "remote_policy": "remote",
            "role_archetype": "llm_app_engineer"
        },
        {
            "company": "Stripe",
            "title": "Backend Developer",
            "skills": ["Python", "FastAPI"],
            "tech_stack": ["Python", "FastAPI"],
            "remote_policy": "remote",
            "role_archetype": "llm_app_engineer"
        }
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = AsyncContextManagerMock(mock_cursor)

    mock_pool = MagicMock()
    mock_pool.connection.return_value = AsyncContextManagerMock(mock_conn)

    # Mock Hermes proxy HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "role_archetypes": [
            "Builds LLM products with Python",
            "Designs state-of-the-art AI applications",
            "Integrates with vector storage and databases",
            "Deploys scalable FastAPI microservices",
            "Coordinates with cross-functional product teams"
        ],
        "llm_observation": "Stripe is aggressively pivoting towards hosting and executing LLM tasks on its primary platform."
    }
    mock_post.return_value = mock_response

    res = await generate_fingerprint_data(mock_pool, "stripe")

    assert res["company_slug"] == "stripe"
    assert res["company_name"] == "Stripe"
    assert len(res["role_archetypes"]) == 5
    # Python is top tech (count = 2)
    assert res["top_technologies"][0]["name"] == "Python"
    assert res["top_technologies"][0]["count"] == 2
    assert "Stripe is aggressively pivoting" in res["llm_observation"]

    mock_health.assert_awaited_once()
    mock_post.assert_awaited_once()
    assert "SELECT company, title" in mock_cursor.execute.call_args_list[1][0][0]

def test_write_static_html_path_traversal(tmp_path):
    fingerprint_data = {
        "company_name": "Stripe",
        "role_archetypes": ["A", "B", "C", "D", "E"],
        "top_technologies": [{"name": "Python", "count": 2}],
        "llm_observation": "Test observation"
    }

    with pytest.raises(ValueError) as excinfo:
        write_static_html("../stripe", fingerprint_data)
    assert "path traversal detected" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        write_static_html("stripe/test", fingerprint_data)
    assert "Invalid company slug" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        write_static_html("stripe\n", fingerprint_data)
    assert "Invalid company slug" in str(excinfo.value)

@patch("backend.services.fingerprinter.Path.resolve")
def test_write_static_html_success(mock_resolve, tmp_path):
    # Mock Path.resolve to write directly to our temp path
    mock_resolve.return_value = tmp_path

    fingerprint_data = {
        "company_name": "Stripe",
        "role_archetypes": [
            "Archetype 1",
            "Archetype 2",
            "Archetype 3",
            "Archetype 4",
            "Archetype 5"
        ],
        "top_technologies": [
            {"name": "Python", "count": 5},
            {"name": "React", "count": 3}
        ],
        "llm_observation": "Stripe is expanding its AI interfaces."
    }

    # Create dummy output file in tmp_path
    target_file = tmp_path / "stripe.html"
    
    with patch("backend.services.fingerprinter.Path.mkdir"), \
         patch("backend.services.fingerprinter.Path.write_text") as mock_write:
         
         # Mock target_path resolution to avoid modifying true public cached folder
         with patch("backend.services.fingerprinter.Path.__truediv__", return_value=target_file):
             write_static_html("stripe", fingerprint_data)
             mock_write.assert_called_once()
             written_html = mock_write.call_args[0][0]
             
             assert "STRIPE // STACK FINGERPRINT" in written_html
             assert "Python" in written_html
             assert "Archetype 1" in written_html
             assert "Stripe is expanding its AI interfaces" in written_html

def test_write_static_html_escapes_generated_content(tmp_path):
    fingerprint_data = {
        "company_name": "<Acme>",
        "role_archetypes": ["<script>alert(1)</script>"],
        "top_technologies": [{"name": "<img src=x onerror=alert(1)>", "count": 2}],
        "llm_observation": "Uses <b>unsafe</b> output."
    }

    target_file = tmp_path / "acme.html"

    with patch("backend.services.fingerprinter.Path.mkdir"), \
         patch("backend.services.fingerprinter.Path.write_text") as mock_write:
        with patch("backend.services.fingerprinter.Path.__truediv__", return_value=target_file):
            write_static_html("acme", fingerprint_data)

    written_html = mock_write.call_args[0][0]
    assert "<script>alert(1)</script>" not in written_html
    assert "<img src=x onerror=alert(1)>" not in written_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in written_html
    assert "&lt;img src=x onerror=alert(1)&gt;" in written_html
