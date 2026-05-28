# Story 3.4: Long-Tail Signals and Provider Yield Reporting

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want GitHub, Reddit, provider yield metrics, and freshness reporting to improve coverage over time,
so that I can see which discovery channels produce useful validated sources and which companies need rechecking or retirement.

## Product Context

Stories 3.1 through 3.3 established the company-signal registry, bounded canonical resolver, optional signal providers, scale providers, validation-gated source activation, and report diagnostics. This story finishes Epic 3 by adding lower-confidence long-tail signal providers and making provider performance visible enough to decide which discovery channels deserve continued use.

GitHub and Reddit are evidence channels only. They can suggest technically relevant companies, domains, careers URLs, and direct ATS URLs, but they must not be treated as hiring proof. All emitted signals must pass the existing `CompanySignal` normalization and canonical resolver path before any source can become active. Weekly ingestion must continue reading only active validated rows from `job_sources`.

## Acceptance Criteria

1. **GitHub Organization Signal Provider Is Official-API-Only And Safe By Default**
   - Given GitHub discovery settings are absent
   - When source discovery runs
   - Then `GitHubOrgSignalProvider` is disabled by default and reports disabled diagnostics without blocking source discovery
   - And when enabled it uses the official GitHub REST API only, with optional token support through environment config
   - And it searches configured AI/backend/devtools topics and repository queries such as `llm`, `rag`, `vector-database`, `mlops`, `agents`, `fastapi`, `developer-tools`, `data-platform`, and `evals`
   - And it extracts organization login/name, public organization metadata where available, repository full name, repository owner URL, repository homepage, repository topics where present, README URLs or README links when within configured caps, evidence URL, and provider metadata
   - And it does not persist full README bodies; README content may only be used transiently to extract bounded careers, homepage, or ATS links
   - And findings are emitted as `CompanySignal` rows with provider name `github_org_signal`
   - And GitHub findings are relevance signals only, not hiring proof.

2. **GitHub Provider Has Conservative Caps, Rate Diagnostics, And No Secret Leakage**
   - Given GitHub API responses include rate-limit headers or rate-limit errors
   - When `GitHubOrgSignalProvider` runs
   - Then diagnostics record query count, repository count, organization count, README fetch count, rate-limit remaining/reset values when available, incomplete search result count, cap exhaustion, and redacted errors
   - And configured caps limit search queries, pages per query, repositories per query, organizations per run, organization metadata fetches, README fetches per run, response bytes, request timeout, and optional request delay
   - And no GitHub token or credential value is written to logs, reports, provider diagnostics, exceptions, or story artifacts
   - And provider errors, malformed payloads, secondary-rate-limit responses, and incomplete search results are isolated to provider diagnostics rather than aborting the whole discovery run unless every configured provider fails.

3. **Reddit Hiring Signal Provider Uses API/Search And Emits Lower-Confidence Signals**
   - Given Reddit discovery is enabled
   - When `RedditHiringSignalProvider` runs
   - Then it uses Reddit API/search endpoints for configured communities instead of scraping HTML pages
   - And default communities include `MachineLearningJobs`, `PythonJobs`, `forhire`, and `remotepython`, with all communities configurable
   - And default search terms include `hiring`, `AI Engineer`, `LLM`, `RAG`, `Python`, `FastAPI`, `backend`, and `remote`, with all terms configurable
   - And it extracts post title, subreddit, permalink/evidence URL, company names where visible, domains, bounded careers URLs, supported direct ATS URLs, post timestamp if available, and provider metadata
   - And output uses provider name `reddit_hiring_signal`, lower default confidence than HN/YC/VC/GitHub unless a bounded careers URL or direct supported ATS URL is visible, and feeds only `CompanySignal` rows into canonical resolution
   - And Reddit post text is never ingested as trusted job corpus data.

4. **Reddit Provider Handles OAuth, Caps, Pagination, And API Policy Constraints**
   - Given Reddit OAuth credentials are absent
   - When Reddit discovery is enabled
   - Then the provider either uses explicitly configured unauthenticated JSON/API mode within conservative caps or reports `missing_credentials`/`disabled` diagnostics based on settings without blocking app startup
   - And when OAuth credentials are configured it uses OAuth endpoints with a descriptive user agent from settings
   - And it respects listing pagination through `after`, `limit`, and `count`, with hard caps for subreddits, queries per subreddit, pages per query, posts per query, total posts per run, response bytes, timeout, and request delay
   - And diagnostics record subreddit/query counts, posts scanned, signals emitted, unsupported URL count, rejected signal reasons, rate-limit/cap exhaustion, and redacted provider errors
   - And mature/explicit communities, deleted/removed posts, spam-like posts, and posts without a company locator are skipped or rejected with visible reasons.

5. **Provider Yield Report Compares Discovery Channels Across All Providers**
   - Given source discovery completes
   - When `source-discovery-report-YYYY-MM-DD.json` is written
   - Then existing top-level report keys remain backward-compatible: `candidate_count`, `validated_count`, `rejected_count`, `error_count`, `counts_by_ats`, `top_rejection_reasons`, `unsupported_url_count`, `active_source_count_after_run`, `source_freshness_counts`, `coverage_gaps`, and `company_signals`
   - And the report adds a backward-compatible nested provider yield section under `company_signals.provider_yield` or another nested key that does not remove existing fields
   - And provider yield compares every configured provider, including disabled providers from `_default_provider_diagnostics`, across at least: signals emitted, candidate count, resolved count, validated active-source count, newly activated source count, active source growth since the previous discovery run, rejected count, error count, unsupported URL count, high-yield company/source count, stale source count, inactive source count, repeated rejection count, top rejection reasons, cap/quota status, and last-seen/last-success markers where available
   - And provider yield can be computed from current run data plus existing `job_sources`, `job_source_candidates`, `company_signals`, `source_discovery_runs`, and `company_discovery_runs` data without adding a second reporting store.

6. **Freshness And Retirement Diagnostics Identify Sources To Recheck Or Drop**
   - Given the registry contains active, stale, inactive, rejected, and repeatedly errored sources/signals
   - When discovery reporting runs
   - Then diagnostics identify stale active sources, inactive sources, repeatedly rejected companies or sources, unresolved companies with fresh evidence, high-yield providers, low-yield providers, and coverage gaps by provider and ATS
   - And stale thresholds are configurable with safe defaults
   - And diagnostics are report-only in this story: no provider automatically deactivates, retires, deletes, or mutates existing active `job_sources` unless existing validation already does so
   - And weekly ingestion still reads only `job_sources` where `active = true` and `validation_status = 'validated'`.

7. **API Diagnostics Surface Yield Without Frontend Scope Creep**
   - Given provider yield reporting is available
   - When `GET /api/v1/ingest/company-signals` is called
   - Then the response exposes latest provider diagnostics, provider errors, and provider yield summary from the latest company discovery run metadata
   - And `GET /api/v1/ingest/sources` remains backward-compatible
   - And no new frontend UI is required in this story unless a small API-compatible display adjustment is needed for existing diagnostics.

8. **Tests Cover Providers, Caps, Reports, And Regressions**
   - Given implementation is complete
   - When targeted backend tests run
   - Then tests cover GitHub disabled/enabled states, official API request shape, topic/query config, repository mapping, README link extraction under caps, token redaction, rate-limit diagnostics, incomplete results, malformed payloads, API errors, and no direct source activation
   - And tests cover Reddit disabled/enabled states, OAuth and unauthenticated configuration behavior, subreddit/search query shape, listing pagination with `after`, post mapping, domain/careers/ATS extraction, lower default confidence, mature/deleted/removed post rejection, caps, rate diagnostics, and no trusted corpus ingestion
   - And tests cover provider yield report compatibility, provider yield metrics across direct candidate providers and company-signal providers, source freshness thresholds, repeated rejection summaries, and API exposure through `/api/v1/ingest/company-signals`
   - And existing source discovery, canonical resolver, ingest router, scheduler, parser, corpus sanity, and prior Epic 3 tests continue passing.

## Tasks / Subtasks

- [x] Task 1: Add safe provider and report configuration (AC: 1, 2, 3, 4, 6)
  - [x] Extend `backend/config.py` with disabled-by-default GitHub settings: enable flag, token, topics/queries, max search queries, max pages per query, max repos per query, max orgs per run, max organization metadata fetches, max README fetches, request timeout, request delay, max response bytes, and optional durable cap/state file if needed.
  - [x] Extend `backend/config.py` with disabled-by-default Reddit settings: enable flag, client ID/secret or token fields if used, user agent, unauthenticated mode flag if supported, subreddits, search terms, max pages per query, max posts per query/run, request timeout, request delay, max response bytes, and confidence defaults.
  - [x] Add freshness/yield thresholds such as stale days, repeated rejection window/count, and high-yield minimum validated source count.
  - [x] Update `.env.example` with every setting and no secrets.
  - [x] Preserve app startup when optional GitHub/Reddit credentials are absent.

- [x] Task 2: Implement `GitHubOrgSignalProvider` (AC: 1, 2)
  - [x] Add the provider in `backend/services/source_discovery.py` unless the file becomes too large; if split, keep imports simple and preserve existing public contracts.
  - [x] Use `httpx.AsyncClient`, official GitHub REST endpoints, explicit `Accept: application/vnd.github+json`, and `X-GitHub-Api-Version` headers.
  - [x] Search repositories through `/search/repositories` using configured topics/queries, `per_page` caps, and conservative pagination.
  - [x] Extract only relevance evidence: org/repo identity, owner URL, public organization metadata such as `blog`/website when available, repository HTML URL, homepage/domain, topics, description, README URLs/text links within cap, and evidence URL.
  - [x] Do not persist full README content in metadata, diagnostics, reports, or database rows; keep only extracted URLs and short source metadata.
  - [x] Convert findings into `CompanySignal` records with `provider="github_org_signal"`, normalized evidence URLs, confidence/category hints, and metadata containing query/rank/repo details.
  - [x] Detect supported ATS URLs with existing `normalize_ats_url` only as signal evidence through `CompanySignal.direct_ats_url`; do not upsert `job_sources` directly.
  - [x] Use `_safe_provider_error` for every reported exception.

- [x] Task 3: Implement `RedditHiringSignalProvider` (AC: 3, 4)
  - [x] Add the provider in `backend/services/source_discovery.py` or the same small provider module chosen for GitHub.
  - [x] Use Reddit API/search endpoints for configured subreddits; do not scrape rendered Reddit HTML.
  - [x] Support OAuth when configured and conservative unauthenticated mode only if explicitly enabled.
  - [x] Use a descriptive user agent setting for all Reddit calls.
  - [x] Page listing responses with `after`, `limit`, and `count`, and stop at configured caps.
  - [x] Extract domains, bounded careers URLs, and supported direct ATS URLs with existing helpers; reject posts without a company locator.
  - [x] Emit `CompanySignal` records with `provider="reddit_hiring_signal"`, lower default confidence, subreddit/query/post metadata, and evidence permalink.
  - [x] Skip or reject mature, deleted, removed, malformed, or spam-like records with visible diagnostics.

- [x] Task 4: Register long-tail providers in existing orchestration (AC: 1, 3, 5)
  - [x] Update `_default_provider_diagnostics()` to include disabled GitHub and Reddit diagnostics.
  - [x] Update `default_discovery_providers()` to append GitHub and Reddit only when enabled/configured.
  - [x] Preserve existing provider order and behavior for HN, seed, Vertex AI Search, Wellfound, Common Crawl, YC, and VC.
  - [x] Preserve `discover_sources()` failure isolation and all-provider-failed semantics.
  - [x] Ensure provider diagnostics flow into `company_signals.provider_diagnostics`, persistence, report JSON, and router responses.

- [x] Task 5: Add provider yield and freshness reporting (AC: 5, 6, 7)
  - [x] Add focused helper functions for provider yield metrics instead of embedding large SQL/report logic directly inside `discover_sources()`.
  - [x] Compute yield from current run objects plus registry/history tables where a real pool is available; return stable zero/empty defaults for mocks and tests.
  - [x] Compute active source growth explicitly, either by snapshotting existing `(ats, slug)` rows before validation or by comparing current validated activations against the previous discovery run.
  - [x] Include all providers in yield output, including disabled providers represented only in diagnostics.
  - [x] Keep existing report keys unchanged and add provider yield as a nested report field.
  - [x] Store latest provider yield in `company_discovery_runs.metadata` so `GET /api/v1/ingest/company-signals` can expose it.
  - [x] Add repeated rejection and stale-source diagnostics without automatically deactivating sources.

- [x] Task 6: Preserve API and ingestion boundaries (AC: 6, 7)
  - [x] Verify `load_active_source_config()` still reads only `active = true AND validation_status = 'validated'`.
  - [x] Extend `GET /api/v1/ingest/company-signals` with `provider_yield` while preserving existing `provider_diagnostics`, `provider_errors`, and `company_signals` keys.
  - [x] Avoid new frontend scope unless existing tests require a small backward-compatible diagnostics display change.
  - [x] Avoid adding new migrations unless a durable provider state table is genuinely needed; prefer settings, JSON metadata, and report artifacts for this story.

- [x] Task 7: Add regression tests and verification (AC: 8)
  - [x] Add focused tests in `backend/tests/services/test_source_discovery.py` or a mirrored provider test module.
  - [x] Mock GitHub API responses for search success, incomplete results, README extraction, rate limit, secondary limit, malformed payload, timeout, HTTP error, and cap exhaustion.
  - [x] Mock Reddit API responses for OAuth/unauthenticated modes, search success, pagination, mature/deleted/removed rejection, malformed payload, timeout, HTTP error, and cap exhaustion.
  - [x] Assert GitHub/Reddit signals pass through `CompanySignal` normalization/resolution paths and never directly activate `job_sources`.
  - [x] Test provider yield helper output with current-run data and mocked SQL rows for active, stale, inactive, repeated rejected, and errored sources/signals.
  - [x] Run `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py`.
  - [x] Run `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts`.

### Review Findings

- [x] [Review][Patch] Reddit OAuth failure falls back to unauthenticated search [backend/services/source_discovery.py:921]
- [x] [Review][Patch] Provider yield persistence can fail on registry datetimes [backend/services/company_discovery.py:212]
- [x] [Review][Patch] Freshness counts ignore the configured stale threshold [backend/services/source_discovery.py:2381]
- [x] [Review][Patch] Provider yield reports revalidations as newly activated sources [backend/services/source_discovery.py:2475]
- [x] [Review][Patch] Registry-backed yield cannot attribute validated signal-provider sources to GitHub/Reddit [backend/services/canonical_resolver.py:178]
- [x] [Review][Patch] Provider yield can double-count validated company-signal results [backend/services/source_discovery.py:2475]
- [x] [Review][Patch] Provider yield drops diagnostics error and unsupported URL counts [backend/services/source_discovery.py:2419]
- [x] [Review][Patch] Active source growth allocation can produce impossible per-provider totals [backend/services/source_discovery.py:2512]
- [x] [Review][Patch] GitHub organization provider emits signals for user-owned repositories [backend/services/source_discovery.py:731]
- [x] [Review][Patch] GitHub malformed `topics` payload can abort processing for a page [backend/services/source_discovery.py:777]
- [x] [Review][Patch] GitHub metadata/README rate limits are reported as partial errors [backend/services/source_discovery.py:815]
- [x] [Review][Patch] Reddit cap diagnostics miss page and posts-per-query exhaustion [backend/services/source_discovery.py:932]
- [x] [Review][Patch] Empty enabled provider inputs report `ok` instead of misconfiguration [backend/services/source_discovery.py:581]

## Dev Notes

### Existing Code To Reuse

- `backend/services/source_discovery.py`
  - Provider contracts: `DiscoveryProvider`, `DiscoveryProviderResult`, `SourceCandidate`, `ValidationResult`.
  - Existing providers and registration: `HNWhoIsHiringProvider`, `OptionalSeedProvider`, `VertexAISearchSignalProvider`, `WellfoundSignalProvider`, `CommonCrawlATSProvider`, `YCCompanyDirectoryProvider`, `VCPortfolioProvider`, `_default_provider_diagnostics`, `default_discovery_providers`.
  - Shared helpers: `_safe_provider_error`, `extract_urls_from_html`, `_normalized_http_url`, `normalize_ats_url`, `dedupe_candidates`, `detect_candidates_in_text`, `validate_candidate_source`, `get_source_freshness_counts`, `discover_sources`, `write_discovery_report`.
- `backend/services/company_discovery.py`
  - `CompanySignal`, `CompanySignalResolution`, `normalize_company_signal`, `company_signal_metrics`, `persist_company_discovery_results`.
- `backend/services/canonical_resolver.py`
  - `resolve_company_signal`, bounded careers path resolution, sitemap parsing, ATS detection, and `JobPosting` JSON-LD evidence.
- `backend/routers/ingest.py`
  - Existing `/api/v1/ingest/discover-sources`, `/api/v1/ingest/sources`, and `/api/v1/ingest/company-signals` endpoints.
- `backend/db/migrations/V005__add_job_source_registry.sql`
  - Registry tables: `source_discovery_runs`, `job_source_candidates`, `job_sources`.
- `backend/db/migrations/V006__add_company_discovery.sql`
  - Company signal tables: `company_discovery_runs`, `company_signals`.

### Hard Requirements

- Do not create a second discovery runner, task system, report format, source activation path, or provider registry.
- Do not activate `job_sources` directly from GitHub or Reddit provider code.
- GitHub and Reddit provider outputs must become `CompanySignal` records and pass `normalize_company_signal` plus `resolve_company_signal`.
- Direct ATS URLs from GitHub/Reddit must still pass existing `validate_candidate_source` through the company-signal resolver path.
- Do not scrape GitHub or Reddit rendered web pages. Use official/API JSON surfaces only.
- Do not ingest GitHub README text or Reddit post text as trusted job corpus data.
- Keep all external calls bounded by strict timeout, response-size caps, item caps, and per-provider diagnostics.
- Keep API payloads and report fields `snake_case`.
- Preserve existing disabled-provider diagnostics behavior from Stories 3.2 and 3.3.
- Keep secrets out of logs, diagnostics, reports, persisted metadata, and test snapshots.
- Weekly ingestion must continue reading only active, validated rows from `job_sources`.

### Architecture Compliance

- Backend business logic belongs in `backend/services/`; routers should only expose diagnostics and task orchestration.
- Raw SQL through psycopg remains the persistence pattern; do not introduce an ORM.
- FastAPI routes stay under `/api/v1`.
- Existing task/SSE lifecycle remains unchanged.
- Tests should mirror backend source paths under `backend/tests/`.
- Use the existing `httpx` dependency. Do not add GitHub, Reddit, scraping, browser automation, or HTML parsing dependencies unless there is a strong documented reason.

### Previous Story Intelligence

- Story 3.1 fixed direct ATS company signals bypassing candidate diagnostics. Do not reintroduce that bypass; direct ATS hits still need validation evidence.
- Story 3.1 fixed malformed provider output aborting discovery. Malformed GitHub/Reddit rows should produce rejected diagnostics, not unhandled exceptions.
- Story 3.1 intentionally kept resolver bounded: only bounded paths, declared sitemaps, supported ATS links, and `JobPosting` JSON-LD; no JavaScript execution or recursive crawl.
- Story 3.2 replaced legacy Google Custom Search with Vertex AI Search because the legacy JSON API is unavailable to new customers. Preserve current `VertexAISearchSignalProvider` behavior and names in code.
- Story 3.2 added durable cap/state handling and diagnostics for optional providers. Follow the same diagnostics pattern for GitHub/Reddit caps and rate state if durable state is needed.
- Story 3.2 review fixed provider error redaction, diagnostics persistence, and quota-state failure handling. New providers should pass errors through `_safe_provider_error` and include disabled/error states in diagnostics even when no signals are emitted.
- Story 3.3 added Common Crawl, YC, and VC providers with deterministic import support, strict caps, no new parsing/crawling dependencies, and nested provider diagnostics. Match that style.
- Story 3.3 review fixed cases where malformed provider config or payloads escaped diagnostics. Invalid GitHub/Reddit settings should not silently fall back to broad live API calls.

### Git Intelligence Summary

- Recent commits are Epic 3 focused: `416e395 Implement scale discovery providers`, `9f0976a Add Vertex AI Search discovery provider`, `2bf7d24 Add company signal resolver`, `5626307 Add source discovery registry and company radar plan`, and `79e224d Add scheduled ingestion and diagnostics`.
- The most recent Epic 3 commit touched `.env.example`, sprint/story artifacts, `backend/config.py`, `backend/services/source_discovery.py`, and `backend/tests/services/test_source_discovery.py`. This story should likely touch the same backend files plus `backend/routers/ingest.py` for provider yield API exposure.
- Story 3.3 verification passed targeted source discovery/canonical resolver/ingest/corpus tests and `compileall`; use the same verification baseline.

### Latest Technical Information

- GitHub REST Search currently provides up to 1,000 results per search and has a custom search rate limit: up to 30 authenticated search requests per minute for most search endpoints and 10 unauthenticated requests per minute. Search queries also have length/operator limitations and can return `incomplete_results`; provider diagnostics must preserve this state.
- GitHub repository search returns up to 100 results per page, supports qualifiers through the `q` parameter, and can be used without authentication for public resources. Use authenticated requests when a token is configured to improve rate headroom, but keep unauthenticated mode capped.
- GitHub repository README access can be used without authentication for public resources. README fetching should be capped because it consumes core API budget and may retrieve large text; only extracted links should be retained.
- Reddit `/r/{subreddit}/search` is a listing endpoint with `after`, `before`, `limit`, `count`, `q`, `restrict_sr`, `sort`, `t`, and `type` parameters. Use listing pagination instead of page numbers.
- Reddit's published API update states free Data API limits of 100 queries per minute per OAuth client ID and 10 queries per minute without OAuth as of July 1, 2023. Use lower defaults than these limits and expose cap/rate diagnostics.

### Project Structure Notes

- Expected code changes are backend-only: `.env.example`, `backend/config.py`, `backend/services/source_discovery.py` or a small provider module, `backend/routers/ingest.py`, and backend tests.
- A migration should not be necessary unless provider yield cannot be represented in existing run metadata; prefer JSON metadata/report fields first.
- No `project-context.md` file exists in this repo at story creation time.

### References

- [Epics: Story 3.4](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md:404)
- [PRD: Company Discovery FR48-FR55](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md:656)
- [Architecture: Company Discovery Boundary](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md:378)
- [Source Discovery Channel Strategy: GitHub/Reddit/Yield](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/source-discovery-channel-strategy.md:157)
- [Source Discovery Service Contracts](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:133)
- [Provider Registration](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:1268)
- [Discovery Orchestration And Report Writing](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:1750)
- [Company Signal Contract](/home/darko/Code/be-an-ai-engineer/backend/services/company_discovery.py:11)
- [Canonical Resolver](/home/darko/Code/be-an-ai-engineer/backend/services/canonical_resolver.py:176)
- [Ingest Diagnostics API](/home/darko/Code/be-an-ai-engineer/backend/routers/ingest.py:190)
- [Story 3.1](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/3-1-company-signals-and-canonical-source-resolver.md:1)
- [Story 3.2](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/3-2-google-and-wellfound-direct-hiring-signal-providers.md:1)
- [Story 3.3](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/3-3-common-crawl-yc-and-vc-scale-discovery-providers.md:1)
- [GitHub REST Search API](https://docs.github.com/en/rest/search/search)
- [GitHub REST Repository Contents API](https://docs.github.com/en/rest/repos/contents)
- [Reddit API Search Endpoint](https://www.reddit.com/dev/api/#GET_search)
- [Reddit API Rate Update](https://redditinc.com/news/apifacts)

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py` -> 72 passed.
- `backend/venv/bin/pytest -q backend/tests/routers/test_ingest.py` -> 19 passed.
- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py` -> 99 passed.
- Code review fixes: `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py` -> 104 passed.
- `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts` -> passed.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added disabled-by-default GitHub and Reddit discovery settings, env examples, safe provider diagnostics, and configurable freshness/yield thresholds.
- Implemented `GitHubOrgSignalProvider` and `RedditHiringSignalProvider` as bounded API-only company-signal providers that do not directly activate `job_sources`.
- Added nested provider yield reporting, registry-backed stale/repeated-rejection diagnostics, company discovery metadata persistence, and `/api/v1/ingest/company-signals` API exposure.
- Added regression coverage for long-tail provider defaults, request shape, caps, diagnostics, token redaction, README/post extraction boundaries, provider yield, report compatibility, and router diagnostics.

### File List

- `.env.example`
- `_bmad-output/implementation-artifacts/3-4-long-tail-signals-and-provider-yield-reporting.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/config.py`
- `backend/routers/ingest.py`
- `backend/services/company_discovery.py`
- `backend/services/source_discovery.py`
- `backend/tests/routers/test_ingest.py`
- `backend/tests/services/test_source_discovery.py`

### Change Log

- 2026-05-28: Implemented Story 3.4 long-tail GitHub/Reddit signal providers, provider yield/freshness reporting, API exposure, and regression tests.
