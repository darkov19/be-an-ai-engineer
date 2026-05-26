from fastapi import Request
from psycopg_pool import AsyncConnectionPool
import structlog

logger = structlog.get_logger()

async def get_db(request: Request):
    """
    Dependency injection for checking out a database connection from the application state pool.
    """
    if not hasattr(request.app.state, "pool") or request.app.state.pool is None:
        logger.error("Database connection pool not found in app state")
        raise RuntimeError("Database pool not initialized")
    
    async with request.app.state.pool.connection() as conn:
        yield conn
