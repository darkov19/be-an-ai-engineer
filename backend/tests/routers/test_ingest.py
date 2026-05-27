import pytest
import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.utils.tasks import task_manager
from backend.routers.ingest import run_ingestion_task, dump_logs_to_file

@pytest.mark.asyncio
async def test_post_ingest_success(app, client):
    mock_pool = MagicMock()
    app.state.pool = mock_pool

    with patch("backend.routers.ingest.run_ingestion_task", new_callable=AsyncMock) as mock_run:
        response = await client.post("/api/v1/ingest", json={"company_slug": "cockroach"})
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
    response = await client.post("/api/v1/ingest", json={"company_slug": "cockroach"})
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
async def test_run_ingestion_task_timeout():
    task_id = "test-task-timeout"
    task_manager.register_task(task_id)
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn

    # Enqueue a log so history has something
    task_manager.enqueue_log(task_id, {"event": "started working", "level": "info"})

    # Force run_full_ingestion to raise TimeoutError by patching wait_for to raise it
    with patch("backend.routers.ingest.run_full_ingestion", new_callable=AsyncMock) as mock_ingest:
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
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
