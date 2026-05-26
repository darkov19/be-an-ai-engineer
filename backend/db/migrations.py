import os
import glob
import structlog
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger()

async def run_migrations(pool: AsyncConnectionPool):
    logger.info("Running database migrations...")
    
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    if not os.path.exists(migrations_dir):
        logger.warning("Migrations directory not found", path=migrations_dir)
        return

    sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    logger.info(f"Found {len(sql_files)} migration files", files=[os.path.basename(f) for f in sql_files])

    async with pool.connection() as conn:
        # Create migrations table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)

        for sql_file in sql_files:
            filename = os.path.basename(sql_file)
            
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (filename,))
                exists = await cur.fetchone()
            
            if exists:
                logger.debug("Migration already applied", migration=filename)
                continue

            logger.info("Applying migration", migration=filename)
            with open(sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()

            try:
                async with conn.transaction():
                    async with conn.cursor() as cur:
                        await cur.execute(sql_content)
                        await cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (filename,))
                logger.info("Migration applied successfully", migration=filename)
            except Exception as e:
                logger.error("Failed to apply migration", migration=filename, error=str(e))
                raise e
