import asyncio
import structlog
from psycopg_pool import AsyncConnectionPool
from backend.config import settings
from backend.services.parser import run_full_ingestion

logger = structlog.get_logger()

async def main():
    logger.info("Starting diagnostic ingestion run...")
    
    # Initialize connection pool
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        open=False,
    )
    
    try:
        await pool.open()
        
        # Test configuration for diagnostic script
        config = {
            "greenhouse": ["stripe"],
            "lever": ["lever"],
            "ashby": [],
            "workable": [],
            "recruitee": [],
            "personio": []
        }
        
        results = await run_full_ingestion(pool, config)
        logger.info("Diagnostic ingestion run completed", results=results)
        
    except Exception as e:
        logger.error("Diagnostic ingestion run failed", error=str(e))
        raise e
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
