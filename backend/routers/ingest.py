import os
import uuid
import asyncio
import json
import structlog
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.utils.tasks import task_manager, active_task_id
from backend.services.parser import run_full_ingestion

router = APIRouter()
logger = structlog.get_logger()

class IngestRequest(BaseModel):
    company_slug: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9-_]+$")

async def dump_logs_to_file(task_id: str):
    """
    Drains/dumps all accumulated task logs to debug-attempt-YYYY-MM-DD.log
    in the workspace root.
    """
    logs = task_manager.get_history(task_id)
    if not logs:
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"debug-attempt-{date_str}.log"
    # Root of the workspace is three levels up from backend/routers/ingest.py
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    filepath = os.path.join(workspace_root, filename)

    try:
        # Write logs as JSON lines
        with open(filepath, "a", encoding="utf-8") as f:
            for log in logs:
                f.write(json.dumps(log, default=str) + "\n")
        logger.info("Successfully dumped timeout logs to file", filepath=filepath)
    except Exception as e:
        logger.error("Failed to dump logs to file", filepath=filepath, error=str(e))

async def run_ingestion_task(task_id: str, pool, config: Optional[dict]):
    """
    Background task wrapper executing the parsing and ingestion logic.
    Supports timeout limits and triggers error propagation and logging.
    """
    active_task_id.set(task_id)
    logger.info("Background ingestion task started", task_id=task_id)

    start_time = asyncio.get_event_loop().time()

    try:
        # Wrap the call to run_full_ingestion in asyncio.wait_for with 3600-second timeout
        result = await asyncio.wait_for(
            run_full_ingestion(pool, config),
            timeout=3600.0
        )
        logger.info("Background ingestion task completed successfully", task_id=task_id)

        # Enqueue completion event
        task_manager.enqueue_log(task_id, {
            "control_type": "completed",
            "summary": result
        })

    except asyncio.TimeoutError:
        logger.error("Background ingestion task timed out", task_id=task_id)
        execution_time = asyncio.get_event_loop().time() - start_time

        # 1. Write failure summary to ingestion_runs table
        if pool is not None:
            try:
                async with pool.connection() as conn:
                    await conn.execute("""
                        INSERT INTO ingestion_runs (status, source_counts, error_message, execution_time_seconds)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        "failure",
                        json.dumps({}),
                        "Ingestion task timed out after 60 minutes",
                        execution_time
                    ))
            except Exception as db_err:
                logger.error("Failed to save timeout metadata to database", error=str(db_err))

        # 2. Dump all accumulated task logs to a file named debug-attempt-YYYY-MM-DD.log
        await dump_logs_to_file(task_id)

        # 3. Raise task.failed event to any connected SSE clients
        task_manager.enqueue_log(task_id, {
            "control_type": "failed",
            "error": "Task timed out after 60 minutes"
        })

    except Exception as exc:
        logger.error("Background ingestion task failed with exception", task_id=task_id, error=str(exc))
        # Send failure event to SSE clients
        task_manager.enqueue_log(task_id, {
            "control_type": "failed",
            "error": str(exc)
        })
    finally:
        task_manager.finish_task(task_id)

@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Optional[IngestRequest] = None
):
    """
    Triggers asynchronous ingestion running in the background.
    Returns 202 Accepted status immediately.
    """
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        logger.error("Database connection pool not found in app state")
        raise RuntimeError("Database pool not initialized")

    company_slug = payload.company_slug if payload else None

    # Generate task UUID
    task_id = str(uuid.uuid4())

    # Register task log queue
    task_manager.register_task(task_id)

    # Derive parser config based on company_slug
    if company_slug:
        config = {
            "greenhouse": [company_slug],
            "lever": [company_slug],
            "ashby": [company_slug],
            "workable": [company_slug],
            "recruitee": [company_slug],
            "personio": [company_slug]
        }
    else:
        config = None

    background_tasks.add_task(
        run_ingestion_task,
        task_id=task_id,
        pool=pool,
        config=config
    )

    return {"task_id": task_id}

@router.get("/tasks/{task_id}/logs/stream")
async def stream_task_logs(task_id: str):
    """
    Streams ingestion logs live for the specified task ID via Server-Sent Events (SSE).
    """
    task_manager.start_stream(task_id)

    async def event_generator():
        # Start emitting task.started
        yield f"event: task.started\ndata: {json.dumps({'task_id': task_id})}\n\n"

        queue = task_manager.get_queue(task_id)
        if queue is None:
            yield f"event: task.failed\ndata: {json.dumps({'error': 'Task not found or queue already cleaned up'})}\n\n"
            return

        consumed_termination = False
        try:
            while True:
                item = await queue.get()
                if isinstance(item, dict) and "control_type" in item:
                    ctrl = item["control_type"]
                    if ctrl == "completed":
                        yield f"event: task.completed\ndata: {json.dumps(item['summary'], default=str)}\n\n"
                        consumed_termination = True
                        break
                    elif ctrl == "failed":
                        yield f"event: task.failed\ndata: {json.dumps({'error': item['error']}, default=str)}\n\n"
                        consumed_termination = True
                        break
                else:
                    yield f"event: task.log\ndata: {json.dumps(item, default=str)}\n\n"
        except asyncio.CancelledError:
            logger.info("SSE client disconnected from log stream", task_id=task_id)
        except Exception as e:
            logger.error("Error in SSE stream generator", task_id=task_id, error=str(e))
            yield f"event: task.failed\ndata: {json.dumps({'error': str(e)}, default=str)}\n\n"
        finally:
            if consumed_termination:
                task_manager.cleanup(task_id)
            else:
                task_manager.stop_stream(task_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
