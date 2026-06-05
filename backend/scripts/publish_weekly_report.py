import argparse
import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import structlog
from psycopg_pool import AsyncConnectionPool

from backend.config import settings
from backend.services import report_publisher

logger = structlog.get_logger()


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_output_root() -> Path:
    return _workspace_root() / "frontend" / "public"


def _connect_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=settings.database_url, open=False)


def _public_path(path: Path, output_root: Path) -> str:
    return f"/{path.relative_to(output_root).as_posix()}"


async def publish_weekly_report(
    run_date: date | None = None,
    output_root: Path | None = None,
    deployment_url: str | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    pool = _connect_pool()
    output = output_root or _default_output_root()
    async with pool:
        async with pool.connection() as conn:
            if run_date is None:
                snapshot = await report_publisher.load_latest_weekly_report_snapshot(conn)
            else:
                snapshot = await report_publisher.load_weekly_report_snapshot(conn, run_date)
            if deployment_url:
                snapshot["deployment_url"] = deployment_url
            if commit_sha:
                snapshot["commit_sha"] = commit_sha
            archive_rows = await report_publisher.load_archive_rows(conn)
            archive_rows = [
                {**row, "deployment_url": deployment_url or row.get("deployment_url"), "commit_sha": commit_sha or row.get("commit_sha")}
                if row.get("run_date") == snapshot.get("run_date") else row
                for row in archive_rows
            ]
            paths = report_publisher.write_report_assets(snapshot, output, archive_rows=archive_rows)

            report_rel = _public_path(paths["report_html"], output)
            og_rel = _public_path(paths["og_image"], output)
            await conn.execute(
                """
                UPDATE weekly_reports
                SET report_slug = %s,
                    report_path = %s,
                    og_image_path = %s,
                    deployment_url = COALESCE(%s, deployment_url),
                    commit_sha = COALESCE(%s, commit_sha),
                    published_at = CURRENT_TIMESTAMP
                WHERE run_date = %s
                """,
                (snapshot["report_slug"], report_rel, og_rel, deployment_url, commit_sha, snapshot["run_date"]),
            )

    result = {"slug": snapshot["report_slug"], "report_path": report_rel, "og_image_path": og_rel}
    logger.info("Published weekly report static assets", **result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish persisted weekly report static assets.")
    parser.add_argument("--date", dest="run_date", help="Run date to publish in YYYY-MM-DD format. Defaults to latest report.")
    parser.add_argument("--output-root", type=Path, default=None, help="Static output root. Defaults to frontend/public.")
    parser.add_argument("--deployment-url", default=None, help="Deployment URL to record on the report row.")
    parser.add_argument("--commit-sha", default=os.getenv("GITHUB_SHA"), help="Commit SHA to record on the report row.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    selected_date = date.fromisoformat(args.run_date) if args.run_date else None
    result = asyncio.run(
        publish_weekly_report(
            run_date=selected_date,
            output_root=args.output_root,
            deployment_url=args.deployment_url,
            commit_sha=args.commit_sha,
        )
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
