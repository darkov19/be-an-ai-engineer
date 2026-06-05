#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from psycopg_pool import AsyncConnectionPool
import structlog

# Add project root to sys.path to enable backend package imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.services.fingerprinter import generate_fingerprint_data, write_static_html

logger = structlog.get_logger()


async def precompute_company_fingerprint(pool: AsyncConnectionPool, company_slug: str) -> bool:
    if not re.fullmatch(r"[a-z0-9-]+", company_slug):
        raise ValueError("Invalid company slug format")

    data = await generate_fingerprint_data(pool, company_slug)
    write_static_html(company_slug, data)
    logger.info("Fingerprint precomputed successfully", slug=company_slug)
    return True


async def precompute_all_fingerprints(pool: AsyncConnectionPool) -> int:
    """
    Selects distinct companies from extracted jobs and job_sources, and precomputes
    their stack fingerprints.
    """
    # 1. Fetch unique companies from jobs
    companies_from_jobs = []
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT DISTINCT company FROM jobs WHERE extraction_status = 'extracted';"
                )
                rows = await cur.fetchall()
                companies_from_jobs = [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.error("Failed to query unique companies from jobs table", error=str(e))
        return 1

    # 2. Fetch slug mappings from job_sources
    slug_to_company = {}
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT slug, company FROM job_sources;")
                rows_sources = await cur.fetchall()
                slug_to_company = {r[0]: r[1] for r in rows_sources if r[0]}
    except Exception as e:
        logger.warning("Failed to query company slugs from job_sources table", error=str(e))

    # Build targets
    targets = []
    seen_slugs = set()

    for slug, comp in slug_to_company.items():
        if slug not in seen_slugs and re.match(r"^[a-z0-9\-]+$", slug):
            targets.append((slug, comp))
            seen_slugs.add(slug)

    for comp in companies_from_jobs:
        # Generate slugified key
        slug = comp.lower().strip()
        slug = re.sub(r"[^a-z0-9\-]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        if slug and slug not in seen_slugs and re.match(r"^[a-z0-9\-]+$", slug):
            targets.append((slug, comp))
            seen_slugs.add(slug)

    logger.info("Found candidate companies for fingerprint precomputation", count=len(targets), targets=[t[0] for t in targets])

    succeeded = 0
    skipped = 0
    failed = 0

    for slug, company in targets:
        try:
            logger.info("Generating fingerprint", company=company, slug=slug)
            await precompute_company_fingerprint(pool, slug)
            succeeded += 1
        except ValueError as ve:
            # Expected when the company variants have no extracted jobs in the database
            skipped += 1
            logger.info("Skipped fingerprint precomputation (no extracted jobs)", slug=slug, reason=str(ve))
        except Exception as e:
            failed += 1
            logger.error("Failed to generate fingerprint for company", slug=slug, error=str(e))

    logger.info(
        "Precomputation finished",
        total=len(targets),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed
    )
    return 1 if failed else 0

async def _main() -> int:
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        open=False,
        kwargs={"autocommit": True}
    )
    await pool.open()
    try:
        return await precompute_all_fingerprints(pool)
    finally:
        await pool.close()

if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
