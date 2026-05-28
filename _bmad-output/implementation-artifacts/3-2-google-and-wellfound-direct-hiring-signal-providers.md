# Story 3.2: Vertex AI Search and Wellfound Direct Hiring Signal Providers

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want Vertex AI Search and constrained Wellfound signals to identify companies that may be hiring,
so that the market scanner can discover fresh startup and AI/backend opportunities while still validating jobs from canonical company sources.

## Product Context

Story 3.1 completed the company-signal registry and canonical resolver. This story adds the first two company-signal providers that feed that layer: Vertex AI Search via Discovery Engine `searchLite` and a constrained Wellfound signal importer/extractor. These providers must emit evidence into `CompanySignal` and let the existing `discover_sources()` orchestration normalize, resolve, validate, persist, and report outcomes.

The trust boundary is unchanged: Vertex AI Search and Wellfound are evidence sources only. They must never create active `job_sources` rows directly, scrape search result pages, ingest third-party job text, ingest Wellfound job text, or bypass canonical resolution and parser-backed ATS validation.

## Acceptance Criteria

1. **Vertex AI Search Provider Is Optional And Official-API Only**
   - Given `VERTEX_SEARCH_API_KEY`, `VERTEX_SEARCH_PROJECT_ID`, and `VERTEX_SEARCH_ENGINE_ID` are configured
   - When `discover_sources(pool)` runs with default providers
   - Then `VertexAISearchSignalProvider` calls only Discovery Engine `searchLite`
   - And each request passes the API key as a query parameter and the query in JSON
   - And no search result page, jobs page, or unofficial SERP endpoint is scraped
   - And if credentials are absent, invalid, quota-exhausted, or the API is unavailable, the provider is skipped or reported as a provider error without aborting the discovery run unless all configured providers fail.

2. **Vertex AI Search Usage Is Capped And Free-Budget Safe**
   - Given Vertex AI Search discovery is enabled
   - When query templates are executed
   - Then the provider enforces test-mode caps by default and a production monthly cap clamped to 8000 queries
   - And daily and monthly caps are tracked across multiple discovery runs, not only within one process/run
   - And production usage remains disabled unless explicitly configured by an environment setting
   - And the provider stops before exceeding its local cap, records `quota_exhausted` or equivalent diagnostic metadata, records query count used, and does not retry indefinitely
   - And the implementation avoids the legacy JSON Search API because it is unavailable to new customers.

3. **Vertex AI Search Results Become Company Signals Only**
   - Given Vertex AI Search returns result items
   - When the provider processes each item
   - Then it stores query text, result URL, title, snippet, rank, and provider metadata
   - And it emits `CompanySignal` records using provider name `vertex_ai_search`
   - And supported direct ATS URLs may be emitted as `direct_ats_url`
   - And bounded company careers/job URLs may be emitted as `careers_url` only when they match the existing bounded path rules
   - And generic company URLs may be emitted as `company_domain`/`normalized_domain` for canonical resolution
   - And duplicate results from multiple queries are deduplicated without losing query/rank evidence in metadata.

4. **Wellfound Provider Is Disabled By Default And Import-First**
   - Given default configuration
   - When source discovery runs
   - Then `WellfoundSignalProvider` is disabled unless `WELLFOUND_DISCOVERY_ENABLED=true`
   - And manual/imported Wellfound company URLs are supported before any automated public extraction
   - And imported entries can come from a committed or user-provided JSON file path without requiring credentials, login, browser automation, or session cookies.

5. **Wellfound Automated Extraction Is Strictly Constrained**
   - Given Wellfound automated public extraction is explicitly enabled
   - When the provider fetches public Wellfound pages
   - Then it enforces no login, no browser automation, no pagination crawling, no disallowed `/_jobs/` crawling, max 5 pages/run by default, 5+ second delay between requests, strict timeout, and maximum response size
   - And it respects Wellfound robots constraints including the disallowed `/_jobs/` path and query patterns for job IDs/slugs
   - And it treats Wellfound terms restrictions as a product risk by minimizing automated access, avoiding copied job/profile content, and storing only source evidence needed for canonical validation
   - And it extracts only company name, domain/homepage if visible, evidence URL, confidence, and metadata
   - And it never ingests Wellfound job text, candidate data, profile data, application pages, or logged-in-only content.

6. **Provider Integration Reuses Story 3.1 Contracts**
   - Given either provider emits company evidence
   - When `discover_sources()` processes provider output
   - Then all evidence flows through existing `DiscoveryProviderResult.company_signals`
   - And company signals are normalized with `normalize_company_signal`
   - And direct ATS URLs are validated through `validate_candidate_source`
   - And domain/careers signals resolve through `resolve_company_signal`
   - And validated ATS sources are activated only through the existing company discovery persistence and `job_sources` upsert path.

7. **Diagnostics And Reports Show Provider Yield**
   - Given discovery completes
   - When `GET /api/v1/ingest/company-signals` is called or a discovery report is written
   - Then Vertex AI Search and Wellfound signals include provider, evidence URL, query/import metadata, status, resolved source metadata, rejection reason, and last error
   - And `source-discovery-report-YYYY-MM-DD.json` includes provider counts, resolved/unresolved/rejected/error counts, quota or disabled-provider diagnostics, and existing report fields from Stories 2.5 and 3.1.

8. **Tests Cover Contracts, Caps, Boundaries, And Regression**
   - Given implementation is complete
   - When targeted tests run
   - Then tests cover Vertex AI Search disabled config, request shape, cap enforcement, API error isolation, result-to-signal mapping, deduplication, and no SERP scraping
   - And tests cover Wellfound disabled config, import-file parsing, constrained extraction boundaries, disallowed path rejection, delay/cap behavior without sleeping in tests, and no job-text ingestion
   - And existing parser, source discovery, canonical resolver, ingest router, scheduler, and corpus sanity tests continue passing.

## Tasks / Subtasks

- [x] Task 1: Add provider configuration (AC: 1, 2, 4, 5)
  - [x] Extend `backend/config.py` with optional settings: `vertex_search_api_key`, `vertex_search_project_id`, `vertex_search_engine_id`, `vertex_search_prod_mode`, daily/monthly/test caps, `vertex_search_quota_state_file`, `wellfound_discovery_enabled` default `false`, `wellfound_import_file`, `wellfound_auto_extract_enabled` default `false`, `wellfound_max_pages_per_run` default `5`, and `wellfound_request_delay_seconds` default `5.0`.
  - [x] Keep `.env` values gitignored; do not commit real API keys or Wellfound session data.
  - [x] Ensure absent optional credentials do not prevent FastAPI startup.

- [x] Task 2: Implement `VertexAISearchSignalProvider` (AC: 1, 2, 3, 6)
  - [x] Add the provider in `backend/services/source_discovery.py` or a small provider module imported by it if the file becomes too broad.
  - [x] Use `httpx.AsyncClient(timeout=10.0)` and Discovery Engine `searchLite` only.
  - [x] Send required API key parameter and query payload.
  - [x] Before issuing each request, consult durable quota state and reserve/count the query so repeated local runs cannot exceed the configured daily/monthly caps.
  - [x] Start with the query templates from `source-discovery-channel-strategy.md`: `site:jobs.lever.co "AI Engineer" "Python"`, `site:boards.greenhouse.io "LLM" "Backend"`, `site:jobs.ashbyhq.com "RAG" "Engineer"`, `"AI Engineer" "careers" "Greenhouse"`, `"Machine Learning Platform Engineer" "careers"`, and `"FastAPI" "Backend Engineer" "jobs"`.
  - [x] Convert result document fields into `CompanySignal` evidence with metadata containing query, rank, title, snippet, and raw link fields needed for diagnostics.
  - [x] Prefer direct ATS detection with existing `normalize_ats_url`; otherwise emit bounded careers URL or company domain for canonical resolution.
  - [x] Deduplicate by normalized result URL and retain multi-query evidence in metadata.

- [x] Task 3: Implement `WellfoundSignalProvider` import-first path (AC: 4, 6)
  - [x] Support a JSON import file with entries such as `wellfound_url`, `company_name`, `company_domain`, `homepage_url`, `confidence`, and `category_hints`.
  - [x] Emit provider name `wellfound_signal` and evidence URL from the Wellfound company URL or supplied search-result URL.
  - [x] Validate imported URLs through `normalize_company_signal`; malformed rows become rejected signal diagnostics instead of unhandled exceptions.
  - [x] Do not require browser cookies, login state, API tokens, or Wellfound account access.

- [x] Task 4: Add constrained Wellfound public extraction only behind explicit config (AC: 5)
  - [x] If `wellfound_auto_extract_enabled` is false, do not perform HTTP fetches against Wellfound.
  - [x] If enabled, fetch at most `wellfound_max_pages_per_run` pages per run with `httpx.AsyncClient(timeout=5.0, follow_redirects=True)` and `MAX_PAGE_BYTES` enforcement.
  - [x] Reject or skip URLs with path/query patterns disallowed by Wellfound robots, especially `/_jobs/`, `jobId`, `jobSlug`, `role`, application/profile/auth paths, and pagination.
  - [x] Enforce `wellfound_request_delay_seconds >= 5.0`; inject the sleeper/time function in tests so unit tests do not actually wait.
  - [x] Parse only public page text/links with standard-library parsers or existing helpers; do not add BeautifulSoup, lxml, Playwright, Selenium, or Scrapy.
  - [x] Extract only company name, homepage/domain, evidence URL, confidence, and metadata; never persist job descriptions from Wellfound.

- [x] Task 5: Register providers in default discovery (AC: 1, 4, 6)
  - [x] Update `default_discovery_providers()` so Vertex AI Search and Wellfound providers are included only when enabled/configured.
  - [x] Preserve the existing `HNWhoIsHiringProvider()` and `OptionalSeedProvider()` order and behavior.
  - [x] Preserve provider failure isolation in `discover_sources()`; seed JSON parse errors may still fail loudly as currently implemented.

- [x] Task 6: Extend diagnostics and report fields (AC: 7)
  - [x] Ensure provider metadata is visible through `GET /api/v1/ingest/company-signals`.
  - [x] Extend report output only by adding fields; preserve existing keys from Stories 2.5 and 3.1.
  - [x] Include disabled, missing credentials, quota exhausted, and API unavailable states in metadata or provider errors.

- [x] Task 7: Add regression tests (AC: 8)
  - [x] Add unit tests in `backend/tests/services/test_source_discovery.py` or a focused provider test module.
  - [x] Mock Vertex AI Search HTTP responses for success, empty results, 403/quota, and transport errors.
  - [x] Assert Vertex AI Search quota state survives multiple provider instances/runs for the same date and resets on the next date.
  - [x] Mock Wellfound import and public extraction paths, including disallowed URLs and delay injection.
  - [x] Add/adjust report and company-signal diagnostics assertions.
  - [x] Run `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py`.
  - [x] Run `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts`.

### Review Findings

- [x] [Review][Patch] Search provider can exceed the free monthly budget while production mode is enabled [backend/services/source_discovery.py:182]
- [x] [Review][Patch] Search provider disabled, missing-credential, and quota-exhausted diagnostics disappear when no signals are emitted [backend/services/source_discovery.py:204]
- [x] [Review][Patch] API keys can leak through raw provider error strings and report metrics [backend/services/source_discovery.py:219]
- [x] [Review][Patch] Search provider quota reservation is non-atomic across concurrent runs [backend/services/source_discovery.py:242]
- [x] [Review][Patch] Long search queries consume quota without sending a request [backend/services/source_discovery.py:204]
- [x] [Review][Patch] Malformed search response payloads fail the provider after quota is reserved [backend/services/source_discovery.py:224]
- [x] [Review][Patch] Wellfound auto-extract failures discard otherwise valid import signals [backend/services/source_discovery.py:335]
- [x] [Review][Patch] Wellfound extraction follows redirects after validating only the original URL [backend/services/source_discovery.py:389]
- [x] [Review][Patch] Wellfound max response size is not strictly enforced before body download [backend/services/source_discovery.py:393]
- [x] [Review][Patch] Malformed Wellfound `content-length` values crash extraction [backend/services/source_discovery.py:395]
- [x] [Review][Patch] Required diagnostics and boundary regression tests are incomplete [backend/tests/services/test_source_discovery.py:812]

### Review Findings - Vertex Replacement Review (2026-05-28)

- [x] [Review][Patch] Provider error redaction regex does not actually stop at whitespace and can leak API keys [backend/services/source_discovery.py:158]
- [x] [Review][Patch] Vertex API failure diagnostics are overwritten by generic orchestration error metadata [backend/services/source_discovery.py:1086]
- [x] [Review][Patch] Provider diagnostics are persisted but not exposed by `GET /api/v1/ingest/company-signals` [backend/routers/ingest.py:288]
- [x] [Review][Patch] Malformed Vertex quota state can crash instead of returning `quota_state_unavailable` diagnostics [backend/services/source_discovery.py:355]
- [x] [Review][Patch] Vertex quota state directory creation can fail before the I/O diagnostic guard is active [backend/services/source_discovery.py:346]
- [x] [Review][Patch] Vertex response schema is not validated after JSON decode and can crash or silently consume quota [backend/services/source_discovery.py:296]
- [x] [Review][Patch] Vertex generic fallback can turn known noise hosts such as LinkedIn into company signals [backend/services/source_discovery.py:425]
- [x] [Review][Patch] Wellfound disallowed URL checks miss exact job roots and blank job query parameters [backend/services/source_discovery.py:572]
- [x] [Review][Patch] Custom ATS path mapping for `careers.tether.io` is too broad and can classify unrelated `/o*` paths as Recruitee [backend/services/source_discovery.py:97]
- [x] [Review][Patch] `.env.example` stores durable Vertex quota state under `/tmp`, weakening monthly cap persistence [/.env.example:18]
- [x] [Review][Patch] Checked-in source discovery report still shows retired `google_search_api` diagnostics [/_bmad-output/implementation-artifacts/source-discovery-report-2026-05-27.json:8]
- [x] [Review][Patch] Required regression coverage is incomplete for transport errors, orchestration-level API failure diagnostics, and multi-page Wellfound delay behavior [backend/tests/services/test_source_discovery.py:416]

## Dev Notes

### Existing Code To Reuse

- `backend/services/source_discovery.py`
  - `DiscoveryProvider`, `DiscoveryProviderResult`, `SourceCandidate`, `ValidationResult`
  - `default_discovery_providers`
  - `normalize_ats_url`
  - `extract_urls_from_html`
  - `_normalized_http_url`
  - `dedupe_candidates`
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
  - `build_bounded_company_urls`
  - sitemap and JSON-LD parsing helpers
- `backend/routers/ingest.py`
  - existing `/api/v1/ingest/discover-sources` task flow
  - existing `/api/v1/ingest/company-signals` diagnostics

### Hard Requirements

- Do not create a second discovery runner, second task system, or second company-signal persistence path.
- Do not activate `job_sources` directly from Vertex AI Search or Wellfound provider code.
- Do not scrape search result pages or jobs aggregators. Search access is official Discovery Engine `searchLite` only.
- Do not treat Wellfound as a job corpus. Wellfound output is company/domain/evidence only.
- Do not add browser automation, recursive crawling, login/session usage, or new HTML parsing dependencies.
- Keep provider failures isolated. Missing Vertex AI Search credentials and disabled Wellfound should be normal non-fatal states.
- Enforce Vertex AI Search quota as a durable daily/monthly cap. A per-run counter alone is insufficient because manual retries could burn past the free quota.
- Keep API response keys and report fields `snake_case`.
- Keep HTTP calls bounded with strict timeout, response-size caps, query/page caps, and no unbounded pagination.
- Keep the weekly ingestion trust boundary: weekly ingestion reads only active, validated rows from `job_sources`.

### Latest Technical Information

- Vertex AI Search uses Discovery Engine `searchLite` with an API key, project id, location, engine id, serving config id, query text, and bounded page size.
- The legacy JSON Search API is closed to new customers, so this implementation uses Vertex AI Search instead and caps local production usage at 8000 queries/month.
- Wellfound robots disallow `/_jobs/` and several job/application/profile/auth paths and job query parameters. Wellfound terms restrict scraping/copying content and automated access that imposes more load than a conventional human browser. Keep automated Wellfound extraction off by default, prefer manual/imported evidence, and heavily cap any explicitly enabled public extraction.

### Previous Story Intelligence

- Story 3.1 review found and fixed issues where direct ATS company signals bypassed candidate diagnostics and malformed provider output could abort discovery. Do not reintroduce those paths.
- Story 3.1 established that provider output must be normalized first; malformed rows become rejected diagnostics with reasons.
- Story 3.1 already updates `job_sources` only after `validate_candidate_source` returns `validated`; reuse this path.
- Story 3.1 intentionally deferred a global per-run company signal cap. This story should add provider-specific caps for Vertex AI Search queries and Wellfound pages, but should not invent a broader scheduler or global quota system unless needed for the ACs.

### Git Intelligence

- Recent commit `2bf7d24 Add company signal resolver` created `backend/services/company_discovery.py`, `backend/services/canonical_resolver.py`, the `V006` company discovery migration, diagnostics, and tests. Extend these seams.
- Recent commit `5626307 Add source discovery registry and company radar plan` added `backend/services/source_discovery.py`, the `V005` source registry migration, source discovery reports, and the channel strategy. Keep report compatibility with these artifacts.

### Architecture Compliance

- Backend business logic belongs in `backend/services/`; routers should orchestrate request/response only.
- Raw SQL migrations in `backend/db/migrations/` remain the schema source of truth. This story should not need a migration unless a new durable quota table is introduced; prefer report/metadata diagnostics for provider caps.
- FastAPI routes stay under `/api/v1`.
- API responses use `snake_case`; do not introduce camelCase conversion.
- Existing SSE event names and task lifecycle must remain unchanged.

### Project Structure Notes

- The implementation should be backend-only unless diagnostics UI changes are explicitly added later.
- Existing tests mirror source paths under `backend/tests/`; provider tests should follow that pattern.
- No `project-context.md` file exists in this repo at story creation time.

### References

- [Epics: Story 3.2](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md:371)
- [PRD: Company Discovery FR48-FR55](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md:656)
- [Architecture: Company Discovery Boundary](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md:378)
- [Source Discovery Channel Strategy](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/source-discovery-channel-strategy.md:81)
- [Story 3.1](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/3-1-company-signals-and-canonical-source-resolver.md:1)
- [Source Discovery Service](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:1)
- [Company Discovery Service](/home/darko/Code/be-an-ai-engineer/backend/services/company_discovery.py:1)
- [Canonical Resolver](/home/darko/Code/be-an-ai-engineer/backend/services/canonical_resolver.py:1)
- [Vertex AI Search Overview](https://cloud.google.com/generative-ai-app-builder/docs/introduction)
- [Migrate from Custom Search Site Restricted JSON API](https://docs.cloud.google.com/generative-ai-app-builder/docs/migrate-from-cse)
- [Preview Search Results](https://docs.cloud.google.com/generative-ai-app-builder/docs/preview-search-results)
- [Wellfound robots.txt](https://wellfound.com/robots.txt)
- [Wellfound General Terms](https://wellfound.com/terms)

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py` failed initially during collection because the search provider did not exist yet, confirming red phase.
- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py` passed: 33 tests.
- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py` passed: 60 tests.
- `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts` passed.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added optional Vertex AI Search and Wellfound discovery settings without requiring credentials for startup.
- Implemented Vertex AI Search signal provider with official Discovery Engine endpoint use, durable quota file, capped test/production modes, result mapping, deduplication, and diagnostics.
- Implemented disabled-by-default Wellfound signal provider with JSON import support and tightly constrained public extraction behind explicit config.
- Registered configured providers into default discovery while preserving existing HN and seed provider ordering and existing company-signal normalization/resolution/persistence paths.
- Extended company-signal report metrics with provider error details and ignored the runtime Vertex AI Search quota state file.
- Added regression coverage for provider configuration, Vertex AI Search request shape/cap/errors/deduplication, Wellfound import/extraction boundaries, and required story regression suites.
- Code review fixes added free-tier cap enforcement, durable quota locking, sanitized provider errors, zero-signal provider diagnostics, streamed Wellfound response limits, import-safe extraction failures, and boundary regression tests.

### File List

- `.gitignore`
- `_bmad-output/implementation-artifacts/3-2-google-and-wellfound-direct-hiring-signal-providers.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/config.py`
- `backend/services/company_discovery.py`
- `backend/services/source_discovery.py`
- `backend/tests/services/test_source_discovery.py`

### Change Log

- 2026-05-27: Implemented search and Wellfound direct hiring signal providers and moved story to review.
- 2026-05-27: Addressed code review findings and moved story to done.
- 2026-05-28: Replaced legacy search support with Vertex AI Search because the legacy JSON API is closed to new customers.
