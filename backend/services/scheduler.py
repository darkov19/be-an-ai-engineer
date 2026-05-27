import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from backend.config import settings
from backend.services.parser import run_full_ingestion
from backend.utils.email import send_email

logger = structlog.get_logger()

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_ist_zone() -> ZoneInfo:
    return ZoneInfo("Asia/Kolkata")


def _kill_criterion_payload(run_date: date, summary: dict[str, Any], corpus_size: int) -> dict[str, Any]:
    return {
        "run_date": run_date.isoformat(),
        "week": run_date.isocalendar().week,
        "status": summary.get("status"),
        "corpus_size": corpus_size,
        "source_counts": summary.get("source_counts", {}),
        "error_message": summary.get("error_message"),
        "execution_time_seconds": summary.get("execution_time_seconds"),
    }


def _render_kill_email_html(payload: dict[str, Any]) -> str:
    csv_template = "url,title,company,location,raw_text,source_slug\nhttps://example.com,AI Engineer,Acme,Remote,Sample text,yc_waas"
    return (
        "<h2>Kill criterion triggered</h2>"
        f"<p>Run date: {payload['run_date']}</p>"
        f"<p>Corpus size: {payload['corpus_size']}</p>"
        f"<p>Status: {payload['status']}</p>"
        f"<p>Error: {payload['error_message'] or 'none'}</p>"
        "<h3>Manual CSV pivot template</h3>"
        f"<pre>{csv_template}</pre>"
    )


def _render_weekly_nudge_html(run_date: date, corpus_size: int, source_counts: dict[str, Any]) -> str:
    return (
        "<h2>Weekly report summary</h2>"
        f"<p>Run date: {run_date.isoformat()}</p>"
        f"<p>Corpus size: {corpus_size}</p>"
        f"<p>Per-source counts: {json.dumps(source_counts)}</p>"
    )


def _two_recent_saturdays(run_date: date) -> list[date]:
    return [run_date - timedelta(days=7), run_date]


async def _send_kill_email(payload: dict[str, Any]) -> None:
    try:
        send_email(
            to=settings.alert_recipient_email,
            from_email="onboarding@resend.dev",
            subject="▲ [KILL CRITERION TRIGGERED] Ingestion corpus below minimum quality thresholds. Dashboard locked.",
            html=_render_kill_email_html(payload),
        )
    except Exception as exc:
        logger.warning("Failed to send kill-criterion email", error=str(exc))


async def _enqueue_kill_notification(pool, run_date: date, payload: dict[str, Any], delay_seconds: int = 60) -> None:
    due_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO notification_outbox (kind, run_date, payload, due_at)
            VALUES (%s, %s, %s::jsonb, %s)
            ON CONFLICT (kind, run_date) DO NOTHING
            """,
            ("kill_criterion", run_date, json.dumps(payload), due_at),
        )


async def dispatch_due_kill_notifications(app: FastAPI) -> None:
    if not hasattr(app.state, "pool") or app.state.pool is None:
        return

    pool = app.state.pool
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, payload
                    FROM notification_outbox
                    WHERE kind = 'kill_criterion'
                      AND sent_at IS NULL
                      AND due_at <= CURRENT_TIMESTAMP
                    ORDER BY due_at ASC
                    LIMIT 50
                    FOR UPDATE SKIP LOCKED
                    """
                )
                rows = await cur.fetchall()

                for row in rows:
                    notification_id = row[0]
                    payload = row[1]
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    try:
                        await _send_kill_email(payload)
                        await cur.execute(
                            """
                            UPDATE notification_outbox
                            SET sent_at = CURRENT_TIMESTAMP,
                                attempts = attempts + 1,
                                last_error = NULL
                            WHERE id = %s
                            """,
                            (notification_id,),
                        )
                    except Exception as exc:
                        await cur.execute(
                            """
                            UPDATE notification_outbox
                            SET attempts = attempts + 1,
                                last_error = %s
                            WHERE id = %s
                            """,
                            (str(exc), notification_id),
                        )


async def _record_weekly_report(conn, run_date: date, corpus_size: int, source_counts: dict[str, Any], report_html: str) -> None:
    await conn.execute(
        """
        INSERT INTO weekly_reports (run_date, corpus_size, per_source_counts, report_html)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (run_date) DO UPDATE
        SET corpus_size = EXCLUDED.corpus_size,
            per_source_counts = EXCLUDED.per_source_counts,
            report_html = EXCLUDED.report_html,
            accessed_at = CURRENT_TIMESTAMP
        """,
        (run_date, corpus_size, json.dumps(source_counts), report_html),
    )


async def _count_corpus_size(conn) -> int:
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM jobs")
        result = await cur.fetchone()
        return int(result[0] if result else 0)


async def _missed_two_saturdays(conn, run_date: date) -> bool:
    saturdays = _two_recent_saturdays(run_date)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) FROM cockpit_access_logs
            WHERE (accessed_at AT TIME ZONE 'Asia/Kolkata')::date = ANY(%s)
            """,
            (saturdays,),
        )
        result = await cur.fetchone()
        return int(result[0] if result else 0) == 0


async def run_weekly_ingestion(app: FastAPI) -> None:
    if not hasattr(app.state, "pool") or app.state.pool is None:
        logger.warning("Weekly ingestion skipped; database pool unavailable")
        return

    pool = app.state.pool
    ist_now = datetime.now(get_ist_zone())
    run_date = ist_now.date()

    summary: dict[str, Any] = {"status": "failure", "source_counts": {}, "error_message": None}
    source_counts: dict[str, Any] = {}
    corpus_size = 0
    missed_two_saturdays = False
    fatal_error: Exception | None = None

    try:
        summary = await run_full_ingestion(pool, config=None)
        source_counts = summary.get("source_counts", {})

        async with pool.connection() as conn:
            corpus_size = await _count_corpus_size(conn)
            report_html = _render_weekly_nudge_html(run_date, corpus_size, source_counts)
            await _record_weekly_report(conn, run_date, corpus_size, source_counts, report_html)
            missed_two_saturdays = await _missed_two_saturdays(conn, run_date)
    except Exception as exc:
        fatal_error = exc
        logger.error("Weekly ingestion execution failed", error=str(exc))
        summary = {
            "status": "failure",
            "source_counts": source_counts,
            "error_message": str(exc),
        }

    kill_fired = summary.get("status") != "success" or corpus_size < 100 or fatal_error is not None
    if kill_fired:
        payload = _kill_criterion_payload(run_date, summary, corpus_size)
        week_no = run_date.isocalendar().week
        artifact_path = _workspace_root() / f"kill-criterion-fired-{run_date.year}-{week_no:02d}.json"
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Dispatch asynchronously after a short delay to satisfy delayed handoff behavior.
        try:
            await _enqueue_kill_notification(pool, run_date, payload, delay_seconds=60)
        except Exception as exc:
            logger.error("Failed to persist kill notification", error=str(exc))
            await _send_kill_email(payload)

    if missed_two_saturdays:
        try:
            send_email(
                to=settings.alert_recipient_email,
                from_email="onboarding@resend.dev",
                subject="Two Saturdays missed — here's your report.",
                html=_render_weekly_nudge_html(run_date, corpus_size, source_counts),
            )
        except Exception as exc:
            logger.warning("Failed to send missed-saturday nudge email", error=str(exc))


async def initialize_scheduler(app: FastAPI) -> AsyncScheduler | None:
    scheduler: AsyncScheduler | None = None
    try:
        scheduler = AsyncScheduler()
        scheduler = await scheduler.__aenter__()
        app.state.scheduler = scheduler
        trigger = CronTrigger(day_of_week="sat", hour=8, minute=0, timezone=get_ist_zone())

        await scheduler.add_schedule(
            run_weekly_ingestion,
            trigger,
            args=(app,),
            id="weekly-ingestion-saturday-0800-ist",
            misfire_grace_time=3600,
        )
        await scheduler.add_schedule(
            dispatch_due_kill_notifications,
            IntervalTrigger(minutes=1),
            args=(app,),
            id="kill-notification-dispatcher",
            misfire_grace_time=300,
        )
        await scheduler.start_in_background()
        asyncio.create_task(dispatch_due_kill_notifications(app))
        return scheduler
    except Exception as exc:
        logger.error("Failed to initialize APScheduler", error=str(exc))
        if scheduler is not None:
            try:
                await scheduler.__aexit__(type(exc), exc, exc.__traceback__)
            except Exception as close_exc:
                logger.warning("Failed to cleanup scheduler after init failure", error=str(close_exc))
        return None


async def shutdown_scheduler(app: FastAPI) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return
    try:
        await scheduler.__aexit__(None, None, None)
    except Exception as exc:
        logger.warning("Failed to stop scheduler cleanly", error=str(exc))
