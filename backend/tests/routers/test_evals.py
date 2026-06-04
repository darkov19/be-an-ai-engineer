import pytest
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, patch

from backend.utils.tasks import task_manager

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

    async def fetchall(self):
        if self.fetch_results:
            val = self.fetch_results.pop(0)
            if isinstance(val, list):
                return val
            return [val]
        return []

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
async def test_get_evals_history_success(app, client):
    history_data = [
        {
            "id": 1,
            "run_timestamp": datetime.now(timezone.utc),
            "prompt_version": "extraction_v1",
            "extraction_schema_version": "1.0.0",
            "overall_accuracy": 0.85,
            "overall_precision": 0.86,
            "overall_recall": 0.84,
            "overall_f1": 0.85,
            "accuracy_regression": False,
            "metrics": {},
            "created_at": datetime.now(timezone.utc)
        }
    ]
    mock_pool = MockPool([history_data])
    app.state.pool = mock_pool

    response = await client.get("/api/v1/evals")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert len(payload["data"]) == 1
    assert payload["data"][0]["overall_f1"] == 0.85

@pytest.mark.asyncio
async def test_get_evals_latest_not_found(client, tmp_path):
    with patch("backend.routers.evals.DEFAULT_SUMMARY_DIR", tmp_path):
        response = await client.get("/api/v1/evals/latest")
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"] is True
        assert payload["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_get_evals_latest_success(client, tmp_path):
    summary_data = {
        "run_id": 42,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": "extraction_v1",
        "schema_version": "1.0.0",
        "split": "held_out",
        "overall_metrics": {"precision": 0.9, "recall": 0.9, "f1": 0.9},
        "accuracy_regression": False,
        "field_metrics": {},
        "detailed_diffs": []
    }
    summary_file = tmp_path / "run-summary-2026-22.json"
    summary_file.write_text(json.dumps(summary_data))

    with patch("backend.routers.evals.DEFAULT_SUMMARY_DIR", tmp_path):
        response = await client.get("/api/v1/evals/latest")
        assert response.status_code == 200
        payload = response.json()
        assert "data" in payload
        assert payload["data"]["run_id"] == 42

@pytest.mark.asyncio
async def test_post_evals_run_success(app, client):
    mock_pool = MockPool([])
    app.state.pool = mock_pool

    with patch("backend.routers.evals.run_evaluation_task", new_callable=AsyncMock) as mock_task:
        response = await client.post("/api/v1/evals/run", json={"split": "held_out", "prompt_version": "extraction_v1"})
        assert response.status_code == 202
        payload = response.json()
        assert "task_id" in payload

        task_id = payload["task_id"]
        assert task_manager.get_queue(task_id) is not None
        mock_task.assert_awaited_once_with(
            task_id=task_id,
            pool=mock_pool,
            split="held_out",
            prompt_version="extraction_v1",
            dry_run=False,
        )

        task_manager.cleanup(task_id)

@pytest.mark.asyncio
async def test_post_evals_run_rejects_null_control_fields(app, client):
    app.state.pool = MockPool([])

    response = await client.post(
        "/api/v1/evals/run",
        json={"split": None, "prompt_version": None, "dry_run": None},
    )

    assert response.status_code == 422
