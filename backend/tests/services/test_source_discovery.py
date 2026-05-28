import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.source_discovery import (
    CommonCrawlATSProvider,
    DiscoveryProviderResult,
    DiscoveryRunResult,
    GitHubOrgSignalProvider,
    HNWhoIsHiringProvider,
    OptionalSeedProvider,
    RedditHiringSignalProvider,
    SourceCandidate,
    ValidationResult,
    VCPortfolioProvider,
    VertexAISearchSignalProvider,
    WellfoundSignalProvider,
    YCCompanyDirectoryProvider,
    compute_provider_yield,
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
    _safe_provider_error,
)
from backend.services.company_discovery import (
    CompanyDiscoveryRunResult,
    CompanySignal,
    CompanySignalResolution,
    normalize_company_signal,
    persist_company_discovery_results,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def disable_env_configured_optional_providers():
    with (
        patch("backend.services.source_discovery.settings.vertex_search_enabled", False),
        patch("backend.services.source_discovery.settings.wellfound_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.common_crawl_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.yc_company_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.vc_portfolio_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.github_org_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.reddit_hiring_discovery_enabled", False),
    ):
        yield


def read_discovery_report(report_dir: Path) -> dict:
    report_files = list(report_dir.glob("source-discovery-report-*.json"))
    assert len(report_files) == 1
    return json.loads(report_files[0].read_text(encoding="utf-8"))


class AsyncStreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class AsyncLineResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self.text.splitlines():
            yield line


def json_response(payload: dict, status_code: int = 200, headers: dict | None = None):
    response = MagicMock()
    response.json.return_value = payload
    response.headers = headers or {}
    response.status_code = status_code
    response.content = json.dumps(payload).encode("utf-8")
    response.text = response.content.decode("utf-8")
    response.raise_for_status.return_value = None
    return response


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
        ("https://boards.greenhouse.io/embed/job_board/js?for=mongodb", ("greenhouse", "mongodb")),
        (
            "https://www.fullstory.com/careers/jobs/110896c1-25d8-4c96-82b4-8f77b1d31bdb?ashby_jid=110896c1-25d8-4c96-82b4-8f77b1d31bdb",
            ("ashby", "fullstory"),
        ),
        ("https://careers.tether.io/o/backend-engineer-wallets-100-remote", ("recruitee", "tether")),
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
    assert normalize_ats_url("https://api.ashbyhq.com/posting-api/job-board/Railway\\", "unit") is None
    assert normalize_ats_url("https://job-boards.greenhouse.io/fal\\", "unit") is None
    assert normalize_ats_url("https://boards-api.greenhouse.io/v1/boards/${ghSlug}/departments/`)", "unit") is None
    assert normalize_ats_url("https://boards.greenhouse.io/embed/job_board/js", "unit") is None
    assert normalize_ats_url("https://careers.tether.io/openings", "unit") is None


def test_safe_provider_error_redacts_credentials_with_whitespace_boundaries():
    error = RuntimeError("failed key=secret api_key=another token=third client_secret=fifth cx=fourth done")

    redacted = _safe_provider_error(error)

    assert "key=secret" not in redacted
    assert "another" not in redacted
    assert "third" not in redacted
    assert "fifth" not in redacted
    assert "fourth" not in redacted
    assert "key=[redacted]" in redacted


def test_company_discovery_migration_defines_signal_registry_shape():
    migration = (BACKEND_ROOT / "db" / "migrations" / "V006__add_company_discovery.sql").read_text(encoding="utf-8")

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
    with (
        patch("backend.services.source_discovery.settings.vertex_search_enabled", False),
        patch("backend.services.source_discovery.settings.wellfound_discovery_enabled", False),
    ):
        providers = default_discovery_providers(tmp_path / "missing-seeds.json")

    assert [provider.name for provider in providers] == ["hn_who_is_hiring", "seed_file"]
    assert isinstance(providers[0], HNWhoIsHiringProvider)
    assert isinstance(providers[1], OptionalSeedProvider)


def test_long_tail_provider_settings_are_safe_by_default():
    from backend.config import settings

    assert settings.github_org_discovery_enabled is False
    assert settings.github_org_token is None
    assert "llm" in settings.github_org_topics
    assert settings.github_org_max_search_queries <= len(settings.github_org_topics.split(","))
    assert settings.reddit_hiring_discovery_enabled is False
    assert settings.reddit_hiring_allow_unauthenticated is False
    assert "MachineLearningJobs" in settings.reddit_hiring_subreddits
    assert settings.discovery_stale_source_days > 0
    assert settings.discovery_repeated_rejection_count > 1


def test_default_discovery_providers_append_enabled_scale_providers(tmp_path):
    with (
        patch("backend.services.source_discovery.settings.vertex_search_enabled", False),
        patch("backend.services.source_discovery.settings.wellfound_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.common_crawl_discovery_enabled", True),
        patch("backend.services.source_discovery.settings.common_crawl_crawl_ids", "CC-MAIN-2026-18"),
        patch("backend.services.source_discovery.settings.yc_company_discovery_enabled", True),
        patch("backend.services.source_discovery.settings.yc_company_import_file", str(tmp_path / "yc.json")),
        patch("backend.services.source_discovery.settings.vc_portfolio_discovery_enabled", True),
        patch("backend.services.source_discovery.settings.vc_portfolio_import_file", str(tmp_path / "vc.json")),
    ):
        providers = default_discovery_providers(tmp_path / "missing-seeds.json")

    assert [provider.name for provider in providers] == [
        "hn_who_is_hiring",
        "seed_file",
        "common_crawl_ats",
        "yc_company_directory",
        "vc_portfolio",
    ]
    assert isinstance(providers[2], CommonCrawlATSProvider)
    assert isinstance(providers[3], YCCompanyDirectoryProvider)
    assert isinstance(providers[4], VCPortfolioProvider)


def test_default_discovery_providers_append_enabled_long_tail_providers(tmp_path):
    with (
        patch("backend.services.source_discovery.settings.github_org_discovery_enabled", True),
        patch("backend.services.source_discovery.settings.github_org_token", None),
        patch("backend.services.source_discovery.settings.reddit_hiring_discovery_enabled", True),
        patch("backend.services.source_discovery.settings.reddit_hiring_allow_unauthenticated", True),
    ):
        providers = default_discovery_providers(tmp_path / "missing-seeds.json")

    assert [provider.name for provider in providers][-2:] == ["github_org_signal", "reddit_hiring_signal"]
    assert isinstance(providers[-2], GitHubOrgSignalProvider)
    assert isinstance(providers[-1], RedditHiringSignalProvider)


@pytest.mark.asyncio
async def test_default_discovery_providers_reports_invalid_vc_targets_json(tmp_path):
    with (
        patch("backend.services.source_discovery.settings.vertex_search_enabled", False),
        patch("backend.services.source_discovery.settings.wellfound_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.common_crawl_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.yc_company_discovery_enabled", False),
        patch("backend.services.source_discovery.settings.vc_portfolio_discovery_enabled", True),
        patch("backend.services.source_discovery.settings.vc_portfolio_targets_json", "{bad json"),
    ):
        providers = default_discovery_providers(tmp_path / "missing-seeds.json")

    assert [provider.name for provider in providers] == ["hn_who_is_hiring", "seed_file", "vc_portfolio"]
    result = await providers[-1].discover()
    diagnostics = result.provider_diagnostics["vc_portfolio"]
    assert diagnostics["status"] == "error"
    assert diagnostics["reason"] == "invalid_vc_portfolio_targets_json"
    assert diagnostics["target_count"] == 0


@pytest.mark.asyncio
async def test_vertex_provider_skips_when_disabled_or_credentials_missing(tmp_path):
    disabled = VertexAISearchSignalProvider(
        enabled=False,
        api_key="key",
        project_id="project",
        engine_id="engine",
        quota_state_file=tmp_path / "quota.json",
    )
    missing = VertexAISearchSignalProvider(enabled=True, quota_state_file=tmp_path / "missing-quota.json")

    disabled_result = await disabled.discover()
    missing_result = await missing.discover()

    assert disabled_result.company_signals == []
    assert disabled_result.provider_diagnostics["vertex_ai_search"]["status"] == "disabled"
    assert missing_result.provider_diagnostics["vertex_ai_search"]["reason"] == "missing_credentials"


@pytest.mark.asyncio
async def test_github_provider_skips_when_disabled_or_caps_zero():
    disabled = GitHubOrgSignalProvider(enabled=False)
    capped = GitHubOrgSignalProvider(enabled=True, max_search_queries=0)

    disabled_result = await disabled.discover()
    capped_result = await capped.discover()

    assert disabled_result.provider_diagnostics["github_org_signal"]["status"] == "disabled"
    assert disabled_result.provider_diagnostics["github_org_signal"]["reason"] == "github_org_discovery_disabled"
    assert capped_result.provider_diagnostics["github_org_signal"]["status"] == "cap_exhausted"
    assert capped_result.company_signals == []


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_github_provider_uses_official_api_and_maps_repo_without_secret_leak(mock_get):
    readme = base64.b64encode(
        b"Careers: https://acme.ai/careers Apply: https://jobs.lever.co/acme"
    ).decode("ascii")
    mock_get.side_effect = [
        json_response(
            {
                "incomplete_results": True,
                "items": [
                    {
                        "full_name": "acme/rag",
                        "html_url": "https://github.com/acme/rag",
                        "homepage": "https://acme.ai",
                        "description": "RAG developer tools",
                        "topics": ["llm", "rag"],
                        "owner": {
                            "login": "acme",
                            "type": "Organization",
                            "html_url": "https://github.com/acme",
                        },
                    }
                ],
            },
            headers={"x-ratelimit-remaining": "29", "x-ratelimit-reset": "1770000000"},
        ),
        json_response({"name": "Acme AI", "blog": "https://acme.ai", "html_url": "https://github.com/acme"}),
        json_response({"html_url": "https://github.com/acme/rag/blob/main/README.md", "content": readme}),
    ]
    provider = GitHubOrgSignalProvider(
        enabled=True,
        token="ghp_secret-token",
        topics=["llm"],
        queries=[],
        max_search_queries=1,
        max_pages_per_query=1,
        max_repos_per_query=1,
        max_orgs_per_run=1,
        max_organization_metadata_fetches=1,
        max_readme_fetches_per_run=1,
    )

    result = await provider.discover()

    assert [signal.provider for signal in result.company_signals] == ["github_org_signal"]
    signal = result.company_signals[0]
    assert signal.company_name == "Acme AI"
    assert signal.company_domain == "acme.ai"
    assert signal.careers_url == "https://acme.ai/careers"
    assert signal.direct_ats_url == "https://jobs.lever.co/acme"
    assert signal.confidence == 0.45
    assert signal.metadata["repository_full_name"] == "acme/rag"
    assert signal.metadata["repository_topics"] == ["llm", "rag"]
    assert signal.metadata["readme_urls"] == [
        "https://acme.ai/careers",
        "https://jobs.lever.co/acme",
    ]
    assert "Careers:" not in json.dumps(signal.metadata)
    diagnostics = result.provider_diagnostics["github_org_signal"]
    assert diagnostics["query_count"] == 1
    assert diagnostics["repository_count"] == 1
    assert diagnostics["organization_count"] == 1
    assert diagnostics["readme_fetch_count"] == 1
    assert diagnostics["incomplete_result_count"] == 1
    assert diagnostics["rate_limit_remaining"] == "29"
    assert "ghp_secret-token" not in json.dumps(diagnostics)
    search_call = mock_get.call_args_list[0]
    assert search_call.args[0] == "https://api.github.com/search/repositories"
    assert search_call.kwargs["params"]["q"] == "topic:llm"
    assert search_call.kwargs["headers"]["Accept"] == "application/vnd.github+json"
    assert search_call.kwargs["headers"]["X-GitHub-Api-Version"] == "2022-11-28"
    assert search_call.kwargs["headers"]["Authorization"] == "Bearer ghp_secret-token"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_github_provider_reports_rate_errors_without_leaking_token(mock_get):
    response = json_response({"message": "secondary rate limit token=ghp_secret"}, status_code=403)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "forbidden token=ghp_secret",
        request=httpx.Request("GET", "https://api.github.com/search/repositories"),
        response=response,
    )
    mock_get.return_value = response
    provider = GitHubOrgSignalProvider(enabled=True, token="ghp_secret", topics=["llm"], queries=[], max_search_queries=1)

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["github_org_signal"]
    assert diagnostics["status"] == "rate_limited"
    assert diagnostics["error_count"] == 1
    assert "ghp_secret" not in json.dumps(diagnostics)


@pytest.mark.asyncio
async def test_github_provider_rejects_user_repos_and_tolerates_missing_topics():
    provider = GitHubOrgSignalProvider(enabled=True)
    provider._fetch_org_metadata = AsyncMock(return_value={"name": "Acme AI", "blog": "https://acme.ai"})
    provider._fetch_readme_urls = AsyncMock(return_value=([], None))

    user_repo = {
        "full_name": "alice/rag",
        "html_url": "https://github.com/alice/rag",
        "owner": {"login": "alice", "type": "User"},
    }
    org_repo = {
        "full_name": "acme/rag",
        "html_url": "https://github.com/acme/rag",
        "homepage": "https://acme.ai",
        "topics": None,
        "owner": {"login": "acme", "type": "Organization", "html_url": "https://github.com/acme"},
    }

    rejected = await provider._signal_from_repo(AsyncMock(), user_repo, "topic:llm", 1)
    signal = await provider._signal_from_repo(AsyncMock(), org_repo, "topic:llm", 2)

    assert rejected is None
    assert provider.diagnostics["rejected_signal_reasons"]["non_organization_owner"] == 1
    assert signal is not None
    assert signal.category_hints == []
    assert signal.metadata["repository_topics"] == []


@pytest.mark.asyncio
async def test_reddit_provider_requires_credentials_or_explicit_unauthenticated_mode():
    provider = RedditHiringSignalProvider(enabled=True, allow_unauthenticated=False)

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["reddit_hiring_signal"]
    assert diagnostics["status"] == "disabled"
    assert diagnostics["reason"] == "missing_credentials"
    assert result.company_signals == []


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
@patch("httpx.AsyncClient.post")
async def test_reddit_provider_does_not_fallback_to_unauthenticated_when_oauth_fails(mock_post, mock_get):
    response = json_response({"error": "invalid_client"}, status_code=401)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "unauthorized client_secret=secret",
        request=httpx.Request("POST", "https://www.reddit.com/api/v1/access_token"),
        response=response,
    )
    mock_post.return_value = response
    provider = RedditHiringSignalProvider(
        enabled=True,
        client_id="client",
        client_secret="secret",
        allow_unauthenticated=False,
    )

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["reddit_hiring_signal"]
    assert diagnostics["status"] == "auth_error"
    assert diagnostics["error_count"] == 1
    assert "client_secret=secret" not in json.dumps(diagnostics)
    assert result.company_signals == []
    mock_get.assert_not_called()


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_reddit_provider_uses_search_api_paginates_and_maps_lower_confidence_signals(mock_get):
    mock_get.side_effect = [
        json_response(
            {
                "data": {
                    "after": "page2",
                    "children": [
                        {
                            "data": {
                                "title": "Acme AI is hiring Python engineers",
                                "subreddit": "PythonJobs",
                                "permalink": "/r/PythonJobs/comments/abc/acme/",
                                "url": "https://acme.ai/careers",
                                "selftext": "Apply at https://jobs.ashbyhq.com/acme",
                                "created_utc": 1770000000,
                                "over_18": False,
                                "removed_by_category": None,
                                "author": "hiring-team",
                            }
                        }
                    ],
                }
            }
        ),
        json_response({"data": {"after": None, "children": []}}),
    ]
    provider = RedditHiringSignalProvider(
        enabled=True,
        allow_unauthenticated=True,
        subreddits=["PythonJobs"],
        search_terms=["hiring"],
        max_pages_per_query=2,
        max_posts_per_query=10,
        max_posts_per_run=10,
        request_delay_seconds=0,
    )

    result = await provider.discover()

    assert [signal.provider for signal in result.company_signals] == ["reddit_hiring_signal"]
    signal = result.company_signals[0]
    assert signal.company_domain == "acme.ai"
    assert signal.careers_url == "https://acme.ai/careers"
    assert signal.direct_ats_url == "https://jobs.ashbyhq.com/acme"
    assert signal.confidence == 0.4
    assert signal.metadata["subreddit"] == "PythonJobs"
    assert "Apply at" not in json.dumps(signal.metadata)
    diagnostics = result.provider_diagnostics["reddit_hiring_signal"]
    assert diagnostics["subreddit_count"] == 1
    assert diagnostics["query_count"] == 1
    assert diagnostics["posts_scanned"] == 1
    assert diagnostics["signals_emitted"] == 1
    first_call = mock_get.call_args_list[0]
    assert first_call.args[0] == "https://www.reddit.com/r/PythonJobs/search.json"
    assert first_call.kwargs["params"] == {
        "q": "hiring",
        "restrict_sr": "1",
        "sort": "new",
        "t": "month",
        "type": "link",
        "limit": 10,
    }
    assert "be-an-ai-engineer" in first_call.kwargs["headers"]["User-Agent"]
    assert mock_get.call_args_list[1].kwargs["params"]["after"] == "page2"
    assert mock_get.call_args_list[1].kwargs["params"]["count"] == 1


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_reddit_provider_records_page_and_post_query_cap_exhaustion(mock_get):
    mock_get.return_value = json_response(
        {
            "data": {
                "after": "next-page",
                "children": [
                    {
                        "data": {
                            "title": "Acme AI is hiring",
                            "subreddit": "PythonJobs",
                            "permalink": "/r/PythonJobs/comments/abc/acme/",
                            "url": "https://acme.ai/careers",
                            "over_18": False,
                        }
                    }
                ],
            }
        }
    )
    provider = RedditHiringSignalProvider(
        enabled=True,
        allow_unauthenticated=True,
        subreddits=["PythonJobs"],
        search_terms=["hiring"],
        max_pages_per_query=1,
        max_posts_per_query=1,
        max_posts_per_run=10,
        request_delay_seconds=0,
    )

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["reddit_hiring_signal"]
    assert "pages_per_query" in diagnostics["cap_exhaustion"]
    assert "posts_per_query" in diagnostics["cap_exhaustion"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_reddit_provider_rejects_mature_removed_and_locatorless_posts(mock_get):
    mock_get.return_value = json_response(
        {
            "data": {
                "children": [
                    {"data": {"title": "mature", "over_18": True, "permalink": "/r/PythonJobs/comments/1"}},
                    {
                        "data": {
                            "title": "removed",
                            "removed_by_category": "moderator",
                            "permalink": "/r/PythonJobs/comments/2",
                        }
                    },
                    {
                        "data": {
                            "title": "Hiring soon but no company locator",
                            "selftext": "DM me",
                            "permalink": "/r/PythonJobs/comments/3",
                            "url": "https://www.reddit.com/r/PythonJobs/comments/3/hiring_soon/",
                            "over_18": False,
                        }
                    },
                ],
                "after": None,
            }
        }
    )
    provider = RedditHiringSignalProvider(
        enabled=True,
        allow_unauthenticated=True,
        subreddits=["PythonJobs"],
        search_terms=["hiring"],
    )

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["reddit_hiring_signal"]
    assert result.company_signals == []
    assert diagnostics["rejected_signal_reasons"] == {
        "mature_or_explicit": 1,
        "deleted_or_removed": 1,
        "missing_company_locator": 1,
    }


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_provider_uses_search_lite_and_maps_results(mock_post, tmp_path):
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {
                "document": {
                    "id": "1",
                    "derivedStructData": {
                        "link": "https://jobs.lever.co/acme",
                        "title": "Acme AI Engineer",
                        "snippet": "Python FastAPI",
                    },
                }
            },
            {
                "document": {
                    "id": "2",
                    "derivedStructData": {
                        "link": "https://example.com/careers",
                        "title": "Example careers",
                        "snippet": "LLM backend roles",
                    },
                }
            },
            {
                "document": {
                    "id": "3",
                    "derivedStructData": {
                        "link": "https://example.org/about",
                        "title": "Example Org",
                        "snippet": "ML platform team",
                    },
                }
            },
        ]
    }
    response.raise_for_status.return_value = None
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["site:jobs.lever.co AI"],
    )

    result = await provider.discover()

    assert mock_post.await_args.args == (
        "https://discoveryengine.googleapis.com/v1/projects/project/locations/global/collections/default_collection/engines/engine/servingConfigs/default_search:searchLite",
    )
    assert mock_post.await_args.kwargs["params"] == {"key": "key"}
    assert mock_post.await_args.kwargs["json"]["query"] == "site:jobs.lever.co AI"
    assert [signal.provider for signal in result.company_signals] == ["vertex_ai_search"] * 3
    assert result.company_signals[0].direct_ats_url == "https://jobs.lever.co/acme"
    assert result.company_signals[1].careers_url == "https://example.com/careers"
    assert result.company_signals[2].company_domain == "example.org"
    assert result.company_signals[0].metadata["queries"][0]["rank"] == 1


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_provider_deduplicates_and_preserves_query_evidence(mock_post, tmp_path):
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {
                "document": {
                    "id": "1",
                    "derivedStructData": {
                        "link": "https://jobs.lever.co/acme",
                        "title": "Acme AI Engineer",
                        "snippet": "Python",
                    },
                }
            }
        ]
    }
    response.raise_for_status.return_value = None
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=2,
        test_monthly_cap=2,
        test_max_queries_per_run=2,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["first query", "second query"],
    )

    result = await provider.discover()

    assert len(result.company_signals) == 1
    assert [item["query"] for item in result.company_signals[0].metadata["queries"]] == [
        "first query",
        "second query",
    ]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_quota_state_survives_provider_instances(mock_post, tmp_path):
    response = MagicMock()
    response.json.return_value = {"results": []}
    response.raise_for_status.return_value = None
    mock_post.return_value = response
    quota_file = tmp_path / "quota.json"

    first = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=quota_file,
        query_templates=["one"],
        date_func=lambda: datetime(2026, 5, 27, tzinfo=timezone.utc),
    )
    second = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=quota_file,
        query_templates=["two"],
        date_func=lambda: datetime(2026, 5, 27, tzinfo=timezone.utc),
    )
    next_day = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=2,
        test_max_queries_per_run=1,
        quota_state_file=quota_file,
        query_templates=["three"],
        date_func=lambda: datetime(2026, 5, 28, tzinfo=timezone.utc),
    )

    await first.discover()
    await second.discover()
    await next_day.discover()

    assert mock_post.await_count == 2
    state = json.loads(quota_file.read_text(encoding="utf-8"))
    assert state["date"] == "2026-05-28"
    assert state["day_used"] == 1
    assert state["month"] == "2026-05"
    assert state["month_used"] == 2


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_provider_reports_api_errors_without_retrying(mock_post, tmp_path):
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "quota",
        request=httpx.Request("POST", "https://discoveryengine.googleapis.com/v1/test:searchLite"),
        response=httpx.Response(403),
    )
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=3,
        test_monthly_cap=3,
        test_max_queries_per_run=2,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one", "two"],
    )

    with pytest.raises(RuntimeError, match="quota_exhausted"):
        await provider.discover()

    assert mock_post.await_count == 1


def test_vertex_provider_uses_test_caps_and_clamps_prod_monthly_cap(tmp_path):
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        prod_mode=False,
        test_monthly_cap=100,
        test_daily_cap=10,
        test_max_queries_per_run=3,
        quota_state_file=tmp_path / "quota.json",
    )
    prod_provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        prod_mode=True,
        prod_monthly_cap=10_000,
        prod_daily_cap=300,
        prod_max_queries_per_run=100,
        quota_state_file=tmp_path / "prod-quota.json",
    )

    assert provider.monthly_cap == 100
    assert provider.daily_cap == 10
    assert provider.max_queries_per_run == 3
    assert prod_provider.monthly_cap == 8000
    assert prod_provider.daily_cap == 300
    assert prod_provider.max_queries_per_run == 100


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_quota_exhaustion_reports_diagnostics_without_signals(mock_post, tmp_path):
    quota_file = tmp_path / "quota.json"
    quota_file.write_text(
        json.dumps({"date": "2026-05-27", "day_used": 1, "month": "2026-05", "month_used": 1}),
        encoding="utf-8",
    )
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=quota_file,
        query_templates=["one"],
        date_func=lambda: datetime(2026, 5, 27, tzinfo=timezone.utc),
    )

    result = await provider.discover()

    assert mock_post.await_count == 0
    assert result.company_signals == []
    assert result.provider_diagnostics["vertex_ai_search"]["status"] == "quota_exhausted"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_respects_max_queries_per_run(mock_post, tmp_path):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": []}
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=10,
        test_monthly_cap=10,
        test_max_queries_per_run=2,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one", "two", "three"],
    )

    result = await provider.discover()

    assert mock_post.await_count == 2
    assert result.provider_diagnostics["vertex_ai_search"]["queries_used"] == 2


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_malformed_payload_reports_provider_error(mock_post, tmp_path):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("bad json with key=secret")
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="secret",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one"],
    )

    with pytest.raises(RuntimeError, match="api_unavailable"):
        await provider.discover()


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_rejects_non_object_or_non_list_results_payload(mock_post, tmp_path):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = []
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="secret",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one"],
    )

    with pytest.raises(RuntimeError, match="api_unavailable"):
        await provider.discover()

    assert provider.diagnostics["reason"] == "malformed_response"

    response.json.return_value = {"results": {"bad": "shape"}}
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="secret",
        project_id="project",
        engine_id="engine",
        test_daily_cap=2,
        test_monthly_cap=2,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "second-quota.json",
        query_templates=["one"],
    )

    with pytest.raises(RuntimeError, match="api_unavailable"):
        await provider.discover()

    assert provider.diagnostics["reason"] == "malformed_response"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_transport_errors_are_isolated_and_sanitized(mock_post, tmp_path):
    mock_post.side_effect = httpx.ConnectError(
        "boom key=secret",
        request=httpx.Request("POST", "https://discoveryengine.googleapis.com/v1/test:searchLite"),
    )
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="secret",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one"],
    )

    with pytest.raises(RuntimeError, match="api_unavailable"):
        await provider.discover()

    assert provider.diagnostics["status"] == "api_unavailable"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_vertex_skips_noise_hosts_when_mapping_generic_results(mock_post, tmp_path):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "results": [
            {"document": {"derivedStructData": {"link": "https://www.linkedin.com/company/acme"}}},
            {"document": {"derivedStructData": {"link": "https://forms.gle/example"}}},
            {"document": {"derivedStructData": {"link": "https://example.com/about"}}},
        ]
    }
    mock_post.return_value = response
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one"],
    )

    result = await provider.discover()

    assert [signal.company_domain for signal in result.company_signals] == ["example.com"]


@pytest.mark.asyncio
async def test_vertex_invalid_quota_state_reports_diagnostics(tmp_path):
    quota_file = tmp_path / "quota.json"
    quota_file.write_text("[]", encoding="utf-8")
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=quota_file,
        query_templates=["one"],
    )

    result = await provider.discover()

    assert result.company_signals == []
    assert result.provider_diagnostics["vertex_ai_search"]["status"] == "quota_state_unavailable"
    assert result.provider_diagnostics["vertex_ai_search"]["reason"] == "invalid_quota_state"


@pytest.mark.asyncio
async def test_vertex_quota_directory_errors_report_diagnostics(tmp_path):
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("x", encoding="utf-8")
    provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="key",
        project_id="project",
        engine_id="engine",
        test_daily_cap=1,
        test_monthly_cap=1,
        test_max_queries_per_run=1,
        quota_state_file=blocking_file / "quota.json",
        query_templates=["one"],
    )

    result = await provider.discover()

    assert result.company_signals == []
    assert result.provider_diagnostics["vertex_ai_search"]["status"] == "quota_state_unavailable"
    assert result.provider_diagnostics["vertex_ai_search"]["reason"] == "quota_state_io_error"


@pytest.mark.asyncio
async def test_wellfound_provider_skips_when_disabled(tmp_path):
    import_file = tmp_path / "wellfound.json"
    import_file.write_text(json.dumps([{"wellfound_url": "https://wellfound.com/company/acme"}]), encoding="utf-8")
    provider = WellfoundSignalProvider(enabled=False, import_file=import_file)

    result = await provider.discover()

    assert result.company_signals == []


@pytest.mark.asyncio
async def test_wellfound_provider_parses_import_file_without_credentials(tmp_path):
    import_file = tmp_path / "wellfound.json"
    import_file.write_text(
        json.dumps(
            [
                {
                    "wellfound_url": "https://wellfound.com/company/acme",
                    "company_name": "Acme",
                    "homepage_url": "https://acme.example",
                    "confidence": 0.7,
                    "category_hints": ["ai", "backend"],
                },
                {"wellfound_url": "not-a-url", "company_name": "Broken"},
            ]
        ),
        encoding="utf-8",
    )
    provider = WellfoundSignalProvider(enabled=True, import_file=import_file)

    result = await provider.discover()

    assert len(result.company_signals) == 2
    assert result.company_signals[0].provider == "wellfound_signal"
    assert result.company_signals[0].evidence_url == "https://wellfound.com/company/acme"
    assert result.company_signals[0].company_domain == "acme.example"
    assert result.company_signals[0].metadata["source_type"] == "import_file"
    assert result.company_signals[1].evidence_url == "not-a-url"


@pytest.mark.asyncio
async def test_wellfound_auto_extract_is_constrained_and_sleeper_injected(tmp_path):
    import_file = tmp_path / "wellfound.json"
    import_file.write_text(
        json.dumps(
            [
                {"wellfound_url": "https://wellfound.com/company/acme"},
                {"wellfound_url": "https://wellfound.com/_jobs/123"},
                {"wellfound_url": "https://wellfound.com/company/bravo?page=2"},
            ]
        ),
        encoding="utf-8",
    )
    html = """
      <html><head><title>Acme | Wellfound</title></head>
      <body><a href="https://acme.example">Homepage</a><p>Job description must not be persisted.</p></body></html>
    """
    sleeps = []

    async def sleeper(delay):
        sleeps.append(delay)

    provider = WellfoundSignalProvider(
        enabled=True,
        import_file=import_file,
        auto_extract_enabled=True,
        max_pages_per_run=2,
        request_delay_seconds=5.0,
        sleeper=sleeper,
    )
    provider._fetch_public_page = AsyncMock(return_value=html)

    result = await provider.discover()

    provider._fetch_public_page.assert_awaited_once()
    assert sleeps == []
    extracted = [signal for signal in result.company_signals if signal.metadata["source_type"] == "public_extract"]
    assert len(extracted) == 1
    assert extracted[0].company_domain == "acme.example"
    assert "Job description" not in json.dumps(extracted[0].metadata)


@pytest.mark.asyncio
async def test_wellfound_auto_extract_enforces_delay_between_allowed_pages(tmp_path):
    import_file = tmp_path / "wellfound.json"
    import_file.write_text(
        json.dumps(
            [
                {"wellfound_url": "https://wellfound.com/company/acme"},
                {"wellfound_url": "https://wellfound.com/company/bravo"},
            ]
        ),
        encoding="utf-8",
    )
    sleeps = []

    async def sleeper(delay):
        sleeps.append(delay)

    provider = WellfoundSignalProvider(
        enabled=True,
        import_file=import_file,
        auto_extract_enabled=True,
        max_pages_per_run=2,
        request_delay_seconds=5.0,
        sleeper=sleeper,
    )
    provider._fetch_public_page = AsyncMock(return_value="<title>Acme | Wellfound</title><a href='https://acme.example'>Home</a>")

    result = await provider.discover()

    assert provider._fetch_public_page.await_count == 2
    assert sleeps == [5.0]
    assert len([signal for signal in result.company_signals if signal.metadata["source_type"] == "public_extract"]) == 2


@pytest.mark.asyncio
async def test_wellfound_auto_extract_failure_preserves_import_signals(tmp_path):
    import_file = tmp_path / "wellfound.json"
    import_file.write_text(
        json.dumps(
            [
                {
                    "wellfound_url": "https://wellfound.com/company/acme",
                    "company_name": "Acme",
                    "homepage_url": "https://acme.example",
                }
            ]
        ),
        encoding="utf-8",
    )
    provider = WellfoundSignalProvider(enabled=True, import_file=import_file, auto_extract_enabled=True)
    provider._fetch_public_page = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    result = await provider.discover()

    assert len(result.company_signals) == 1
    assert result.company_signals[0].metadata["source_type"] == "import_file"
    assert result.provider_diagnostics["wellfound_signal"]["status"] == "partial_error"


@pytest.mark.asyncio
async def test_wellfound_fetch_rejects_disallowed_redirect_and_oversized_body():
    provider = WellfoundSignalProvider(enabled=True, auto_extract_enabled=True)

    class FakeResponse:
        def __init__(self, url, chunks, headers=None):
            self.url = url
            self.chunks = chunks
            self.headers = headers or {}
            self.encoding = "utf-8"

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            for chunk in self.chunks:
                yield chunk

    class FakeStream:
        def __init__(self, response):
            self.response = response

        async def __aenter__(self):
            return self.response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, response):
            self.response = response

        def stream(self, method, url):
            return FakeStream(self.response)

    redirected = FakeResponse("https://example.com/company/acme", [b"ok"])
    with pytest.raises(ValueError, match="redirected_to_disallowed_url"):
        await provider._fetch_public_page(FakeClient(redirected), "https://wellfound.com/company/acme")

    oversized = FakeResponse("https://wellfound.com/company/acme", [b"x" * 500_001])
    with pytest.raises(ValueError, match="response_too_large"):
        await provider._fetch_public_page(FakeClient(oversized), "https://wellfound.com/company/acme")

    malformed_length = FakeResponse("https://wellfound.com/company/acme", [b"ok"], {"content-length": "unknown"})
    with pytest.raises(ValueError, match="invalid_content_length"):
        await provider._fetch_public_page(FakeClient(malformed_length), "https://wellfound.com/company/acme")


def test_wellfound_disallowed_public_urls_are_rejected():
    provider = WellfoundSignalProvider(enabled=True, auto_extract_enabled=True)

    assert provider.is_allowed_public_page("https://wellfound.com/company/acme")
    assert not provider.is_allowed_public_page("https://wellfound.com/_jobs")
    assert not provider.is_allowed_public_page("https://wellfound.com/_jobs/123")
    assert not provider.is_allowed_public_page("https://wellfound.com/jobs")
    assert not provider.is_allowed_public_page("https://wellfound.com/company/acme?jobId=123")
    assert not provider.is_allowed_public_page("https://wellfound.com/company/acme?jobId=")
    assert not provider.is_allowed_public_page("https://wellfound.com/login")


@pytest.mark.asyncio
async def test_common_crawl_provider_skips_when_disabled():
    provider = CommonCrawlATSProvider(enabled=False)

    result = await provider.discover()

    assert result.candidates == []
    assert result.provider_diagnostics["common_crawl_ats"]["status"] == "disabled"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.stream")
@patch("httpx.AsyncClient.get")
async def test_common_crawl_uses_collinfo_cdx_endpoint_and_parses_ndjson(mock_get, mock_stream):
    collinfo_response = MagicMock()
    collinfo_response.json.return_value = [
        {"id": "CC-MAIN-2026-18", "cdx-api": "https://index.commoncrawl.org/cc-main-2026-18-index"}
    ]
    collinfo_response.raise_for_status.return_value = None
    cdx_text = "\n".join(
        [
            json.dumps({"url": "https://boards.greenhouse.io/acme/jobs/123", "status": "200"}),
            "{bad json",
            json.dumps({"url": "https://example.com/careers", "status": "200"}),
            "",
        ]
    )
    mock_get.return_value = collinfo_response
    mock_stream.return_value = AsyncStreamContext(AsyncLineResponse(cdx_text))
    provider = CommonCrawlATSProvider(
        enabled=True,
        crawl_ids=None,
        max_crawls=1,
        url_patterns=["boards.greenhouse.io/*"],
        max_records_per_pattern=5,
        total_record_cap=5,
        request_delay_seconds=0,
    )

    result = await provider.discover()

    assert mock_get.await_args_list[0].args == ("https://index.commoncrawl.org/collinfo.json",)
    assert mock_stream.call_args_list[0].args == ("GET", "https://index.commoncrawl.org/cc-main-2026-18-index")
    assert mock_stream.call_args_list[0].kwargs["params"] == {
        "url": "boards.greenhouse.io/*",
        "output": "json",
        "limit": 5,
        "filter": "=status:200",
        "fl": "url,status,mime,timestamp",
    }
    assert [(candidate.ats, candidate.slug) for candidate in result.candidates] == [("greenhouse", "acme")]
    assert result.candidates[0].discovery_method == "common_crawl_ats"
    assert result.candidates[0].metadata["source_urls"] == ["https://boards.greenhouse.io/acme/jobs/123"]
    assert result.unsupported_urls == ["https://example.com/careers"]
    diagnostics = result.provider_diagnostics["common_crawl_ats"]
    assert diagnostics["crawl_ids_queried"] == ["CC-MAIN-2026-18"]
    assert diagnostics["records_scanned"] == 2
    assert diagnostics["malformed_records"] == 1
    assert diagnostics["candidate_count"] == 1


@pytest.mark.asyncio
@patch("httpx.AsyncClient.stream")
async def test_common_crawl_enforces_total_record_cap(mock_stream):
    cdx_text = "\n".join(
        [
            json.dumps({"url": "https://jobs.lever.co/acme/1"}),
            json.dumps({"url": "https://jobs.lever.co/bravo/1"}),
        ]
    )
    mock_stream.return_value = AsyncStreamContext(AsyncLineResponse(cdx_text))
    provider = CommonCrawlATSProvider(
        enabled=True,
        crawl_ids=["CC-MAIN-2026-18"],
        max_crawls=1,
        url_patterns=["jobs.lever.co/*", "jobs.ashbyhq.com/*"],
        max_records_per_pattern=2,
        total_record_cap=1,
        request_delay_seconds=0,
    )

    result = await provider.discover()

    assert mock_stream.call_count == 1
    diagnostics = result.provider_diagnostics["common_crawl_ats"]
    assert diagnostics["records_scanned"] == 1
    assert diagnostics["cap_exhausted"] is True
    assert [(candidate.ats, candidate.slug) for candidate in result.candidates] == [("lever", "acme")]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_common_crawl_malformed_index_reports_diagnostics(mock_get):
    response = MagicMock()
    response.json.return_value = {"bad": "shape"}
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    provider = CommonCrawlATSProvider(enabled=True, crawl_ids=None, max_crawls=1, request_delay_seconds=0)

    result = await provider.discover()

    assert result.candidates == []
    diagnostics = result.provider_diagnostics["common_crawl_ats"]
    assert diagnostics["status"] == "error"
    assert diagnostics["reason"] == "malformed_index"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.stream")
async def test_common_crawl_transport_errors_are_diagnostics(mock_stream):
    mock_stream.side_effect = httpx.TimeoutException("timeout key=secret")
    provider = CommonCrawlATSProvider(
        enabled=True,
        crawl_ids=["CC-MAIN-2026-18"],
        url_patterns=["jobs.lever.co/*"],
        request_delay_seconds=0,
    )

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["common_crawl_ats"]
    assert diagnostics["status"] == "error"
    assert "secret" not in json.dumps(diagnostics)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.stream")
async def test_common_crawl_rejects_oversized_cdx_responses(mock_stream):
    cdx_text = json.dumps({"url": "https://jobs.lever.co/acme/1"}) + "\n" + ("x" * 100)
    mock_stream.return_value = AsyncStreamContext(AsyncLineResponse(cdx_text))
    provider = CommonCrawlATSProvider(
        enabled=True,
        crawl_ids=["CC-MAIN-2026-18"],
        url_patterns=["jobs.lever.co/*"],
        max_response_bytes=20,
        request_delay_seconds=0,
    )

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["common_crawl_ats"]
    assert diagnostics["status"] == "error"
    assert diagnostics["per_pattern"][0]["errors"] == ["cdx_response_too_large"]


@pytest.mark.asyncio
@patch("httpx.AsyncClient.stream")
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
@patch("backend.services.source_discovery.validate_candidate_source", new_callable=AsyncMock)
async def test_discover_sources_validates_common_crawl_candidates_through_parser_path(
    mock_validate,
    mock_persist,
    mock_persist_company,
    mock_stream,
    tmp_path,
):
    cdx_text = json.dumps({"url": "https://jobs.lever.co/acme/1"})
    mock_stream.return_value = AsyncStreamContext(AsyncLineResponse(cdx_text))

    async def fake_validate(candidate):
        return ValidationResult(candidate, "validated", job_count=1, usable_job_count=1, relevant_job_count=1)

    mock_validate.side_effect = fake_validate
    provider = CommonCrawlATSProvider(
        enabled=True,
        crawl_ids=["CC-MAIN-2026-18"],
        url_patterns=["jobs.lever.co/*"],
        request_delay_seconds=0,
    )

    result = await discover_sources(MagicMock(), providers=[provider], report_dir=tmp_path)

    assert result.validated_count == 1
    validated_candidate = mock_validate.await_args.args[0]
    assert validated_candidate.discovery_method == "common_crawl_ats"
    assert (validated_candidate.ats, validated_candidate.slug) == ("lever", "acme")
    mock_persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_yc_provider_import_maps_signals_and_rejections(tmp_path):
    import_file = tmp_path / "yc.json"
    import_file.write_text(
        json.dumps(
            {
                "companies": [
                    {
                        "name": "Acme AI",
                        "website": "https://acme.example",
                        "yc_url": "https://www.ycombinator.com/companies/acme-ai",
                        "tags": ["AI", "Developer Tools"],
                        "batch": "S25",
                        "status": "Active",
                    },
                    {
                        "name": "Name Only",
                        "yc_url": "https://www.ycombinator.com/companies/name-only",
                    },
                    {"name": "Broken", "website": "not-a-url", "yc_url": "not-a-url"},
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = YCCompanyDirectoryProvider(enabled=True, import_file=import_file, categories=["ai"], max_total_companies=10)

    result = await provider.discover()

    assert len(result.company_signals) == 1
    signal = result.company_signals[0]
    assert signal.provider == "yc_company_directory"
    assert signal.company_name == "Acme AI"
    assert signal.company_domain == "acme.example"
    assert signal.evidence_url == "https://www.ycombinator.com/companies/acme-ai"
    assert signal.category_hints == ["AI", "Developer Tools"]
    assert signal.metadata["batch"] == "S25"
    diagnostics = result.provider_diagnostics["yc_company_directory"]
    assert diagnostics["status"] == "ok"
    assert diagnostics["category_counts"]["ai"] == 1
    assert diagnostics["rejected_signal_reasons"]["missing_company_locator"] == 1
    assert diagnostics["rejected_signal_reasons"]["invalid_evidence_url"] == 1


@pytest.mark.asyncio
async def test_yc_public_extraction_is_bounded_and_uses_no_logged_in_paths():
    html = """
      <a href="/companies/acme-ai">Acme AI</a>
      <a href="https://acme.example">Home</a>
      <a href="/jobs">Work at a Startup</a>
    """
    provider = YCCompanyDirectoryProvider(enabled=True, categories=["ai"], max_total_companies=5)
    provider._fetch_public_category = AsyncMock(return_value=html)

    result = await provider.discover()

    provider._fetch_public_category.assert_awaited_once()
    assert result.company_signals[0].provider == "yc_company_directory"
    assert result.company_signals[0].company_domain == "acme.example"
    assert result.provider_diagnostics["yc_company_directory"]["category_counts"]["ai"] == 1
    assert "/jobs" not in json.dumps(result.company_signals[0].metadata)


@pytest.mark.asyncio
async def test_vc_portfolio_import_maps_signals_rejections_and_caps(tmp_path):
    import_file = tmp_path / "vc.json"
    import_file.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "firm": "a16z",
                        "portfolio_url": "https://a16z.com/portfolio",
                        "companies": [
                            {"name": "Acme", "homepage_url": "https://acme.example"},
                            {"name": "Name Only"},
                            {"name": "Ignored", "homepage_url": "https://ignored.example"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = VCPortfolioProvider(enabled=True, import_file=import_file, max_companies_per_target=2)

    result = await provider.discover()

    assert len(result.company_signals) == 1
    signal = result.company_signals[0]
    assert signal.provider == "vc_portfolio"
    assert signal.company_name == "Acme"
    assert signal.company_domain == "acme.example"
    assert signal.evidence_url == "https://a16z.com/portfolio"
    assert signal.metadata["vc_firm"] == "a16z"
    diagnostics = result.provider_diagnostics["vc_portfolio"]
    assert diagnostics["target_count"] == 1
    assert diagnostics["per_target"][0]["cap_exhausted"] is True
    assert diagnostics["rejected_signal_reasons"]["missing_company_locator"] == 1


@pytest.mark.asyncio
async def test_vc_public_extracts_homepages_with_response_caps():
    html = """
      <a href="https://acme.example">Acme</a>
      <a href="https://jobs.lever.co/acme">Jobs</a>
      <a href="/talent">Talent</a>
    """
    provider = VCPortfolioProvider(
        enabled=True,
        targets=[{"firm": "Conviction", "url": "https://conviction.com/portfolio"}],
        max_companies_per_target=5,
    )
    provider._fetch_portfolio_page = AsyncMock(return_value=html)

    result = await provider.discover()

    assert [signal.company_domain for signal in result.company_signals if signal.company_domain] == ["acme.example"]
    assert [signal.direct_ats_url for signal in result.company_signals if signal.direct_ats_url] == [
        "https://jobs.lever.co/acme"
    ]
    assert result.company_signals[0].metadata["source_type"] == "public_extract"
    assert result.provider_diagnostics["vc_portfolio"]["target_count"] == 1


@pytest.mark.asyncio
async def test_vc_malformed_import_json_reports_provider_diagnostics(tmp_path):
    import_file = tmp_path / "vc.json"
    import_file.write_text("{bad json", encoding="utf-8")
    provider = VCPortfolioProvider(enabled=True, import_file=import_file)

    result = await provider.discover()

    diagnostics = result.provider_diagnostics["vc_portfolio"]
    assert diagnostics["status"] == "error"
    assert diagnostics["reason"] == "invalid_import_file"
    assert "Invalid discovery import JSON" in diagnostics["last_error"]


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.resolve_company_signal", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_resolves_yc_and_vc_provider_signals(
    mock_persist,
    mock_persist_company,
    mock_resolve,
    tmp_path,
):
    yc_import = tmp_path / "yc.json"
    yc_import.write_text(
        json.dumps(
            {
                "companies": [
                    {
                        "name": "Acme AI",
                        "website": "https://acme.example",
                        "yc_url": "https://www.ycombinator.com/companies/acme-ai",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    vc_import = tmp_path / "vc.json"
    vc_import.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "firm": "a16z",
                        "portfolio_url": "https://a16z.com/portfolio",
                        "companies": [{"name": "Bravo", "homepage_url": "https://bravo.example"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def unresolved(signal):
        return CompanySignalResolution(signal=signal, status="unresolved", rejection_reason="no_canonical_source_found")

    mock_resolve.side_effect = unresolved
    providers = [
        YCCompanyDirectoryProvider(enabled=True, import_file=yc_import, categories=["ai"]),
        VCPortfolioProvider(enabled=True, import_file=vc_import),
    ]

    result = await discover_sources(MagicMock(), providers=providers, report_dir=tmp_path)

    assert result.company_signal_counts["counts_by_provider"] == {
        "yc_company_directory": 1,
        "vc_portfolio": 1,
    }
    assert mock_resolve.await_count == 2
    mock_persist_company.assert_awaited_once()
    report = read_discovery_report(tmp_path)
    assert report["company_signals"]["provider_diagnostics"]["yc_company_directory"]["signals_emitted"] == 1
    assert report["company_signals"]["provider_diagnostics"]["vc_portfolio"]["signals_emitted"] == 1


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


class ProviderYieldCursor:
    def __init__(self, row_sets):
        self.row_sets = row_sets
        self.executed = []
        self.index = -1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.executed.append((query, vars))
        self.index += 1

    async def fetchall(self):
        return self.row_sets[self.index]


class ProviderYieldConn:
    def __init__(self, row_sets):
        self.cursor_obj = ProviderYieldCursor(row_sets)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return self.cursor_obj


class ProviderYieldPool:
    def __init__(self, row_sets):
        self.conn = ProviderYieldConn(row_sets)

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
    run_started_at = datetime(2026, 5, 28, tzinfo=timezone.utc)

    with patch("backend.services.source_discovery.settings.discovery_stale_source_days", 30):
        counts = await get_source_freshness_counts(pool, run_started_at, validated_within_current_run=5)

    assert counts == {
        "never_validated": 2,
        "validated_within_current_run": 5,
        "stale": 3,
        "inactive": 4,
    }
    assert "last_validated_at < %s" in pool.conn.cursor_obj.executed[0][0]
    assert pool.conn.cursor_obj.executed[0][1] == (run_started_at - timedelta(days=30),)


@pytest.mark.asyncio
async def test_compute_provider_yield_combines_run_data_registry_and_disabled_providers():
    pool = ProviderYieldPool(
        [
            [("seed_file", 3, 1, 2, datetime(2026, 5, 1, tzinfo=timezone.utc))],
            [("seed_file", "blocked_provider", 4, datetime(2026, 5, 2, tzinfo=timezone.utc))],
            [("github_org_signal", datetime(2026, 5, 3, tzinfo=timezone.utc))],
        ]
    )
    validation = ValidationResult(
        SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "seed_file"),
        "validated",
    )
    signal = CompanySignal(
        provider="github_org_signal",
        evidence_url="https://github.com/acme/rag",
        company_domain="acme.ai",
    )
    company_result = CompanyDiscoveryRunResult(
        signals=[signal],
        resolutions=[
            CompanySignalResolution(signal=signal, status="rejected", rejection_reason="no_canonical_source_found")
        ],
        provider_diagnostics={
            "github_org_signal": {"status": "ok", "rate_limit_remaining": "28"},
            "reddit_hiring_signal": {"status": "disabled", "reason": "reddit_hiring_discovery_disabled"},
        },
    )

    provider_yield = await compute_provider_yield(
        pool,
        ["seed_file", "github_org_signal"],
        [validation],
        company_result,
        {"github_org_signal": 2},
        active_source_count_before_run=2,
        active_source_count_after_run=4,
    )

    assert set(provider_yield["providers"]) == {"seed_file", "github_org_signal", "reddit_hiring_signal"}
    assert provider_yield["providers"]["seed_file"]["candidate_count"] == 1
    assert provider_yield["providers"]["seed_file"]["validated_active_source_count"] == 3
    assert provider_yield["providers"]["seed_file"]["stale_source_count"] == 1
    assert provider_yield["providers"]["seed_file"]["inactive_source_count"] == 2
    assert provider_yield["providers"]["seed_file"]["repeated_rejection_count"] == 4
    assert provider_yield["providers"]["github_org_signal"]["signals_emitted"] == 1
    assert provider_yield["providers"]["github_org_signal"]["unsupported_url_count"] == 2
    assert provider_yield["providers"]["github_org_signal"]["rejected_count"] == 1
    assert provider_yield["providers"]["reddit_hiring_signal"]["cap_quota_status"]["reason"] == "reddit_hiring_discovery_disabled"
    assert provider_yield["summary"]["active_source_growth_since_previous_run"] == 2
    assert "seed_file" in provider_yield["summary"]["high_yield_providers"]


@pytest.mark.asyncio
async def test_compute_provider_yield_does_not_double_count_existing_company_signal_validation():
    candidate = SourceCandidate(
        "Acme",
        "greenhouse",
        "acme",
        "https://boards.greenhouse.io/acme",
        "github_org_signal",
    )
    validation = ValidationResult(candidate, "validated")
    signal = CompanySignal(
        provider="github_org_signal",
        evidence_url="https://github.com/acme/rag",
        direct_ats_url="https://boards.greenhouse.io/acme",
    )
    company_result = CompanyDiscoveryRunResult(
        signals=[signal],
        resolutions=[
            CompanySignalResolution(
                signal=signal,
                status="resolved",
                resolved_candidate=candidate,
                validation_result=validation,
            )
        ],
        provider_diagnostics={
            "github_org_signal": {
                "status": "partial_error",
                "error_count": 2,
                "unsupported_url_count": 3,
            }
        },
    )

    provider_yield = await compute_provider_yield(
        MagicMock(),
        ["github_org_signal"],
        [validation],
        company_result,
        active_source_count_before_run=1,
        active_source_count_after_run=1,
        active_source_keys_before_run={("greenhouse", "acme")},
    )

    metrics = provider_yield["providers"]["github_org_signal"]
    assert metrics["validated_active_source_count"] == 1
    assert metrics["newly_activated_source_count"] == 0
    assert metrics["resolved_count"] == 1
    assert metrics["error_count"] == 2
    assert metrics["unsupported_url_count"] == 3


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
async def test_persist_company_discovery_results_serializes_provider_yield_datetimes():
    signal = CompanySignal(provider="unit", evidence_url="https://example.com/evidence", company_domain="example.com")
    result = CompanyDiscoveryRunResult(
        signals=[signal],
        provider_yield={
            "providers": {
                "unit": {
                    "last_seen_at": datetime(2026, 5, 28, tzinfo=timezone.utc),
                }
            }
        },
    )
    pool = PersistPool()

    await persist_company_discovery_results(pool, result, 1.25, None)

    run_insert = next(call for call in pool.conn.cursor_obj.execute_calls if "INSERT INTO company_discovery_runs" in call[0])
    metadata = json.loads(run_insert[1][7])
    assert metadata["provider_yield"]["providers"]["unit"]["last_seen_at"] == "2026-05-28 00:00:00+00:00"


@pytest.mark.asyncio
@patch("backend.services.source_discovery.discover_from_hn", new_callable=AsyncMock)
@patch("backend.services.source_discovery.discover_from_seed_file", new_callable=AsyncMock)
@patch("backend.services.source_discovery.expand_careers_page_once", new_callable=AsyncMock)
@patch("backend.services.source_discovery.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
async def test_discover_sources_deduplicates_and_writes_report(
    mock_persist_company,
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
    assert report["company_signals"]["provider_diagnostics"]["vertex_ai_search"]["status"] == "disabled"
    assert report["company_signals"]["provider_diagnostics"]["wellfound_signal"]["status"] == "disabled"
    assert report["company_signals"]["provider_yield"]["providers"]["vertex_ai_search"]["cap_quota_status"]["status"] == "disabled"
    assert "github_org_signal" in report["company_signals"]["provider_yield"]["providers"]
    mock_persist_company.assert_awaited_once()


@pytest.mark.asyncio
@patch("backend.services.source_discovery.expand_careers_page_once", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_filters_obvious_noise_from_unsupported_counts(
    mock_persist,
    mock_expand,
    tmp_path,
):
    class GenericProvider:
        name = "generic_test"

        async def discover(self):
            return DiscoveryProviderResult(
                generic_urls=[
                    ("https://www.linkedin.com/in/example", None, "generic_test"),
                    ("https://forms.gle/example", None, "generic_test"),
                    ("https://example.com/careers", None, "generic_test"),
                ]
            )

    mock_expand.return_value = []

    result = await discover_sources(MagicMock(), providers=[GenericProvider()], report_dir=tmp_path)

    assert result.unsupported_url_count == 1
    assert result.rejected_count == 1
    assert result.validation_results[0].candidate.source_url == "https://example.com/careers"
    report = read_discovery_report(tmp_path)
    assert report["unsupported_url_count"] == 1


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
async def test_discover_sources_preserves_vertex_failure_diagnostics(
    mock_persist,
    mock_persist_company,
    mock_post,
    tmp_path,
):
    class NoopProvider:
        name = "noop"

        async def discover(self):
            return DiscoveryProviderResult()

    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "quota key=secret",
        request=httpx.Request("POST", "https://discoveryengine.googleapis.com/v1/test:searchLite?key=secret"),
        response=httpx.Response(403),
    )
    mock_post.return_value = response
    vertex_provider = VertexAISearchSignalProvider(
        enabled=True,
        api_key="secret",
        project_id="project",
        engine_id="engine",
        test_daily_cap=3,
        test_monthly_cap=3,
        test_max_queries_per_run=1,
        quota_state_file=tmp_path / "quota.json",
        query_templates=["one"],
    )

    result = await discover_sources(
        MagicMock(),
        providers=[NoopProvider(), vertex_provider],
        report_dir=tmp_path,
    )

    diagnostics = result.company_signal_counts["provider_diagnostics"]["vertex_ai_search"]
    assert diagnostics["status"] == "quota_exhausted"
    assert diagnostics["queries_used"] == 1
    assert diagnostics["last_error"] == "quota_exhausted"
    assert "secret" not in json.dumps(result.company_signal_counts)
    mock_persist_company.assert_awaited_once()


@pytest.mark.asyncio
@patch("backend.services.source_discovery.discover_from_hn", new_callable=AsyncMock)
@patch("backend.services.source_discovery.discover_from_seed_file", new_callable=AsyncMock)
@patch("backend.services.source_discovery.expand_careers_page_once", new_callable=AsyncMock)
@patch("backend.services.source_discovery.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_discovery_result", new_callable=AsyncMock)
@patch("backend.services.source_discovery.persist_company_discovery_results", new_callable=AsyncMock)
async def test_discover_sources_expands_hn_generic_urls_with_hn_method(
    mock_persist_company,
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
