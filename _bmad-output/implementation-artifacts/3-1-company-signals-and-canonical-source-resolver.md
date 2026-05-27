# Story 3.1: Company Signals and Canonical Source Resolver

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want discovered company signals to be persisted and resolved to canonical careers or ATS sources,
so that later provider integrations can identify which companies are worth checking without directly trusting third-party job boards.

## Product Context

Epic 2 established the trusted source boundary: weekly ingestion reads only active, validated rows from `job_sources`; discovery inputs and rejected URLs remain diagnostic evidence. Story 3.1 extends that boundary one layer upstream. New providers in Stories 3.2-3.4 will emit company names, domains, careers URLs, and evidence metadata. Those signals must be persisted first, then resolved through bounded canonical-source checks, then activated only if they produce a supported ATS source that passes the existing parser-backed validation.

This story must not turn Google, Wellfound, YC, VC portfolios, GitHub, Reddit, or marketplace pages into trusted job corpora. It creates the company-signal registry and canonical resolver that later providers use before anything reaches `job_sources`.

## Acceptance Criteria

1. **Company Signal Migration**
   - Given migrations run after `backend/db/migrations/V005__add_job_source_registry.sql`
   - When the new migration is applied
   - Then it creates plural snake_case tables for company discovery runs and company signals
   - And rows store provider name, evidence URL, company name/domain, normalized domain, optional careers URL, confidence/category hints, status, rejection reason, timestamps, and JSONB metadata
   - And signal status fields support at least `candidate`, `resolved`, `rejected`, `unresolved`, and `error`
   - And repeated provider evidence is deduplicated or upserted without losing first-seen/last-seen timestamps
   - And migration numbering does not collide with existing migrations; Story 3.1 owns `V006__add_company_discovery.sql`, and later eval/extraction migrations must move to the next available version

2. **Company Signal Provider Contract**
   - Given a discovery provider emits company-level evidence
   - When the backend receives the provider output
   - Then a typed company signal model/contract can represent company domains, careers URLs, direct ATS URLs, confidence, category hints, provider metadata, and evidence URLs
   - And unsupported or incomplete provider output is rejected with visible reasons instead of raising unhandled exceptions

3. **Canonical Resolver Boundaries**
   - Given a company domain or careers URL signal
   - When canonical resolution runs
   - Then it checks only bounded company paths: `/careers`, `/jobs`, `/join-us`, `/work-with-us`, `/company/careers`
   - And it may inspect declared sitemaps from `/robots.txt` and `/sitemap.xml`
   - And it parses anchors, canonical links, visible text, script/config text, supported ATS URLs, and `JobPosting` JSON-LD
   - And it never executes JavaScript, uses browser automation, follows recursive links, scrapes marketplace result pages, or crawls unbounded URLs

4. **ATS Validation And Activation Boundary**
   - Given canonical resolution finds a supported ATS URL
   - When the resolver attempts activation
   - Then it normalizes the URL through existing `normalize_ats_url`
   - And validates through existing `validate_candidate_source`
   - And only validated ATS sources are upserted into `job_sources(active = true, validation_status = 'validated')`
   - And unresolved, unsupported, rejected, or errored signals remain visible in company signal/candidate diagnostics with rejection reasons
   - And `JobPosting` JSON-LD findings are persisted as resolved evidence unless an explicit JSON-LD validation path is implemented; do not insert unvalidated JSON-LD pages into active `job_sources`

5. **Discovery Orchestration Integration**
   - Given `discover_sources(pool)` runs
   - When company-signal providers are configured
   - Then their signals are persisted in a company discovery run
   - And direct ATS signals still flow through the existing source candidate validation path
   - And domain/careers signals flow through canonical resolution before any source activation
   - And provider failures are isolated per provider so one noisy channel does not abort the whole run unless all configured inputs fail or the input file/config is invalid

6. **API Diagnostics**
   - Given the FastAPI app is running
   - When `GET /api/v1/ingest/company-signals` is called
   - Then it returns recent company signals with provider, evidence, resolution status, resolved source metadata, rejection reason, and last error
   - And response keys remain snake_case
   - And the existing `/api/v1/ingest/discover-sources` task/SSE lifecycle remains unchanged

7. **Report Coverage**
   - Given a discovery run completes
   - When `_bmad-output/implementation-artifacts/source-discovery-report-YYYY-MM-DD.json` is written
   - Then it includes company-signal counts, resolved source counts, unresolved counts, rejected reasons, and counts by provider
   - And existing source discovery report fields from Story 2.5 remain present

8. **Tests And Regression Protection**
   - Given implementation is complete
   - When targeted tests run
   - Then they cover migration shape, provider contract normalization/rejection, bounded path generation, sitemap parsing caps, JSON-LD extraction, ATS URL resolution, validation-gated activation, persistence, API diagnostics, and report fields
   - And existing parser, source discovery, ingest router, scheduler, and corpus sanity tests continue passing

## Tasks / Subtasks

- [x] Task 1: Add company discovery migration (AC: 1)
  - [x] Create `backend/db/migrations/V006__add_company_discovery.sql` unless a `V006` migration already exists; if so, use the next available version.
  - [x] Add `company_discovery_runs` for run summaries and provider-level error accounting.
  - [x] Add `company_signals` for provider evidence, company domain plus normalized domain, resolution status, resolved ATS/source metadata, rejection reason, last error, and metadata JSONB.
  - [x] Add indexes on provider, normalized domain, status, confidence, and last_seen/resolved timestamps.
  - [x] Add a dedupe/upsert constraint that prevents repeated provider evidence from creating unbounded duplicate signal rows while preserving `first_seen_at` and updating `last_seen_at`.

- [x] Task 2: Add company signal models and provider contract (AC: 2)
  - [x] Extend `backend/services/source_discovery.py` or add `backend/services/company_discovery.py` if the source file becomes too broad.
  - [x] Define a dataclass/protocol for company signals with provider name, evidence URL, company name, company domain, careers URL, direct ATS URL, confidence, category hints, and metadata.
  - [x] Normalize domains with `urllib.parse`; reject malformed, non-HTTP(S), duplicate, or unsupported inputs without unhandled exceptions.
  - [x] Keep direct ATS signal handling compatible with existing `SourceCandidate`.

- [x] Task 3: Implement canonical resolver (AC: 3, 4)
  - [x] Add resolver functions in `backend/services/canonical_resolver.py` or the agreed service module.
  - [x] Generate only bounded path candidates for company domains.
  - [x] Fetch pages once with strict `httpx.AsyncClient(timeout=5.0, follow_redirects=True)` and `MAX_PAGE_BYTES` enforcement.
  - [x] Reuse existing HTML URL extraction patterns; do not add BeautifulSoup, lxml, Playwright, Selenium, or browser automation.
  - [x] Parse `/robots.txt` sitemap declarations and `/sitemap.xml` with caps on sitemap URLs inspected.
  - [x] Extract `JobPosting` JSON-LD with standard-library `json` parsing and persist it as evidence unless fully validated.

- [x] Task 4: Wire resolver to validation and persistence (AC: 4, 5)
  - [x] Route resolved ATS URLs through `normalize_ats_url` and `validate_candidate_source`.
  - [x] Reuse `persist_discovery_result`/`job_sources` upsert behavior for validated ATS sources where practical.
  - [x] Persist rejected/unresolved company signals with explicit reasons such as `invalid_domain`, `no_canonical_source_found`, `unsupported_ats`, `validation_rejected`, `validation_error`, or `json_ld_unvalidated`.
  - [x] Preserve failure isolation: one failed company must not abort the discovery run.

- [x] Task 5: Add API diagnostics (AC: 6)
  - [x] Add `GET /api/v1/ingest/company-signals` to `backend/routers/ingest.py`.
  - [x] Return recent company signals and enough resolved source metadata to debug provider yield.
  - [x] Keep existing `/api/v1/ingest/discover-sources`, task IDs, SSE event names, and source registry endpoint behavior intact.

- [x] Task 6: Extend report artifact (AC: 7)
  - [x] Add company-signal metrics to `write_discovery_report`.
  - [x] Preserve existing keys: `candidate_count`, `validated_count`, `rejected_count`, `error_count`, `counts_by_ats`, `top_rejection_reasons`, `unsupported_url_count`, `active_source_count_after_run`, `source_freshness_counts`, and `coverage_gaps`.
  - [x] Include provider counts, resolved source counts, unresolved counts, and rejected reasons for company signals.

- [x] Task 7: Verification (AC: 8)
  - [x] Add or update `backend/tests/services/test_source_discovery.py` and/or `backend/tests/services/test_canonical_resolver.py`.
  - [x] Add router tests in `backend/tests/routers/test_ingest.py`.
  - [x] Run targeted backend tests: `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py`.
  - [x] Run `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts`.

### Review Findings

- [x] [Review][Patch] Resolver accepts arbitrary provider-supplied careers URLs [backend/services/canonical_resolver.py:130]
- [x] [Review][Patch] Rejected ATS validations from domain/careers resolution are dropped [backend/services/canonical_resolver.py:185]
- [x] [Review][Patch] Malformed company-signal provider output can abort discovery [backend/services/source_discovery.py:568]
- [x] [Review][Patch] Direct ATS company signals bypass source candidate diagnostics [backend/services/source_discovery.py:565]
- [x] [Review][Patch] Resolver response-size cap is applied after full buffering [backend/services/canonical_resolver.py:119]
- [x] [Review][Patch] Company signal diagnostics omit resolved candidate metadata [backend/services/company_discovery.py:225]
- [x] [Review][Patch] Company diagnostics persistence failure can abort the source discovery run [backend/services/source_discovery.py:670]
- [x] [Review][Patch] Date-dependent report test will fail after 2026-05-27 [backend/tests/services/test_source_discovery.py:660]
- [x] [Review][Defer] Resolver has no per-run company signal cap [backend/services/source_discovery.py:582] — deferred, story does not specify a global provider yield cap.

## Dev Notes

### Existing Code To Reuse

- `backend/services/source_discovery.py`
  - `SourceCandidate`, `ValidationResult`, `DiscoveryProviderResult`, `DiscoveryProvider`
  - `normalize_ats_url`
  - `dedupe_candidates`
  - `extract_urls_from_html`
  - `expand_careers_page_once`
  - `validate_candidate_source`
  - `persist_discovery_result`
  - `write_discovery_report`
- Parser-backed validation already lives in `backend/services/parser.py` and supports Greenhouse, Lever, Ashby, Workable, Recruitee, and Personio.
- Existing source registry tables are in `backend/db/migrations/V005__add_job_source_registry.sql`.
- Existing discovery API/SSE task flow is in `backend/routers/ingest.py`; do not create a second task system.

### Hard Requirements

- Do not activate a source from a company signal unless it resolves to a supported ATS URL and passes `validate_candidate_source`.
- Do not scrape Google/Bing result pages, LinkedIn, Indeed, or marketplace job pages.
- Do not trust Wellfound, YC, VC, GitHub, Reddit, or Google output as job data; they are evidence only.
- Do not add browser automation or recursive crawling.
- Do not add new parsing dependencies unless absolutely necessary; current implementation uses `html.parser`, `urllib.parse`, `json`, and `httpx`.
- Keep HTTP calls bounded by strict timeouts and maximum response size.
- Keep DB and API naming plural snake_case, JSON fields JSONB, and timestamps `TIMESTAMP WITH TIME ZONE`.
- Keep `DEFAULT_INGESTION_CONFIG` as bootstrap fallback only; weekly ingestion must continue using active validated `job_sources`.
- Do not reuse `V003` or `V005`. `V005` belongs to Story 2.5.
- `V006__add_company_discovery.sql` belongs to this story; planned eval/extraction migrations must use later available versions.

### Suggested Schema

`company_discovery_runs`:

- `id SERIAL PRIMARY KEY`
- `run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `status VARCHAR(50) NOT NULL`
- `provider_counts JSONB NOT NULL DEFAULT '{}'::jsonb`
- `resolved_count INTEGER NOT NULL DEFAULT 0`
- `unresolved_count INTEGER NOT NULL DEFAULT 0`
- `rejected_count INTEGER NOT NULL DEFAULT 0`
- `error_count INTEGER NOT NULL DEFAULT 0`
- `rejection_reasons JSONB NOT NULL DEFAULT '{}'::jsonb`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_message TEXT`
- `execution_time_seconds NUMERIC(10, 2) NOT NULL DEFAULT 0.0`

`company_signals`:

- `id SERIAL PRIMARY KEY`
- `run_id INTEGER REFERENCES company_discovery_runs(id)`
- `provider VARCHAR(100) NOT NULL`
- `company_name TEXT`
- `company_domain TEXT`
- `normalized_domain TEXT`
- `careers_url TEXT`
- `direct_ats_url TEXT`
- `evidence_url TEXT NOT NULL`
- `confidence NUMERIC(5, 2)`
- `category_hints JSONB NOT NULL DEFAULT '[]'::jsonb`
- `status VARCHAR(50) NOT NULL DEFAULT 'candidate'`
- `resolved_ats VARCHAR(50)`
- `resolved_slug VARCHAR(255)`
- `resolved_source_url TEXT`
- `json_ld_evidence JSONB NOT NULL DEFAULT '[]'::jsonb`
- `rejection_reason TEXT`
- `last_error TEXT`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `resolved_at TIMESTAMP WITH TIME ZONE`

Suggested signal statuses: `candidate`, `resolved`, `rejected`, `unresolved`, `error`.

### Previous Story Intelligence

- Story 2.5 already built and reviewed the source registry. Extend it instead of creating parallel ingestion activation logic.
- Reuse the existing provider failure-isolation pattern: provider exceptions are logged and counted; invalid committed seed JSON is allowed to fail loudly.
- Reuse the existing one-hop expansion constraints: strict timeout, max response size, no JavaScript, no unbounded crawling.
- Workable must remain inactive unless public validation returns non-empty descriptions; authenticated Workable SPI is still out of scope.
- The latest source discovery commit was `5626307 Add source discovery registry and company radar plan`, which added the current architecture and channel strategy for this story.

### Architecture Compliance

- Backend services live under `backend/services/`; routers only orchestrate request/response and call services.
- Raw SQL migrations in `backend/db/migrations/` are the database source of truth; no Alembic or ORM.
- API routes stay under `/api/v1` via the existing router prefix.
- API responses should use snake_case keys and avoid camelCase conversion layers.
- SSE events must remain `task.started`, `task.log`, `task.completed`, and `task.failed`.

### References

- [Epics: Story 3.1](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md:351)
- [PRD: Company Discovery FR48-FR55](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md:656)
- [Architecture: Company Discovery Boundary](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md:378)
- [Source Discovery Channel Strategy](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/source-discovery-channel-strategy.md:1)
- [Epic 3 Readiness Notes](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/epic-3-readiness.md:1)
- [Story 2.5](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/2-5-automated-ats-source-discovery-and-registry.md:1)
- [Source Discovery Service](/home/darko/Code/be-an-ai-engineer/backend/services/source_discovery.py:1)
- [Source Registry Migration](/home/darko/Code/be-an-ai-engineer/backend/db/migrations/V005__add_job_source_registry.sql:1)

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `backend/venv/bin/pytest -q backend/tests/services/test_canonical_resolver.py backend/tests/services/test_source_discovery.py backend/tests/routers/test_ingest.py` - 44 passed, 1 warning
- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/services/test_canonical_resolver.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py` - 47 passed, 1 warning
- `backend/venv/bin/pytest -q backend/tests/services/test_source_discovery.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py` - 42 passed, 1 warning
- `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts` - passed
- `backend/venv/bin/pytest -q backend/tests` - 94 passed, 1 warning

### Completion Notes List

- Added `V006__add_company_discovery.sql` with `company_discovery_runs`, `company_signals`, status checks, diagnostic JSONB fields, timestamps, indexes, and a null-safe unique index for provider evidence upserts.
- Added company signal contract, normalization, metrics, persistence, and validation-gated `job_sources` activation.
- Added bounded canonical resolver for direct ATS URLs, company path checks, robots/sitemap inspection, supported ATS extraction, and `JobPosting` JSON-LD evidence capture without browser automation or recursive crawling.
- Integrated company-signal providers into `discover_sources`, preserving existing source candidate validation/report fields, adding all-provider failure handling, and adding company-signal report metrics.
- Added `GET /api/v1/ingest/company-signals` diagnostics with snake_case response keys.
- Added regression coverage for migration shape, provider normalization/rejection, bounded paths, sitemap caps, JSON-LD extraction, ATS validation, persistence, API diagnostics, report fields, and full backend regression.

### File List

- `backend/db/migrations/V006__add_company_discovery.sql`
- `backend/services/company_discovery.py`
- `backend/services/canonical_resolver.py`
- `backend/services/source_discovery.py`
- `backend/routers/ingest.py`
- `backend/tests/services/test_canonical_resolver.py`
- `backend/tests/services/test_source_discovery.py`
- `backend/tests/routers/test_ingest.py`
- `_bmad-output/implementation-artifacts/3-1-company-signals-and-canonical-source-resolver.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-05-27: Implemented Story 3.1 company signal registry, bounded canonical resolver, diagnostics API, report metrics, and regression tests. Status moved to review.
