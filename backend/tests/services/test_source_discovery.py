import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.source_discovery import (
    DiscoveryProviderResult,
    DiscoveryRunResult,
    HNWhoIsHiringProvider,
    OptionalSeedProvider,
    SourceCandidate,
    ValidationResult,
    default_discovery_providers,
    discover_sources,
    discover_from_hn,
    discover_from_seed_file,
    expand_careers_page_once,
    extract_urls_from_html,
    get_source_freshness_counts,
    load_active_source_config,
    normalize_ats_url,
    persist_discovery_result,
    validate_candidate_source,
)
from backend.services.company_discovery import (
    CompanyDiscoveryRunResult,
    CompanySignal,
    CompanySignalResolution,
    normalize_company_signal,
    persist_company_discovery_results,
)


def read_discovery_report(report_dir: Path) -> dict:
    report_files = list(report_dir.glob("source-discovery-report-*.json"))
    assert len(report_files) == 1
    return json.loads(report_files[0].read_text(encoding="utf-8"))


def test_normalize_ats_url_supported_patterns():
    cases = [
        ("https://boards.greenhouse.io/stripe", ("greenhouse", "stripe")),
        ("https://job-boards.greenhouse.io/acme/jobs/1", ("greenhouse", "acme")),
        ("https://boards-api.greenhouse.io/v1/boards/openai/jobs", ("greenhouse", "openai")),
        ("https://jobs.lever.co/employ/abc", ("lever", "employ")),
        ("https://api.lever.co/v0/postings/anthropic", ("lever", "anthropic")),
        ("https://jobs.ashbyhq.com/sentry", ("ashby", "sentry")),
        ("https://api.ashbyhq.com/posting-api/job-board/linear", ("ashby", "linear")),
        ("https://bunq.recruitee.com/o/backend", ("recruitee", "bunq")),
        ("https://personio.jobs.personio.de/", ("personio", "personio")),
        ("https://demo.jobs.personio.com/job/1", ("personio", "demo")),
        ("https://apply.workable.com/canonical-ai/", ("workable", "canonical-ai")),
        ("https://apply.workable.com/api/v1/widget/accounts/spacelift", ("workable", "spacelift")),
    ]

    for url, expected in cases:
        candidate = normalize_ats_url(url, discovery_method="unit")
        assert candidate is not None
        assert (candidate.ats, candidate.slug) == expected
        assert candidate.source_url.startswith("https://")


def test_normalize_ats_url_rejects_malformed_and_unsupported():
    assert normalize_ats_url("ftp://boards.greenhouse.io/stripe", "unit") is None
    assert normalize_ats_url("not a url", "unit") is None
    assert normalize_ats_url("https://example.com/careers", "unit") is None


def test_company_discovery_migration_defines_signal_registry_shape():
    migration = Path("backend/db/migrations/V006__add_company_discovery.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS company_discovery_runs" in migration
    assert "CREATE TABLE IF NOT EXISTS company_signals" in migration
    assert "status IN ('candidate', 'resolved', 'rejected', 'unresolved', 'error')" in migration
    assert "NULLS NOT DISTINCT" in migration
    assert "idx_company_signals_provider_evidence_unique" in migration


def test_normalize_company_signal_accepts_domains_and_rejects_bad_inputs():
    accepted = normalize_company_signal(
        CompanySignal(
            provider="unit",
            evidence_url="https://example.com/evidence",
            company_name="Example",
            company_domain="https://www.Example.com/about",
            careers_url="https://example.com/careers",
            confidence=0.8,
            category_hints=["ai"],
        )
    )

    assert accepted.signal is not None
    assert accepted.signal.normalized_domain == "example.com"
    assert accepted.rejection_reason is None

    rejected = normalize_company_signal(
        CompanySignal(provider="unit", evidence_url="not-a-url", company_name="Bad")
    )

    assert rejected.signal is None
    assert rejected.rejection_reason == "invalid_evidence_url"

    unbounded_careers_url = normalize_company_signal(
        CompanySignal(
            provider="unit",
            evidence_url="https://example.com/evidence",
            careers_url="https://example.com/team/open-roles",
        )
    )

    assert unbounded_careers_url.signal is None
    assert unbounded_careers_url.rejection_reason == "invalid_careers_url"

    missing_provider = normalize_company_signal(
        CompanySignal(provider="", evidence_url="https://example.com/evidence", company_domain="example.com")
    )

    assert missing_provider.signal is None
    assert missing_provider.rejection_reason == "missing_provider"


def test_extract_urls_from_html_handles_links_and_text():
    html = """
    <a href="https://boards.greenhouse.io/stripe">Jobs</a>
    <script>window.jobs = "https://jobs.lever.co/employ";</script>
    Visit https://jobs.ashbyhq.com/sentry too.
    """
    urls = extract_urls_from_html(html)

    assert "https://boards.greenhouse.io/stripe" in urls
    assert "https://jobs.lever.co/employ" in urls
    assert "https://jobs.ashbyhq.com/sentry" in urls


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_discover_from_hn_uses_latest_who_is_hiring_thread(mock_get):
    search_resp = MagicMock()
    search_resp.json.return_value = {"hits": [{"objectID": "123"}]}
    search_resp.raise_for_status.return_value = None
    item_resp = MagicMock()
    item_resp.json.return_value = {
        "children": [
            {
                "text": "<p>Acme AI | Remote <a href='https://boards.greenhouse.io/acme'>Jobs</a></p>"
            },
            {"text": "<p>Bad link <a href='not-a-url'>broken</a></p>"},
        ]
    }
    item_resp.raise_for_status.return_value = None
    mock_get.side_effect = [search_resp, item_resp]

    candidates, unsupported, generic = await discover_from_hn()

    assert [(c.ats, c.slug, c.discovery_method) for c in candidates] == [
        ("greenhouse", "acme", "hn_who_is_hiring")
    ]
    assert unsupported == ["not-a-url"]
    assert generic == []
    assert mock_get.call_args_list[0].kwargs["params"]["tags"] == "story,author_whoishiring"
    assert mock_get.call_args_list[0].kwargs["params"]["hitsPerPage"] == 1
    assert "items/123" in mock_get.call_args_list[1].args[0]


@pytest.mark.asyncio
async def test_discover_from_seed_file_valid_missing_and_invalid(tmp_path):
    seed_file = tmp_path / "source-discovery-seeds.json"
    seed_file.write_text(
        json.dumps(
            [
                {"url": "https://jobs.lever.co/employ", "company_hint": "Employ"},
                {"url": "https://example.com/careers", "company_hint": "Example"},
            ]
        ),
        encoding="utf-8",
    )

    candidates, generic = await discover_from_seed_file(seed_file)
    assert [(c.ats, c.slug, c.company_hint) for c in candidates] == [("lever", "employ", "Employ")]
    assert generic == [("https://example.com/careers", "Example", "seed_file")]

    missing_candidates, missing_generic = await discover_from_seed_file(tmp_path / "missing.json")
    assert missing_candidates == []
    assert missing_generic == []

    seed_file.write_text("{bad json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid source discovery seed JSON"):
        await discover_from_seed_file(seed_file)


def test_default_discovery_providers_include_seed_as_optional_provider(tmp_path):
    providers = default_discovery_providers(tmp_path / "missing-seeds.json")

    assert [provider.name for provider in providers] == ["hn_who_is_hiring", "seed_file"]
    assert isinstance(providers[0], HNWhoIsHiringProvider)
    assert isinstance(providers[1], OptionalSeedProvider)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_expand_careers_page_once_extracts_supported_ats_links(mock_get):
    response = MagicMock()
    response.text = """
    <html>
      <head><link rel="canonical" href="https://jobs.ashbyhq.com/sentry"></head>
      <body>
        <a href="https://boards.greenhouse.io/stripe">Greenhouse</a>
        <a href="https://jobs.lever.co/employ">Lever</a>
        <a href="https://apply.workable.com/spacelift/">Workable</a>
        <a href="https://bunq.recruitee.com">Recruitee</a>
        Text https://personio.jobs.personio.de/
      </body>
    </html>
    """
    response.raise_for_status.return_value = None
    response.headers = {"content-length": str(len(response.text))}
    mock_get.return_value = response

    candidates = await expand_careers_page_once("https://example.com/careers", "Example", "seed_file")
    pairs = {(c.ats, c.slug) for c in candidates}

    assert pairs == {
        ("greenhouse", "stripe"),
        ("lever", "employ"),
        ("ashby", "sentry"),
        ("workable", "spacelift"),
        ("recruitee", "bunq"),
        ("personio", "personio"),
    }


@pytest.mark.asyncio
@patch("backend.services.source_discovery.fetch_greenhouse_jobs", new_callable=AsyncMock)
async def test_validate_candidate_source_success(mock_fetch):
    mock_fetch.return_value = [
        {
            "title": "Backend AI Engineer",
            "raw_text": "Build FastAPI LLM evaluation systems",
        }
    ]

    result = await validate_candidate_source(
        SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "unit")
    )

    assert result.validation_status == "validated"
    assert result.job_count == 1
    assert result.usable_job_count == 1
    assert result.relevant_job_count == 1


@pytest.mark.asyncio
@patch("backend.services.source_discovery.fetch_workable_jobs", new_callable=AsyncMock)
async def test_validate_candidate_source_rejects_workable_403(mock_fetch):
    mock_fetch.side_effect = Exception("HTTP Error 403")

    result = await validate_candidate_source(
        SourceCandidate("Blocked", "workable", "blocked", "https://apply.workable.com/blocked", "unit")
    )

    assert result.validation_status == "rejected"
    assert result.rejection_reason == "blocked_provider"


@pytest.mark.asyncio
@patch("backend.services.source_discovery.fetch_lever_jobs", new_callable=AsyncMock)
async def test_validate_candidate_source_rejects_empty_and_irrelevant(mock_fetch):
    mock_fetch.return_value = [{"title": "Sales", "raw_text": ""}]
    empty = await validate_candidate_source(
        SourceCandidate("Acme", "lever", "acme", "https://jobs.lever.co/acme", "unit")
    )
    assert empty.validation_status == "rejected"
    assert empty.rejection_reason == "empty_descriptions"

    mock_fetch.return_value = [{"title": "Sales", "raw_text": "Carry a quota and manage accounts"}]
    irrelevant = await validate_candidate_source(
        SourceCandidate("Acme", "lever", "acme", "https://jobs.lever.co/acme", "unit")
    )
    assert irrelevant.validation_status == "rejected"
    assert irrelevant.rejection_reason == "irrelevant_postings"


class RegistryCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.executed.append((query, vars))

    async def fetchall(self):
        return self.rows


class RegistryConn:
    def __init__(self, rows):
        self.cursor_obj = RegistryCursor(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return self.cursor_obj


class RegistryPool:
    def __init__(self, rows):
        self.conn = RegistryConn(rows)

    def connection(self):
        return self.conn


class FreshnessCursor:
    def __init__(self, row):
        self.row = row
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.executed.append((query, vars))

    async def fetchone(self):
        return self.row


class FreshnessConn:
    def __init__(self, row):
        self.cursor_obj = FreshnessCursor(row)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return self.cursor_obj


class FreshnessPool:
    def __init__(self, row):
        self.conn = FreshnessConn(row)

    def connection(self):
        return self.conn


class PersistCursor:
    def __init__(self):
        self.execute_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_calls.append((query, vars))

    async def fetchone(self):
        return (42,)


class PersistTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class PersistConn:
    def __init__(self):
        self.cursor_obj = PersistCursor()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return self.cursor_obj

    def transaction(self):
        return PersistTransaction()


class PersistPool:
    def __init__(self):
        self.conn = PersistConn()

    def connection(self):
        return self.conn


@pytest.mark.asyncio
async def test_load_active_source_config_returns_expected_shape():
    pool = RegistryPool([("greenhouse", "stripe"), ("lever", "employ")])

    config = await load_active_source_config(pool)

    assert config == {
        "greenhouse": ["stripe"],
        "lever": ["employ"],
        "ashby": [],
        "workable": [],
        "recruitee": [],
        "personio": [],
    }


@pytest.mark.asyncio
async def test_get_source_freshness_counts_queries_registry_state():
    pool = FreshnessPool((2, 3, 4))

    counts = await get_source_freshness_counts(pool, MagicMock(), validated_within_current_run=5)

    assert counts == {
        "never_validated": 2,
        "validated_within_current_run": 5,
        "stale": 3,
        "inactive": 4,
    }
    assert "last_validated_at < %s" in pool.conn.cursor_obj.executed[0][0]


@pytest.mark.asyncio
async def test_persist_discovery_result_inserts_candidates_and_upserts_sources():
    candidate = SourceCandidate(
        "Stripe",
        "greenhouse",
        "stripe",
        "https://boards.greenhouse.io/stripe",
        "seed_file",
        {"source_urls": ["https://boards.greenhouse.io/stripe"]},
    )
    rejected = SourceCandidate(
        "Example",
        None,
        None,
        "https://example.com/careers",
        "unsupported",
    )
    result = DiscoveryRunResult(
        candidate_count=1,
        validated_count=1,
        rejected_count=1,
        error_count=0,
        unsupported_url_count=1,
        source_counts={"greenhouse": 1},
        rejection_reasons={"unsupported_or_no_ats_detected": 1},
        coverage_gaps={"no_ats_found": 1},
        active_source_count_after_run=0,
        report_path=None,
        validation_results=[
            ValidationResult(candidate, "validated", job_count=2, usable_job_count=2, relevant_job_count=1),
            ValidationResult(rejected, "rejected", rejection_reason="unsupported_or_no_ats_detected"),
        ],
    )
    pool = PersistPool()

    await persist_discovery_result(pool, result, 1.25, None)

    queries = [call[0] for call in pool.conn.cursor_obj.execute_calls]
    assert any("INSERT INTO source_discovery_runs" in query for query in queries)
    assert sum("INSERT INTO job_source_candidates" in query for query in queries) == 2
    assert any("INSERT INTO job_sources" in query and "ON CONFLICT (ats, slug) DO UPDATE" in query for query in queries)


@pytest.mark.asyncio
async def test_persist_company_discovery_results_upserts_signals_and_validated_sources():
    signal = CompanySignal(
        provider="unit",
        evidence_url="https://example.com/evidence",
        company_name="Acme",
        company_domain="example.com",
        normalized_domain="example.com",
    )
    candidate = SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "company_signal")
    result = CompanyDiscoveryRunResult(
        signals=[signal],
        resolutions=[
            CompanySignalResolution(
                signal=signal,
                status="resolved",
                resolved_candidate=candidate,
                validation_result=ValidationResult(candidate, "validated", job_count=2, usable_job_count=2),
            )
        ],
        provider_errors={},
    )
    pool = PersistPool()

    await persist_company_discovery_results(pool, result, 1.25, None)

    queries = [call[0] for call in pool.conn.cursor_obj.execute_calls]
    assert any("INSERT INTO company_discovery_runs" in query for query in queries)
    assert any("INSERT INTO company_signals" in query and "ON CONFLICT" in query for query in queries)
    assert any("INSERT INTO job_sources" in query and "ON CONFLICT (ats, slug) DO UPDATE" in query for query in queries)


@pytest.mark.asyncio
@patch("backend.services.source_discovery.discover_from_hn", new_callable=AsyncMock)
@patch("backend.services.source_discovery.discover_from_seed_file", new_callable=AsyncMock)
@patch("backend.services.source_discovery.expand_careers_page_once", new_callable=AsyncMock)
@patch("backend.services.source_discovery.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_deduplicates_and_writes_report(
    mock_persist,
    mock_validate,
    mock_expand,
    mock_seed,
    mock_hn,
    tmp_path,
):
    candidate = SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "seed_file")
    duplicate = SourceCandidate("Acme", "greenhouse", "acme", "https://job-boards.greenhouse.io/acme", "hn_who_is_hiring")
    mock_hn.return_value = ([duplicate], [], [])
    mock_seed.return_value = ([candidate], [("https://example.com/careers", "Example", "seed_file")])
    mock_expand.return_value = []
    mock_validate.return_value.validation_status = "validated"
    mock_validate.return_value.rejection_reason = None
    mock_validate.return_value.last_error = None
    mock_validate.return_value.candidate = candidate

    result = await discover_sources(MagicMock(), seed_file=tmp_path / "seeds.json", report_dir=tmp_path)

    assert result.candidate_count == 1
    assert result.validated_count == 1
    report = read_discovery_report(tmp_path)
    assert report["candidate_count"] == 1
    assert report["active_source_count_after_run"] == 0
    assert report["source_freshness_counts"]["validated_within_current_run"] == 1
    assert report["company_signals"]["signal_count"] == 0


@pytest.mark.asyncio
@patch("backend.services.source_discovery.discover_from_hn", new_callable=AsyncMock)
@patch("backend.services.source_discovery.discover_from_seed_file", new_callable=AsyncMock)
@patch("backend.services.source_discovery.expand_careers_page_once", new_callable=AsyncMock)
@patch("backend.services.source_discovery.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_expands_hn_generic_urls_with_hn_method(
    mock_persist,
    mock_validate,
    mock_expand,
    mock_seed,
    mock_hn,
    tmp_path,
):
    hn_candidate = SourceCandidate(
        "Acme",
        "greenhouse",
        "acme",
        "https://boards.greenhouse.io/acme",
        "hn_who_is_hiring",
    )
    mock_hn.return_value = ([], [], [("https://example.com/careers", "Acme", "hn_who_is_hiring")])
    mock_seed.return_value = ([], [])
    mock_expand.return_value = [hn_candidate]
    mock_validate.return_value = ValidationResult(
        hn_candidate,
        "validated",
        job_count=1,
        usable_job_count=1,
        relevant_job_count=1,
    )

    result = await discover_sources(MagicMock(), seed_file=tmp_path / "seeds.json", report_dir=tmp_path)

    mock_expand.assert_awaited_once_with(
        "https://example.com/careers",
        "Acme",
        "hn_who_is_hiring",
    )
    assert result.validated_count == 1


@pytest.mark.asyncio
@patch("backend.services.source_discovery.discover_from_hn", new_callable=AsyncMock)
@patch("backend.services.source_discovery.discover_from_seed_file", new_callable=AsyncMock)
async def test_discover_sources_fails_on_invalid_seed_json(mock_seed, mock_hn, tmp_path):
    mock_hn.return_value = ([], [], [])
    mock_seed.side_effect = ValueError("Invalid source discovery seed JSON: line 1")

    with pytest.raises(ValueError, match="Invalid source discovery seed JSON"):
        await discover_sources(MagicMock(), seed_file=tmp_path / "bad.json", report_dir=tmp_path)


@pytest.mark.asyncio
async def test_discover_sources_fails_when_all_configured_providers_fail(tmp_path):
    class FailingProvider:
        name = "failing"

        async def discover(self):
            raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="All source discovery providers failed"):
        await discover_sources(MagicMock(), providers=[FailingProvider()], report_dir=tmp_path)


@pytest.mark.asyncio
@patch("backend.services.source_discovery.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_can_run_without_seed_provider(mock_persist, mock_validate, tmp_path):
    class StaticProvider:
        name = "static_test"

        async def discover(self):
            return DiscoveryProviderResult(
                candidates=[
                    SourceCandidate(
                        "Acme",
                        "greenhouse",
                        "acme",
                        "https://boards.greenhouse.io/acme",
                        "static_test",
                    )
                ]
            )

    mock_validate.return_value = ValidationResult(
        SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "static_test"),
        "validated",
        job_count=1,
        usable_job_count=1,
        relevant_job_count=1,
    )

    result = await discover_sources(MagicMock(), providers=[StaticProvider()], report_dir=tmp_path)

    assert result.candidate_count == 1
    assert result.validated_count == 1


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.resolve_company_signal", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_resolves_company_signals_with_isolated_failures(
    mock_persist,
    mock_persist_company,
    mock_resolve,
    tmp_path,
):
    signal = CompanySignal(
        provider="static_company",
        evidence_url="https://example.com/evidence",
        company_name="Acme",
        company_domain="example.com",
    )

    class StaticCompanyProvider:
        name = "static_company"

        async def discover(self):
            return DiscoveryProviderResult(company_signals=[signal])

    mock_resolve.return_value = CompanySignalResolution(signal=signal, status="unresolved", rejection_reason="no_canonical_source_found")

    result = await discover_sources(MagicMock(), providers=[StaticCompanyProvider()], report_dir=tmp_path)

    assert result.company_signal_counts["signal_count"] == 1
    assert result.company_signal_counts["unresolved_count"] == 1
    mock_persist_company.assert_awaited_once()
    report = read_discovery_report(tmp_path)
    assert report["company_signals"]["counts_by_provider"] == {"static_company": 1}


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.resolve_company_signal", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_adds_direct_ats_company_signals_to_candidate_diagnostics(
    mock_persist,
    mock_persist_company,
    mock_resolve,
    tmp_path,
):
    signal = CompanySignal(
        provider="static_company",
        evidence_url="https://example.com/evidence",
        direct_ats_url="https://boards.greenhouse.io/acme",
    )
    candidate = SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "company_signal")
    validation = ValidationResult(candidate, "validated", job_count=2, usable_job_count=2)

    class StaticCompanyProvider:
        name = "static_company"

        async def discover(self):
            return DiscoveryProviderResult(company_signals=[signal])

    mock_resolve.return_value = CompanySignalResolution(
        signal=signal,
        status="resolved",
        resolved_candidate=candidate,
        validation_result=validation,
    )

    result = await discover_sources(MagicMock(), providers=[StaticCompanyProvider()], report_dir=tmp_path)

    assert result.candidate_count == 1
    assert result.validated_count == 1
    persisted_result = mock_persist.await_args.args[1]
    assert persisted_result.validation_results[0].candidate.discovery_method == "company_signal"
    mock_persist_company.assert_awaited_once()


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.resolve_company_signal", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_continues_when_company_diagnostics_persistence_fails(
    mock_persist,
    mock_persist_company,
    mock_resolve,
    tmp_path,
):
    signal = CompanySignal(
        provider="static_company",
        evidence_url="https://example.com/evidence",
        company_domain="example.com",
    )

    class StaticCompanyProvider:
        name = "static_company"

        async def discover(self):
            return DiscoveryProviderResult(company_signals=[signal])

    mock_resolve.return_value = CompanySignalResolution(signal=signal, status="unresolved", rejection_reason="no_canonical_source_found")
    mock_persist_company.side_effect = RuntimeError("diagnostics failed")

    result = await discover_sources(MagicMock(), providers=[StaticCompanyProvider()], report_dir=tmp_path)

    assert result.company_signal_counts["signal_count"] == 1
    assert result.report_path is not None
    assert Path(result.report_path).exists()
