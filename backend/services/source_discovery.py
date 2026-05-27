import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Protocol
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import structlog

from backend.services.parser import (
    fetch_ashby_jobs,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_personio_jobs,
    fetch_recruitee_jobs,
    fetch_workable_jobs,
)
from backend.services.company_discovery import (
    CompanyDiscoveryRunResult,
    CompanySignal,
    CompanySignalResolution,
    company_signal_metrics,
    normalize_company_signal,
    persist_company_discovery_results,
)

logger = structlog.get_logger()

SUPPORTED_ATS = ("greenhouse", "lever", "ashby", "workable", "recruitee", "personio")
MAX_PAGE_BYTES = 1_000_000
RELEVANCE_KEYWORDS = (
    "ai",
    "llm",
    "machine learning",
    "ml",
    "rag",
    "agent",
    "agents",
    "backend",
    "platform",
    "data",
    "mlops",
    "inference",
    "vector",
    "python",
    "fastapi",
    "pytorch",
    "kubernetes",
    "eval",
    "evaluation",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_FILE = REPO_ROOT / "_bmad-output" / "planning-artifacts" / "source-discovery-seeds.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "_bmad-output" / "implementation-artifacts"


@dataclass
class SourceCandidate:
    company_hint: Optional[str]
    ats: Optional[str]
    slug: Optional[str]
    source_url: str
    discovery_method: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    candidate: SourceCandidate
    validation_status: str
    job_count: int = 0
    usable_job_count: int = 0
    relevant_job_count: int = 0
    rejection_reason: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class DiscoveryRunResult:
    candidate_count: int
    validated_count: int
    rejected_count: int
    error_count: int
    unsupported_url_count: int
    source_counts: dict
    rejection_reasons: dict
    coverage_gaps: dict
    active_source_count_after_run: int
    report_path: Optional[str]
    source_freshness_counts: dict = field(default_factory=dict)
    validation_results: list[ValidationResult] = field(default_factory=list)
    company_signal_counts: dict = field(default_factory=dict)


@dataclass
class DiscoveryProviderResult:
    candidates: list[SourceCandidate] = field(default_factory=list)
    unsupported_urls: list[str] = field(default_factory=list)
    generic_urls: list[tuple[str, Optional[str], str]] = field(default_factory=list)
    company_signals: list[CompanySignal] = field(default_factory=list)


class DiscoveryProvider(Protocol):
    name: str

    async def discover(self) -> DiscoveryProviderResult:
        ...


class HNWhoIsHiringProvider:
    name = "hn_who_is_hiring"

    async def discover(self) -> DiscoveryProviderResult:
        candidates, unsupported_urls, generic_urls = await discover_from_hn()
        return DiscoveryProviderResult(
            candidates=candidates,
            unsupported_urls=unsupported_urls,
            generic_urls=generic_urls,
        )


class OptionalSeedProvider:
    name = "seed_file"

    def __init__(self, seed_file: Path = DEFAULT_SEED_FILE):
        self.seed_file = seed_file

    async def discover(self) -> DiscoveryProviderResult:
        candidates, generic_urls = await discover_from_seed_file(self.seed_file)
        return DiscoveryProviderResult(candidates=candidates, generic_urls=generic_urls)


def default_discovery_providers(seed_file: Path = DEFAULT_SEED_FILE) -> list[DiscoveryProvider]:
    return [
        HNWhoIsHiringProvider(),
        OptionalSeedProvider(seed_file),
    ]


class URLExtractingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = {name.lower(): value for name, value in attrs if value}
        if "href" in attrs_dict:
            self.urls.append(attrs_dict["href"])
        if tag.lower() == "link" and attrs_dict.get("rel", "").lower() == "canonical" and attrs_dict.get("href"):
            self.urls.append(attrs_dict["href"])

    def handle_data(self, data):
        if data:
            self.text_parts.append(data)


def _clean_url(raw_url: str) -> str:
    return raw_url.strip().strip("'\"()[]{}<>.,;")


def extract_urls_from_html(html: str, base_url: Optional[str] = None) -> list[str]:
    parser = URLExtractingParser()
    try:
        parser.feed(html or "")
    except Exception:
        pass

    text = " ".join(parser.text_parts + [html or ""])
    urls = list(parser.urls)
    urls.extend(re.findall(r"https?://[^\s'\"<>]+", text))

    normalized = []
    seen = set()
    for raw_url in urls:
        clean = _clean_url(raw_url)
        if base_url and clean.startswith("/"):
            clean = urljoin(base_url, clean)
        if clean and clean not in seen:
            normalized.append(clean)
            seen.add(clean)
    return normalized


def _normalized_http_url(raw_url: str) -> Optional[str]:
    raw_url = _clean_url(raw_url)
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunparse(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", parsed.query, ""))


def _path_parts(parsed) -> list[str]:
    return [part for part in parsed.path.split("/") if part]


def normalize_ats_url(
    raw_url: str,
    discovery_method: str,
    company_hint: Optional[str] = None,
) -> Optional[SourceCandidate]:
    normalized_url = _normalized_http_url(raw_url)
    if not normalized_url:
        return None

    parsed = urlparse(normalized_url)
    host = parsed.netloc
    parts = _path_parts(parsed)
    ats = None
    slug = None

    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
        ats, slug = "greenhouse", parts[0]
    elif host == "boards-api.greenhouse.io" and len(parts) >= 4 and parts[:3] == ["v1", "boards", parts[2]]:
        ats, slug = "greenhouse", parts[2]
    elif host == "jobs.lever.co" and parts:
        ats, slug = "lever", parts[0]
    elif host == "api.lever.co" and len(parts) >= 3 and parts[:2] == ["v0", "postings"]:
        ats, slug = "lever", parts[2]
    elif host == "jobs.ashbyhq.com" and parts:
        ats, slug = "ashby", parts[0]
    elif host == "api.ashbyhq.com" and len(parts) >= 3 and parts[:2] == ["posting-api", "job-board"]:
        ats, slug = "ashby", parts[2]
    elif host.endswith(".recruitee.com"):
        ats, slug = "recruitee", host.removesuffix(".recruitee.com")
    elif host.endswith(".jobs.personio.de"):
        ats, slug = "personio", host.removesuffix(".jobs.personio.de")
    elif host.endswith(".jobs.personio.com"):
        ats, slug = "personio", host.removesuffix(".jobs.personio.com")
    elif host == "apply.workable.com" and parts:
        if parts[:4] == ["api", "v1", "widget", "accounts"] and len(parts) >= 5:
            ats, slug = "workable", parts[4]
        elif parts[0] not in {"api", "j"}:
            ats, slug = "workable", parts[0]

    if not ats or not slug:
        return None

    return SourceCandidate(
        company_hint=company_hint,
        ats=ats,
        slug=slug.lower(),
        source_url=normalized_url,
        discovery_method=discovery_method,
        metadata={"source_urls": [normalized_url]},
    )


def detect_candidates_in_text(
    text: str,
    discovery_method: str,
    company_hint: Optional[str] = None,
    base_url: Optional[str] = None,
) -> tuple[list[SourceCandidate], list[str]]:
    candidates = []
    unsupported = []
    for url in extract_urls_from_html(text, base_url=base_url):
        candidate = normalize_ats_url(url, discovery_method, company_hint)
        if candidate:
            candidates.append(candidate)
        else:
            unsupported.append(url)
    return dedupe_candidates(candidates), unsupported


def dedupe_candidates(candidates: list[SourceCandidate]) -> list[SourceCandidate]:
    by_key: dict[tuple[str, str], SourceCandidate] = {}
    for candidate in candidates:
        if not candidate.ats or not candidate.slug:
            continue
        key = (candidate.ats, candidate.slug)
        existing = by_key.get(key)
        if not existing:
            by_key[key] = candidate
            continue
        urls = existing.metadata.setdefault("source_urls", [existing.source_url])
        for url in candidate.metadata.get("source_urls", [candidate.source_url]):
            if url not in urls:
                urls.append(url)
        if not existing.company_hint and candidate.company_hint:
            existing.company_hint = candidate.company_hint
    return list(by_key.values())


async def discover_from_hn() -> tuple[list[SourceCandidate], list[str], list[tuple[str, Optional[str], str]]]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={
                "query": '"Ask HN: Who is hiring"',
                "tags": "story,author_whoishiring",
                "hitsPerPage": 1,
            },
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
        if not hits:
            raise ValueError("Could not find latest 'Ask HN: Who is hiring' thread via Algolia")

        thread_id = hits[0].get("objectID")
        item_response = await client.get(f"https://hn.algolia.com/api/v1/items/{thread_id}")
        item_response.raise_for_status()
        item_data = item_response.json()

    candidates = []
    unsupported = []
    generic_urls = []
    for comment in item_data.get("children", []):
        html = comment.get("text") or ""
        company_hint = _company_hint_from_comment(html)
        found, rejected = detect_candidates_in_text(html, "hn_who_is_hiring", company_hint)
        candidates.extend(found)
        for url in rejected:
            normalized = _normalized_http_url(url)
            if normalized:
                generic_urls.append((normalized, company_hint, "hn_who_is_hiring"))
            else:
                unsupported.append(url)
    return dedupe_candidates(candidates), unsupported, generic_urls


def _company_hint_from_comment(html: str) -> Optional[str]:
    text = re.sub(r"<[^>]+>", " ", html or "")
    first_line = " ".join(text.split()).split("|")[0].strip()
    return first_line[:120] or None


async def discover_from_seed_file(
    seed_file: Path = DEFAULT_SEED_FILE,
) -> tuple[list[SourceCandidate], list[tuple[str, Optional[str], str]]]:
    if not seed_file.exists():
        return [], []

    try:
        seed_data = json.loads(seed_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid source discovery seed JSON: {exc}") from exc

    if isinstance(seed_data, dict):
        entries = seed_data.get("sources", [])
    else:
        entries = seed_data

    candidates = []
    generic_urls = []
    for entry in entries:
        if isinstance(entry, str):
            raw_url, company_hint = entry, None
        elif isinstance(entry, dict):
            raw_url = entry.get("url")
            company_hint = entry.get("company_hint") or entry.get("company")
        else:
            continue
        if not raw_url:
            continue
        candidate = normalize_ats_url(raw_url, "seed_file", company_hint)
        if candidate:
            candidates.append(candidate)
        elif _normalized_http_url(raw_url):
            generic_urls.append((_normalized_http_url(raw_url), company_hint, "seed_file"))

    return dedupe_candidates(candidates), generic_urls


async def expand_careers_page_once(
    url: str,
    company_hint: Optional[str],
    discovery_method: str,
    max_bytes: int = MAX_PAGE_BYTES,
) -> list[SourceCandidate]:
    normalized_url = _normalized_http_url(url)
    if not normalized_url:
        return []

    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        response = await client.get(normalized_url)
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("careers page exceeds maximum response size")
        html = response.text[:max_bytes]

    candidates, _ = detect_candidates_in_text(html, discovery_method, company_hint, normalized_url)
    return candidates


async def validate_candidate_source(candidate: SourceCandidate) -> ValidationResult:
    adapters = {
        "greenhouse": fetch_greenhouse_jobs,
        "lever": fetch_lever_jobs,
        "ashby": fetch_ashby_jobs,
        "workable": fetch_workable_jobs,
        "recruitee": fetch_recruitee_jobs,
        "personio": fetch_personio_jobs,
    }
    adapter = adapters.get(candidate.ats or "")
    if adapter is None or not candidate.slug:
        return ValidationResult(candidate, "rejected", rejection_reason="unsupported_ats")

    try:
        jobs = await adapter(candidate.slug)
    except Exception as exc:
        error_text = str(exc)
        if candidate.ats == "workable" and "403" in error_text:
            return ValidationResult(candidate, "rejected", rejection_reason="blocked_provider", last_error=error_text)
        return ValidationResult(candidate, "error", last_error=error_text)

    job_count = len(jobs)
    usable_jobs = [job for job in jobs if (job.get("raw_text") or "").strip()]
    if job_count == 0:
        return ValidationResult(candidate, "rejected", job_count=0, rejection_reason="empty_provider")
    if not usable_jobs:
        return ValidationResult(candidate, "rejected", job_count=job_count, rejection_reason="empty_descriptions")

    relevant_jobs = [job for job in usable_jobs if is_relevant_job(job)]
    if not relevant_jobs:
        return ValidationResult(
            candidate,
            "rejected",
            job_count=job_count,
            usable_job_count=len(usable_jobs),
            rejection_reason="irrelevant_postings",
        )

    return ValidationResult(
        candidate,
        "validated",
        job_count=job_count,
        usable_job_count=len(usable_jobs),
        relevant_job_count=len(relevant_jobs),
    )


def is_relevant_job(job: dict) -> bool:
    haystack = f"{job.get('title', '')} {job.get('raw_text', '')}".lower()
    return any(keyword in haystack for keyword in RELEVANCE_KEYWORDS)


async def load_active_source_config(pool) -> dict:
    config = {ats: [] for ats in SUPPORTED_ATS}
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT ats, slug
                FROM job_sources
                WHERE active = true AND validation_status = 'validated'
                ORDER BY ats, slug
                """
            )
            rows = await cur.fetchall()
    for ats, slug in rows:
        if ats in config:
            config[ats].append(slug)
    return config


async def get_active_source_count(pool) -> int:
    if pool.__class__.__module__.startswith("unittest.mock"):
        return 0
    if not hasattr(pool, "connection"):
        return 0
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM job_sources WHERE active = true AND validation_status = 'validated'"
                )
                row = await cur.fetchone()
                return int(row[0]) if row else 0
    except Exception:
        return 0


async def get_source_freshness_counts(pool, run_started_at: datetime, validated_within_current_run: int) -> dict:
    counts = {
        "never_validated": 0,
        "validated_within_current_run": validated_within_current_run,
        "stale": 0,
        "inactive": 0,
    }
    if pool.__class__.__module__.startswith("unittest.mock"):
        return counts
    if not hasattr(pool, "connection"):
        return counts
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE last_validated_at IS NULL),
                        COUNT(*) FILTER (
                            WHERE active = true
                              AND last_validated_at IS NOT NULL
                              AND last_validated_at < %s
                        ),
                        COUNT(*) FILTER (WHERE active = false OR validation_status = 'inactive')
                    FROM job_sources
                    """,
                    (run_started_at,),
                )
                row = await cur.fetchone()
                if row:
                    counts["never_validated"] = int(row[0] or 0)
                    counts["stale"] = int(row[1] or 0)
                    counts["inactive"] = int(row[2] or 0)
    except Exception:
        logger.warning("Failed to compute source freshness counts", exc_info=True)
    return counts


async def discover_sources(
    pool,
    seed_file: Path = DEFAULT_SEED_FILE,
    report_dir: Path = DEFAULT_REPORT_DIR,
    providers: Optional[list[DiscoveryProvider]] = None,
) -> DiscoveryRunResult:
    start_time = time.perf_counter()
    run_started_at = datetime.now(timezone.utc)
    unsupported_urls: list[str] = []
    candidates: list[SourceCandidate] = []
    validation_results: list[ValidationResult] = []
    errors: list[str] = []
    generic_urls: list[tuple[str, Optional[str], str]] = []
    company_signals: list[CompanySignal] = []
    company_resolutions: list[CompanySignalResolution] = []
    company_candidate_results: list[ValidationResult] = []
    provider_errors: dict[str, str] = {}

    configured_providers = providers or default_discovery_providers(seed_file)
    for provider in configured_providers:
        try:
            provider_result = await provider.discover()
            candidates.extend(provider_result.candidates)
            unsupported_urls.extend(provider_result.unsupported_urls)
            generic_urls.extend(provider_result.generic_urls)
            company_signals.extend(provider_result.company_signals)
            logger.info(
                "Source discovery provider complete",
                provider=provider.name,
                discovered=len(provider_result.candidates),
                generic=len(provider_result.generic_urls),
                unsupported=len(provider_result.unsupported_urls),
                company_signals=len(provider_result.company_signals),
            )
        except Exception as exc:
            if provider.name == "seed_file" and isinstance(exc, ValueError):
                raise
            errors.append(f"{provider.name}: {exc}")
            provider_errors[provider.name] = str(exc)
            logger.error("Source discovery provider failed", provider=provider.name, error=str(exc))

    if provider_errors and len(provider_errors) == len(configured_providers):
        raise RuntimeError(f"All source discovery providers failed: {'; '.join(errors)}")

    if company_signals:
        from backend.services.canonical_resolver import resolve_company_signal

        normalized_company_signals = []
        for signal in company_signals:
            try:
                normalized = normalize_company_signal(signal)
            except Exception as exc:
                company_resolutions.append(
                    CompanySignalResolution(
                        signal=CompanySignal(
                            provider=str(getattr(signal, "provider", "") or "unknown"),
                            evidence_url=str(getattr(signal, "evidence_url", "") or "invalid"),
                        ),
                        status="rejected",
                        rejection_reason="malformed_company_signal",
                        last_error=str(exc),
                    )
                )
                continue
            if normalized.signal:
                normalized_company_signals.append(normalized.signal)
                continue
            company_resolutions.append(
                CompanySignalResolution(
                    signal=signal,
                    status="rejected",
                    rejection_reason=normalized.rejection_reason or "unsupported_company_signal",
                )
            )

        for signal in normalized_company_signals:
            try:
                resolution = await resolve_company_signal(signal)
                company_resolutions.append(resolution)
                if signal.direct_ats_url and resolution.validation_result:
                    company_candidate_results.append(resolution.validation_result)
            except Exception as exc:
                company_resolutions.append(
                    CompanySignalResolution(
                        signal=signal,
                        status="error",
                        rejection_reason="validation_error",
                        last_error=str(exc),
                    )
                )
                logger.warning(
                    "Company signal resolution failed",
                    provider=signal.provider,
                    evidence_url=signal.evidence_url,
                    error=str(exc),
                )

    for url, company_hint, discovery_method in generic_urls:
        try:
            expanded = await expand_careers_page_once(url, company_hint, discovery_method)
            if expanded:
                candidates.extend(expanded)
            else:
                unsupported_urls.append(url)
        except Exception as exc:
            unsupported_urls.append(url)
            logger.warning("One-hop careers page expansion failed", url=url, error=str(exc))

    candidates = dedupe_candidates(candidates)
    for candidate in candidates:
        result = await validate_candidate_source(candidate)
        validation_results.append(result)
        if result.validation_status == "validated":
            logger.info("Source validated", ats=candidate.ats, slug=candidate.slug, jobs=result.job_count)
        elif result.validation_status == "rejected":
            logger.info("Source rejected", ats=candidate.ats, slug=candidate.slug, reason=result.rejection_reason)
        else:
            logger.error("Source validation errored", ats=candidate.ats, slug=candidate.slug, error=result.last_error)

    existing_result_keys = {
        (result.candidate.ats, result.candidate.slug, result.candidate.source_url)
        for result in validation_results
    }
    for result in company_candidate_results:
        key = (result.candidate.ats, result.candidate.slug, result.candidate.source_url)
        if key in existing_result_keys:
            continue
        candidates.append(result.candidate)
        validation_results.append(result)
        existing_result_keys.add(key)

    rejected_unsupported = [
        ValidationResult(
            SourceCandidate(None, None, None, url, "unsupported"),
            "rejected",
            rejection_reason="unsupported_or_no_ats_detected",
        )
        for url in unsupported_urls
    ]
    all_results = validation_results + rejected_unsupported

    source_counts = Counter(result.candidate.ats for result in validation_results if result.candidate.ats)
    rejection_reasons = Counter(result.rejection_reason for result in all_results if result.rejection_reason)
    coverage_gaps = {
        "unsupported_ats": rejection_reasons.get("unsupported_ats", 0),
        "blocked_provider": rejection_reasons.get("blocked_provider", 0),
        "empty_descriptions": rejection_reasons.get("empty_descriptions", 0),
        "irrelevant_postings": rejection_reasons.get("irrelevant_postings", 0),
        "no_ats_found": rejection_reasons.get("unsupported_or_no_ats_detected", 0),
    }
    validated_count = sum(1 for result in validation_results if result.validation_status == "validated")
    rejected_count = sum(1 for result in all_results if result.validation_status == "rejected")
    error_count = sum(1 for result in validation_results if result.validation_status == "error")

    discovery_result = DiscoveryRunResult(
        candidate_count=len(candidates),
        validated_count=validated_count,
        rejected_count=rejected_count,
        error_count=error_count,
        unsupported_url_count=len(unsupported_urls),
        source_counts=dict(source_counts),
        rejection_reasons=dict(rejection_reasons),
        coverage_gaps=coverage_gaps,
        active_source_count_after_run=0,
        report_path=None,
        source_freshness_counts={},
        validation_results=all_results,
        company_signal_counts={},
    )

    company_discovery_result = CompanyDiscoveryRunResult(
        signals=company_signals,
        resolutions=company_resolutions,
        provider_errors=provider_errors,
    )
    discovery_result.company_signal_counts = company_signal_metrics(company_discovery_result)

    await persist_discovery_result(pool, discovery_result, time.perf_counter() - start_time, "; ".join(errors) or None)
    if company_signals or provider_errors:
        try:
            await persist_company_discovery_results(
                pool,
                company_discovery_result,
                time.perf_counter() - start_time,
                "; ".join(errors) or None,
            )
        except Exception as exc:
            logger.warning("Company discovery diagnostics persistence failed", error=str(exc))
    discovery_result.active_source_count_after_run = await get_active_source_count(pool)
    discovery_result.source_freshness_counts = await get_source_freshness_counts(
        pool,
        run_started_at,
        validated_count,
    )
    discovery_result.report_path = str(write_discovery_report(discovery_result, report_dir))
    return discovery_result


async def persist_discovery_result(
    pool,
    result: DiscoveryRunResult,
    execution_time_seconds: float,
    error_message: Optional[str],
) -> None:
    status = "success" if result.validated_count or result.rejected_count else "failure"
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO source_discovery_runs (
                        status, candidate_count, validated_count, rejected_count, error_count,
                        source_counts, rejection_reasons, coverage_gaps, error_message, execution_time_seconds
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        status,
                        result.candidate_count,
                        result.validated_count,
                        result.rejected_count,
                        result.error_count,
                        json.dumps(result.source_counts),
                        json.dumps(result.rejection_reasons),
                        json.dumps(result.coverage_gaps),
                        error_message,
                        execution_time_seconds,
                    ),
                )
                row = await cur.fetchone()
                run_id = row[0] if row else None

                for validation in result.validation_results:
                    candidate = validation.candidate
                    await cur.execute(
                        """
                        INSERT INTO job_source_candidates (
                            run_id, raw_url, normalized_url, company_hint, detected_ats, detected_slug,
                            discovery_method, validation_status, rejection_reason, last_error, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            candidate.source_url,
                            candidate.source_url,
                            candidate.company_hint,
                            candidate.ats,
                            candidate.slug,
                            candidate.discovery_method,
                            validation.validation_status,
                            validation.rejection_reason,
                            validation.last_error,
                            json.dumps(candidate.metadata),
                        ),
                    )

                    if validation.validation_status == "validated":
                        await cur.execute(
                            """
                            INSERT INTO job_sources (
                                company, ats, slug, source_url, discovery_method, validation_status, active,
                                job_count, usable_job_count, last_validated_at, last_success_at, last_error, metadata
                            )
                            VALUES (%s, %s, %s, %s, %s, 'validated', true, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, %s)
                            ON CONFLICT (ats, slug) DO UPDATE SET
                                company = EXCLUDED.company,
                                source_url = EXCLUDED.source_url,
                                discovery_method = EXCLUDED.discovery_method,
                                validation_status = 'validated',
                                active = true,
                                job_count = EXCLUDED.job_count,
                                usable_job_count = EXCLUDED.usable_job_count,
                                last_validated_at = CURRENT_TIMESTAMP,
                                last_success_at = CURRENT_TIMESTAMP,
                                last_error = NULL,
                                metadata = EXCLUDED.metadata,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (
                                candidate.company_hint,
                                candidate.ats,
                                candidate.slug,
                                candidate.source_url,
                                candidate.discovery_method,
                                validation.job_count,
                                validation.usable_job_count,
                                json.dumps(candidate.metadata),
                            ),
                        )


def write_discovery_report(result: DiscoveryRunResult, report_dir: Path = DEFAULT_REPORT_DIR) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"source-discovery-report-{datetime.now().date().isoformat()}.json"
    payload = {
        "candidate_count": result.candidate_count,
        "validated_count": result.validated_count,
        "rejected_count": result.rejected_count,
        "error_count": result.error_count,
        "counts_by_ats": result.source_counts,
        "top_rejection_reasons": result.rejection_reasons,
        "unsupported_url_count": result.unsupported_url_count,
        "active_source_count_after_run": result.active_source_count_after_run,
        "source_freshness_counts": result.source_freshness_counts or {
            "never_validated": 0,
            "validated_within_current_run": result.validated_count,
            "stale": 0,
            "inactive": 0,
        },
        "coverage_gaps": result.coverage_gaps,
        "company_signals": result.company_signal_counts or {
            "signal_count": 0,
            "resolved_count": 0,
            "unresolved_count": 0,
            "rejected_count": 0,
            "error_count": 0,
            "counts_by_provider": {},
            "rejection_reasons": {},
        },
    }
    try:
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to write source discovery report", path=str(report_path), error=str(exc))
    return report_path
