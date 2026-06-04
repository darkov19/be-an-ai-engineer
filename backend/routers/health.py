import datetime
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
import psycopg
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.get("/health")
async def health_check(request: Request):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Check if database pool exists
    if not hasattr(request.app.state, "pool") or request.app.state.pool is None:
        logger.error("Database pool not initialized in app state")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "data": {
                    "status": "unhealthy",
                    "database": "disconnected",
                    "timestamp": timestamp,
                    "corpus_size": 0,
                    "eval_accuracy": None,
                    "system_state": "locked",
                    "warning_mode": False
                }
            }
        )

    pool = request.app.state.pool

    try:
        # Try to check out a connection with a timeout of 3.0 seconds
        async with pool.connection(timeout=3.0) as conn:
            # Connection check succeeded. Now run query.
            try:
                async with conn.cursor() as cur:
                    # 1. Corpus size
                    await cur.execute("SELECT COUNT(*) FROM jobs")
                    row = await cur.fetchone()
                    corpus_size = int(row[0]) if row else 0

                    # 2. Latest evaluation F1
                    await cur.execute("SELECT overall_f1 FROM evaluation_runs ORDER BY run_timestamp DESC, id DESC LIMIT 1")
                    row = await cur.fetchone()
                    eval_accuracy = float(row[0]) if (row and row[0] is not None) else None

                    # 3. Latest ingestion run status
                    await cur.execute("SELECT status FROM ingestion_runs ORDER BY run_timestamp DESC, id DESC LIMIT 1")
                    row = await cur.fetchone()
                    latest_ingest_status = row[0] if row else None

                    check_accuracy = eval_accuracy if eval_accuracy is not None else 1.0
                    corpus_breached = corpus_size < 100
                    accuracy_breached = check_accuracy < 0.70

                    latest_ingest_succeeded = latest_ingest_status == "success"
                    if (
                        corpus_size == 0
                        or not latest_ingest_succeeded
                        or (corpus_breached and accuracy_breached)
                    ):
                        system_state = "locked"
                    elif corpus_breached != accuracy_breached:
                        system_state = "warning"
                    else:
                        system_state = "nominal"

                    warning_mode = (system_state == "warning")

                    return {
                        "data": {
                            "status": "healthy",
                            "database": "connected",
                            "timestamp": timestamp,
                            "corpus_size": corpus_size,
                            "eval_accuracy": eval_accuracy,
                            "system_state": system_state,
                            "warning_mode": warning_mode
                        }
                    }
            except Exception as query_exc:
                # If a database query fails or raises an exception
                logger.error("Database query failed during health check", error=str(query_exc))
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": True,
                        "code": "DB_CONNECTION_ERROR",
                        "detail": "Database query execution failure."
                    }
                )
    except Exception as conn_exc:
        # Catch connection and checkout failures (OperationalError, TimeoutError, etc.)
        logger.error("Database connectivity check failed during health check", error=str(conn_exc))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "data": {
                    "status": "unhealthy",
                    "database": "disconnected",
                    "timestamp": timestamp,
                    "corpus_size": 0,
                    "eval_accuracy": None,
                    "system_state": "locked",
                    "warning_mode": False
                }
            }
        )


@router.post("/cockpit/access")
async def record_cockpit_access(request: Request):
    if not hasattr(request.app.state, "pool") or request.app.state.pool is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "code": "DB_CONNECTION_ERROR",
                "detail": "Database connection pool is not initialized."
            }
        )

    pool = request.app.state.pool
    try:
        async with pool.connection(timeout=3.0) as conn:
            await conn.execute("INSERT INTO cockpit_access_logs DEFAULT VALUES")
    except Exception as exc:
        logger.error("Failed to record cockpit access", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "code": "DB_CONNECTION_ERROR",
                "detail": "Database query execution failure."
            }
        )

    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"ok": True})
