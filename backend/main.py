import contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import AsyncConnectionPool
import structlog

from backend.config import settings
from backend.utils.logging import setup_logging
from backend.routers.health import router as health_router

setup_logging()
logger = structlog.get_logger()

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Initializing database connection pool", database_url=settings.database_url)
    
    # Create the connection pool. It will be opened asynchronously.
    # We set autocommit=True for connection defaults, which is standard for psycopg3 async.
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        open=False,
        kwargs={"autocommit": True}
    )
    
    try:
        await pool.open()
        app.state.pool = pool
        logger.info("Database connection pool successfully initialized and opened")
    except Exception as e:
        # Pool failed to open — set state to None so downstream None-guards work correctly.
        # The health check will return unhealthy; get_db will raise RuntimeError cleanly.
        logger.error("Failed to open database connection pool on startup", error=str(e))
        await pool.close()  # Release any partial resources
        app.state.pool = None
        
    yield
    
    # Shutdown logic
    if hasattr(app.state, "pool") and app.state.pool is not None:
        logger.info("Closing database connection pool")
        await app.state.pool.close()
        logger.info("Database connection pool successfully closed")

app = FastAPI(
    title="Cognitive Core Backend",
    lifespan=lifespan
)

# Global Exception Handlers for Database Errors
from fastapi import Request
from fastapi.responses import JSONResponse
import psycopg
from psycopg_pool import PoolClosed

@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    if "pool" in str(exc).lower() or "database" in str(exc).lower():
        logger.error("Database connection error raised", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "code": "DB_CONNECTION_ERROR",
                "detail": "Database connection pool is not initialized."
            }
        )
    logger.error("Unhandled runtime error occurred", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "INTERNAL_SERVER_ERROR",
            "detail": "An internal server error occurred."
        }
    )

@app.exception_handler(psycopg.OperationalError)
async def psycopg_operational_error_handler(request: Request, exc: psycopg.OperationalError):
    logger.error("Database operational error raised", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "DB_CONNECTION_ERROR",
            "detail": "Database connection failure."
        }
    )

@app.exception_handler(PoolClosed)
async def pool_closed_error_handler(request: Request, exc: PoolClosed):
    logger.error("Database connection pool closed error raised", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "DB_CONNECTION_ERROR",
            "detail": "Database connection pool is closed."
        }
    )

# CORS Security: Restricted strictly to frontend local development port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Include API endpoints
app.include_router(health_router, prefix="/api/v1")
