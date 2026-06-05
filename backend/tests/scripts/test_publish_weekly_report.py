from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scripts import publish_weekly_report


class MockConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.mark.asyncio
async def test_publish_latest_weekly_report_writes_assets_and_updates_paths(tmp_path: Path):
    conn = MagicMock()
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.connection.return_value = MockConnectionContext(conn)
    snapshot = {
        "run_date": date(2026, 6, 6),
        "report_slug": "2026-W23",
        "corpus_size": 100,
        "per_source_counts": {},
        "eval_accuracy": 0.8,
        "geo_us_eu": {"top_skills": []},
        "geo_india": {"top_skills": []},
    }

    with (
        patch.object(publish_weekly_report, "_connect_pool", return_value=pool),
        patch.object(publish_weekly_report.report_publisher, "load_latest_weekly_report_snapshot", AsyncMock(return_value=snapshot)),
        patch.object(publish_weekly_report.report_publisher, "load_archive_rows", AsyncMock(return_value=[snapshot])),
        patch.object(publish_weekly_report.report_publisher, "write_report_assets") as mock_write_assets,
    ):
        mock_write_assets.return_value = {
            "report_html": tmp_path / "reports" / "2026-W23" / "index.html",
            "og_image": tmp_path / "reports" / "2026-W23" / "og.png",
            "archive_html": tmp_path / "archive" / "index.html",
        }

        result = await publish_weekly_report.publish_weekly_report(output_root=tmp_path)

    assert result["slug"] == "2026-W23"
    assert result["report_path"] == "/reports/2026-W23/index.html"
    assert result["og_image_path"] == "/reports/2026-W23/og.png"
    assert any("UPDATE weekly_reports" in call.args[0] for call in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_publish_weekly_report_can_select_explicit_run_date(tmp_path: Path):
    conn = MagicMock()
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.connection.return_value = MockConnectionContext(conn)

    with (
        patch.object(publish_weekly_report, "_connect_pool", return_value=pool),
        patch.object(publish_weekly_report.report_publisher, "load_weekly_report_snapshot", AsyncMock(return_value={"run_date": date(2026, 6, 6), "report_slug": "2026-W23"})) as mock_load,
        patch.object(publish_weekly_report.report_publisher, "load_archive_rows", AsyncMock(return_value=[])),
        patch.object(publish_weekly_report.report_publisher, "write_report_assets", return_value={"report_html": tmp_path / "reports/2026-W23/index.html", "og_image": tmp_path / "reports/2026-W23/og.png"}),
    ):
        await publish_weekly_report.publish_weekly_report(run_date=date(2026, 6, 6), output_root=tmp_path)

    mock_load.assert_awaited_once()
