import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import scheduler as scheduler_service


class MockScheduler:
    def __init__(self):
        self.add_schedule = AsyncMock()
        self.start_in_background = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class MockPoolConnectionCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_initialize_scheduler_registers_weekly_trigger():
    app = SimpleNamespace(state=SimpleNamespace())
    mock_scheduler = MockScheduler()

    with (
        patch.object(scheduler_service, "AsyncScheduler", return_value=mock_scheduler),
        patch.object(
            scheduler_service.asyncio,
            "create_task",
            side_effect=lambda coro: (coro.close(), MagicMock())[1],
        ),
    ):
        result = await scheduler_service.initialize_scheduler(app)

    assert result is mock_scheduler
    assert mock_scheduler.__aenter__.await_count == 1
    assert mock_scheduler.start_in_background.await_count == 1
    assert mock_scheduler.add_schedule.await_count == 2
    first_kwargs = mock_scheduler.add_schedule.await_args_list[0].kwargs
    second_kwargs = mock_scheduler.add_schedule.await_args_list[1].kwargs
    assert first_kwargs["id"] == "weekly-ingestion-saturday-0800-ist"
    assert first_kwargs["misfire_grace_time"] == 3600
    assert second_kwargs["id"] == "kill-notification-dispatcher"


@pytest.mark.asyncio
async def test_run_weekly_ingestion_triggers_kill_and_nudge(tmp_path: Path):
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(50,), (0.85,), (0,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "failure", "source_counts": {"hn": 5}, "error_message": "boom"})),
        patch.object(scheduler_service, "send_email", MagicMock()),
        patch.object(scheduler_service, "_workspace_root", return_value=tmp_path),
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

        artifact = tmp_path / "kill-criterion-fired-2026-22.json"
        assert artifact.exists()
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        assert payload["corpus_size"] == 50
        assert scheduler_service.send_email.call_count == 1
        assert any(
            "notification_outbox" in (call.args[0] if call.args else "")
            for call in mock_conn.execute.await_args_list
        )


@pytest.mark.asyncio
async def test_run_weekly_ingestion_skips_notifications_when_healthy():
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(150,), (0.9,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "send_email", MagicMock()),
        patch.object(scheduler_service, "_publish_weekly_static_assets", AsyncMock()),
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)
        scheduler_service.send_email.assert_not_called()


@pytest.mark.asyncio
async def test_run_weekly_ingestion_kills_when_both_thresholds_breached(tmp_path: Path):
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(50,), (0.65,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "_workspace_root", return_value=tmp_path),
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

    artifact = tmp_path / "kill-criterion-fired-2026-22.json"
    assert artifact.exists()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["corpus_size"] == 50
    assert payload["eval_accuracy"] == 0.65
    assert any(
        "notification_outbox" in (call.args[0] if call.args else "")
        for call in mock_conn.execute.await_args_list
    )
    assert not any(
        "INSERT INTO weekly_reports" in (call.args[0] if call.args else "")
        for call in mock_conn.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_run_weekly_ingestion_warning_writes_summary_without_notification(tmp_path: Path):
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(50,), (0.85,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "_workspace_root", return_value=tmp_path),
        patch.object(scheduler_service, "_publish_weekly_static_assets", AsyncMock()),
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

    summary = tmp_path / "run-summary-2026-22.json"
    assert summary.exists()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["status"] == "warning"
    assert payload["corpus_size"] == 50
    assert payload["eval_accuracy"] == 0.85
    assert any(
        "INSERT INTO weekly_reports" in (call.args[0] if call.args else "")
        for call in mock_conn.execute.await_args_list
    )
    assert not any(
        "notification_outbox" in (call.args[0] if call.args else "")
        for call in mock_conn.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_run_weekly_ingestion_publishes_static_assets_for_nominal_run():
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(150,), (0.9,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "_publish_weekly_static_assets", AsyncMock()) as mock_publish,
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

    mock_publish.assert_awaited_once_with(mock_conn, run_date)


@pytest.mark.asyncio
async def test_run_weekly_ingestion_publishes_static_assets_for_warning_run(tmp_path: Path):
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(50,), (0.85,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "_workspace_root", return_value=tmp_path),
        patch.object(scheduler_service, "_publish_weekly_static_assets", AsyncMock()) as mock_publish,
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

    mock_publish.assert_awaited_once_with(mock_conn, run_date)


@pytest.mark.asyncio
async def test_run_weekly_ingestion_does_not_publish_static_assets_for_locked_run(tmp_path: Path):
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(50,), (0.65,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "_workspace_root", return_value=tmp_path),
        patch.object(scheduler_service, "_publish_weekly_static_assets", AsyncMock()) as mock_publish,
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

    mock_publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_weekly_ingestion_enqueues_notification_when_artifact_write_fails():
    run_date = date(2026, 5, 30)
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(side_effect=[(50,), (0.65,), (1,)])
    mock_cursor.__aenter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    class FailingArtifactPath:
        def __truediv__(self, _name):
            return self

        def write_text(self, *_args, **_kwargs):
            raise OSError("artifact directory unavailable")

        def __str__(self):
            return "/tmp/unavailable/kill-criterion-fired-2026-22.json"

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(return_value={"status": "success", "source_counts": {"hn": 5}})),
        patch.object(scheduler_service, "_workspace_root", return_value=FailingArtifactPath()),
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

    assert any(
        "notification_outbox" in (call.args[0] if call.args else "")
        for call in mock_conn.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_run_weekly_ingestion_still_emits_kill_artifact_on_ingestion_exception(tmp_path: Path):
    run_date = date(2026, 5, 30)
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with (
        patch.object(scheduler_service, "run_full_ingestion", AsyncMock(side_effect=RuntimeError("ingestion exploded"))),
        patch.object(scheduler_service, "_workspace_root", return_value=tmp_path),
        patch.object(scheduler_service, "datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value = MagicMock(date=lambda: run_date)
        await scheduler_service.run_weekly_ingestion(app)

        artifact = tmp_path / "kill-criterion-fired-2026-22.json"
        assert artifact.exists()
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        assert payload["status"] == "failure"
        assert "ingestion exploded" in (payload["error_message"] or "")
        assert any(
            "notification_outbox" in (call.args[0] if call.args else "")
            for call in mock_conn.execute.await_args_list
        )


@pytest.mark.asyncio
async def test_send_kill_email_swallows_email_errors():
    with patch.object(scheduler_service, "send_email", MagicMock(side_effect=RuntimeError("email failed"))):
        await scheduler_service._send_kill_email(
            {"run_date": "2026-05-30", "corpus_size": 1, "status": "failure", "error_message": "boom"}
        )


@pytest.mark.asyncio
async def test_dispatch_due_kill_notifications_marks_sent():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(
        return_value=[(1, {"run_date": "2026-05-30", "corpus_size": 50, "status": "failure", "error_message": None})]
    )
    mock_cursor.__aenter__.return_value = mock_cursor

    class TxCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.transaction.return_value = TxCtx()
    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockPoolConnectionCtx(mock_conn)
    app = SimpleNamespace(state=SimpleNamespace(pool=mock_pool))

    with patch.object(scheduler_service, "send_email", MagicMock()) as mock_send_email:
        await scheduler_service.dispatch_due_kill_notifications(app)

    assert mock_send_email.call_count == 1
    assert any(
        "UPDATE notification_outbox" in (call.args[0] if call.args else "")
        for call in mock_cursor.execute.await_args_list
    )
