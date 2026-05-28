import json
import re
import asyncio
import fcntl
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
NOISE_UNSUPPORTED_HOSTS = {
    "www.linkedin.com",
    "linkedin.com",
    "forms.gle",
    "docs.google.com",
    "blog.cloudflare.com",
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
    return re.sub(r"((?:[?&]|\b)(?:key|api_key|token|access_token|cx)=)[^&\s]+", r"\1[redacted]", text, flags=re.IGNORECASE)


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
    provider_diagnostics: dict[str, dict] = _default_provider_diagnostics() if providers is None else {}

    configured_providers = providers or default_discovery_providers(seed_file)
    for provider in configured_providers:
        try:
            provider_result = await provider.discover()
            candidates.extend(provider_result.candidates)
            unsupported_urls.extend(provider_result.unsupported_urls)
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
            elif _is_actionable_unsupported_url(url):
                unsupported_urls.append(url)
        except Exception as exc:
            if _is_actionable_unsupported_url(url):
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
        provider_diagnostics=provider_diagnostics,
    )
    discovery_result.company_signal_counts = company_signal_metrics(company_discovery_result)

    await persist_discovery_result(pool, discovery_result, time.perf_counter() - start_time, "; ".join(errors) or None)
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
            "provider_errors": {},
            "provider_diagnostics": {},
        },
    }
    try:
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to write source discovery report", path=str(report_path), error=str(exc))
    return report_path
