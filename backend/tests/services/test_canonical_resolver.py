from unittest.mock import AsyncMock, patch

import pytest

from backend.services.canonical_resolver import (
    build_bounded_company_urls,
    extract_jobposting_json_ld,
    parse_sitemap_locations,
    resolve_company_signal,
)
from backend.services.company_discovery import CompanySignal
from backend.services.source_discovery import ValidationResult, SourceCandidate


class MockStreamResponse:
    def __init__(self, text="", headers=None, error=None):
        self.text = text
        self.headers = headers if headers is not None else {"content-length": str(len(text))}
        self.error = error
        self.encoding = "utf-8"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self):
        if self.error:
            raise self.error

    async def aiter_bytes(self):
        yield self.text.encode("utf-8")


def test_build_bounded_company_urls_limits_candidate_paths():
    urls = build_bounded_company_urls("https://example.com/about")

    assert urls == [
        "https://example.com/careers",
        "https://example.com/jobs",
        "https://example.com/join-us",
        "https://example.com/work-with-us",
        "https://example.com/company/careers",
    ]


def test_parse_sitemap_locations_caps_and_filters_to_company_host():
    sitemap_xml = """
    <urlset>
      <url><loc>https://example.com/careers</loc></url>
      <url><loc>https://example.com/jobs</loc></url>
      <url><loc>https://other.example/jobs</loc></url>
    </urlset>
    """

    urls = parse_sitemap_locations(sitemap_xml, "example.com", limit=1)

    assert urls == ["https://example.com/careers"]


def test_extract_jobposting_json_ld_handles_graph_and_plain_objects():
    html = """
    <script type="application/ld+json">
    {"@graph": [{"@type": "Organization"}, {"@type": "JobPosting", "title": "AI Engineer"}]}
    </script>
    <script type="application/ld+json">{"@type": "JobPosting", "title": "ML Engineer"}</script>
    """

    postings = extract_jobposting_json_ld(html)

    assert [posting["title"] for posting in postings] == ["AI Engineer", "ML Engineer"]


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.canonical_resolver.httpx.AsyncClient.stream")
async def test_resolve_company_signal_validates_supported_ats_before_activation(mock_stream, mock_validate):
    response = MockStreamResponse('<a href="https://boards.greenhouse.io/acme">Jobs</a>')
    mock_stream.return_value = response
    candidate = SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "company_signal")
    mock_validate.return_value = ValidationResult(candidate, "validated", job_count=2, usable_job_count=2)

    result = await resolve_company_signal(
        CompanySignal(
            provider="unit",
            evidence_url="https://example.com/list",
            company_name="Acme",
            company_domain="example.com",
        )
    )

    assert result.status == "resolved"
    assert result.validation_result is mock_validate.return_value
    assert result.resolved_candidate is not None
    assert result.resolved_candidate.ats == "greenhouse"
    assert mock_validate.await_args.args[0].discovery_method == "unit"


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.canonical_resolver.httpx.AsyncClient.stream")
async def test_resolve_company_signal_continues_after_bounded_page_fetch_failure(mock_stream, mock_validate):
    failed_response = MockStreamResponse(error=RuntimeError("not found"))
    success_response = MockStreamResponse('<a href="https://boards.greenhouse.io/acme">Jobs</a>')
    robots_response = MockStreamResponse("")

    def response_for_url(url, *args, **kwargs):
        if args and args[0] in {"https://example.com/careers", "https://example.com/jobs"}:
            url = args[0]
        if url == "https://example.com/careers":
            return failed_response
        if url == "https://example.com/jobs":
            return success_response
        return robots_response

    mock_stream.side_effect = response_for_url
    candidate = SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "company_signal")
    mock_validate.return_value = ValidationResult(candidate, "validated", job_count=2, usable_job_count=2)

    result = await resolve_company_signal(
        CompanySignal(
            provider="unit",
            evidence_url="https://example.com/list",
            company_name="Acme",
            careers_url="https://example.com/careers",
            company_domain="example.com",
        )
    )

    assert result.status == "resolved"
    fetched_urls = [call.args[1] for call in mock_stream.call_args_list]
    assert "https://example.com/careers" in fetched_urls
    assert "https://example.com/jobs" in fetched_urls
    assert result.resolved_candidate is not None
    assert result.resolved_candidate.slug == "acme"


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.httpx.AsyncClient.stream")
async def test_resolve_company_signal_persists_json_ld_as_evidence_only(mock_stream):
    response = MockStreamResponse('<script type="application/ld+json">{"@type":"JobPosting","title":"AI Engineer"}</script>')
    mock_stream.return_value = response

    result = await resolve_company_signal(
        CompanySignal(
            provider="unit",
            evidence_url="https://example.com/list",
            company_name="Acme",
            careers_url="https://example.com/careers",
        )
    )

    assert result.status == "unresolved"
    assert result.rejection_reason == "json_ld_unvalidated"
    assert result.json_ld_evidence[0]["title"] == "AI Engineer"


@pytest.mark.asyncio
@patch("backend.services.canonical_resolver.validate_candidate_source", new_callable=AsyncMock)
@patch("backend.services.canonical_resolver.httpx.AsyncClient.stream")
async def test_resolve_company_signal_returns_validation_rejection_reason(mock_stream, mock_validate):
    response = MockStreamResponse('<a href="https://boards.greenhouse.io/acme">Jobs</a>')
    mock_stream.return_value = response
    candidate = SourceCandidate("Acme", "greenhouse", "acme", "https://boards.greenhouse.io/acme", "company_signal")
    mock_validate.return_value = ValidationResult(candidate, "rejected", rejection_reason="empty_provider")

    result = await resolve_company_signal(
        CompanySignal(
            provider="unit",
            evidence_url="https://example.com/list",
            company_name="Acme",
            careers_url="https://example.com/careers",
        )
    )

    assert result.status == "rejected"
    assert result.rejection_reason == "empty_provider"
