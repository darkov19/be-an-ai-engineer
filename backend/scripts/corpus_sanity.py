#!/usr/bin/env python3
import argparse
import asyncio
import json
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from backend.config import settings


async def collect_corpus_sanity(pool: AsyncConnectionPool) -> dict[str, Any]:
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT COUNT(*) AS total_jobs FROM jobs")
            total_jobs = int((await cur.fetchone())["total_jobs"])

            await cur.execute(
                """
                SELECT source_slug, COUNT(*) AS count
                FROM jobs
                GROUP BY source_slug
                ORDER BY source_slug
                """
            )
            per_source_counts = {
                row["source_slug"]: int(row["count"])
                for row in await cur.fetchall()
            }

            await cur.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM jobs
                GROUP BY status
                ORDER BY status
                """
            )
            status_counts = {
                row["status"]: int(row["count"])
                for row in await cur.fetchall()
            }

            await cur.execute(
                """
                SELECT COUNT(*) AS empty_raw_text_jobs
                FROM jobs
                WHERE raw_text IS NULL OR btrim(raw_text) = ''
                """
            )
            empty_raw_text_jobs = int((await cur.fetchone())["empty_raw_text_jobs"])

            await cur.execute(
                """
                SELECT COUNT(*) AS duplicate_url_rows
                FROM (
                    SELECT url
                    FROM jobs
                    GROUP BY url
                    HAVING COUNT(*) > 1
                ) duplicates
                """
            )
            duplicate_url_rows = int((await cur.fetchone())["duplicate_url_rows"])

            await cur.execute(
                """
                SELECT id, status, source_counts, error_message, execution_time_seconds, run_timestamp
                FROM ingestion_runs
                ORDER BY run_timestamp DESC, id DESC
                LIMIT 1
                """
            )
            latest_run = await cur.fetchone()

            await cur.execute(
                """
                SELECT
                    COUNT(*) AS total_runs,
                    COUNT(*) FILTER (WHERE status = 'failure') AS failed_runs,
                    COUNT(*) FILTER (WHERE error_message IS NOT NULL AND error_message <> '') AS runs_with_errors
                FROM ingestion_runs
                """
            )
            run_stats = await cur.fetchone()

    total_runs = int(run_stats["total_runs"])
    failed_runs = int(run_stats["failed_runs"])
    runs_with_errors = int(run_stats["runs_with_errors"])
    latest_source_counts = latest_run["source_counts"] if latest_run else {}
    if isinstance(latest_source_counts, str):
        latest_source_counts = json.loads(latest_source_counts)

    return {
        "total_jobs": total_jobs,
        "per_source_counts": per_source_counts,
        "status_counts": status_counts,
        "empty_raw_text_jobs": empty_raw_text_jobs,
        "duplicate_url_rows": duplicate_url_rows,
        "latest_ingestion_run": dict(latest_run) if latest_run else None,
        "latest_attempted_source_counts": latest_source_counts,
        "run_failure_rate": failed_runs / total_runs if total_runs else 0.0,
        "run_error_rate": runs_with_errors / total_runs if total_runs else 0.0,
        "duplicate_skip_note": (
            "Historical duplicate skips are exact for CSV endpoint responses, but remote parser duplicate "
            "skips were not persisted before this diagnostic. duplicate_url_rows verifies the jobs table "
            "contains no duplicate URLs."
        ),
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Report corpus readiness before Epic 3 extraction.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    pool = AsyncConnectionPool(conninfo=settings.database_url, open=False)
    await pool.open()
    try:
        report = await collect_corpus_sanity(pool)
    finally:
        await pool.close()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("Corpus sanity report")
        print(f"total_jobs: {report['total_jobs']}")
        print(f"per_source_counts: {json.dumps(report['per_source_counts'], sort_keys=True)}")
        print(f"status_counts: {json.dumps(report['status_counts'], sort_keys=True)}")
        print(f"empty_raw_text_jobs: {report['empty_raw_text_jobs']}")
        print(f"duplicate_url_rows: {report['duplicate_url_rows']}")
        print(f"run_failure_rate: {report['run_failure_rate']:.3f}")
        print(f"run_error_rate: {report['run_error_rate']:.3f}")
        print(f"duplicate_skip_note: {report['duplicate_skip_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

