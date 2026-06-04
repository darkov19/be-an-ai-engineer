#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.llm.client import DEFAULT_BATCH_SIZE, DEFAULT_SUMMARY_DIR, ExtractionError, run_extraction_batch
from backend.llm.hermes import HermesProxyError


async def run_extraction_for_pool(
    pool,
    limit: int | None,
    batch_size: int,
    dry_run: bool,
    summary_dir: Path = DEFAULT_SUMMARY_DIR,
) -> dict:
    summary = await run_extraction_batch(
        pool,
        limit=limit,
        batch_size=batch_size,
        dry_run=dry_run,
        summary_dir=summary_dir,
    )
    if summary.get("summary_path"):
        return summary

    summary_dir.mkdir(parents=True, exist_ok=True)
    path = summary_dir / f"extraction-run-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}.json"
    summary = {**summary, "summary_path": str(path)}
    path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return summary


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run structured job extraction through the local Hermes proxy.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum jobs to select for this run.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Jobs per Hermes request.")
    parser.add_argument("--dry-run", action="store_true", help="Verify health and selection without posting to Hermes.")
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=DEFAULT_SUMMARY_DIR,
        help="Directory for extraction-run summary artifacts.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    pool = AsyncConnectionPool(conninfo=settings.database_url, open=False)
    await pool.open()
    try:
        summary = await run_extraction_for_pool(
            pool,
            limit=args.limit,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            summary_dir=args.summary_dir,
        )
    except (HermesProxyError, ExtractionError) as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        await pool.close()

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    else:
        print("Extraction run summary")
        print(f"run_id: {summary['run_id']}")
        print(f"selected: {summary['selected']}")
        print(f"extracted: {summary['extracted']}")
        print(f"skipped: {summary['skipped']}")
        print(f"failed: {summary['failed']}")
        print(f"retryable_errors: {summary['retryable_errors']}")
        print(f"prompt_version: {summary['prompt_version']}")
        print(f"schema_version: {summary['schema_version']}")
        print(f"elapsed_seconds: {summary['elapsed_seconds']}")
        print(f"summary_path: {summary.get('summary_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
