import os
import uuid
import asyncio
import json
import structlog
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Request, status, UploadFile, File, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import psycopg

from backend.db.connection import get_db
from backend.utils.tasks import task_manager, active_task_id
from backend.services.parser import run_full_ingestion
from backend.services.source_discovery import discover_sources

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


async def run_source_discovery_task(task_id: str, pool):
    """
    Background task wrapper for ATS source discovery using the same task/SSE
    infrastructure as ingestion.
    """
    active_task_id.set(task_id)
    logger.info("Background source discovery task started", task_id=task_id)

    try:
        result = await asyncio.wait_for(discover_sources(pool), timeout=1800.0)
        summary = {
            "candidate_count": result.candidate_count,
            "validated_count": result.validated_count,
            "rejected_count": result.rejected_count,
            "error_count": result.error_count,
            "unsupported_url_count": result.unsupported_url_count,
            "report_path": result.report_path,
        }
        logger.info("Background source discovery task completed successfully", task_id=task_id, **summary)
        task_manager.enqueue_log(task_id, {
            "control_type": "completed",
            "summary": summary,
        })
    except Exception as exc:
        logger.error("Background source discovery task failed with exception", task_id=task_id, error=str(exc))
        task_manager.enqueue_log(task_id, {
            "control_type": "failed",
            "error": str(exc),
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


@router.post("/ingest/discover-sources", status_code=status.HTTP_202_ACCEPTED)
async def start_source_discovery(request: Request, background_tasks: BackgroundTasks):
    """
    Triggers asynchronous source discovery and validation.
    """
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        logger.error("Database connection pool not found in app state")
        raise RuntimeError("Database pool not initialized")

    task_id = str(uuid.uuid4())
    task_manager.register_task(task_id)
    background_tasks.add_task(run_source_discovery_task, task_id=task_id, pool=pool)
    return {"task_id": task_id}


@router.get("/ingest/sources")
async def list_ingest_sources(request: Request):
    """
    Returns active and rejected source registry rows for coverage diagnostics.
    """
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        logger.error("Database connection pool not found in app state")
        raise RuntimeError("Database pool not initialized")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT company, ats, slug, source_url, discovery_method, validation_status,
                       active, job_count, usable_job_count, last_validated_at, last_error, metadata
                FROM job_sources
                ORDER BY active DESC, ats, slug
                """
            )
            source_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT raw_url, company_hint, detected_ats, detected_slug, discovery_method,
                       validation_status, rejection_reason, last_error, metadata, created_at
                FROM job_source_candidates
                WHERE validation_status IN ('rejected', 'error')
                ORDER BY created_at DESC
                LIMIT 200
                """
            )
            candidate_rows = await cur.fetchall()

    return {
        "sources": [
            {
                "company": row[0],
                "ats": row[1],
                "slug": row[2],
                "source_url": row[3],
                "discovery_method": row[4],
                "validation_status": row[5],
                "active": row[6],
                "job_count": row[7],
                "usable_job_count": row[8],
                "last_validated_at": row[9],
                "last_error": row[10],
                "metadata": row[11],
            }
            for row in source_rows
        ],
        "rejected_candidates": [
            {
                "raw_url": row[0],
                "company_hint": row[1],
                "detected_ats": row[2],
                "detected_slug": row[3],
                "discovery_method": row[4],
                "validation_status": row[5],
                "rejection_reason": row[6],
                "last_error": row[7],
                "metadata": row[8],
                "created_at": row[9],
            }
            for row in candidate_rows
        ],
    }

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

async def record_ingestion_run(conn, status: str, source_counts: dict, error_message: Optional[str], execution_time_seconds: float):
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO ingestion_runs (status, source_counts, error_message, execution_time_seconds)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    status,
                    json.dumps(source_counts),
                    error_message,
                    execution_time_seconds
                )
            )
    except Exception as e:
        logger.error("Failed to record CSV ingestion run to telemetry database", error=str(e))

@router.post("/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    conn: psycopg.AsyncConnection = Depends(get_db)
):
    """
    Exposes POST /api/v1/ingest/csv accepting a multipart form upload file.
    Validates file extension, size limit, and inserts parsed jobs into the jobs table.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=400,
            content={"error": True, "code": "INVALID_FILE_TYPE", "detail": "File must have .csv extension."}
        )

    start_time = datetime.now()
    max_size = 5 * 1024 * 1024  # 5MB limit
    if file.size is not None and file.size > max_size:
        return JSONResponse(
            status_code=413,
            content={"error": True, "code": "FILE_TOO_LARGE", "detail": "File size exceeds 5MB limit."}
        )

    size = 0
    contents = bytearray()

    try:
        while True:
            chunk = await file.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > max_size:
                return JSONResponse(
                    status_code=413,
                    content={"error": True, "code": "FILE_TOO_LARGE", "detail": "File size exceeds 5MB limit."}
                )
            contents.extend(chunk)

        csv_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = contents.decode("latin-1")
        except Exception as e:
            execution_time_seconds = (datetime.now() - start_time).total_seconds()
            await record_ingestion_run(conn, "failure", {}, "Could not decode file content: " + str(e), execution_time_seconds)
            return JSONResponse(
                status_code=400,
                content={"error": True, "code": "INVALID_ENCODING", "detail": "Could not decode file content."}
            )
    except Exception as e:
        execution_time_seconds = (datetime.now() - start_time).total_seconds()
        await record_ingestion_run(conn, "failure", {}, str(e), execution_time_seconds)
        return JSONResponse(
            status_code=500,
            content={"error": True, "code": "INTERNAL_SERVER_ERROR", "detail": str(e)}
        )

    try:
        import csv
        import io
        f = io.StringIO(csv_text)
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            await record_ingestion_run(conn, "failure", {}, "CSV file has no headers.", (datetime.now() - start_time).total_seconds())
            return JSONResponse(
                status_code=400,
                content={"error": True, "code": "MALFORMED_CSV", "detail": "CSV file has no headers."}
            )

        required_headers = {"url", "title", "company", "raw_text"}
        missing_headers = required_headers - set(reader.fieldnames)
        if missing_headers:
            err_msg = f"CSV is missing required headers: {', '.join(missing_headers)}"
            await record_ingestion_run(conn, "failure", {}, err_msg, (datetime.now() - start_time).total_seconds())
            return JSONResponse(
                status_code=400,
                content={
                    "error": True,
                    "code": "MISSING_HEADERS",
                    "detail": err_msg
                }
            )

        imported_jobs = 0
        skipped_jobs = 0

        async with conn.transaction():
            for row_idx, row in enumerate(reader, start=1):
                url = (row.get("url") or "").strip()
                title = (row.get("title") or "").strip()
                company = (row.get("company") or "").strip()
                raw_text = (row.get("raw_text") or "").strip()

                # Validate required columns and URL structure
                if not url or not title or not company or not raw_text or not (url.startswith("http://") or url.startswith("https://")):
                    logger.warn("Skipping CSV row due to missing required columns or invalid URL pattern", row_index=row_idx, row=row)
                    skipped_jobs += 1
                    continue

                location = row.get("location")
                if location is not None:
                    location = location.strip()
                source_slug = (row.get("source_slug") or "").strip() or "csv"

                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO jobs (url, title, company, location, raw_text, source_slug)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        RETURNING id
                        """,
                        (url, title, company, location, raw_text, source_slug)
                    )
                    res = await cur.fetchone()
                    if res and res[0] is not None:
                        imported_jobs += 1
                    else:
                        logger.warn("Skipping duplicate job URL from CSV", url=url)
                        skipped_jobs += 1

        execution_time_seconds = (datetime.now() - start_time).total_seconds()
        await record_ingestion_run(conn, "success", {"csv": imported_jobs}, None, execution_time_seconds)

        return {
            "status": "success",
            "imported_jobs": imported_jobs,
            "skipped_jobs": skipped_jobs
        }
    except Exception as e:
        execution_time_seconds = (datetime.now() - start_time).total_seconds()
        await record_ingestion_run(conn, "failure", {}, str(e), execution_time_seconds)
        return JSONResponse(
            status_code=500,
            content={"error": True, "code": "INTERNAL_SERVER_ERROR", "detail": str(e)}
        )
