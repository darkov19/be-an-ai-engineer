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
                    "timestamp": timestamp
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
                    # Parameterized query to follow guidelines, even for static SELECT 1
                    await cur.execute("SELECT %s", (1,))
                    result = await cur.fetchone()
                    if result and result[0] == 1:
                        return {
                            "data": {
                                "status": "healthy",
                                "database": "connected",
                                "timestamp": timestamp
                            }
                        }
                    else:
                        raise psycopg.Error("Database returned unexpected result")
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
                    "timestamp": timestamp
                }
            }
        )
