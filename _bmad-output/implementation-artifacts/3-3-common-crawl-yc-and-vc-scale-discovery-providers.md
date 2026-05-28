# Story 3.3: Common Crawl, YC, and VC Scale Discovery Providers

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want scale-oriented discovery providers to find direct ATS boards and relevant startup/company domains,
so that the scanner can grow beyond a small set of obvious companies without relying on manual seeds.

## Product Context

Story 3.1 created the company-signal registry, canonical resolver, and validation-gated activation path. Story 3.2 added optional search and Wellfound providers on top of that path. This story adds scale-oriented discovery:

- Common Crawl discovers direct public ATS board URLs at larger scale.
- YC discovers startup/company domains from public YC company surfaces.
- VC portfolio providers discover company domains from configured public portfolio pages.

The trust boundary is unchanged. Common Crawl may produce direct `SourceCandidate` rows, but those candidates must be validated by existing ATS parser adapters before activation. YC and VC providers produce `CompanySignal` evidence only; their outputs must pass canonical source resolution before any source reaches active `job_sources`.

## Acceptance Criteria

1. **Common Crawl ATS Provider Is Capped And Index-Aware**
   - Given Common Crawl indexes are reachable
   - When `CommonCrawlATSProvider` runs
   - Then it fetches the current crawl index list from `https://index.commoncrawl.org/collinfo.json` or uses explicitly configured crawl IDs
   - And it queries only capped URL patterns for supported ATS hosts: Greenhouse, Lever, Ashby, Workable, Recruitee, and Personio
   - And it uses each crawl's `cdx-api` endpoint from `collinfo.json` when present rather than constructing brittle endpoint URLs manually
   - And every query uses hard limits for number of crawls, patterns, records per pattern, total records per run, request timeout, and optional delay between requests
   - And it parses CDX `output=json` responses as newline-delimited JSON records suitable for URL analysis, not as a single JSON array
   - And it does not download WARC content or use `filename`/`offset`/`length` retrieval in this story
   - And provider failure, index unavailability, or quota/cap exhaustion is recorded in provider diagnostics without aborting the whole discovery run unless all configured providers fail.

2. **Common Crawl Direct ATS Hits Reuse Existing SourceCandidate Flow**
   - Given Common Crawl returns ATS URLs
   - When provider output is processed
   - Then URLs are normalized with existing `normalize_ats_url`
   - And candidates are deduplicated by `(ats, slug)` via existing `dedupe_candidates`
   - And discovered URLs are preserved in candidate metadata as source evidence
   - And candidates validate through existing `validate_candidate_source` parser adapters before activation
   - And unsupported, malformed, non-HTTP(S), and noisy URLs become rejected/unsupported diagnostics rather than exceptions.

3. **YC Company Directory Provider Emits Company Signals Only**
   - Given YC company discovery is enabled
   - When `YCCompanyDirectoryProvider` runs
   - Then it extracts company name, website/homepage, YC evidence URL, tags, batch/category/status if visible, and category hints for selected public YC categories including AI, developer tools, infrastructure, data engineering, databases, open source, and search
   - And it never uses logged-in-only Work at a Startup flows, browser automation, session cookies, or third-party unofficial YC APIs as required runtime dependencies
   - And if the public YC HTML/data shape is unavailable, the provider records diagnostics and supports a committed/user-provided JSON import file with the same output contract
   - And company-name-only rows without website, bounded careers URL, or direct ATS URL are skipped or rejected with visible diagnostics because they cannot pass the existing `CompanySignal` locator contract
   - And all valid outputs use provider name `yc_company_directory` and become `CompanySignal` records for canonical resolution only.

4. **VC Portfolio Providers Are Configured, Capped, And Evidence-Only**
   - Given VC portfolio discovery is enabled
   - When `VCPortfolioProvider` runs
   - Then it reads a configurable list of public portfolio pages, initially covering a16z, Sequoia, Index, Accel, Greylock, Lightspeed, and Conviction
   - And each portfolio target has per-page caps, timeout, maximum response size, and provider metadata identifying the VC firm and source URL
   - And the provider extracts company names and homepage URLs where available
   - And company-name-only rows without homepage, bounded careers URL, or direct ATS URL are skipped or rejected with visible diagnostics because they cannot pass the existing `CompanySignal` locator contract
   - And portfolio job-board or talent links are treated only as evidence unless they point to a supported ATS URL and still pass existing validation
   - And all company/domain outputs use provider name `vc_portfolio` and become `CompanySignal` records for canonical resolution only.

5. **Provider Registration Preserves Existing Discovery Orchestration**
   - Given default source discovery is configured
   - When `default_discovery_providers()` builds provider order
   - Then Common Crawl, YC, and VC providers are appended only when enabled/configured
   - And existing HN, seed, Vertex AI Search, and Wellfound behavior remains unchanged
   - And provider diagnostics from disabled, capped, exhausted, malformed, or unavailable providers are included in `company_signals.provider_diagnostics` in the discovery report.

6. **Configuration Is Explicit And Safe By Default**
   - Given the FastAPI app starts without optional discovery credentials/config
   - When settings load
   - Then new provider settings default to disabled or conservative caps
   - And missing optional config does not prevent app startup
   - And `.env.example` documents every new setting without secrets
   - And durable cap/crawl state, if needed, is stored under `_bmad-output/implementation-artifacts/` rather than `/tmp`.

7. **Diagnostics And Report Coverage Include Scale Providers**
   - Given discovery completes
   - When `source-discovery-report-YYYY-MM-DD.json` is written
   - Then report fields from Stories 2.5, 3.1, and 3.2 remain backward-compatible
   - And provider diagnostics include Common Crawl crawl IDs queried, pattern counts, records scanned, candidate counts, cap-exhausted states, YC category counts, VC target counts, and provider errors
   - And `GET /api/v1/ingest/company-signals` exposes YC and VC provider metadata, status, resolved source metadata, rejection reasons, and last error.

8. **Tests Cover Contracts, Caps, Boundaries, And Regression**
   - Given implementation is complete
   - When targeted backend tests run
   - Then tests cover Common Crawl disabled/configured states, crawl-index selection, CDX request shape, cap enforcement, malformed index responses, transport errors, URL normalization, dedupe, unsupported URL rejection, and parser-validation gating
   - And tests cover YC import/public extraction mapping, category hints, malformed rows, no logged-in WaaS usage, and canonical-resolution integration
   - And tests cover VC config parsing, per-target diagnostics, extraction mapping, unsupported portfolio links, cap behavior, and canonical-resolution integration
   - And existing source discovery, canonical resolver, ingest router, scheduler, parser, and corpus sanity tests continue passing.

## Tasks / Subtasks

- [x] Task 1: Add provider configuration and safe defaults (AC: 1, 3, 4, 6)
  - [x] Extend `backend/config.py` with explicit settings for `common_crawl_discovery_enabled`, crawl IDs, max crawls, max records per pattern, total record cap, timeout, delay, `yc_company_discovery_enabled`, YC categories/import file/cap, `vc_portfolio_discovery_enabled`, VC portfolio config/import file/caps.
  - [x] Update `.env.example` with conservative disabled defaults and no secrets.
  - [x] Store any durable provider state or fixture-like runtime output under `_bmad-output/implementation-artifacts/`.
  - [x] Ensure absent optional provider settings do not block app startup.

- [x] Task 2: Implement `CommonCrawlATSProvider` (AC: 1, 2, 5, 7)
  - [x] Add provider code in `backend/services/source_discovery.py` unless the file becomes too large; if split, keep imports simple and preserve existing public contracts.
  - [x] Fetch `collinfo.json` only when enabled and no explicit crawl IDs are configured.
  - [x] Query URL patterns from the source discovery strategy: `boards.greenhouse.io/*`, `job-boards.greenhouse.io/*`, `jobs.lever.co/*`, `jobs.ashbyhq.com/*`, `apply.workable.com/*`, `*.recruitee.com/*`, `*.jobs.personio.de/*`, and `*.jobs.personio.com/*`.
  - [x] Use CDX params such as `url`, `output=json`, `limit`, optional exact filter `filter==status:200`, and `fl=url,status,mime,timestamp` where supported; do not download WARC records.
  - [x] Parse CDX `output=json` as newline-delimited JSON, tolerating blank lines and malformed records by counting rejected diagnostics instead of failing the full provider.
  - [x] Convert returned `url` values through `normalize_ats_url("common_crawl_ats")`.
  - [x] Return `DiscoveryProviderResult(candidates=..., unsupported_urls=..., provider_diagnostics=...)`.
  - [x] Preserve per-pattern diagnostics: crawl ID, URL pattern, records returned, candidates emitted, unsupported count, cap status, and errors.

- [x] Task 3: Implement `YCCompanyDirectoryProvider` (AC: 3, 5, 7)
  - [x] Use provider name `yc_company_directory`.
  - [x] Support a JSON import path first so tests and local runs are stable even if YC public HTML changes.
  - [x] Add bounded public extraction only when enabled/configured; use `httpx.AsyncClient`, standard-library parsing, strict timeout, max response size, and category/company caps.
  - [x] Extract only company name, website/homepage/domain, YC evidence URL, tags/category hints, and visible metadata needed for diagnostics.
  - [x] Skip or reject name-only rows with `missing_company_locator` diagnostics unless a website, bounded careers URL, or direct supported ATS URL is available.
  - [x] Emit `CompanySignal` records, not `SourceCandidate`s, unless a direct supported ATS URL is explicitly visible and still goes through canonical validation.
  - [x] Record malformed rows as rejected signal diagnostics, not unhandled exceptions.

- [x] Task 4: Implement `VCPortfolioProvider` (AC: 4, 5, 7)
  - [x] Use provider name `vc_portfolio`.
  - [x] Support configured portfolio targets and an import-file path for deterministic local use.
  - [x] Add default target names for a16z, Sequoia, Index, Accel, Greylock, Lightspeed, and Conviction without hardcoding brittle assumptions about exact HTML structure.
  - [x] Fetch public portfolio pages only with strict timeout, response-size cap, per-target caps, and no browser automation.
  - [x] Extract company names and homepage URLs using existing URL/HTML helpers where practical; avoid new dependencies such as BeautifulSoup, lxml, Playwright, Selenium, or Scrapy.
  - [x] Skip or reject name-only rows with `missing_company_locator` diagnostics unless a homepage, bounded careers URL, or direct supported ATS URL is available.
  - [x] Emit `CompanySignal` records with metadata containing VC firm, portfolio URL, source type, and extraction evidence.

- [x] Task 5: Register providers in the existing orchestration (AC: 5, 7)
  - [x] Update `default_discovery_providers()` to append Common Crawl, YC, and VC providers only when enabled/configured.
  - [x] Preserve existing provider order and behavior for HN, seed, Vertex AI Search, and Wellfound.
  - [x] Preserve `discover_sources()` failure isolation and all-provider-failed semantics.
  - [x] Ensure provider diagnostics flow into `provider_diagnostics`, company-signal metrics, persistence, and report JSON.

- [x] Task 6: Add diagnostics/API/report compatibility checks (AC: 7)
  - [x] Keep existing report keys unchanged: `candidate_count`, `validated_count`, `rejected_count`, `error_count`, `counts_by_ats`, `top_rejection_reasons`, `unsupported_url_count`, `active_source_count_after_run`, `source_freshness_counts`, `coverage_gaps`, and `company_signals`.
  - [x] Add only nested provider diagnostics for new scale providers.
  - [x] Ensure `GET /api/v1/ingest/company-signals` surfaces YC/VC metadata through existing `metadata`, `provider_diagnostics`, and `provider_errors` fields.
  - [x] Do not add a frontend UI in this story unless tests or existing diagnostics require a minor API-compatible adjustment.

- [x] Task 7: Add regression tests and verification (AC: 8)
  - [x] Add focused tests in `backend/tests/services/test_source_discovery.py` or a new mirrored provider test module.
  - [x] Mock Common Crawl `collinfo.json` and CDX responses for success, empty result, malformed result, timeout, HTTP error, and cap-exhausted states.
  - [x] Assert Common Crawl candidates validate through the existing `validate_candidate_source` path and never upsert active sources directly from provider code.
  - [x] Test YC import/public extraction mapping, category hints, malformed rows, diagnostics, and no logged-in WaaS dependency.
  - [x] Test VC import/config/public extraction mapping, per-target caps, diagnostics, unsupported links, and canonical-resolution integration.
  - [x] Run `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py`.
  - [x] Run `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts`.

### Review Findings

- [x] [Review][Patch] VC public extraction drops supported ATS links instead of emitting validation evidence [backend/services/source_discovery.py:1187]
- [x] [Review][Patch] Invalid `VC_PORTFOLIO_TARGETS_JSON` silently falls back to default portfolio scraping [backend/services/source_discovery.py:1295]
- [x] [Review][Patch] Malformed VC import JSON escapes provider-level diagnostics [backend/services/source_discovery.py:1102]
- [x] [Review][Patch] Common Crawl reads entire CDX response before applying record caps [backend/services/source_discovery.py:836]
- [x] [Review][Patch] YC public category diagnostics are double-counted [backend/services/source_discovery.py:1018]
- [x] [Review][Patch] Required scale-provider integration tests are missing for parser-validation gating and canonical-resolution coverage [backend/tests/services/test_source_discovery.py:953]

## Dev Notes

### Existing Code To Reuse

- `backend/services/source_discovery.py`
  - `DiscoveryProvider`, `DiscoveryProviderResult`, `SourceCandidate`, `ValidationResult`
  - `default_discovery_providers`
  - `normalize_ats_url`
  - `dedupe_candidates`
  - `extract_urls_from_html`
  - `_normalized_http_url`
  - `_safe_provider_error`
  - `validate_candidate_source`
  - `discover_sources`
  - `write_discovery_report`
- `backend/services/company_discovery.py`
  - `CompanySignal`
  - `normalize_company_signal`
  - `company_signal_metrics`
  - `persist_company_discovery_results`
  - `BOUNDED_COMPANY_PATHS`
- `backend/services/canonical_resolver.py`
  - `resolve_company_signal`
  - bounded company URL, sitemap, and JSON-LD helpers
- `backend/routers/ingest.py`
  - existing `/api/v1/ingest/discover-sources` background task
  - existing `/api/v1/ingest/company-signals` diagnostics endpoint
- `backend/services/parser.py`
  - existing supported ATS parser adapters for Greenhouse, Lever, Ashby, Workable, Recruitee, and Personio.

### Hard Requirements

- Do not create a second discovery runner, task system, report format, or source activation path.
- Do not activate `job_sources` directly from Common Crawl, YC, or VC provider code.
- Common Crawl direct ATS URLs must become `SourceCandidate`s and pass `validate_candidate_source`.
- YC and VC company/domain outputs must become `CompanySignal`s and pass `normalize_company_signal` plus `resolve_company_signal`.
- Do not use browser automation, logged-in sessions, recursive crawlers, or new HTML parsing dependencies.
- Do not use unofficial third-party YC APIs as required runtime dependencies. An import file fallback is acceptable and should be covered by tests.
- Do not download Common Crawl WARC payloads in this story; query the URL index only.
- Keep HTTP calls bounded by strict timeout, response-size caps, record caps, and per-provider diagnostics.
- Keep API and report keys `snake_case`.
- Preserve existing disabled-provider diagnostics behavior from Story 3.2.
- Weekly ingestion must continue reading only active, validated rows from `job_sources`.

### Architecture Compliance

- Backend business logic belongs in `backend/services/`; routers should only orchestrate request/response and background task wiring.
- Raw SQL migrations in `backend/db/migrations/` remain the schema source of truth. This story should not need a migration unless a durable provider state table is introduced; prefer settings, metadata, and report diagnostics.
- FastAPI routes stay under `/api/v1`; existing task/SSE lifecycle remains unchanged.
- Tests should mirror backend source paths under `backend/tests/`.

### Previous Story Intelligence

- Story 3.1 fixed direct ATS company signals bypassing candidate diagnostics. Do not reintroduce that bypass; direct ATS hits still need `ValidationResult` evidence.
- Story 3.1 fixed malformed provider output aborting discovery. Malformed Common Crawl, YC, or VC rows should produce rejected diagnostics.
- Story 3.1 intentionally kept resolver bounded: only bounded paths, declared sitemaps, supported ATS links, and `JobPosting` JSON-LD; no JavaScript execution or recursive crawl.
- Story 3.2 replaced legacy Google Custom Search with Vertex AI Search because the legacy JSON API is unavailable to new customers. Preserve current `VertexAISearchSignalProvider` behavior and names in code.
- Story 3.2 added durable cap/state handling and diagnostics for optional providers. Follow the same pattern for Common Crawl/YC/VC caps.
- Story 3.2 review fixed provider error redaction, diagnostics persistence, and quota-state failure handling. New providers should pass errors through `_safe_provider_error` and include disabled/error states in diagnostics even when no signals are emitted.

### Latest Technical Information

- Common Crawl exposes crawl index endpoints at `https://index.commoncrawl.org/`, with a JSON index list available via `collinfo.json`. The official page warns not to overload the URL index server and recommends the columnar index for bulk filtering/aggregation. This story must stay conservative: small capped URL-index queries only.
- Common Crawl CDXJ index records are URL/capture metadata. They include fields such as `url`, `timestamp`, `status`, `mime`, `digest`, `length`, `offset`, and `filename`. Use only URL metadata for discovery; do not use `filename`, `offset`, and `length` to retrieve WARC records in this story.
- PyWB CDX API supports `url`, wildcard/prefix/domain matching, `limit`, `output=json`, `filter`, and `fl` parameters. Use `output=json` for predictable newline-delimited JSON parsing and exact filters such as `filter==status:200` when filtering to successful captures.
- YC has an official public Startup Directory that supports filtering by industry/status/region/company size and includes a hiring filter, but no stable official public API contract was identified during story creation. Build YC provider with import-file resilience and diagnostics for public surface changes.

### Project Structure Notes

- Expected code changes are backend-only: `backend/config.py`, `.env.example`, `backend/services/source_discovery.py` or a small provider module, and backend tests.
- Use existing `httpx` dependency. Do not add parsing/crawling dependencies.
- No `project-context.md` file exists in this repo at story creation time.

### References

- [Epics: Story 3.3](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md:388)
- [Source Discovery Channel Strategy: Common Crawl/YC/VC](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/source-discovery-channel-strategy.md:127)
- [PRD: Company Discovery FR48-FR55](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md:656)
- [Architecture: Company Discovery Boundary](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md:378)
- [Source Discovery Service Contracts](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:104)
- [ATS Normalization](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:738)
- [Discovery Orchestration](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:1065)
- [Company Signal Contract](/home/darko/Code/be-an-ai-engineer/backend/services/company_discovery.py:11)
- [Canonical Resolver](/home/darko/Code/be-an-ai-engineer/backend/services/canonical_resolver.py:176)
- [Ingest Diagnostics API](/home/darko/Code/be-an-ai-engineer/backend/routers/ingest.py:190)
- [Story 3.1](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/3-1-company-signals-and-canonical-source-resolver.md:1)
- [Story 3.2](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/3-2-google-and-wellfound-direct-hiring-signal-providers.md:1)
- [Common Crawl Index Server](https://index.commoncrawl.org/)
- [Common Crawl CDXJ Index](https://commoncrawl.org/cdxj-index)
- [PyWB CDX Server API](https://github.com/webrecorder/pywb/wiki/CDX-Server-API)
- [YC Directory Announcement](https://www.ycombinator.com/blog/the-yc-directory/)

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py` - 58 passed
- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py` - 85 passed
- `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts` - passed

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added safe disabled-by-default settings and `.env.example` documentation for Common Crawl, YC company directory, and VC portfolio discovery.
- Implemented capped Common Crawl URL-index querying with collinfo support, NDJSON CDX parsing, ATS normalization, dedupe-compatible metadata, and provider diagnostics.
- Implemented YC and VC company-signal providers with deterministic JSON import support, bounded public HTML extraction, rejection diagnostics, and no new parsing/crawling dependencies.
- Registered scale providers behind explicit settings while preserving existing discovery orchestration, report shape, persistence, and API diagnostics.
- Added focused regression coverage for provider registration, Common Crawl caps/errors/parsing, YC import/public extraction, VC import/public extraction, and discovery report diagnostics.

### File List

- `.env.example`
- `backend/config.py`
- `backend/services/source_discovery.py`
- `backend/tests/services/test_source_discovery.py`
- `_bmad-output/implementation-artifacts/3-3-common-crawl-yc-and-vc-scale-discovery-providers.md`

### Change Log

- 2026-05-28: Implemented Story 3.3 scale discovery providers and moved story to review.
