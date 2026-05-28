import pytest
import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.utils.tasks import task_manager
from backend.routers.ingest import ingest_csv, run_ingestion_task, run_source_discovery_task, dump_logs_to_file

@pytest.mark.asyncio
async def test_post_ingest_success(app, client):
    mock_pool = MagicMock()
    app.state.pool = mock_pool

    async def noop_ingestion_task(*args, **kwargs):
        return None

    with patch("backend.routers.ingest.run_ingestion_task", new=noop_ingestion_task):
        response = await client.post("/api/v1/ingest", json={"company_slug": "stripe"})
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        task_id = data["task_id"]

        # Verify the queue is registered
        assert task_manager.get_queue(task_id) is not None

        # Cleanup
        task_manager.cleanup(task_id)

@pytest.mark.asyncio
async def test_post_ingest_no_pool(app, client):
    app.state.pool = None
    response = await client.post("/api/v1/ingest", json={"company_slug": "stripe"})
    assert response.status_code == 500
    data = response.json()
    assert data["code"] == "DB_CONNECTION_ERROR"


@pytest.mark.asyncio
async def test_post_discover_sources_success(app, client):
    mock_pool = MagicMock()
    app.state.pool = mock_pool

    async def noop_source_discovery_task(*args, **kwargs):
        return None

    with patch("backend.routers.ingest.run_source_discovery_task", new=noop_source_discovery_task):
        response = await client.post("/api/v1/ingest/discover-sources")
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        task_manager.cleanup(data["task_id"])


@pytest.mark.asyncio
async def test_post_discover_sources_no_pool(app, client):
    app.state.pool = None
    response = await client.post("/api/v1/ingest/discover-sources")
    assert response.status_code == 500
    data = response.json()
    assert data["code"] == "DB_CONNECTION_ERROR"

@pytest.mark.asyncio
async def test_stream_logs_success(client):
    task_id = "test-task-123"
    task_manager.register_task(task_id)

    # Enqueue a log and a completion event
    task_manager.enqueue_log(task_id, {"event": "hello", "level": "info"})
    task_manager.enqueue_log(task_id, {"control_type": "completed", "summary": {"status": "success"}})

    # Let the event loop process the enqueues before requesting the stream
    await asyncio.sleep(0.01)

    response = await client.get(f"/api/v1/tasks/{task_id}/logs/stream")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    lines = response.text.split("\n")
    # Clean empty lines
    lines = [line for line in lines if line.strip()]

    assert "event: task.started" in lines[0]
    assert "data: " in lines[1]
    assert "event: task.log" in lines[2]
    assert "hello" in lines[3]
    assert "event: task.completed" in lines[4]
    assert "success" in lines[5]

    # Verify queue cleaned up
    assert task_manager.get_queue(task_id) is None

@pytest.mark.asyncio
async def test_run_ingestion_task_success():
    task_id = "test-task-success"
    task_manager.register_task(task_id)
    mock_pool = MagicMock()

    mock_summary = {"status": "success", "source_counts": {}, "execution_time_seconds": 1.5}

    with patch("backend.routers.ingest.run_full_ingestion", new_callable=AsyncMock, return_value=mock_summary):
        await run_ingestion_task(task_id, mock_pool, None)

        # Allow the event loop to process scheduled call_soon_threadsafe callbacks
        await asyncio.sleep(0.01)

        queue = task_manager.get_queue(task_id)
        assert queue is not None

        # Read the completion control event
        logs = []
        while not queue.empty():
            logs.append(queue.get_nowait())

        assert len(logs) == 3  # Started log, Completed log, and Completed control event
        assert logs[0]["event"] == "Background ingestion task started"
        assert logs[1]["event"] == "Background ingestion task completed successfully"
        assert logs[2]["control_type"] == "completed"
        assert logs[2]["summary"] == mock_summary

    task_manager.cleanup(task_id)


@pytest.mark.asyncio
async def test_run_source_discovery_task_success():
    task_id = "test-source-discovery-success"
    task_manager.register_task(task_id)
    mock_pool = MagicMock()
    mock_result = MagicMock(
        candidate_count=2,
        validated_count=1,
        rejected_count=1,
        error_count=0,
        unsupported_url_count=1,
        report_path="report.json",
    )

    with patch("backend.routers.ingest.discover_sources", new_callable=AsyncMock, return_value=mock_result):
        await run_source_discovery_task(task_id, mock_pool)
        await asyncio.sleep(0.01)

        queue = task_manager.get_queue(task_id)
        logs = []
        while not queue.empty():
            logs.append(queue.get_nowait())

        assert logs[-1]["control_type"] == "completed"
        assert logs[-1]["summary"]["validated_count"] == 1

    task_manager.cleanup(task_id)

@pytest.mark.asyncio
async def test_run_ingestion_task_timeout():
    task_id = "test-task-timeout"
    task_manager.register_task(task_id)
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn

    # Enqueue a log so history has something
    task_manager.enqueue_log(task_id, {"event": "started working", "level": "info"})

    async def timeout_wait_for(coro, timeout):
        coro.close()
        raise asyncio.TimeoutError

    # Force run_full_ingestion to raise TimeoutError by patching wait_for to raise it
    with patch("backend.routers.ingest.run_full_ingestion", new_callable=AsyncMock) as mock_ingest:
        with patch("asyncio.wait_for", side_effect=timeout_wait_for):
            await run_ingestion_task(task_id, mock_pool, None)

            # Allow event loop to process scheduled callbacks
            await asyncio.sleep(0.01)

            # Assert insert query run
            assert mock_conn.execute.called
            args = mock_conn.execute.call_args[0]
            assert "Ingestion task timed out after 60 minutes" in args[1]

            # Assert file debug-attempt-YYYY-MM-DD.log was created
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"debug-attempt-{date_str}.log"
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            filepath = os.path.join(workspace_root, filename)

            assert os.path.exists(filepath)

            # Clean up the file
            try:
                os.remove(filepath)
            except OSError:
                pass

            # Assert queue has the failed event
            queue = task_manager.get_queue(task_id)
            logs = []
            while not queue.empty():
                logs.append(queue.get_nowait())

            # Logs should contain:
            # 1. Manual log
            # 2. Started log
            # 3. Timeout log
            # 4. Dump success log
            # 5. Failed control event
            assert len(logs) == 5
            assert logs[-1]["control_type"] == "failed"
            assert "timed out" in logs[-1]["error"].lower()

    task_manager.cleanup(task_id)

@pytest.mark.asyncio
async def test_post_ingest_invalid_company_slug(app, client):
    mock_pool = MagicMock()
    app.state.pool = mock_pool

    # Send a slug with spaces and special characters
    response = await client.post("/api/v1/ingest", json={"company_slug": "invalid/slug?"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True
    assert data["code"] == "VALIDATION_ERROR"
    assert "company_slug" in data["detail"]

@pytest.mark.asyncio
async def test_delayed_cleanup_and_stream_lifecycle():
    task_id = "test-lifecycle-1"
    task_manager.register_task(task_id)
    
    # 1. Start streaming client
    task_manager.start_stream(task_id)
    
    # 2. Finish task (should NOT clean up yet since stream is active)
    task_manager.finish_task(task_id)
    assert task_manager.get_queue(task_id) is not None
    
    # 3. Stop streaming client (should clean up immediately because task is finished)
    task_manager.stop_stream(task_id)
    assert task_manager.get_queue(task_id) is None

@pytest.mark.asyncio
async def test_finish_task_delayed_cleanup():
    task_id = "test-lifecycle-2"
    task_manager.register_task(task_id)
    
    # 1. Finish task without any active stream (should clean up after a delay)
    task_manager.finish_task(task_id)
    assert task_manager.get_queue(task_id) is not None
    
    # Test delayed cleanup directly with mocked sleep
    async def dummy_sleep(delay):
        pass

    with patch("asyncio.sleep", new_callable=lambda: dummy_sleep):
        await task_manager._delayed_cleanup(task_id, delay=0.01)
        assert task_manager.get_queue(task_id) is None

# Helper classes for database mocking in ingestion tests
class MockIngestCursor:
    def __init__(self, fetch_results=None):
        self.fetch_results = fetch_results if fetch_results is not None else []
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

class MockIngestTransaction:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class MockIngestConnection:
    def __init__(self, fetch_results=None):
        self.fetch_results = fetch_results
        self.cursors = []

    def cursor(self, *args, **kwargs):
        cur = MockIngestCursor(self.fetch_results)
        self.cursors.append(cur)
        return cur

    def transaction(self):
        return MockIngestTransaction()

class MockIngestPool:
    def __init__(self, fetch_results=None):
        self.fetch_results = fetch_results
        self.connections = []

    async def __aenter__(self):
        conn = MockIngestConnection(self.fetch_results)
        self.connections.append(conn)
        return conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def connection(self):
        return self


class MockSourceListCursor:
    def __init__(self):
        self.execute_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_count += 1

    async def fetchall(self):
        if self.execute_count == 1:
            return [
                (
                    "Stripe",
                    "greenhouse",
                    "stripe",
                    "https://boards.greenhouse.io/stripe",
                    "seed_file",
                    "validated",
                    True,
                    3,
                    3,
                    None,
                    None,
                    {"source_urls": ["https://boards.greenhouse.io/stripe"]},
                )
            ]
        return [
            (
                "https://example.com/careers",
                "Example",
                None,
                None,
                "seed_file",
                "rejected",
                "unsupported_or_no_ats_detected",
                None,
                {},
                None,
            )
        ]


class MockSourceListConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return MockSourceListCursor()


class MockSourceListPool:
    def connection(self):
        return MockSourceListConnection()


class MockCompanySignalCursor:
    def __init__(self):
        self.execute_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_count += 1
        self.query = query
        self.vars = vars

    async def fetchall(self):
        return [
            (
                "unit",
                "https://example.com/evidence",
                "Acme",
                "example.com",
                "resolved",
                "greenhouse",
                "acme",
                "https://boards.greenhouse.io/acme",
                None,
                None,
                {"source_urls": ["https://boards.greenhouse.io/acme"]},
                None,
            )
        ]

    async def fetchone(self):
        return (
            {
                "provider_diagnostics": {
                    "vertex_ai_search": {"status": "disabled", "reason": "missing_credentials"}
                },
                "provider_errors": {"vertex_ai_search": "quota_exhausted"},
            },
        )


class MockCompanySignalConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return MockCompanySignalCursor()


class MockCompanySignalPool:
    def connection(self):
        return MockCompanySignalConnection()


@pytest.mark.asyncio
async def test_get_ingest_sources_lists_registry_diagnostics(app, client):
    app.state.pool = MockSourceListPool()

    response = await client.get("/api/v1/ingest/sources")

    assert response.status_code == 200
    data = response.json()
    assert data["sources"][0]["ats"] == "greenhouse"
    assert data["sources"][0]["active"] is True
    assert data["rejected_candidates"][0]["rejection_reason"] == "unsupported_or_no_ats_detected"


@pytest.mark.asyncio
async def test_get_company_signals_lists_recent_diagnostics(app, client):
    app.state.pool = MockCompanySignalPool()

    response = await client.get("/api/v1/ingest/company-signals")

    assert response.status_code == 200
    data = response.json()
    assert data["company_signals"][0]["provider"] == "unit"
    assert data["company_signals"][0]["resolved_ats"] == "greenhouse"
    assert data["company_signals"][0]["metadata"]["source_urls"] == ["https://boards.greenhouse.io/acme"]
    assert data["provider_diagnostics"]["vertex_ai_search"]["reason"] == "missing_credentials"
    assert data["provider_errors"]["vertex_ai_search"] == "quota_exhausted"

@pytest.mark.asyncio
async def test_ingest_csv_success(app, client):
    # Setup mock db pool
    # Returns (1,) for job insert, then no return for ingestion runs insert
    mock_pool = MockIngestPool([(1,), None])
    app.state.pool = mock_pool

    csv_content = "url,title,company,location,raw_text,source_slug\nhttps://example.com/job1,Software Engineer,Acme Inc,Remote,Job description,csv"
    files = {"file": ("jobs.csv", csv_content, "text/csv")}

    response = await client.post("/api/v1/ingest/csv", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_jobs"] == 1
    assert data["skipped_jobs"] == 0

    # Ensure execute calls were made
    assert len(mock_pool.connections[0].cursors) == 2
    # First is the job insertion
    assert "INSERT INTO jobs" in mock_pool.connections[0].cursors[0].execute_calls[0][0]
    # Second is the telemetry run logs
    assert "INSERT INTO ingestion_runs" in mock_pool.connections[0].cursors[1].execute_calls[0][0]

@pytest.mark.asyncio
async def test_ingest_csv_invalid_extension(app, client):
    mock_pool = MockIngestPool([])
    app.state.pool = mock_pool

    files = {"file": ("jobs.txt", "some text content", "text/plain")}
    response = await client.post("/api/v1/ingest/csv", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_FILE_TYPE"

@pytest.mark.asyncio
async def test_ingest_csv_payload_too_large(app, client):
    class OversizedUpload:
        filename = "jobs.csv"
        size = (5 * 1024 * 1024) + 1

        async def read(self, size=-1):
            raise AssertionError("Oversized uploads should be rejected before reading the body")

    response = await ingest_csv(file=OversizedUpload(), conn=MagicMock())
    assert response.status_code == 413
    data = json.loads(response.body)
    assert data["code"] == "FILE_TOO_LARGE"

@pytest.mark.asyncio
async def test_ingest_csv_skipped_rows(app, client):
    # 2 rows: one is valid, one has missing required 'title'
    mock_pool = MockIngestPool([(1,), None])
    app.state.pool = mock_pool

    csv_content = "url,title,company,location,raw_text,source_slug\nhttps://example.com/job1,Software Engineer,Acme Inc,Remote,Job description,csv\nhttps://example.com/job2,,Acme Inc,Remote,Job description,csv"
    files = {"file": ("jobs.csv", csv_content, "text/csv")}

    response = await client.post("/api/v1/ingest/csv", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_jobs"] == 1
    assert data["skipped_jobs"] == 1

@pytest.mark.asyncio
async def test_ingest_csv_duplicates(app, client):
    # 2 valid rows: one gets inserted (returns ID), one is duplicate (returns None due to conflict)
    mock_pool = MockIngestPool([(1,), None, None])
    app.state.pool = mock_pool

    csv_content = (
        "url,title,company,location,raw_text,source_slug\n"
        "https://example.com/job1,Software Engineer,Acme Inc,Remote,Job description,csv\n"
        "https://example.com/job2,Software Engineer,Acme Inc,Remote,Job description,csv"
    )
    files = {"file": ("jobs.csv", csv_content, "text/csv")}

    response = await client.post("/api/v1/ingest/csv", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_jobs"] == 1
    assert data["skipped_jobs"] == 1


@pytest.mark.asyncio
async def test_ingest_csv_invalid_url_pattern(app, client):
    # 3 rows: one with valid URL, one with empty/whitespace URL, one with non-http URL
    mock_pool = MockIngestPool([(1,), None, None])
    app.state.pool = mock_pool

    csv_content = (
        "url,title,company,location,raw_text,source_slug\n"
        "https://example.com/job1,Software Engineer,Acme Inc,Remote,Job description,csv\n"
        "   ,Software Engineer,Acme Inc,Remote,Job description,csv\n"
        "not-a-valid-url,Software Engineer,Acme Inc,Remote,Job description,csv"
    )
    files = {"file": ("jobs.csv", csv_content, "text/csv")}

    response = await client.post("/api/v1/ingest/csv", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_jobs"] == 1
    assert data["skipped_jobs"] == 2
