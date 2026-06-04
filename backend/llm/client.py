from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog
from psycopg.rows import dict_row
from pydantic import ValidationError

from backend.config import settings
from backend.llm.hermes import (
    HermesProxyConnectionError,
    check_hermes_proxy_health,
)
from backend.llm.schemas import (
    EXTRACTION_SCHEMA_VERSION,
    ExtractionBatch,
    ExtractedJobSignal,
)


logger = structlog.get_logger()

DEFAULT_BATCH_SIZE = 20
PROMPT_VERSION = "extraction_v1"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extraction_v1.md"
DEFAULT_SUMMARY_DIR = Path(__file__).resolve().parents[2] / "_bmad-output" / "implementation-artifacts"
HIGH_YIELD_DISCOVERY_METHODS = ("hn_who_is_hiring", "vertex_ai_search", "common_crawl_ats")
CORPUS_SELECTION_NOTE = (
    "Initial extraction selects jobs by jobs.source_slug matched to ATS families from active, validated "
    "job_sources discovered by high-yield providers. jobs rows do not preserve job_sources.id or "
    "discovery_method, so exact per-row provider attribution remains a reporting limitation."
)


class ExtractionError(RuntimeError):
    """Base class for structured extraction failures."""


class ExtractionHTTPError(ExtractionError):
    """Raised when the Hermes extraction request fails at the HTTP layer."""


class ExtractionResponseError(ExtractionError):
    """Raised when Hermes returns malformed or unmappable extraction content."""


@dataclass(frozen=True)
class JobForExtraction:
    id: int
    url: str
    title: str
    company: str
    location: str | None
    raw_text: str
    source_slug: str


@dataclass
class ExtractionRunSummary:
    run_id: str
    selected: int = 0
    extracted: int = 0
    skipped: int = 0
    failed: int = 0
    retryable_errors: int = 0
    dry_run: bool = False
    prompt_version: str = PROMPT_VERSION
    schema_version: str = EXTRACTION_SCHEMA_VERSION
    elapsed_seconds: float = 0.0
    corpus_selection_note: str = CORPUS_SELECTION_NOTE
    summary_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def hermes_extract_url() -> str:
    return f"http://{settings.hermes_host}:{settings.hermes_port}/extract"


def redact_extraction_error(error: Exception | str, max_length: int = 240) -> str:
    text = (str(error) or error.__class__.__name__) if isinstance(error, Exception) else str(error)
    text = re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|client_secret|authorization|bearer|token)\s*[:=]\s*\S+",
        lambda match: f"{match.group(1)}=[redacted]",
        text,
    )
    text = re.sub(r"(?i)\b(secret|token)[-_][A-Za-z0-9._~+/=-]+\b", "[redacted]", text)
    text = re.sub(r"(?is)(prompt|raw_text|response_body)=.*?(?=\s\w+=|$)", r"\1=[redacted]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def load_extraction_prompt(prompt_path: Path = PROMPT_PATH) -> str:
    template = prompt_path.read_text(encoding="utf-8")
    schema_json = json.dumps(ExtractionBatch.model_json_schema(), indent=2, sort_keys=True)
    return template.replace("{json_schema}", schema_json)


def _job_payload(job: JobForExtraction) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "url": job.url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source_slug": job.source_slug,
        "raw_text": job.raw_text,
    }


async def select_unextracted_jobs(conn, limit: int = DEFAULT_BATCH_SIZE) -> list[JobForExtraction]:
    query = """
        SELECT id, url, title, company, location, raw_text, source_slug
        FROM jobs
        WHERE raw_text IS NOT NULL
          AND btrim(raw_text) <> ''
          AND extracted_at IS NULL
          AND extraction_status IN ('pending', 'retryable_error')
          AND source_slug IN (
              SELECT ats
              FROM job_sources
              WHERE active = TRUE
                AND validation_status = 'validated'
                AND discovery_method = ANY(%(discovery_methods)s)
          )
        ORDER BY created_at ASC, id ASC
        LIMIT %(limit)s
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            query,
            {
                "discovery_methods": list(HIGH_YIELD_DISCOVERY_METHODS),
                "limit": max(0, int(limit)),
            },
        )
        rows = await cur.fetchall()

    return [
        JobForExtraction(
            id=int(row["id"]),
            url=row["url"],
            title=row["title"],
            company=row["company"],
            location=row.get("location"),
            raw_text=row["raw_text"],
            source_slug=row["source_slug"],
        )
        for row in rows
    ]


async def _post_to_hermes(jobs: list[JobForExtraction], prompt: str) -> dict[str, Any]:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "prompt": prompt,
        "jobs": [_job_payload(job) for job in jobs],
    }
    url = hermes_extract_url()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            parsed = response.json()
    except httpx.HTTPStatusError as exc:
        safe_error = redact_extraction_error(exc)
        logger.error("Hermes extraction HTTP status failed", target_url=url, error=safe_error)
        raise ExtractionHTTPError(f"Hermes extraction HTTP status failed for {url}: {safe_error}") from exc
    except httpx.RequestError as exc:
        safe_error = redact_extraction_error(exc)
        logger.error("Hermes extraction request failed", target_url=url, error=safe_error)
        raise ExtractionHTTPError(f"Hermes extraction request failed for {url}: {safe_error}") from exc
    except ValueError as exc:
        logger.error("Hermes extraction response was not valid JSON", target_url=url)
        raise ExtractionResponseError(f"Hermes extraction response was not valid JSON for {url}") from exc

    if not isinstance(parsed, dict):
        raise ExtractionResponseError("Hermes extraction response must be a JSON object")
    return parsed


def _validate_response_items(
    payload: dict[str, Any],
    requested_ids: set[int],
) -> tuple[dict[int, ExtractedJobSignal], dict[int, str]]:
    extra_keys = set(payload) - {"items"}
    if extra_keys:
        raise ExtractionResponseError("Hermes extraction response included unexpected top-level keys")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ExtractionResponseError("Hermes extraction response must include an items array")

    valid_by_id: dict[int, ExtractedJobSignal] = {}
    item_errors: dict[int, str] = {}
    seen_ids: set[int] = set()

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ExtractionResponseError("Hermes extraction item must be an object")

        raw_job_id = raw_item.get("job_id")
        if not isinstance(raw_job_id, int) or isinstance(raw_job_id, bool):
            raise ExtractionResponseError("Hermes extraction item has malformed job_id")
        if raw_job_id not in requested_ids:
            raise ExtractionResponseError(f"Hermes returned unknown job_id {raw_job_id}")
        if raw_job_id in seen_ids:
            raise ExtractionResponseError(f"Hermes returned duplicate job_id {raw_job_id}")
        seen_ids.add(raw_job_id)

        try:
            valid_by_id[raw_job_id] = ExtractedJobSignal.model_validate(raw_item)
        except ValidationError as exc:
            item_errors[raw_job_id] = redact_extraction_error(exc)

    return valid_by_id, item_errors


async def _persist_results(
    conn,
    jobs: list[JobForExtraction],
    valid_by_id: dict[int, ExtractedJobSignal],
    item_errors: dict[int, str],
    run_id: str,
) -> dict[str, int]:
    counts = {"extracted": 0, "failed": 0, "retryable_errors": 0, "skipped": 0}
    requested_ids = {job.id for job in jobs}
    missing_ids = requested_ids - set(valid_by_id) - set(item_errors)

    async with conn.transaction():
        async with conn.cursor() as cur:
            for job_id, item in valid_by_id.items():
                await cur.execute(
                    """
                    UPDATE jobs
                    SET skills = %(skills)s::jsonb,
                        seniority = %(seniority)s,
                        tech_stack = %(tech_stack)s::jsonb,
                        salary_band = %(salary_band)s::jsonb,
                        remote_policy = %(remote_policy)s,
                        role_archetype = %(role_archetype)s,
                        extracted_at = CURRENT_TIMESTAMP,
                        prompt_version = %(prompt_version)s,
                        extraction_schema_version = %(schema_version)s,
                        extraction_status = 'extracted',
                        extraction_error = NULL,
                        extraction_run_id = %(run_id)s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %(job_id)s
                      AND extracted_at IS NULL
                    """,
                    {
                        "job_id": job_id,
                        "skills": json.dumps(item.skills),
                        "seniority": item.seniority,
                        "tech_stack": json.dumps(item.tech_stack),
                        "salary_band": item.salary_band.model_dump_json(),
                        "remote_policy": item.remote_policy,
                        "role_archetype": item.role_archetype,
                        "prompt_version": PROMPT_VERSION,
                        "schema_version": EXTRACTION_SCHEMA_VERSION,
                        "run_id": run_id,
                    },
                )
                if _cursor_rowcount(cur):
                    counts["extracted"] += 1
                else:
                    counts["skipped"] += 1

            for job_id, error in item_errors.items():
                if await _mark_job_error(cur, job_id, "failed", error, run_id):
                    counts["failed"] += 1
                else:
                    counts["skipped"] += 1

            for job_id in missing_ids:
                if await _mark_job_error(cur, job_id, "retryable_error", "missing extraction result", run_id):
                    counts["retryable_errors"] += 1
                else:
                    counts["skipped"] += 1

    return counts


async def _mark_batch_retryable(conn, jobs: list[JobForExtraction], error: Exception, run_id: str) -> None:
    safe_error = redact_extraction_error(error)
    async with conn.transaction():
        async with conn.cursor() as cur:
            for job in jobs:
                await _mark_job_error(cur, job.id, "retryable_error", safe_error, run_id)


async def _mark_job_error(cur, job_id: int, status: str, error: str, run_id: str) -> bool:
    await cur.execute(
        """
        UPDATE jobs
        SET extraction_status = %(status)s,
            extraction_error = %(error)s,
            extraction_run_id = %(run_id)s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %(job_id)s
          AND extracted_at IS NULL
        """,
        {
            "job_id": job_id,
            "status": status,
            "error": redact_extraction_error(error),
            "run_id": run_id,
        },
    )
    return _cursor_rowcount(cur)


def _cursor_rowcount(cur) -> bool:
    rowcount = getattr(cur, "rowcount", None)
    return rowcount is None or rowcount > 0


def _chunks(items: list[JobForExtraction], size: int) -> list[list[JobForExtraction]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def run_extraction_batch(
    pool,
    limit: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    run_id: str | None = None,
    summary_dir: Path | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    resolved_run_id = run_id or f"extraction-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    summary = ExtractionRunSummary(run_id=resolved_run_id, dry_run=dry_run)

    await check_hermes_proxy_health()
    prompt = load_extraction_prompt()

    async with pool.connection() as conn:
        selection_limit = batch_size if limit is None else limit
        jobs = await select_unextracted_jobs(conn, selection_limit)
        summary.selected = len(jobs)
        if dry_run:
            summary.skipped = len(jobs)
            summary.elapsed_seconds = round(time.perf_counter() - start, 3)
            return _maybe_write_summary(summary, summary_dir)

        for batch in _chunks(jobs, max(1, int(batch_size))):
            try:
                response_payload = await _post_to_hermes(batch, prompt)
                requested_ids = {job.id for job in batch}
                valid_by_id, item_errors = _validate_response_items(response_payload, requested_ids)
            except ExtractionHTTPError as exc:
                await _mark_batch_retryable(conn, batch, exc, resolved_run_id)
                summary.retryable_errors += len(batch)
                summary.elapsed_seconds = round(time.perf_counter() - start, 3)
                _maybe_write_summary(summary, summary_dir)
                raise
            except ExtractionResponseError as exc:
                await _mark_batch_retryable(conn, batch, exc, resolved_run_id)
                summary.retryable_errors += len(batch)
                summary.elapsed_seconds = round(time.perf_counter() - start, 3)
                _maybe_write_summary(summary, summary_dir)
                raise

            counts = await _persist_results(conn, batch, valid_by_id, item_errors, resolved_run_id)
            summary.extracted += counts["extracted"]
            summary.failed += counts["failed"]
            summary.retryable_errors += counts["retryable_errors"]
            summary.skipped += counts["skipped"]

    summary.elapsed_seconds = round(time.perf_counter() - start, 3)
    return _maybe_write_summary(summary, summary_dir)


def _maybe_write_summary(summary: ExtractionRunSummary, summary_dir: Path | None) -> dict[str, Any]:
    if summary_dir is None:
        return summary.to_dict()

    summary_dir.mkdir(parents=True, exist_ok=True)
    date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    path = summary_dir / f"extraction-run-{date_part}.json"
    data = summary.to_dict()
    data["summary_path"] = str(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return data
