import json
from pathlib import Path

import httpx
import pytest

from backend.llm.client import (
    DEFAULT_BATCH_SIZE,
    PROMPT_VERSION,
    ExtractionHTTPError,
    ExtractionResponseError,
    redact_extraction_error,
    run_extraction_batch,
    select_unextracted_jobs,
)
from backend.llm.hermes import HermesProxyConnectionError


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def valid_item(job_id: int) -> dict:
    return {
        "job_id": job_id,
        "skills": ["Python", "LLM"],
        "seniority": "senior",
        "tech_stack": ["FastAPI", "Postgres"],
        "salary_band": {"kind": "not_disclosed"},
        "remote_policy": "remote",
        "role_archetype": "llm_app_engineer",
    }


class MockResponse:
    def __init__(self, payload=None, status_error=None, json_error=None):
        self.payload = payload
        self.status_error = status_error
        self.json_error = json_error
        self.status_code = 200

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class MockAsyncClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        self.posts.append((url, json))
        if self.error:
            raise self.error
        return self.response


class MockCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []
        self.rowcount = -1
        self.next_rowcounts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, vars=None):
        self.executed.append((query, vars))
        self.rowcount = self.next_rowcounts.pop(0) if self.next_rowcounts else 1

    async def fetchall(self):
        return self.rows


class MockTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class MockConnection:
    def __init__(self, rows=None):
        self.cursor_obj = MockCursor(rows)
        self.transaction_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def transaction(self):
        self.transaction_count += 1
        return MockTransaction()


class MockPool:
    def __init__(self, rows=None):
        self.conn = MockConnection(rows)
        self.connection_count = 0

    def connection(self):
        self.connection_count += 1
        return self.conn


def test_migration_defines_extraction_columns_indexes_and_updated_at_trigger():
    migration = (BACKEND_ROOT / "db" / "migrations" / "V007__add_job_extraction_fields.sql").read_text(
        encoding="utf-8"
    )

    for column in (
        "extracted_at",
        "prompt_version",
        "extraction_schema_version",
        "skills",
        "seniority",
        "tech_stack",
        "salary_band",
        "remote_policy",
        "role_archetype",
        "extraction_status",
        "extraction_error",
        "extraction_run_id",
    ):
        assert column in migration

    assert "ALTER TABLE jobs" in migration
    assert "JSONB" in migration
    assert "idx_jobs_extraction_unextracted_retryable" in migration
    assert "idx_jobs_prompt_schema_version" in migration
    assert "set_jobs_updated_at" in migration


@pytest.mark.asyncio
async def test_select_unextracted_jobs_filters_retryable_rows_and_selected_corpus():
    rows = [
        {
            "id": 1,
            "url": "https://jobs.example/1",
            "title": "AI Engineer",
            "company": "Example",
            "location": "Remote",
            "raw_text": "Build LLM apps",
            "source_slug": "example",
        }
    ]
    conn = MockConnection(rows)

    selected = await select_unextracted_jobs(conn, limit=DEFAULT_BATCH_SIZE)

    assert selected[0].id == 1
    query, vars = conn.cursor_obj.executed[0]
    assert "extracted_at IS NULL" in query
    assert "OR extraction_status" not in query
    assert "retryable_error" in query
    assert "job_sources" in query
    assert "SELECT ats" in query
    assert "SELECT slug" not in query
    assert "company_signals" not in query
    assert vars["limit"] == DEFAULT_BATCH_SIZE


@pytest.mark.asyncio
async def test_health_failure_aborts_before_select_or_mutation(monkeypatch):
    async def fail_health():
        raise HermesProxyConnectionError("Could not connect to Hermes proxy at http://127.0.0.1:3000/health")

    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", fail_health)
    pool = MockPool([])

    with pytest.raises(HermesProxyConnectionError):
        await run_extraction_batch(pool, limit=2)

    assert pool.connection_count == 0


@pytest.mark.asyncio
async def test_run_extraction_persists_valid_rows_and_marks_missing_retryable(monkeypatch):
    async def healthy():
        return None

    http_client = MockAsyncClient(response=MockResponse(payload={"items": [valid_item(1)]}))
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            },
            {
                "id": 2,
                "url": "https://jobs.example/2",
                "title": "Agent Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build agents",
                "source_slug": "example",
            },
        ]
    )

    summary = await run_extraction_batch(pool, limit=2, run_id="run-test")

    assert summary["selected"] == 2
    assert summary["extracted"] == 1
    assert summary["retryable_errors"] == 1
    assert summary["prompt_version"] == PROMPT_VERSION
    executed_sql = "\n".join(query for query, _ in pool.conn.cursor_obj.executed)
    assert "extraction_status = 'extracted'" in executed_sql
    assert any(vars and vars.get("status") == "retryable_error" for _, vars in pool.conn.cursor_obj.executed)
    assert any(vars and vars.get("prompt_version") == PROMPT_VERSION for _, vars in pool.conn.cursor_obj.executed)
    posted_payload = http_client.posts[0][1]
    assert posted_payload["jobs"][0]["raw_text"] == "Build LLM apps"
    assert "Build LLM apps" not in posted_payload["prompt"]


@pytest.mark.asyncio
async def test_duplicate_returned_ids_mark_batch_retryable_then_reject(monkeypatch):
    async def healthy():
        return None

    http_client = MockAsyncClient(
        response=MockResponse(payload={"items": [valid_item(1), valid_item(1)]})
    )
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            }
        ]
    )

    with pytest.raises(ExtractionResponseError):
        await run_extraction_batch(pool, limit=1)

    executed_sql = "\n".join(query for query, _ in pool.conn.cursor_obj.executed)
    assert "UPDATE jobs" in executed_sql
    assert any(vars and vars.get("status") == "retryable_error" for _, vars in pool.conn.cursor_obj.executed)


@pytest.mark.asyncio
async def test_unknown_returned_id_marks_batch_retryable_then_rejects(monkeypatch):
    async def healthy():
        return None

    http_client = MockAsyncClient(response=MockResponse(payload={"items": [valid_item(999)]}))
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            }
        ]
    )

    with pytest.raises(ExtractionResponseError):
        await run_extraction_batch(pool, limit=1)

    executed_sql = "\n".join(query for query, _ in pool.conn.cursor_obj.executed)
    assert "UPDATE jobs" in executed_sql
    assert any(vars and vars.get("status") == "retryable_error" for _, vars in pool.conn.cursor_obj.executed)


@pytest.mark.asyncio
async def test_boolean_job_id_is_malformed_and_marks_batch_retryable(monkeypatch):
    async def healthy():
        return None

    item = valid_item(1)
    item["job_id"] = True
    http_client = MockAsyncClient(response=MockResponse(payload={"items": [item]}))
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            }
        ]
    )

    with pytest.raises(ExtractionResponseError):
        await run_extraction_batch(pool, limit=1)

    assert any(vars and vars.get("job_id") == 1 for _, vars in pool.conn.cursor_obj.executed)
    assert not any(vars and vars.get("job_id") is True for _, vars in pool.conn.cursor_obj.executed)


@pytest.mark.asyncio
async def test_invalid_returned_item_marks_requested_row_failed(monkeypatch):
    async def healthy():
        return None

    invalid = valid_item(1)
    invalid["seniority"] = "principal"
    http_client = MockAsyncClient(response=MockResponse(payload={"items": [invalid]}))
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            }
        ]
    )

    summary = await run_extraction_batch(pool, limit=1)

    assert summary["failed"] == 1
    assert summary["extracted"] == 0
    assert any(vars and vars.get("status") == "failed" for _, vars in pool.conn.cursor_obj.executed)


@pytest.mark.asyncio
async def test_malformed_json_response_marks_batch_retryable_then_rejects(monkeypatch):
    async def healthy():
        return None

    http_client = MockAsyncClient(response=MockResponse(json_error=ValueError("bad json")))
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            }
        ]
    )

    with pytest.raises(ExtractionResponseError):
        await run_extraction_batch(pool, limit=1)

    executed_sql = "\n".join(query for query, _ in pool.conn.cursor_obj.executed)
    assert "UPDATE jobs" in executed_sql
    assert any(vars and vars.get("status") == "retryable_error" for _, vars in pool.conn.cursor_obj.executed)


@pytest.mark.asyncio
async def test_zero_row_update_is_counted_as_skipped_not_extracted(monkeypatch):
    async def healthy():
        return None

    http_client = MockAsyncClient(response=MockResponse(payload={"items": [valid_item(1)]}))
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 1,
                "url": "https://jobs.example/1",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "Build LLM apps",
                "source_slug": "example",
            }
        ]
    )
    pool.conn.cursor_obj.next_rowcounts = [1, 0]

    summary = await run_extraction_batch(pool, limit=1)

    assert summary["extracted"] == 0
    assert summary["skipped"] == 1


@pytest.mark.asyncio
async def test_http_status_errors_are_safe_and_retryable(monkeypatch):
    async def healthy():
        return None

    request = httpx.Request("POST", "http://127.0.0.1:3000/extract")
    response = httpx.Response(500, request=request)
    http_client = MockAsyncClient(
        response=MockResponse(status_error=httpx.HTTPStatusError("boom secret-token", request=request, response=response))
    )
    monkeypatch.setattr("backend.llm.client.check_hermes_proxy_health", healthy)
    monkeypatch.setattr("backend.llm.client.httpx.AsyncClient", lambda timeout: http_client)
    pool = MockPool(
        [
            {
                "id": 3,
                "url": "https://jobs.example/3",
                "title": "AI Engineer",
                "company": "Example",
                "location": "Remote",
                "raw_text": "text",
                "source_slug": "example",
            }
        ]
    )

    with pytest.raises(ExtractionHTTPError):
        await run_extraction_batch(pool, limit=1)

    executed_sql = "\n".join(query for query, _ in pool.conn.cursor_obj.executed)
    assert "UPDATE jobs" in executed_sql
    assert any(vars and vars.get("status") == "retryable_error" for _, vars in pool.conn.cursor_obj.executed)


def test_redact_extraction_error_removes_large_text_prompt_and_response():
    error = (
        "prompt=full raw_text=Build "
        + ("x" * 500)
        + " response_body=secret api_key=abc123 Authorization: Bearer abc token: xyz secret-token"
    )

    redacted = redact_extraction_error(error)

    assert "api_key=abc123" not in redacted
    assert "Authorization: Bearer abc" not in redacted
    assert "token: xyz" not in redacted
    assert "secret-token" not in redacted
    assert "response_body=secret" not in redacted
    assert "raw_text=Build" not in redacted
    assert len(redacted) <= 240


def test_client_reuses_existing_hermes_health_boundary():
    source = (BACKEND_ROOT / "llm" / "client.py").read_text(encoding="utf-8")

    assert "from backend.llm.hermes import" in source
    assert "check_hermes_proxy_health" in source
    assert "class HermesProxyConnectionError" not in source
