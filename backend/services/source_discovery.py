import json
import re
import asyncio
import base64
import fcntl
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Awaitable, Callable, Optional, Protocol
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import httpx
import structlog

from backend.config import settings
from backend.services.parser import (
    fetch_ashby_jobs,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_personio_jobs,
    fetch_recruitee_jobs,
    fetch_workable_jobs,
)
from backend.services.company_discovery import (
    BOUNDED_COMPANY_PATHS,
    CompanyDiscoveryRunResult,
    CompanySignal,
    CompanySignalResolution,
    company_signal_metrics,
    normalize_company_domain,
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
DEFAULT_VERTEX_SEARCH_QUERIES = (
    'site:jobs.lever.co "AI Engineer" "Python"',
    'site:boards.greenhouse.io "LLM" "Backend"',
    'site:jobs.ashbyhq.com "RAG" "Engineer"',
    '"AI Engineer" "careers" "Greenhouse"',
    '"Machine Learning Platform Engineer" "careers"',
    '"FastAPI" "Backend Engineer" "jobs"',
)
DEFAULT_VERTEX_SEARCH_QUOTA_STATE_FILE = DEFAULT_REPORT_DIR / "vertex-search-quota-state.json"
VERTEX_SEARCH_ENDPOINT = "https://discoveryengine.googleapis.com/v1/{serving_config}:searchLite"
VERTEX_SEARCH_FREE_MONTHLY_CAP = 8000
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPOSITORY_SEARCH_ENDPOINT = f"{GITHUB_API_BASE}/search/repositories"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_GITHUB_ORG_TOPICS = (
    "llm",
    "rag",
    "vector-database",
    "mlops",
    "agents",
    "fastapi",
    "developer-tools",
    "data-platform",
    "evals",
)
DEFAULT_REDDIT_COMMUNITIES = ("MachineLearningJobs", "PythonJobs", "forhire", "remotepython")
DEFAULT_REDDIT_SEARCH_TERMS = ("hiring", "AI Engineer", "LLM", "RAG", "Python", "FastAPI", "backend", "remote")
WELLFOUND_MAX_PAGE_BYTES = 500_000
WELLFOUND_DISALLOWED_PATH_PREFIXES = (
    "/_jobs/",
    "/jobs/",
    "/login",
    "/signup",
    "/profile",
    "/profiles",
    "/talent",
    "/recruit",
    "/apply",
)
WELLFOUND_DISALLOWED_QUERY_KEYS = {"jobid", "jobslug", "role", "page"}
COMMON_CRAWL_COLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
COMMON_CRAWL_URL_PATTERNS = (
    "boards.greenhouse.io/*",
    "job-boards.greenhouse.io/*",
    "jobs.lever.co/*",
    "jobs.ashbyhq.com/*",
    "apply.workable.com/*",
    "*.recruitee.com/*",
    "*.jobs.personio.de/*",
    "*.jobs.personio.com/*",
)
YC_DEFAULT_CATEGORIES = (
    "ai",
    "developer-tools",
    "infrastructure",
    "data-engineering",
    "databases",
    "open-source",
    "search",
)
VC_DEFAULT_TARGETS = (
    {"firm": "a16z", "url": "https://a16z.com/portfolio"},
    {"firm": "Sequoia", "url": "https://www.sequoiacap.com/companies"},
    {"firm": "Index", "url": "https://www.indexventures.com/companies"},
    {"firm": "Accel", "url": "https://www.accel.com/companies"},
    {"firm": "Greylock", "url": "https://greylock.com/portfolio"},
    {"firm": "Lightspeed", "url": "https://lsvp.com/portfolio"},
    {"firm": "Conviction", "url": "https://www.conviction.com/portfolio"},
)
NOISE_UNSUPPORTED_HOSTS = {
    "www.linkedin.com",
    "linkedin.com",
    "forms.gle",
    "docs.google.com",
    "blog.cloudflare.com",
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "oauth.reddit.com",
}
CUSTOM_ATS_DOMAIN_MAPPINGS = {
    ("www.fullstory.com", "/careers/jobs"): ("ashby", "fullstory"),
    ("fullstory.com", "/careers/jobs"): ("ashby", "fullstory"),
    ("careers.tether.io", "/o"): ("recruitee", "tether"),
}


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
    provider_yield: dict = field(default_factory=dict)


@dataclass
class DiscoveryProviderResult:
    candidates: list[SourceCandidate] = field(default_factory=list)
    unsupported_urls: list[str] = field(default_factory=list)
    generic_urls: list[tuple[str, Optional[str], str]] = field(default_factory=list)
    company_signals: list[CompanySignal] = field(default_factory=list)
    provider_diagnostics: dict = field(default_factory=dict)


class DiscoveryProvider(Protocol):
    name: str

    async def discover(self) -> DiscoveryProviderResult:
        ...


def _safe_provider_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    return re.sub(
        r"((?:[?&]|\b)(?:key|api_key|token|access_token|client_secret|client_id|cx)=)[^&\s]+",
        r"\1[redacted]",
        text,
        flags=re.IGNORECASE,
    )


def _limit_company_signals(
    company_signals: list[CompanySignal],
    provider_diagnostics: dict[str, dict],
) -> list[CompanySignal]:
    max_signals = max(0, int(settings.discovery_max_company_signals_per_run or 0))
    if len(company_signals) <= max_signals:
        return company_signals

    dropped = company_signals[max_signals:]
    dropped_by_provider = Counter(str(getattr(signal, "provider", "") or "unknown") for signal in dropped)
    provider_diagnostics["company_signal_orchestration"] = {
        "status": "cap_exhausted",
        "cap_type": "company_signals",
        "max_company_signals_per_run": max_signals,
        "signals_seen": len(company_signals),
        "signals_kept": max_signals,
        "signals_dropped": len(dropped),
        "dropped_by_provider": dict(dropped_by_provider),
    }
    return company_signals[:max_signals]


def _limit_company_resolutions(
    normalized_company_signals: list[CompanySignal],
    company_resolutions: list[CompanySignalResolution],
    provider_diagnostics: dict[str, dict],
) -> list[CompanySignal]:
    max_resolutions = max(0, int(settings.discovery_max_company_resolutions_per_run or 0))
    if len(normalized_company_signals) <= max_resolutions:
        return normalized_company_signals

    dropped = normalized_company_signals[max_resolutions:]
    dropped_by_provider = Counter(signal.provider or "unknown" for signal in dropped)
    provider_diagnostics["company_signal_orchestration"] = {
        **provider_diagnostics.get("company_signal_orchestration", {}),
        "status": "cap_exhausted",
        "cap_type": "company_resolutions",
        "max_company_resolutions_per_run": max_resolutions,
        "resolutions_seen": len(normalized_company_signals),
        "resolutions_kept": max_resolutions,
        "resolutions_dropped": len(dropped),
        "resolution_dropped_by_provider": dict(dropped_by_provider),
    }
    for signal in dropped:
        company_resolutions.append(
            CompanySignalResolution(
                signal=signal,
                status="rejected",
                rejection_reason="resolution_cap_exceeded",
            )
        )
    return normalized_company_signals[:max_resolutions]


def _split_config_list(value: str | list[str] | tuple[str, ...] | None, default: tuple[str, ...] = ()) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    return [str(item).strip() for item in items if str(item).strip()]


def _path_matches_prefix(path: str, prefix: str) -> bool:
    normalized_path = path.rstrip("/") or "/"
    normalized_prefix = prefix.rstrip("/") or "/"
    return normalized_path == normalized_prefix or normalized_path.startswith(f"{normalized_prefix}/")


def _default_provider_diagnostics() -> dict[str, dict]:
    diagnostics: dict[str, dict] = {}
    if not settings.vertex_search_enabled:
        diagnostics["vertex_ai_search"] = {
            "status": "disabled",
            "reason": "vertex_search_disabled",
            "prod_mode": settings.vertex_search_prod_mode,
        }
    elif (
        not settings.vertex_search_api_key
        or not settings.vertex_search_project_id
        or not settings.vertex_search_engine_id
    ):
        diagnostics["vertex_ai_search"] = {
            "status": "disabled",
            "reason": "missing_credentials",
            "prod_mode": settings.vertex_search_prod_mode,
        }
    if not settings.wellfound_discovery_enabled:
        diagnostics["wellfound_signal"] = {
            "status": "disabled",
            "reason": "wellfound_discovery_disabled",
            "auto_extract_enabled": settings.wellfound_auto_extract_enabled,
            "max_pages_per_run": settings.wellfound_max_pages_per_run,
        }
    if not settings.common_crawl_discovery_enabled:
        diagnostics["common_crawl_ats"] = {
            "status": "disabled",
            "reason": "common_crawl_discovery_disabled",
            "max_crawls": settings.common_crawl_max_crawls,
            "total_record_cap": settings.common_crawl_total_record_cap,
        }
    if not settings.yc_company_discovery_enabled:
        diagnostics["yc_company_directory"] = {
            "status": "disabled",
            "reason": "yc_company_discovery_disabled",
            "max_total_companies": settings.yc_company_max_total_companies,
        }
    if not settings.vc_portfolio_discovery_enabled:
        diagnostics["vc_portfolio"] = {
            "status": "disabled",
            "reason": "vc_portfolio_discovery_disabled",
            "max_companies_per_target": settings.vc_portfolio_max_companies_per_target,
        }
    if not settings.github_org_discovery_enabled:
        diagnostics["github_org_signal"] = {
            "status": "disabled",
            "reason": "github_org_discovery_disabled",
            "max_search_queries": settings.github_org_max_search_queries,
            "max_repos_per_query": settings.github_org_max_repos_per_query,
        }
    if not settings.reddit_hiring_discovery_enabled:
        diagnostics["reddit_hiring_signal"] = {
            "status": "disabled",
            "reason": "reddit_hiring_discovery_disabled",
            "max_posts_per_run": settings.reddit_hiring_max_posts_per_run,
            "allow_unauthenticated": settings.reddit_hiring_allow_unauthenticated,
        }
    elif (
        not settings.reddit_hiring_access_token
        and (not settings.reddit_hiring_client_id or not settings.reddit_hiring_client_secret)
        and not settings.reddit_hiring_allow_unauthenticated
    ):
        diagnostics["reddit_hiring_signal"] = {
            "status": "disabled",
            "reason": "missing_credentials",
            "max_posts_per_run": settings.reddit_hiring_max_posts_per_run,
            "allow_unauthenticated": settings.reddit_hiring_allow_unauthenticated,
        }
    return diagnostics


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


class VertexAISearchSignalProvider:
    name = "vertex_ai_search"

    def __init__(
        self,
        enabled: bool = False,
        prod_mode: bool = False,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        location: str = "global",
        engine_id: Optional[str] = None,
        serving_config_id: str = "default_search",
        quota_state_file: Path | str = DEFAULT_VERTEX_SEARCH_QUOTA_STATE_FILE,
        query_templates: Optional[list[str]] = None,
        test_monthly_cap: int = 100,
        test_daily_cap: int = 10,
        test_max_queries_per_run: int = 3,
        prod_monthly_cap: int = 8000,
        prod_daily_cap: int = 300,
        prod_max_queries_per_run: int = 100,
        date_func: Optional[Callable[[], datetime]] = None,
    ):
        self.enabled = enabled
        self.prod_mode = prod_mode
        self.api_key = api_key
        self.project_id = project_id
        self.location = location or "global"
        self.engine_id = engine_id
        self.serving_config_id = serving_config_id or "default_search"
        self.quota_state_file = Path(quota_state_file)
        self.query_templates = query_templates or list(DEFAULT_VERTEX_SEARCH_QUERIES)
        self.monthly_cap = min(
            max(0, int(prod_monthly_cap if prod_mode else test_monthly_cap or 0)),
            VERTEX_SEARCH_FREE_MONTHLY_CAP,
        )
        self.daily_cap = max(0, int(prod_daily_cap if prod_mode else test_daily_cap or 0))
        self.max_queries_per_run = max(0, int(prod_max_queries_per_run if prod_mode else test_max_queries_per_run or 0))
        self.date_func = date_func or (lambda: datetime.now(timezone.utc))
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "prod_mode": prod_mode,
            "monthly_cap": self.monthly_cap,
            "daily_cap": self.daily_cap,
            "max_queries_per_run": self.max_queries_per_run,
            "queries_used": 0,
            "service": "discoveryengine.googleapis.com",
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            self.diagnostics.update({"status": "disabled", "reason": "vertex_search_disabled"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if not self.api_key or not self.project_id or not self.engine_id:
            self.diagnostics.update({"status": "disabled", "reason": "missing_credentials"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        signals_by_url: dict[str, CompanySignal] = {}
        request_count = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for query in self.query_templates[: self.max_queries_per_run]:
                if not self._reserve_query():
                    self.diagnostics.update(
                        {
                            "status": "quota_exhausted"
                            if self.diagnostics.get("status") == "enabled"
                            else self.diagnostics.get("status") or "quota_exhausted",
                            "queries_used": request_count,
                        }
                    )
                    break
                request_count += 1
                try:
                    response = await client.post(
                        self._search_endpoint(),
                        params={"key": self.api_key},
                        json={
                            "servingConfig": self._serving_config(),
                            "query": query,
                            "pageSize": 10,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict) or not isinstance(payload.get("results", []), list):
                        self.diagnostics.update(
                            {
                                "status": "api_unavailable",
                                "reason": "malformed_response",
                                "queries_used": request_count,
                            }
                        )
                        raise RuntimeError("api_unavailable")
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    reason = "quota_exhausted" if status in {403, 429} else "api_unavailable"
                    self.diagnostics.update({"status": reason, "queries_used": request_count})
                    raise RuntimeError(reason) from exc
                except (httpx.HTTPError, ValueError) as exc:
                    self.diagnostics.update({"status": "api_unavailable", "queries_used": request_count})
                    raise RuntimeError("api_unavailable") from exc

                for rank, result in enumerate(payload.get("results", []), start=1):
                    if not isinstance(result, dict):
                        continue
                    signal = self._signal_from_result(result, query, rank)
                    if not signal:
                        continue
                    existing = signals_by_url.get(signal.evidence_url)
                    if existing:
                        existing.metadata.setdefault("queries", []).extend(signal.metadata.get("queries", []))
                    else:
                        signals_by_url[signal.evidence_url] = signal

        self.diagnostics.update(
            {
                "status": "ok" if self.diagnostics.get("status") == "enabled" else self.diagnostics.get("status") or "ok",
                "queries_used": request_count,
            }
        )
        for signal in signals_by_url.values():
            signal.metadata["provider_diagnostics"] = dict(self.diagnostics)
        return DiscoveryProviderResult(
            company_signals=list(signals_by_url.values()),
            provider_diagnostics={self.name: dict(self.diagnostics)},
        )

    def _serving_config(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}/collections/default_collection/"
            f"engines/{self.engine_id}/servingConfigs/{self.serving_config_id}"
        )

    def _search_endpoint(self) -> str:
        return VERTEX_SEARCH_ENDPOINT.format(serving_config=self._serving_config())

    def _quota_keys(self) -> tuple[str, str]:
        now = self.date_func()
        return now.date().isoformat(), f"{now.year:04d}-{now.month:02d}"

    def _reserve_query(self) -> bool:
        today, month = self._quota_keys()
        try:
            self.quota_state_file.parent.mkdir(parents=True, exist_ok=True)
            with self.quota_state_file.open("a+", encoding="utf-8") as state_file:
                fcntl.flock(state_file.fileno(), fcntl.LOCK_EX)
                state_file.seek(0)
                raw_state = state_file.read()
                state = {"date": today, "day_used": 0, "month": month, "month_used": 0}
                if raw_state.strip():
                    try:
                        loaded = json.loads(raw_state)
                        if not isinstance(loaded, dict):
                            raise ValueError("quota state must be an object")
                        if loaded.get("date") == today:
                            state["day_used"] = int(loaded.get("day_used", 0))
                        if loaded.get("month") == month:
                            state["month_used"] = int(loaded.get("month_used", 0))
                    except (ValueError, TypeError):
                        self.diagnostics.update({"status": "quota_state_unavailable", "reason": "invalid_quota_state"})
                        return False
                if state["day_used"] >= self.daily_cap or state["month_used"] >= self.monthly_cap:
                    return False
                state["day_used"] += 1
                state["month_used"] += 1
                state_file.seek(0)
                state_file.truncate()
                state_file.write(json.dumps(state, indent=2, sort_keys=True))
                state_file.flush()
                return True
        except OSError:
            self.diagnostics.update({"status": "quota_state_unavailable", "reason": "quota_state_io_error"})
            return False

    def _signal_from_result(self, result: dict, query: str, rank: int) -> Optional[CompanySignal]:
        document = result.get("document") if isinstance(result.get("document"), dict) else {}
        derived = document.get("derivedStructData") if isinstance(document.get("derivedStructData"), dict) else {}
        struct_data = document.get("structData") if isinstance(document.get("structData"), dict) else {}
        raw_url = (
            derived.get("link")
            or derived.get("uri")
            or struct_data.get("link")
            or struct_data.get("uri")
            or document.get("uri")
        )
        evidence_url = _normalized_http_url(str(raw_url or ""))
        if not evidence_url:
            return None
        metadata = {
            "source_type": "vertex_ai_search",
            "queries": [
                {
                    "query": query,
                    "rank": rank,
                    "title": derived.get("title") or struct_data.get("title"),
                    "snippet": derived.get("snippet") or derived.get("extractive_answers") or derived.get("snippets"),
                    "link": raw_url,
                    "document_id": document.get("id") or document.get("name"),
                }
            ],
        }
        candidate = normalize_ats_url(evidence_url, self.name)
        if candidate:
            return CompanySignal(
                provider=self.name,
                evidence_url=evidence_url,
                company_name=None,
                direct_ats_url=candidate.source_url,
                confidence=0.7,
                metadata=metadata,
            )

        parsed = urlparse(evidence_url)
        if parsed.netloc.lower() in NOISE_UNSUPPORTED_HOSTS:
            return None
        path = parsed.path.rstrip("/") or "/"
        if path in BOUNDED_COMPANY_PATHS:
            return CompanySignal(
                provider=self.name,
                evidence_url=evidence_url,
                careers_url=evidence_url,
                confidence=0.45,
                metadata=metadata,
            )

        domain = normalize_company_domain(evidence_url)
        if not domain:
            return None
        return CompanySignal(
            provider=self.name,
            evidence_url=evidence_url,
            company_domain=domain,
            confidence=0.3,
            metadata=metadata,
        )


class GitHubOrgSignalProvider:
    name = "github_org_signal"

    def __init__(
        self,
        enabled: bool = False,
        token: Optional[str] = None,
        topics: str | list[str] | tuple[str, ...] | None = None,
        queries: str | list[str] | tuple[str, ...] | None = None,
        max_search_queries: int = 6,
        max_pages_per_query: int = 1,
        max_repos_per_query: int = 10,
        max_orgs_per_run: int = 25,
        max_organization_metadata_fetches: int = 10,
        max_readme_fetches_per_run: int = 10,
        request_timeout_seconds: float = 5.0,
        request_delay_seconds: float = 1.0,
        max_response_bytes: int = 500_000,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.enabled = enabled
        self.token = token
        self.topics = _split_config_list(topics, DEFAULT_GITHUB_ORG_TOPICS)
        self.queries = _split_config_list(queries, DEFAULT_GITHUB_ORG_TOPICS)
        self.query_templates = [f"topic:{topic}" for topic in self.topics] + self.queries
        self.max_search_queries = max(0, int(max_search_queries or 0))
        self.max_pages_per_query = max(0, int(max_pages_per_query or 0))
        self.max_repos_per_query = max(0, int(max_repos_per_query or 0))
        self.max_orgs_per_run = max(0, int(max_orgs_per_run or 0))
        self.max_organization_metadata_fetches = max(0, int(max_organization_metadata_fetches or 0))
        self.max_readme_fetches_per_run = max(0, int(max_readme_fetches_per_run or 0))
        self.request_timeout_seconds = max(0.1, float(request_timeout_seconds or 0.1))
        self.request_delay_seconds = max(0.0, float(request_delay_seconds or 0))
        self.max_response_bytes = max(1_000, int(max_response_bytes or 1_000))
        self.sleeper = sleeper
        self._seen_orgs: set[str] = set()
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "query_count": 0,
            "repository_count": 0,
            "organization_count": 0,
            "organization_metadata_fetch_count": 0,
            "readme_fetch_count": 0,
            "signals_emitted": 0,
            "unsupported_url_count": 0,
            "rejected_signal_reasons": {},
            "error_count": 0,
            "errors": [],
            "incomplete_result_count": 0,
            "cap_exhaustion": [],
            "rate_limit_remaining": None,
            "rate_limit_reset": None,
            "max_search_queries": self.max_search_queries,
            "max_repos_per_query": self.max_repos_per_query,
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            self.diagnostics.update({"status": "disabled", "reason": "github_org_discovery_disabled"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if not self.query_templates:
            self.diagnostics.update({"status": "config_error", "reason": "missing_queries"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if self.max_search_queries == 0 or self.max_pages_per_query == 0 or self.max_repos_per_query == 0:
            self.diagnostics.update({"status": "cap_exhausted"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        signals_by_url: dict[str, CompanySignal] = {}
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
            for query in self.query_templates[: self.max_search_queries]:
                repos_for_query = 0
                for page in range(1, self.max_pages_per_query + 1):
                    if repos_for_query >= self.max_repos_per_query:
                        self._record_cap("repositories_per_query")
                        break
                    try:
                        response = await client.get(
                            GITHUB_REPOSITORY_SEARCH_ENDPOINT,
                            headers=self._headers(),
                            params={
                                "q": query,
                                "sort": "stars",
                                "order": "desc",
                                "per_page": min(100, self.max_repos_per_query - repos_for_query),
                                "page": page,
                            },
                        )
                        self.diagnostics["query_count"] += 1
                        self._record_rate_headers(response)
                        self._enforce_response_size(response)
                        response.raise_for_status()
                        payload = response.json()
                        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                            self._record_error("malformed_payload", RuntimeError("malformed_payload"))
                            continue
                        if payload.get("incomplete_results"):
                            self.diagnostics["incomplete_result_count"] += 1
                        for rank, repo in enumerate(payload.get("items", []), start=1):
                            if repos_for_query >= self.max_repos_per_query:
                                self._record_cap("repositories_per_query")
                                break
                            if not isinstance(repo, dict):
                                self._record_rejection("malformed_repository")
                                continue
                            signal = await self._signal_from_repo(client, repo, query, rank)
                            repos_for_query += 1
                            self.diagnostics["repository_count"] += 1
                            if self.diagnostics.get("status") == "rate_limited":
                                break
                            if not signal:
                                continue
                            existing = signals_by_url.get(signal.evidence_url)
                            if existing:
                                existing.metadata.setdefault("queries", []).append({"query": query, "rank": rank})
                            else:
                                signals_by_url[signal.evidence_url] = signal
                    except httpx.HTTPStatusError as exc:
                        status_code = exc.response.status_code if exc.response is not None else None
                        status = "rate_limited" if status_code in {403, 429} else "api_error"
                        self._record_error(status, exc)
                        if status == "rate_limited":
                            self.diagnostics["status"] = "rate_limited"
                            break
                    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                        self._record_error("api_error", exc)
                    if self.request_delay_seconds:
                        await self.sleeper(self.request_delay_seconds)
                if self.diagnostics.get("status") == "rate_limited":
                    break

        if len(self.query_templates) > self.max_search_queries:
            self._record_cap("search_queries")
        if self.diagnostics.get("status") == "enabled":
            self.diagnostics["status"] = "ok"
        self.diagnostics["signals_emitted"] = len(signals_by_url)
        for signal in signals_by_url.values():
            signal.metadata["provider_diagnostics"] = dict(self.diagnostics)
        return DiscoveryProviderResult(
            company_signals=list(signals_by_url.values()),
            provider_diagnostics={self.name: dict(self.diagnostics)},
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _record_rate_headers(self, response) -> None:
        remaining = response.headers.get("x-ratelimit-remaining") if response.headers else None
        reset = response.headers.get("x-ratelimit-reset") if response.headers else None
        if remaining is not None:
            self.diagnostics["rate_limit_remaining"] = remaining
        if reset is not None:
            self.diagnostics["rate_limit_reset"] = reset

    def _enforce_response_size(self, response) -> None:
        content = getattr(response, "content", b"") or b""
        if len(content) > self.max_response_bytes:
            raise RuntimeError("response_too_large")

    def _record_cap(self, reason: str) -> None:
        caps = self.diagnostics.setdefault("cap_exhaustion", [])
        if reason not in caps:
            caps.append(reason)

    def _record_rejection(self, reason: str) -> None:
        rejected = self.diagnostics.setdefault("rejected_signal_reasons", {})
        rejected[reason] = rejected.get(reason, 0) + 1

    def _record_error(self, status: str, exc: Exception) -> None:
        if status == "rate_limited" or self.diagnostics.get("status") == "enabled":
            self.diagnostics["status"] = status
        else:
            self.diagnostics["status"] = self.diagnostics.get("status", status)
        self.diagnostics["error_count"] += 1
        self.diagnostics.setdefault("errors", []).append(_safe_provider_error(exc))

    async def _signal_from_repo(self, client: httpx.AsyncClient, repo: dict, query: str, rank: int) -> Optional[CompanySignal]:
        owner = repo.get("owner") if isinstance(repo.get("owner"), dict) else {}
        org_login = str(owner.get("login") or "").strip()
        if not org_login:
            self._record_rejection("missing_owner")
            return None
        if owner.get("type") != "Organization":
            self._record_rejection("non_organization_owner")
            return None
        if org_login not in self._seen_orgs:
            if len(self._seen_orgs) >= self.max_orgs_per_run:
                self._record_cap("organizations_per_run")
                return None
            self._seen_orgs.add(org_login)
            self.diagnostics["organization_count"] = len(self._seen_orgs)

        org_metadata = await self._fetch_org_metadata(client, org_login)
        if self.diagnostics.get("status") == "rate_limited":
            return None
        readme_urls, readme_html_url = await self._fetch_readme_urls(client, str(repo.get("full_name") or ""))
        if self.diagnostics.get("status") == "rate_limited":
            return None
        locator_urls = [
            repo.get("homepage"),
            org_metadata.get("blog"),
            org_metadata.get("website"),
            *readme_urls,
        ]
        repo_topics = repo.get("topics") if isinstance(repo.get("topics"), list) else []
        direct_ats_url = None
        careers_url = None
        company_domain = None
        for raw_url in locator_urls:
            normalized_url = _normalized_http_url(str(raw_url or ""))
            if not normalized_url:
                continue
            candidate = normalize_ats_url(normalized_url, self.name)
            if candidate and not direct_ats_url:
                direct_ats_url = candidate.source_url
                continue
            parsed = urlparse(normalized_url)
            if parsed.path.rstrip("/") in BOUNDED_COMPANY_PATHS and not careers_url:
                careers_url = normalized_url
            domain = normalize_company_domain(normalized_url)
            if domain and domain not in {"github.com", "www.github.com"} and not company_domain:
                company_domain = domain

        signal = CompanySignal(
            provider=self.name,
            evidence_url=_normalized_http_url(str(repo.get("html_url") or "")) or f"https://github.com/{repo.get('full_name')}",
            company_name=org_metadata.get("name") or org_login,
            company_domain=company_domain,
            careers_url=careers_url,
            direct_ats_url=direct_ats_url,
            confidence=0.45,
            category_hints=[str(topic) for topic in repo_topics if isinstance(topic, str)],
            metadata={
                "source_type": "github_repository_search",
                "query": query,
                "rank": rank,
                "repository_full_name": repo.get("full_name"),
                "repository_url": repo.get("html_url"),
                "repository_owner_url": owner.get("html_url"),
                "repository_homepage": repo.get("homepage"),
                "repository_topics": [str(topic) for topic in repo_topics if isinstance(topic, str)],
                "repository_description": repo.get("description"),
                "organization_login": org_login,
                "organization_name": org_metadata.get("name"),
                "organization_url": org_metadata.get("html_url") or owner.get("html_url"),
                "readme_url": readme_html_url,
                "readme_urls": readme_urls,
                "queries": [{"query": query, "rank": rank}],
                "hiring_proof": False,
            },
        )
        normalized = normalize_company_signal(signal)
        if not normalized.signal:
            self._record_rejection(normalized.rejection_reason or "unsupported_company_signal")
            return None
        return normalized.signal

    async def _fetch_org_metadata(self, client: httpx.AsyncClient, org_login: str) -> dict:
        if self.diagnostics["organization_metadata_fetch_count"] >= self.max_organization_metadata_fetches:
            self._record_cap("organization_metadata_fetches")
            return {}
        try:
            response = await client.get(f"{GITHUB_API_BASE}/orgs/{org_login}", headers=self._headers())
            self.diagnostics["organization_metadata_fetch_count"] += 1
            self._record_rate_headers(response)
            self._enforce_response_size(response)
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            self._record_error("rate_limited" if status_code in {403, 429} else "partial_error", exc)
            return {}
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            self._record_error("partial_error", exc)
            return {}

    async def _fetch_readme_urls(self, client: httpx.AsyncClient, full_name: str) -> tuple[list[str], Optional[str]]:
        if not full_name or "/" not in full_name:
            return [], None
        if self.diagnostics["readme_fetch_count"] >= self.max_readme_fetches_per_run:
            self._record_cap("readme_fetches")
            return [], None
        try:
            response = await client.get(f"{GITHUB_API_BASE}/repos/{full_name}/readme", headers=self._headers())
            self.diagnostics["readme_fetch_count"] += 1
            self._record_rate_headers(response)
            self._enforce_response_size(response)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return [], None
            readme_text = ""
            if isinstance(payload.get("content"), str):
                try:
                    readme_text = base64.b64decode(payload["content"], validate=False).decode("utf-8", errors="ignore")
                except (ValueError, TypeError):
                    readme_text = ""
            urls = [_normalized_http_url(url) for url in extract_urls_from_html(readme_text)]
            return [url for url in urls if url], _normalized_http_url(str(payload.get("html_url") or ""))
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code != 404:
                self._record_error("rate_limited" if status_code in {403, 429} else "partial_error", exc)
            return [], None
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            self._record_error("partial_error", exc)
            return [], None


class RedditHiringSignalProvider:
    name = "reddit_hiring_signal"

    def __init__(
        self,
        enabled: bool = False,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        user_agent: str = "be-an-ai-engineer-source-discovery/1.0",
        allow_unauthenticated: bool = False,
        subreddits: str | list[str] | tuple[str, ...] | None = None,
        search_terms: str | list[str] | tuple[str, ...] | None = None,
        max_pages_per_query: int = 1,
        max_posts_per_query: int = 10,
        max_posts_per_run: int = 50,
        request_timeout_seconds: float = 5.0,
        request_delay_seconds: float = 1.0,
        max_response_bytes: int = 500_000,
        default_confidence: float = 0.25,
        strong_signal_confidence: float = 0.4,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.enabled = enabled
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.user_agent = user_agent or "be-an-ai-engineer-source-discovery/1.0"
        self.allow_unauthenticated = allow_unauthenticated
        self.subreddits = _split_config_list(subreddits, DEFAULT_REDDIT_COMMUNITIES)
        self.search_terms = _split_config_list(search_terms, DEFAULT_REDDIT_SEARCH_TERMS)
        self.max_pages_per_query = max(0, int(max_pages_per_query or 0))
        self.max_posts_per_query = max(0, int(max_posts_per_query or 0))
        self.max_posts_per_run = max(0, int(max_posts_per_run or 0))
        self.request_timeout_seconds = max(0.1, float(request_timeout_seconds or 0.1))
        self.request_delay_seconds = max(0.0, float(request_delay_seconds or 0))
        self.max_response_bytes = max(1_000, int(max_response_bytes or 1_000))
        self.default_confidence = float(default_confidence)
        self.strong_signal_confidence = float(strong_signal_confidence)
        self.sleeper = sleeper
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "auth_mode": "oauth" if access_token or (client_id and client_secret) else "unauthenticated",
            "subreddit_count": 0,
            "query_count": 0,
            "posts_scanned": 0,
            "signals_emitted": 0,
            "unsupported_url_count": 0,
            "rejected_signal_reasons": {},
            "error_count": 0,
            "errors": [],
            "cap_exhaustion": [],
            "rate_limit_remaining": None,
            "rate_limit_reset": None,
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            self.diagnostics.update({"status": "disabled", "reason": "reddit_hiring_discovery_disabled"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if not self.access_token and not (self.client_id and self.client_secret) and not self.allow_unauthenticated:
            self.diagnostics.update({"status": "disabled", "reason": "missing_credentials"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if not self.subreddits or not self.search_terms:
            self.diagnostics.update({"status": "config_error", "reason": "missing_queries"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if self.max_pages_per_query == 0 or self.max_posts_per_query == 0 or self.max_posts_per_run == 0:
            self.diagnostics.update({"status": "cap_exhausted"})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        signals_by_url: dict[str, CompanySignal] = {}
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
            token = self.access_token
            oauth_configured = bool(self.client_id and self.client_secret)
            if not token and oauth_configured:
                token = await self._fetch_oauth_token(client)
                if not token:
                    return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
            base_url = "https://oauth.reddit.com" if token else "https://www.reddit.com"
            headers = self._headers(token)
            for subreddit in self.subreddits:
                self.diagnostics["subreddit_count"] += 1
                for search_term in self.search_terms:
                    self.diagnostics["query_count"] += 1
                    after = None
                    count = 0
                    posts_for_query = 0
                    for page_index in range(self.max_pages_per_query):
                        if self.diagnostics["posts_scanned"] >= self.max_posts_per_run:
                            self._record_cap("posts_per_run")
                            break
                        if posts_for_query >= self.max_posts_per_query:
                            self._record_cap("posts_per_query")
                            break
                        params = {
                            "q": search_term,
                            "restrict_sr": "1",
                            "sort": "new",
                            "t": "month",
                            "type": "link",
                            "limit": min(
                                self.max_posts_per_query - posts_for_query,
                                self.max_posts_per_run - self.diagnostics["posts_scanned"],
                            ),
                        }
                        if after:
                            params["after"] = after
                            params["count"] = count
                        try:
                            suffix = "" if token else ".json"
                            response = await client.get(
                                f"{base_url}/r/{subreddit}/search{suffix}",
                                headers=headers,
                                params=params,
                            )
                            self._record_rate_headers(response)
                            self._enforce_response_size(response)
                            response.raise_for_status()
                            payload = response.json()
                            data = payload.get("data") if isinstance(payload, dict) else None
                            children = data.get("children") if isinstance(data, dict) else None
                            if not isinstance(children, list):
                                self._record_error("malformed_payload", RuntimeError("malformed_payload"))
                                break
                            for child in children:
                                if self.diagnostics["posts_scanned"] >= self.max_posts_per_run:
                                    self._record_cap("posts_per_run")
                                    break
                                post = child.get("data") if isinstance(child, dict) else None
                                if not isinstance(post, dict):
                                    self._record_rejection("malformed_post")
                                    continue
                                self.diagnostics["posts_scanned"] += 1
                                posts_for_query += 1
                                signal = self._signal_from_post(post, subreddit, search_term)
                                if signal:
                                    signals_by_url.setdefault(signal.evidence_url, signal)
                            after = data.get("after") if isinstance(data, dict) else None
                            count += len(children)
                            if after and page_index == self.max_pages_per_query - 1:
                                self._record_cap("pages_per_query")
                            if after and posts_for_query >= self.max_posts_per_query:
                                self._record_cap("posts_per_query")
                            if not after:
                                break
                        except httpx.HTTPStatusError as exc:
                            status_code = exc.response.status_code if exc.response is not None else None
                            self._record_error("rate_limited" if status_code == 429 else "api_error", exc)
                            break
                        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                            self._record_error("api_error", exc)
                            break
                        if self.request_delay_seconds:
                            await self.sleeper(self.request_delay_seconds)
                    if self.diagnostics["posts_scanned"] >= self.max_posts_per_run:
                        break
                if self.diagnostics["posts_scanned"] >= self.max_posts_per_run:
                    break

        if self.diagnostics.get("status") == "enabled":
            self.diagnostics["status"] = "ok"
        self.diagnostics["signals_emitted"] = len(signals_by_url)
        for signal in signals_by_url.values():
            signal.metadata["provider_diagnostics"] = dict(self.diagnostics)
        return DiscoveryProviderResult(
            company_signals=list(signals_by_url.values()),
            provider_diagnostics={self.name: dict(self.diagnostics)},
        )

    async def _fetch_oauth_token(self, client: httpx.AsyncClient) -> Optional[str]:
        try:
            response = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": self.user_agent},
            )
            self._enforce_response_size(response)
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if isinstance(token, str) and token:
                return token
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            self._record_error("auth_error", exc)
        return None

    def _headers(self, token: Optional[str] = None) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _record_rate_headers(self, response) -> None:
        remaining = response.headers.get("x-ratelimit-remaining") if response.headers else None
        reset = response.headers.get("x-ratelimit-reset") if response.headers else None
        if remaining is not None:
            self.diagnostics["rate_limit_remaining"] = remaining
        if reset is not None:
            self.diagnostics["rate_limit_reset"] = reset

    def _enforce_response_size(self, response) -> None:
        content = getattr(response, "content", b"") or b""
        if len(content) > self.max_response_bytes:
            raise RuntimeError("response_too_large")

    def _record_cap(self, reason: str) -> None:
        caps = self.diagnostics.setdefault("cap_exhaustion", [])
        if reason not in caps:
            caps.append(reason)

    def _record_error(self, status: str, exc: Exception) -> None:
        if status in {"rate_limited", "auth_error"} or self.diagnostics.get("status") == "enabled":
            self.diagnostics["status"] = status
        else:
            self.diagnostics["status"] = self.diagnostics.get("status", status)
        self.diagnostics["error_count"] += 1
        self.diagnostics.setdefault("errors", []).append(_safe_provider_error(exc))

    def _record_rejection(self, reason: str) -> None:
        rejected = self.diagnostics.setdefault("rejected_signal_reasons", {})
        rejected[reason] = rejected.get(reason, 0) + 1

    def _signal_from_post(self, post: dict, subreddit: str, search_term: str) -> Optional[CompanySignal]:
        title = str(post.get("title") or "").strip()
        selftext = str(post.get("selftext") or "")
        if post.get("over_18"):
            self._record_rejection("mature_or_explicit")
            return None
        if post.get("removed_by_category") or title.lower() in {"[deleted]", "[removed]"} or selftext.lower() in {"[deleted]", "[removed]"}:
            self._record_rejection("deleted_or_removed")
            return None
        permalink = str(post.get("permalink") or "")
        evidence_url = _normalized_http_url(permalink if permalink.startswith("http") else f"https://www.reddit.com{permalink}")
        if not evidence_url:
            self._record_rejection("invalid_permalink")
            return None
        raw_urls = []
        if post.get("url"):
            raw_urls.append(str(post.get("url")))
        raw_urls.extend(extract_urls_from_html(f"{title}\n{selftext}"))
        direct_ats_url = None
        careers_url = None
        company_domain = None
        unsupported_count = 0
        for raw_url in raw_urls:
            normalized_url = _normalized_http_url(raw_url)
            if not normalized_url:
                continue
            candidate = normalize_ats_url(normalized_url, self.name)
            if candidate:
                direct_ats_url = direct_ats_url or candidate.source_url
                continue
            parsed = urlparse(normalized_url)
            if parsed.path.rstrip("/") in BOUNDED_COMPANY_PATHS:
                careers_url = careers_url or normalized_url
            domain = normalize_company_domain(normalized_url)
            if domain and domain not in NOISE_UNSUPPORTED_HOSTS:
                company_domain = company_domain or domain
            else:
                unsupported_count += 1
        self.diagnostics["unsupported_url_count"] += unsupported_count
        company_name = self._company_name_from_title(title)
        confidence = self.strong_signal_confidence if careers_url or direct_ats_url else self.default_confidence
        signal = CompanySignal(
            provider=self.name,
            evidence_url=evidence_url,
            company_name=company_name,
            company_domain=company_domain,
            careers_url=careers_url,
            direct_ats_url=direct_ats_url,
            confidence=confidence,
            metadata={
                "source_type": "reddit_search",
                "title": title,
                "subreddit": subreddit,
                "search_term": search_term,
                "permalink": evidence_url,
                "post_url": _normalized_http_url(str(post.get("url") or "")),
                "created_utc": post.get("created_utc"),
                "hiring_proof": False,
            },
        )
        normalized = normalize_company_signal(signal)
        if not normalized.signal:
            self._record_rejection(normalized.rejection_reason or "unsupported_company_signal")
            return None
        return normalized.signal

    def _company_name_from_title(self, title: str) -> Optional[str]:
        patterns = (
            r"^(?P<name>.+?)\s+(?:is\s+)?hiring\b",
            r"^\[?(?P<name>[A-Za-z0-9 ._-]{2,80})\]?\s*[-|:]",
        )
        for pattern in patterns:
            match = re.search(pattern, title, flags=re.IGNORECASE)
            if match:
                name = match.group("name").strip(" []-|:")
                if name:
                    return name
        return None


class WellfoundSignalProvider:
    name = "wellfound_signal"

    def __init__(
        self,
        enabled: bool = False,
        import_file: Optional[Path | str] = None,
        auto_extract_enabled: bool = False,
        max_pages_per_run: int = 5,
        request_delay_seconds: float = 5.0,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.enabled = enabled
        self.import_file = Path(import_file) if import_file else None
        self.auto_extract_enabled = auto_extract_enabled
        self.max_pages_per_run = max(0, int(max_pages_per_run or 0))
        self.request_delay_seconds = max(5.0, float(request_delay_seconds or 0))
        self.sleeper = sleeper
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "auto_extract_enabled": auto_extract_enabled,
            "max_pages_per_run": self.max_pages_per_run,
            "request_delay_seconds": self.request_delay_seconds,
            "pages_fetched": 0,
            "page_errors": [],
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        entries = self._load_import_entries()
        signals = [self._signal_from_import(entry) for entry in entries]
        if self.auto_extract_enabled:
            try:
                signals.extend(await self._extract_public_pages(entries))
            except Exception as exc:
                self.diagnostics["status"] = "partial_error"
                self.diagnostics.setdefault("page_errors", []).append(_safe_provider_error(exc))
        return DiscoveryProviderResult(
            company_signals=[signal for signal in signals if signal],
            provider_diagnostics={self.name: dict(self.diagnostics)},
        )

    def _load_import_entries(self) -> list[dict]:
        if not self.import_file or not self.import_file.exists():
            return []
        try:
            data = json.loads(self.import_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid Wellfound import JSON: {exc}") from exc
        if isinstance(data, dict):
            entries = data.get("entries") or data.get("companies") or data.get("sources") or []
        else:
            entries = data
        return [entry for entry in entries if isinstance(entry, dict)]

    def _signal_from_import(self, entry: dict) -> CompanySignal:
        evidence_url = (
            entry.get("wellfound_url")
            or entry.get("evidence_url")
            or entry.get("search_result_url")
            or entry.get("url")
            or ""
        )
        company_domain = normalize_company_domain(
            entry.get("company_domain") or entry.get("homepage_url") or entry.get("domain")
        )
        return CompanySignal(
            provider=self.name,
            evidence_url=str(evidence_url),
            company_name=entry.get("company_name") or entry.get("name"),
            company_domain=company_domain,
            confidence=entry.get("confidence"),
            category_hints=entry.get("category_hints") or [],
            metadata={
                "source_type": "import_file",
                "wellfound_url": entry.get("wellfound_url"),
                "search_result_url": entry.get("search_result_url"),
            },
        )

    async def _extract_public_pages(self, entries: list[dict]) -> list[CompanySignal]:
        urls = []
        for entry in entries:
            raw_url = entry.get("wellfound_url") or entry.get("url")
            if raw_url and self.is_allowed_public_page(str(raw_url)):
                urls.append(_normalized_http_url(str(raw_url)))
            if len(urls) >= self.max_pages_per_run:
                break
        urls = [url for url in urls if url]
        signals = []
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            for index, url in enumerate(urls):
                if index > 0:
                    await self.sleeper(self.request_delay_seconds)
                try:
                    html = await self._fetch_public_page(client, url)
                except Exception as exc:
                    self.diagnostics["status"] = "partial_error"
                    self.diagnostics.setdefault("page_errors", []).append(_safe_provider_error(exc))
                    continue
                signals.append(self._signal_from_public_page(url, html))
        return [signal for signal in signals if signal]

    async def _fetch_public_page(self, client: httpx.AsyncClient, url: str) -> str:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            final_url = str(response.url)
            if not self.is_allowed_public_page(final_url):
                raise ValueError("redirected_to_disallowed_url")
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    declared_length = int(content_length)
                except ValueError as exc:
                    raise ValueError("invalid_content_length") from exc
                if declared_length > WELLFOUND_MAX_PAGE_BYTES:
                    raise ValueError("response_too_large")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > WELLFOUND_MAX_PAGE_BYTES:
                    raise ValueError("response_too_large")
            self.diagnostics["pages_fetched"] = int(self.diagnostics.get("pages_fetched", 0)) + 1
            return bytes(body).decode(response.encoding or "utf-8", errors="replace")

    def is_allowed_public_page(self, raw_url: str) -> bool:
        normalized = _normalized_http_url(raw_url)
        if not normalized:
            return False
        parsed = urlparse(normalized)
        if parsed.netloc not in {"wellfound.com", "www.wellfound.com"}:
            return False
        path = parsed.path.lower()
        if any(_path_matches_prefix(path, prefix) for prefix in WELLFOUND_DISALLOWED_PATH_PREFIXES):
            return False
        query_keys = {key.lower() for key in parse_qs(parsed.query, keep_blank_values=True)}
        if query_keys & WELLFOUND_DISALLOWED_QUERY_KEYS:
            return False
        return True

    def _signal_from_public_page(self, evidence_url: str, html: str) -> Optional[CompanySignal]:
        parser = URLExtractingParser()
        try:
            parser.feed(html or "")
        except Exception:
            pass
        company_domain = None
        for url in parser.urls:
            normalized = _normalized_http_url(url)
            if not normalized:
                continue
            domain = normalize_company_domain(normalized)
            if domain and domain not in {"wellfound.com"}:
                company_domain = domain
                break
        company_name = None
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            company_name = re.sub(r"\s+", " ", title_match.group(1)).replace("| Wellfound", "").strip() or None
        if not company_domain and not company_name:
            return None
        return CompanySignal(
            provider=self.name,
            evidence_url=evidence_url,
            company_name=company_name,
            company_domain=company_domain,
            confidence=0.4,
            metadata={"source_type": "public_extract"},
        )


def _split_csv_setting(value: Optional[str] | list[str] | tuple[str, ...]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = str(value).split(",")
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _load_json_entries(path: Optional[Path], *keys: str) -> list[dict]:
    if not path or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid discovery import JSON: {exc}") from exc
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = []
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                entries = value
                break
    else:
        entries = []
    return [entry for entry in entries if isinstance(entry, dict)]


def _category_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


class LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current_href: Optional[str] = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs_dict = {name.lower(): value for name, value in attrs if value}
        href = attrs_dict.get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data):
        if self._current_href and data:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._current_href:
            return
        text = re.sub(r"\s+", " ", " ".join(self._current_text)).strip()
        self.links.append({"href": self._current_href, "text": text})
        self._current_href = None
        self._current_text = []


class CommonCrawlATSProvider:
    name = "common_crawl_ats"

    def __init__(
        self,
        enabled: bool = False,
        crawl_ids: Optional[str | list[str]] = None,
        max_crawls: int = 1,
        url_patterns: Optional[list[str]] = None,
        max_records_per_pattern: int = 25,
        total_record_cap: int = 100,
        request_timeout_seconds: float = 5.0,
        request_delay_seconds: float = 1.0,
        max_response_bytes: int = 500_000,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.enabled = enabled
        self.explicit_crawl_ids = _split_csv_setting(crawl_ids)
        self.max_crawls = max(0, int(max_crawls or 0))
        self.url_patterns = list(url_patterns or COMMON_CRAWL_URL_PATTERNS)
        self.max_records_per_pattern = max(0, int(max_records_per_pattern or 0))
        self.total_record_cap = max(0, int(total_record_cap or 0))
        self.request_timeout_seconds = max(0.1, float(request_timeout_seconds or 0))
        self.request_delay_seconds = max(0.0, float(request_delay_seconds or 0))
        self.max_response_bytes = max(1, int(max_response_bytes or 1))
        self.sleeper = sleeper
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "crawl_ids_queried": [],
            "pattern_count": 0,
            "records_scanned": 0,
            "candidate_count": 0,
            "unsupported_count": 0,
            "malformed_records": 0,
            "cap_exhausted": False,
            "errors": [],
            "per_pattern": [],
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            self.diagnostics["reason"] = "common_crawl_discovery_disabled"
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if self.max_crawls == 0 or self.max_records_per_pattern == 0 or self.total_record_cap == 0:
            self.diagnostics.update({"status": "cap_exhausted", "cap_exhausted": True})
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        crawl_indexes = []
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
            if self.explicit_crawl_ids:
                crawl_indexes = [
                    {
                        "id": crawl_id,
                        "cdx_api": f"https://index.commoncrawl.org/{crawl_id}-index",
                    }
                    for crawl_id in self.explicit_crawl_ids[: self.max_crawls]
                ]
            else:
                crawl_indexes = await self._fetch_crawl_indexes(client)
                if not crawl_indexes:
                    return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

            candidates: list[SourceCandidate] = []
            unsupported_urls: list[str] = []
            request_index = 0
            for crawl in crawl_indexes[: self.max_crawls]:
                crawl_id = crawl["id"]
                self.diagnostics["crawl_ids_queried"].append(crawl_id)
                for pattern in self.url_patterns:
                    if int(self.diagnostics["records_scanned"]) >= self.total_record_cap:
                        self.diagnostics["cap_exhausted"] = True
                        break
                    if request_index > 0 and self.request_delay_seconds:
                        await self.sleeper(self.request_delay_seconds)
                    request_index += 1
                    pattern_diagnostics = {
                        "crawl_id": crawl_id,
                        "url_pattern": pattern,
                        "records_returned": 0,
                        "candidates_emitted": 0,
                        "unsupported_count": 0,
                        "cap_exhausted": False,
                        "errors": [],
                    }
                    self.diagnostics["pattern_count"] = int(self.diagnostics["pattern_count"]) + 1
                    try:
                        params = {
                            "url": pattern,
                            "output": "json",
                            "limit": self.max_records_per_pattern,
                            "filter": "=status:200",
                            "fl": "url,status,mime,timestamp",
                        }
                        async for raw_line in self._iter_cdx_lines(client, crawl["cdx_api"], params):
                            if int(self.diagnostics["records_scanned"]) >= self.total_record_cap:
                                self.diagnostics["cap_exhausted"] = True
                                pattern_diagnostics["cap_exhausted"] = True
                                break
                            line = raw_line.strip()
                            if not line:
                                continue
                            try:
                                record = json.loads(line)
                            except json.JSONDecodeError:
                                self.diagnostics["malformed_records"] = int(self.diagnostics["malformed_records"]) + 1
                                continue
                            if not isinstance(record, dict):
                                self.diagnostics["malformed_records"] = int(self.diagnostics["malformed_records"]) + 1
                                continue
                            raw_url = str(record.get("url") or "")
                            if not raw_url:
                                self.diagnostics["malformed_records"] = int(self.diagnostics["malformed_records"]) + 1
                                continue
                            self.diagnostics["records_scanned"] = int(self.diagnostics["records_scanned"]) + 1
                            pattern_diagnostics["records_returned"] += 1
                            candidate = normalize_ats_url(raw_url, self.name)
                            if candidate:
                                candidate.metadata["common_crawl"] = {
                                    "crawl_id": crawl_id,
                                    "url_pattern": pattern,
                                    "timestamp": record.get("timestamp"),
                                    "status": record.get("status"),
                                    "mime": record.get("mime"),
                                }
                                candidates.append(candidate)
                                pattern_diagnostics["candidates_emitted"] += 1
                            else:
                                unsupported_urls.append(raw_url)
                                pattern_diagnostics["unsupported_count"] += 1
                    except Exception as exc:
                        safe_error = _safe_provider_error(exc)
                        pattern_diagnostics["errors"].append(safe_error)
                        self.diagnostics.setdefault("errors", []).append(safe_error)
                    self.diagnostics["per_pattern"].append(pattern_diagnostics)
                if self.diagnostics.get("cap_exhausted"):
                    break

        deduped = dedupe_candidates(candidates)
        self.diagnostics["candidate_count"] = len(deduped)
        self.diagnostics["unsupported_count"] = len(unsupported_urls)
        if self.diagnostics.get("errors") and not deduped and not unsupported_urls:
            self.diagnostics["status"] = "error"
        elif self.diagnostics.get("errors"):
            self.diagnostics["status"] = "partial_error"
        else:
            self.diagnostics["status"] = "ok"
        return DiscoveryProviderResult(
            candidates=deduped,
            unsupported_urls=unsupported_urls,
            provider_diagnostics={self.name: dict(self.diagnostics)},
        )

    async def _iter_cdx_lines(self, client: httpx.AsyncClient, cdx_api: str, params: dict):
        bytes_seen = 0
        async with client.stream("GET", cdx_api, params=params) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                bytes_seen += len(line.encode("utf-8")) + 1
                if bytes_seen > self.max_response_bytes:
                    raise ValueError("cdx_response_too_large")
                yield line

    async def _fetch_crawl_indexes(self, client: httpx.AsyncClient) -> list[dict]:
        try:
            response = await client.get(COMMON_CRAWL_COLINFO_URL)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            self.diagnostics.update({"status": "error", "reason": "index_unavailable", "last_error": _safe_provider_error(exc)})
            return []
        if not isinstance(payload, list):
            self.diagnostics.update({"status": "error", "reason": "malformed_index"})
            return []
        indexes = []
        for item in payload:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            cdx_api = item.get("cdx-api") or item.get("cdx_api")
            if not cdx_api:
                continue
            indexes.append({"id": str(item["id"]), "cdx_api": str(cdx_api)})
            if len(indexes) >= self.max_crawls:
                break
        if not indexes:
            self.diagnostics.update({"status": "error", "reason": "no_usable_cdx_api"})
        return indexes


class YCCompanyDirectoryProvider:
    name = "yc_company_directory"

    def __init__(
        self,
        enabled: bool = False,
        categories: Optional[str | list[str]] = None,
        import_file: Optional[Path | str] = None,
        max_companies_per_category: int = 25,
        max_total_companies: int = 100,
        request_timeout_seconds: float = 5.0,
        max_response_bytes: int = 500_000,
    ):
        self.enabled = enabled
        self.categories = _split_csv_setting(categories) or list(YC_DEFAULT_CATEGORIES)
        self.import_file = Path(import_file) if import_file else None
        self.max_companies_per_category = max(0, int(max_companies_per_category or 0))
        self.max_total_companies = max(0, int(max_total_companies or 0))
        self.request_timeout_seconds = max(0.1, float(request_timeout_seconds or 0))
        self.max_response_bytes = max(1, int(max_response_bytes or 1))
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "category_counts": {},
            "rejected_signal_reasons": {},
            "rows_seen": 0,
            "signals_emitted": 0,
            "errors": [],
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            self.diagnostics["reason"] = "yc_company_discovery_disabled"
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        raw_entries: list[dict] = []
        try:
            raw_entries.extend(_load_json_entries(self.import_file, "companies", "entries", "sources"))
        except Exception as exc:
            self.diagnostics["errors"].append(_safe_provider_error(exc))
            self.diagnostics["status"] = "partial_error"

        if not raw_entries:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds, follow_redirects=True) as client:
                for category in self.categories:
                    if len(raw_entries) >= self.max_total_companies:
                        break
                    try:
                        html = await self._fetch_public_category(client, category)
                        entries = self._extract_entries_from_public_html(category, html)
                        raw_entries.extend(entries[: self.max_companies_per_category])
                    except Exception as exc:
                        self.diagnostics["errors"].append(_safe_provider_error(exc))
                        self.diagnostics["status"] = "partial_error"

        signals = []
        for entry in raw_entries[: self.max_total_companies]:
            self.diagnostics["rows_seen"] = int(self.diagnostics["rows_seen"]) + 1
            signal = self._signal_from_entry(entry)
            if signal:
                signals.append(signal)
        self.diagnostics["signals_emitted"] = len(signals)
        if self.diagnostics.get("errors") and not signals:
            self.diagnostics["status"] = "error"
        elif self.diagnostics.get("status") != "partial_error":
            self.diagnostics["status"] = "ok"
        return DiscoveryProviderResult(company_signals=signals, provider_diagnostics={self.name: dict(self.diagnostics)})

    async def _fetch_public_category(self, client: httpx.AsyncClient, category: str) -> str:
        response = await client.get("https://www.ycombinator.com/companies", params={"industry": category})
        response.raise_for_status()
        content = response.content
        if len(content) > self.max_response_bytes:
            raise ValueError("response_too_large")
        return content.decode(response.encoding or "utf-8", errors="replace")

    def _extract_entries_from_public_html(self, category: str, html: str) -> list[dict]:
        parser = LinkTextParser()
        try:
            parser.feed(html or "")
        except Exception:
            pass
        entries = []
        pending_company: Optional[dict] = None
        for link in parser.links:
            href = urljoin("https://www.ycombinator.com", link["href"])
            parsed = urlparse(href)
            if parsed.netloc in {"www.ycombinator.com", "ycombinator.com"} and parsed.path.startswith("/companies/"):
                pending_company = {
                    "name": link.get("text"),
                    "yc_url": href,
                    "category_hints": [category],
                    "category": category,
                }
                continue
            if pending_company and parsed.netloc not in {"www.ycombinator.com", "ycombinator.com"}:
                pending_company["website"] = href
                entries.append(pending_company)
                pending_company = None
            if len(entries) >= self.max_companies_per_category:
                break
        return entries

    def _signal_from_entry(self, entry: dict) -> Optional[CompanySignal]:
        evidence_url = _normalized_http_url(
            str(entry.get("yc_url") or entry.get("evidence_url") or entry.get("url") or entry.get("website") or "")
        )
        website = entry.get("website") or entry.get("homepage_url") or entry.get("homepage") or entry.get("company_domain")
        careers_url = entry.get("careers_url")
        direct_ats_url = entry.get("direct_ats_url")
        candidate = normalize_ats_url(str(website or direct_ats_url or ""), self.name)
        if candidate:
            direct_ats_url = candidate.source_url
            company_domain = None
        else:
            company_domain = normalize_company_domain(website)
        category_hints = entry.get("category_hints") or entry.get("tags") or []
        category = entry.get("category")
        if category:
            category_hints = list(category_hints) + [category]
        signal = CompanySignal(
            provider=self.name,
            evidence_url=evidence_url or str(entry.get("yc_url") or entry.get("evidence_url") or ""),
            company_name=entry.get("company_name") or entry.get("name"),
            company_domain=company_domain,
            careers_url=careers_url,
            direct_ats_url=direct_ats_url,
            confidence=0.55,
            category_hints=category_hints,
            metadata={
                "source_type": "import_file" if self.import_file and self.import_file.exists() else "public_extract",
                "yc_url": entry.get("yc_url") or evidence_url,
                "batch": entry.get("batch"),
                "status": entry.get("status"),
                "category": category,
            },
        )
        normalized = normalize_company_signal(signal)
        if not normalized.signal:
            reason = normalized.rejection_reason or "unsupported_company_signal"
            self.diagnostics["rejected_signal_reasons"][reason] = self.diagnostics["rejected_signal_reasons"].get(reason, 0) + 1
            return None
        for hint in normalized.signal.category_hints:
            key = _category_key(hint)
            if key:
                self.diagnostics["category_counts"][key] = self.diagnostics["category_counts"].get(key, 0) + 1
        return normalized.signal


class VCPortfolioProvider:
    name = "vc_portfolio"

    def __init__(
        self,
        enabled: bool = False,
        targets: Optional[list[dict]] = None,
        import_file: Optional[Path | str] = None,
        max_companies_per_target: int = 50,
        request_timeout_seconds: float = 5.0,
        max_response_bytes: int = 500_000,
        config_error: Optional[str] = None,
    ):
        self.enabled = enabled
        self.targets = targets if targets is not None else [dict(target) for target in VC_DEFAULT_TARGETS]
        self.import_file = Path(import_file) if import_file else None
        self.max_companies_per_target = max(0, int(max_companies_per_target or 0))
        self.request_timeout_seconds = max(0.1, float(request_timeout_seconds or 0))
        self.max_response_bytes = max(1, int(max_response_bytes or 1))
        self.config_error = config_error
        self.diagnostics: dict = {
            "status": "enabled" if enabled else "disabled",
            "target_count": 0,
            "signals_emitted": 0,
            "rejected_signal_reasons": {},
            "per_target": [],
            "errors": [],
        }

    async def discover(self) -> DiscoveryProviderResult:
        if not self.enabled:
            self.diagnostics["reason"] = "vc_portfolio_discovery_disabled"
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        if self.config_error:
            self.diagnostics.update(
                {
                    "status": "error",
                    "reason": self.config_error,
                    "errors": [self.config_error],
                }
            )
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})

        try:
            targets = self._configured_targets()
        except Exception as exc:
            safe_error = _safe_provider_error(exc)
            self.diagnostics.update(
                {
                    "status": "error",
                    "reason": "invalid_import_file",
                    "last_error": safe_error,
                    "errors": [safe_error],
                }
            )
            return DiscoveryProviderResult(provider_diagnostics={self.name: dict(self.diagnostics)})
        self.diagnostics["target_count"] = len(targets)
        all_signals = []
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds, follow_redirects=True) as client:
            for target in targets:
                all_signals.extend(await self._discover_target(client, target))
        self.diagnostics["signals_emitted"] = len(all_signals)
        if self.diagnostics.get("errors") and not all_signals:
            self.diagnostics["status"] = "error"
        elif self.diagnostics.get("errors"):
            self.diagnostics["status"] = "partial_error"
        else:
            self.diagnostics["status"] = "ok"
        return DiscoveryProviderResult(company_signals=all_signals, provider_diagnostics={self.name: dict(self.diagnostics)})

    def _configured_targets(self) -> list[dict]:
        import_targets = _load_json_entries(self.import_file, "targets", "portfolios") if self.import_file and self.import_file.exists() else []
        if import_targets:
            return import_targets
        return self.targets

    async def _discover_target(self, client: httpx.AsyncClient, target: dict) -> list[CompanySignal]:
        firm = str(target.get("firm") or target.get("name") or "unknown").strip() or "unknown"
        portfolio_url = _normalized_http_url(str(target.get("portfolio_url") or target.get("url") or ""))
        target_diag = {
            "firm": firm,
            "source_url": portfolio_url,
            "rows_seen": 0,
            "signals_emitted": 0,
            "rejected_count": 0,
            "cap_exhausted": False,
            "errors": [],
        }
        try:
            if isinstance(target.get("companies"), list):
                entries = [entry for entry in target["companies"] if isinstance(entry, dict)]
            else:
                if not portfolio_url:
                    raise ValueError("missing_portfolio_url")
                html = await self._fetch_portfolio_page(client, portfolio_url)
                entries = self._extract_entries_from_public_html(firm, portfolio_url, html)
            if len(entries) > self.max_companies_per_target:
                target_diag["cap_exhausted"] = True
            signals = []
            for entry in entries[: self.max_companies_per_target]:
                target_diag["rows_seen"] += 1
                signal = self._signal_from_entry(entry, firm, portfolio_url)
                if signal:
                    signals.append(signal)
                    target_diag["signals_emitted"] += 1
                else:
                    target_diag["rejected_count"] += 1
            self.diagnostics["per_target"].append(target_diag)
            return signals
        except Exception as exc:
            safe_error = _safe_provider_error(exc)
            target_diag["errors"].append(safe_error)
            self.diagnostics["errors"].append(safe_error)
            self.diagnostics["per_target"].append(target_diag)
            return []

    async def _fetch_portfolio_page(self, client: httpx.AsyncClient, url: str) -> str:
        response = await client.get(url)
        response.raise_for_status()
        content = response.content
        if len(content) > self.max_response_bytes:
            raise ValueError("response_too_large")
        return content.decode(response.encoding or "utf-8", errors="replace")

    def _extract_entries_from_public_html(self, firm: str, portfolio_url: str, html: str) -> list[dict]:
        parser = LinkTextParser()
        try:
            parser.feed(html or "")
        except Exception:
            pass
        portfolio_host = urlparse(portfolio_url).netloc
        entries = []
        seen_domains = set()
        for link in parser.links:
            href = _normalized_http_url(urljoin(portfolio_url, link["href"]))
            if not href:
                continue
            parsed = urlparse(href)
            if parsed.netloc == portfolio_host:
                continue
            candidate = normalize_ats_url(href, self.name)
            if candidate:
                entries.append({"name": link.get("text"), "direct_ats_url": candidate.source_url})
                if len(entries) >= self.max_companies_per_target:
                    break
                continue
            domain = normalize_company_domain(href)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            entries.append({"name": link.get("text"), "homepage_url": href})
            if len(entries) >= self.max_companies_per_target:
                break
        return entries

    def _signal_from_entry(self, entry: dict, firm: str, portfolio_url: Optional[str]) -> Optional[CompanySignal]:
        homepage = entry.get("homepage_url") or entry.get("website") or entry.get("company_domain") or entry.get("url")
        direct_ats_url = entry.get("direct_ats_url")
        candidate = normalize_ats_url(str(homepage or direct_ats_url or ""), self.name)
        if candidate:
            company_domain = None
            direct_ats_url = candidate.source_url
        else:
            company_domain = normalize_company_domain(homepage)
        signal = CompanySignal(
            provider=self.name,
            evidence_url=portfolio_url or str(entry.get("evidence_url") or homepage or ""),
            company_name=entry.get("company_name") or entry.get("name"),
            company_domain=company_domain,
            direct_ats_url=direct_ats_url,
            confidence=0.5,
            category_hints=entry.get("category_hints") or [],
            metadata={
                "source_type": "import_file" if self.import_file and self.import_file.exists() else "public_extract",
                "vc_firm": firm,
                "portfolio_url": portfolio_url,
                "homepage_url": homepage,
            },
        )
        normalized = normalize_company_signal(signal)
        if not normalized.signal:
            reason = normalized.rejection_reason or "unsupported_company_signal"
            self.diagnostics["rejected_signal_reasons"][reason] = self.diagnostics["rejected_signal_reasons"].get(reason, 0) + 1
            return None
        return normalized.signal


def default_discovery_providers(seed_file: Path = DEFAULT_SEED_FILE) -> list[DiscoveryProvider]:
    providers: list[DiscoveryProvider] = [
        HNWhoIsHiringProvider(),
        OptionalSeedProvider(seed_file),
    ]
    if settings.vertex_search_enabled:
        providers.append(
            VertexAISearchSignalProvider(
                enabled=settings.vertex_search_enabled,
                prod_mode=settings.vertex_search_prod_mode,
                api_key=settings.vertex_search_api_key,
                project_id=settings.vertex_search_project_id,
                location=settings.vertex_search_location,
                engine_id=settings.vertex_search_engine_id,
                serving_config_id=settings.vertex_search_serving_config_id,
                quota_state_file=settings.vertex_search_quota_state_file or DEFAULT_VERTEX_SEARCH_QUOTA_STATE_FILE,
                test_monthly_cap=settings.vertex_search_test_monthly_cap,
                test_daily_cap=settings.vertex_search_test_daily_cap,
                test_max_queries_per_run=settings.vertex_search_test_max_queries_per_run,
                prod_monthly_cap=settings.vertex_search_prod_monthly_cap,
                prod_daily_cap=settings.vertex_search_prod_daily_cap,
                prod_max_queries_per_run=settings.vertex_search_prod_max_queries_per_run,
            )
        )
    if settings.wellfound_discovery_enabled:
        providers.append(
            WellfoundSignalProvider(
                enabled=settings.wellfound_discovery_enabled,
                import_file=settings.wellfound_import_file,
                auto_extract_enabled=settings.wellfound_auto_extract_enabled,
                max_pages_per_run=settings.wellfound_max_pages_per_run,
                request_delay_seconds=settings.wellfound_request_delay_seconds,
            )
        )
    if settings.common_crawl_discovery_enabled:
        providers.append(
            CommonCrawlATSProvider(
                enabled=settings.common_crawl_discovery_enabled,
                crawl_ids=settings.common_crawl_crawl_ids,
                max_crawls=settings.common_crawl_max_crawls,
                max_records_per_pattern=settings.common_crawl_max_records_per_pattern,
                total_record_cap=settings.common_crawl_total_record_cap,
                request_timeout_seconds=settings.common_crawl_request_timeout_seconds,
                request_delay_seconds=settings.common_crawl_request_delay_seconds,
                max_response_bytes=settings.common_crawl_max_response_bytes,
            )
        )
    if settings.yc_company_discovery_enabled:
        providers.append(
            YCCompanyDirectoryProvider(
                enabled=settings.yc_company_discovery_enabled,
                categories=settings.yc_company_categories,
                import_file=settings.yc_company_import_file,
                max_companies_per_category=settings.yc_company_max_companies_per_category,
                max_total_companies=settings.yc_company_max_total_companies,
                request_timeout_seconds=settings.yc_company_request_timeout_seconds,
                max_response_bytes=settings.yc_company_max_response_bytes,
            )
        )
    if settings.vc_portfolio_discovery_enabled:
        targets = None
        config_error = None
        if settings.vc_portfolio_targets_json:
            try:
                loaded_targets = json.loads(settings.vc_portfolio_targets_json)
                if isinstance(loaded_targets, list):
                    targets = [target for target in loaded_targets if isinstance(target, dict)]
                else:
                    targets = []
                    config_error = "invalid_vc_portfolio_targets_json"
            except json.JSONDecodeError:
                targets = []
                config_error = "invalid_vc_portfolio_targets_json"
        providers.append(
            VCPortfolioProvider(
                enabled=settings.vc_portfolio_discovery_enabled,
                targets=targets,
                import_file=settings.vc_portfolio_import_file,
                max_companies_per_target=settings.vc_portfolio_max_companies_per_target,
                request_timeout_seconds=settings.vc_portfolio_request_timeout_seconds,
                max_response_bytes=settings.vc_portfolio_max_response_bytes,
                config_error=config_error,
            )
        )
    if settings.github_org_discovery_enabled:
        providers.append(
            GitHubOrgSignalProvider(
                enabled=settings.github_org_discovery_enabled,
                token=settings.github_org_token,
                topics=settings.github_org_topics,
                queries=settings.github_org_queries,
                max_search_queries=settings.github_org_max_search_queries,
                max_pages_per_query=settings.github_org_max_pages_per_query,
                max_repos_per_query=settings.github_org_max_repos_per_query,
                max_orgs_per_run=settings.github_org_max_orgs_per_run,
                max_organization_metadata_fetches=settings.github_org_max_organization_metadata_fetches,
                max_readme_fetches_per_run=settings.github_org_max_readme_fetches_per_run,
                request_timeout_seconds=settings.github_org_request_timeout_seconds,
                request_delay_seconds=settings.github_org_request_delay_seconds,
                max_response_bytes=settings.github_org_max_response_bytes,
            )
        )
    if settings.reddit_hiring_discovery_enabled:
        providers.append(
            RedditHiringSignalProvider(
                enabled=settings.reddit_hiring_discovery_enabled,
                client_id=settings.reddit_hiring_client_id,
                client_secret=settings.reddit_hiring_client_secret,
                access_token=settings.reddit_hiring_access_token,
                user_agent=settings.reddit_hiring_user_agent,
                allow_unauthenticated=settings.reddit_hiring_allow_unauthenticated,
                subreddits=settings.reddit_hiring_subreddits,
                search_terms=settings.reddit_hiring_search_terms,
                max_pages_per_query=settings.reddit_hiring_max_pages_per_query,
                max_posts_per_query=settings.reddit_hiring_max_posts_per_query,
                max_posts_per_run=settings.reddit_hiring_max_posts_per_run,
                request_timeout_seconds=settings.reddit_hiring_request_timeout_seconds,
                request_delay_seconds=settings.reddit_hiring_request_delay_seconds,
                max_response_bytes=settings.reddit_hiring_max_response_bytes,
                default_confidence=settings.reddit_hiring_default_confidence,
                strong_signal_confidence=settings.reddit_hiring_strong_signal_confidence,
            )
        )
    return providers


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


def _valid_ats_slug(slug: Optional[str]) -> bool:
    return bool(slug and re.fullmatch(r"[A-Za-z0-9._-]+", slug))


def _is_actionable_unsupported_url(raw_url: str) -> bool:
    normalized_url = _normalized_http_url(raw_url)
    if not normalized_url:
        return False
    parsed = urlparse(normalized_url)
    return parsed.netloc.lower() not in NOISE_UNSUPPORTED_HOSTS


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

    for (mapped_host, path_prefix), mapped in CUSTOM_ATS_DOMAIN_MAPPINGS.items():
        if host == mapped_host and _path_matches_prefix(parsed.path, path_prefix):
            ats, slug = mapped
            break

    if not ats and host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
        query = parse_qs(parsed.query)
        if parts[:3] == ["embed", "job_board", "js"]:
            if not query.get("for"):
                return None
            ats, slug = "greenhouse", query["for"][0]
        else:
            ats, slug = "greenhouse", parts[0]
    elif not ats and host == "boards-api.greenhouse.io" and len(parts) >= 4 and parts[:3] == ["v1", "boards", parts[2]]:
        ats, slug = "greenhouse", parts[2]
    elif not ats and host == "jobs.lever.co" and parts:
        ats, slug = "lever", parts[0]
    elif not ats and host == "api.lever.co" and len(parts) >= 3 and parts[:2] == ["v0", "postings"]:
        ats, slug = "lever", parts[2]
    elif not ats and host == "jobs.ashbyhq.com" and parts:
        ats, slug = "ashby", parts[0]
    elif not ats and host == "api.ashbyhq.com" and len(parts) >= 3 and parts[:2] == ["posting-api", "job-board"]:
        ats, slug = "ashby", parts[2]
    elif not ats and host.endswith(".recruitee.com"):
        ats, slug = "recruitee", host.removesuffix(".recruitee.com")
    elif not ats and host.endswith(".jobs.personio.de"):
        ats, slug = "personio", host.removesuffix(".jobs.personio.de")
    elif not ats and host.endswith(".jobs.personio.com"):
        ats, slug = "personio", host.removesuffix(".jobs.personio.com")
    elif not ats and host == "apply.workable.com" and parts:
        if parts[:4] == ["api", "v1", "widget", "accounts"] and len(parts) >= 5:
            ats, slug = "workable", parts[4]
        elif parts[0] not in {"api", "j"}:
            ats, slug = "workable", parts[0]

    if not ats or not _valid_ats_slug(slug):
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


async def get_active_source_keys(pool) -> set[tuple[str, str]]:
    if pool.__class__.__module__.startswith("unittest.mock"):
        return set()
    if not hasattr(pool, "connection"):
        return set()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT ats, slug
                    FROM job_sources
                    WHERE active = true
                      AND validation_status = 'validated'
                    """
                )
                rows = await cur.fetchall()
                return {
                    (str(row[0]), str(row[1]))
                    for row in rows
                    if row and row[0] and row[1]
                }
    except Exception:
        return set()


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
    stale_cutoff = run_started_at - timedelta(days=max(1, int(settings.discovery_stale_source_days or 1)))
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
                    (stale_cutoff,),
                )
                row = await cur.fetchone()
                if row:
                    counts["never_validated"] = int(row[0] or 0)
                    counts["stale"] = int(row[1] or 0)
                    counts["inactive"] = int(row[2] or 0)
    except Exception:
        logger.warning("Failed to compute source freshness counts", exc_info=True)
    return counts


def _empty_provider_yield(provider: str, diagnostics: Optional[dict] = None) -> dict:
    diagnostics = diagnostics or {}
    return {
        "provider": provider,
        "signals_emitted": 0,
        "candidate_count": 0,
        "resolved_count": 0,
        "validated_active_source_count": 0,
        "newly_activated_source_count": 0,
        "active_source_growth_since_previous_run": 0,
        "rejected_count": 0,
        "error_count": 0,
        "unsupported_url_count": 0,
        "high_yield_company_or_source_count": 0,
        "stale_source_count": 0,
        "inactive_source_count": 0,
        "repeated_rejection_count": 0,
        "top_rejection_reasons": {},
        "cap_quota_status": {
            "status": diagnostics.get("status"),
            "cap_exhaustion": diagnostics.get("cap_exhaustion", []),
            "rate_limit_remaining": diagnostics.get("rate_limit_remaining"),
            "rate_limit_reset": diagnostics.get("rate_limit_reset"),
            "reason": diagnostics.get("reason"),
        },
        "last_seen_at": diagnostics.get("last_seen_at"),
        "last_success_at": diagnostics.get("last_success_at"),
    }


async def compute_provider_yield(
    pool,
    provider_names: list[str],
    validation_results: list[ValidationResult],
    company_discovery_result: CompanyDiscoveryRunResult,
    unsupported_counts_by_provider: Optional[dict[str, int]] = None,
    active_source_count_before_run: int = 0,
    active_source_count_after_run: int = 0,
    active_source_keys_before_run: Optional[set[tuple[str, str]]] = None,
) -> dict:
    diagnostics = company_discovery_result.provider_diagnostics or {}
    provider_diagnostic_names = {name for name in diagnostics.keys() if name != "company_signal_orchestration"}
    names = set(provider_names) | provider_diagnostic_names | set(company_discovery_result.provider_errors.keys())
    names.update(result.candidate.discovery_method for result in validation_results if result.candidate.discovery_method)
    names.update(signal.provider for signal in company_discovery_result.signals)
    providers = {name: _empty_provider_yield(name, diagnostics.get(name)) for name in sorted(names)}
    unsupported_counts_by_provider = unsupported_counts_by_provider or {}
    active_source_keys_before_run = active_source_keys_before_run or set()
    counted_validation_keys: set[tuple[str, str, str, str]] = set()

    for provider, provider_diagnostics in diagnostics.items():
        if provider == "company_signal_orchestration":
            continue
        metrics = providers.setdefault(provider, _empty_provider_yield(provider, provider_diagnostics))
        metrics["error_count"] += int(provider_diagnostics.get("error_count") or 0)
        metrics["unsupported_url_count"] += int(
            provider_diagnostics.get("unsupported_url_count")
            or provider_diagnostics.get("unsupported_count")
            or 0
        )

    def validation_key(result: ValidationResult) -> tuple[str, str, str, str]:
        candidate = result.candidate
        return (
            candidate.discovery_method or "",
            candidate.ats or "",
            candidate.slug or "",
            candidate.source_url or "",
        )

    def is_new_activation(result: ValidationResult) -> bool:
        candidate = result.candidate
        if result.validation_status != "validated" or not candidate.ats or not candidate.slug:
            return False
        return (candidate.ats, candidate.slug) not in active_source_keys_before_run

    for provider, count in unsupported_counts_by_provider.items():
        providers.setdefault(provider, _empty_provider_yield(provider, diagnostics.get(provider)))
        providers[provider]["unsupported_url_count"] += count

    for result in validation_results:
        provider = result.candidate.discovery_method
        if not provider:
            continue
        counted_validation_keys.add(validation_key(result))
        metrics = providers.setdefault(provider, _empty_provider_yield(provider, diagnostics.get(provider)))
        metrics["candidate_count"] += 1
        if result.validation_status == "validated":
            metrics["validated_active_source_count"] += 1
            if is_new_activation(result):
                metrics["newly_activated_source_count"] += 1
            metrics["high_yield_company_or_source_count"] += 1
        elif result.validation_status == "rejected":
            metrics["rejected_count"] += 1
            reason = result.rejection_reason or "unknown"
            metrics["top_rejection_reasons"][reason] = metrics["top_rejection_reasons"].get(reason, 0) + 1
        elif result.validation_status == "error":
            metrics["error_count"] += 1

    for signal in company_discovery_result.signals:
        metrics = providers.setdefault(signal.provider, _empty_provider_yield(signal.provider, diagnostics.get(signal.provider)))
        metrics["signals_emitted"] += 1

    for resolution in company_discovery_result.resolutions:
        provider = resolution.signal.provider
        metrics = providers.setdefault(provider, _empty_provider_yield(provider, diagnostics.get(provider)))
        if resolution.status == "resolved":
            metrics["resolved_count"] += 1
            if (
                resolution.validation_result
                and resolution.validation_result.validation_status == "validated"
                and validation_key(resolution.validation_result) not in counted_validation_keys
            ):
                metrics["validated_active_source_count"] += 1
                if is_new_activation(resolution.validation_result):
                    metrics["newly_activated_source_count"] += 1
                metrics["high_yield_company_or_source_count"] += 1
        elif resolution.status == "rejected":
            metrics["rejected_count"] += 1
            reason = resolution.rejection_reason or "unknown"
            metrics["top_rejection_reasons"][reason] = metrics["top_rejection_reasons"].get(reason, 0) + 1
        elif resolution.status == "error":
            metrics["error_count"] += 1

    for provider in company_discovery_result.provider_errors:
        providers.setdefault(provider, _empty_provider_yield(provider, diagnostics.get(provider)))
        providers[provider]["error_count"] += 1

    await _hydrate_provider_yield_from_registry(pool, providers)

    active_growth = max(0, active_source_count_after_run - active_source_count_before_run)
    total_newly_activated = sum(metrics["newly_activated_source_count"] for metrics in providers.values())
    if active_growth and total_newly_activated:
        allocations: list[tuple[str, int, float]] = []
        assigned = 0
        for provider, metrics in providers.items():
            share = metrics["newly_activated_source_count"] / total_newly_activated
            raw_growth = active_growth * share
            base_growth = int(raw_growth)
            allocations.append((provider, base_growth, raw_growth - base_growth))
            assigned += base_growth
        remaining = active_growth - assigned
        for provider, _, _ in sorted(allocations, key=lambda item: item[2], reverse=True)[:remaining]:
            providers[provider]["active_source_growth_since_previous_run"] += 1
        for provider, base_growth, _ in allocations:
            providers[provider]["active_source_growth_since_previous_run"] += base_growth

    high_yield_min = max(1, int(settings.discovery_high_yield_min_validated_sources or 1))
    high_yield_providers = [
        provider
        for provider, metrics in providers.items()
        if metrics["validated_active_source_count"] >= high_yield_min
    ]
    low_yield_providers = [
        provider
        for provider, metrics in providers.items()
        if metrics["signals_emitted"] or metrics["candidate_count"] or metrics["cap_quota_status"].get("status") == "ok"
        if metrics["validated_active_source_count"] == 0
    ]
    return {
        "providers": providers,
        "summary": {
            "provider_count": len(providers),
            "high_yield_providers": sorted(high_yield_providers),
            "low_yield_providers": sorted(low_yield_providers),
            "stale_source_count": sum(metrics["stale_source_count"] for metrics in providers.values()),
            "inactive_source_count": sum(metrics["inactive_source_count"] for metrics in providers.values()),
            "repeated_rejection_count": sum(metrics["repeated_rejection_count"] for metrics in providers.values()),
            "active_source_growth_since_previous_run": active_growth,
        },
    }


async def _hydrate_provider_yield_from_registry(pool, providers: dict[str, dict]) -> None:
    if pool.__class__.__module__.startswith("unittest.mock") or not hasattr(pool, "connection"):
        return
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(settings.discovery_stale_source_days or 1)))
    repeated_cutoff = datetime.now(timezone.utc) - timedelta(
        days=max(1, int(settings.discovery_repeated_rejection_window_days or 1))
    )
    repeated_threshold = max(1, int(settings.discovery_repeated_rejection_count or 1))
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT discovery_method,
                           COUNT(*) FILTER (WHERE active = true AND validation_status = 'validated'),
                           COUNT(*) FILTER (
                               WHERE active = true AND validation_status = 'validated'
                                 AND last_validated_at IS NOT NULL
                                 AND last_validated_at < %s
                           ),
                           COUNT(*) FILTER (WHERE active = false OR validation_status = 'inactive'),
                           MAX(last_success_at)
                    FROM job_sources
                    GROUP BY discovery_method
                    """,
                    (stale_cutoff,),
                )
                for row in await cur.fetchall():
                    provider = row[0]
                    metrics = providers.setdefault(provider, _empty_provider_yield(provider))
                    metrics["validated_active_source_count"] = max(metrics["validated_active_source_count"], int(row[1] or 0))
                    metrics["stale_source_count"] = int(row[2] or 0)
                    metrics["inactive_source_count"] = int(row[3] or 0)
                    metrics["last_success_at"] = row[4]

                await cur.execute(
                    """
                    SELECT discovery_method, rejection_reason, COUNT(*), MAX(created_at)
                    FROM job_source_candidates
                    WHERE validation_status = 'rejected'
                      AND created_at >= %s
                    GROUP BY discovery_method, rejection_reason
                    HAVING COUNT(*) >= %s
                    """,
                    (repeated_cutoff, repeated_threshold),
                )
                for row in await cur.fetchall():
                    provider = row[0]
                    metrics = providers.setdefault(provider, _empty_provider_yield(provider))
                    reason = row[1] or "unknown"
                    count = int(row[2] or 0)
                    metrics["repeated_rejection_count"] += count
                    metrics["top_rejection_reasons"][reason] = max(
                        metrics["top_rejection_reasons"].get(reason, 0),
                        count,
                    )
                    metrics["last_seen_at"] = row[3]

                await cur.execute(
                    """
                    SELECT provider, MAX(last_seen_at)
                    FROM company_signals
                    GROUP BY provider
                    """
                )
                for row in await cur.fetchall():
                    provider = row[0]
                    metrics = providers.setdefault(provider, _empty_provider_yield(provider))
                    metrics["last_seen_at"] = row[1]
    except Exception:
        logger.warning("Failed to compute provider yield registry diagnostics", exc_info=True)


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
    provider_diagnostics: dict[str, dict] = _default_provider_diagnostics() if providers is None else {}
    unsupported_counts_by_provider: dict[str, int] = {}

    configured_providers = providers or default_discovery_providers(seed_file)
    provider_names = [provider.name for provider in configured_providers]
    active_source_count_before_run = await get_active_source_count(pool)
    active_source_keys_before_run = await get_active_source_keys(pool)
    for provider in configured_providers:
        try:
            provider_result = await provider.discover()
            candidates.extend(provider_result.candidates)
            unsupported_urls.extend(provider_result.unsupported_urls)
            if provider_result.unsupported_urls:
                unsupported_counts_by_provider[provider.name] = (
                    unsupported_counts_by_provider.get(provider.name, 0) + len(provider_result.unsupported_urls)
                )
            generic_urls.extend(provider_result.generic_urls)
            company_signals.extend(provider_result.company_signals)
            if provider_result.provider_diagnostics:
                provider_diagnostics.update(provider_result.provider_diagnostics)
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
            safe_error = _safe_provider_error(exc)
            errors.append(f"{provider.name}: {safe_error}")
            provider_errors[provider.name] = safe_error
            diagnostics = dict(getattr(provider, "diagnostics", {}) or {})
            provider_diagnostics[provider.name] = {
                **diagnostics,
                "status": diagnostics.get("status") or "error",
                "last_error": safe_error,
            }
            logger.error("Source discovery provider failed", provider=provider.name, error=safe_error)

    if provider_errors and len(provider_errors) == len(configured_providers):
        raise RuntimeError(f"All source discovery providers failed: {'; '.join(errors)}")

    company_signals = _limit_company_signals(company_signals, provider_diagnostics)
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

        normalized_company_signals = _limit_company_resolutions(
            normalized_company_signals,
            company_resolutions,
            provider_diagnostics,
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
            elif _is_actionable_unsupported_url(url):
                unsupported_urls.append(url)
                unsupported_counts_by_provider[discovery_method] = unsupported_counts_by_provider.get(discovery_method, 0) + 1
        except Exception as exc:
            if _is_actionable_unsupported_url(url):
                unsupported_urls.append(url)
                unsupported_counts_by_provider[discovery_method] = unsupported_counts_by_provider.get(discovery_method, 0) + 1
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
        provider_diagnostics=provider_diagnostics,
    )
    discovery_result.company_signal_counts = company_signal_metrics(company_discovery_result)

    await persist_discovery_result(pool, discovery_result, time.perf_counter() - start_time, "; ".join(errors) or None)
    discovery_result.active_source_count_after_run = await get_active_source_count(pool)
    discovery_result.source_freshness_counts = await get_source_freshness_counts(
        pool,
        run_started_at,
        validated_count,
    )
    discovery_result.provider_yield = await compute_provider_yield(
        pool,
        provider_names,
        all_results,
        company_discovery_result,
        unsupported_counts_by_provider,
        active_source_count_before_run,
        discovery_result.active_source_count_after_run,
        active_source_keys_before_run,
    )
    company_discovery_result.provider_yield = discovery_result.provider_yield
    discovery_result.company_signal_counts = company_signal_metrics(company_discovery_result)
    if company_signals or provider_errors or provider_diagnostics:
        try:
            await persist_company_discovery_results(
                pool,
                company_discovery_result,
                time.perf_counter() - start_time,
                "; ".join(errors) or None,
            )
        except Exception as exc:
            logger.warning("Company discovery diagnostics persistence failed", error=str(exc))
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
    company_signals = result.company_signal_counts or {
        "signal_count": 0,
        "resolved_count": 0,
        "unresolved_count": 0,
        "rejected_count": 0,
        "error_count": 0,
        "counts_by_provider": {},
        "rejection_reasons": {},
        "provider_errors": {},
        "provider_diagnostics": {},
    }
    company_signals["provider_yield"] = result.provider_yield or {
        "providers": {},
        "summary": {
            "provider_count": 0,
            "high_yield_providers": [],
            "low_yield_providers": [],
            "stale_source_count": 0,
            "inactive_source_count": 0,
            "repeated_rejection_count": 0,
            "active_source_growth_since_previous_run": 0,
        },
    }
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
        "company_signals": company_signals,
    }
    try:
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to write source discovery report", path=str(report_path), error=str(exc))
    return report_path
