# Story 2.5: Automated ATS Source Discovery and Registry

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want the app to discover, validate, and persist public ATS job-board sources automatically,
so that weekly ingestion scans the widest practical AI-engineering market corpus without requiring me to manually provide company slugs.

## Product Context

Manual slugs are an implementation detail, not a product workflow. The weekly scanner must not depend on Darko knowing that Stripe is `greenhouse/stripe`, Employ is `lever/employ`, or Bunq is `recruitee/bunq`. The system needs a discovery layer that finds candidate career/job-board URLs, detects supported ATS providers, validates that the provider API returns usable job postings, persists a source registry, and feeds active validated sources into `run_full_ingestion`.

This story does **not** promise "all jobs on the internet." It promises honest coverage of jobs discoverable through supported public discovery channels and supported public ATS surfaces. Unsupported, blocked, empty, or irrelevant sources must be recorded with rejection reasons so misses are visible rather than silent. Generic careers pages must be expanded one hop to find embedded ATS links; otherwise most HN/company links will be missed.

## Acceptance Criteria

1. **Database Registry Migration**
   - Given the migration runner executes on startup
   - When `backend/db/migrations/V005__add_job_source_registry.sql` is applied
   - Then it creates `job_source_candidates`, `job_sources`, and `source_discovery_runs`
   - And `job_sources` has a unique constraint on `(ats, slug)`
   - And source status fields support at least `candidate`, `validated`, `rejected`, `inactive`, and `error`
   - And all JSON fields use `JSONB`, timestamps use `TIMESTAMP WITH TIME ZONE`, and table names are plural snake_case

2. **ATS URL Detection**
   - Given a URL or HTML/comment text containing supported ATS links
   - When the discovery service parses it
   - Then it detects and normalizes these patterns:
     - Greenhouse: `boards.greenhouse.io/{slug}`, `job-boards.greenhouse.io/{slug}`, `boards-api.greenhouse.io/v1/boards/{slug}/jobs`
     - Lever: `jobs.lever.co/{slug}` and `api.lever.co/v0/postings/{slug}`
     - Ashby: `jobs.ashbyhq.com/{slug}` and `api.ashbyhq.com/posting-api/job-board/{slug}`
     - Recruitee: `{slug}.recruitee.com`
     - Personio: `{slug}.jobs.personio.de` and `{slug}.jobs.personio.com`
     - Workable: `apply.workable.com/{slug}` and `apply.workable.com/api/v1/widget/accounts/{slug}`
   - And it rejects non-HTTP(S), malformed, duplicate, or unsupported URLs without raising unhandled exceptions

3. **Discovery From HN Who's Hiring**
   - Given the latest monthly HN "Who is hiring" thread is available through Algolia
   - When source discovery runs
   - Then it finds the latest official thread using `search_by_date` with `tags=story,author_whoishiring`
   - And fetches comments through `/api/v1/items/{thread_id}`
   - And extracts candidate career/ATS URLs from comment HTML using standard-library parsing or existing `strip_html` helpers
   - And records all detected ATS candidates with `discovery_method = 'hn_who_is_hiring'`

4. **Optional Manual-Hint Discovery**
   - Given an optional local manual-hint seed file is present
   - When source discovery runs
   - Then it can load seed URLs and company hints from that file
   - And treats the manual hints as bootstrap input only, not as the final market corpus
   - And source discovery still runs successfully when the file is absent

5. **One-Hop Careers Page Expansion**
   - Given a discovered URL is HTTP(S) but does not directly match a supported ATS pattern
   - When source discovery processes the URL
   - Then it may fetch that page once with a strict timeout and maximum response size
   - And it extracts ATS URLs from anchors, canonical links, script/config text, and visible page text using standard-library parsing
   - And it does not execute JavaScript, use browser automation, follow unbounded links, or crawl beyond the one fetched page
   - And it records unsupported or unparseable pages with `rejection_reason = 'unsupported_or_no_ats_detected'`

6. **Source Validation**
   - Given a detected candidate source
   - When validation runs
   - Then it calls the existing parser adapter for that ATS using the detected slug
   - And accepts the source only if:
     - the provider request succeeds
     - at least one posting is returned
     - at least one posting has non-empty `raw_text`
     - at least one posting passes AI/backend/data/product relevance keywords
   - And rejected sources persist `validation_status = 'rejected'` plus `rejection_reason`
   - And provider failures persist `validation_status = 'error'` plus `last_error`
   - And Workable is validated with the same standard as every other source; do not include Workable in active ingestion if the public widget endpoint returns `403` or empty descriptions
   - And Workable's authenticated SPI API is explicitly out of scope unless credentials are later added; this story only uses public/non-authenticated surfaces

7. **Active Registry Powers Weekly Ingestion**
   - Given active validated rows exist in `job_sources`
   - When `run_full_ingestion(pool, config=None)` is called by the scheduler or diagnostic script
   - Then it builds its ingestion config from active registry rows instead of `DEFAULT_INGESTION_CONFIG`
   - And `DEFAULT_INGESTION_CONFIG` is used only as a bootstrap fallback when no active registry rows exist
   - And the fallback path logs a warning stating that the source registry is empty

8. **Discovery API And Diagnostics**
   - Given the FastAPI app is running
   - When `POST /api/v1/ingest/discover-sources` is called
   - Then it runs source discovery in a background task using the existing task/SSE pattern
   - And emits log events for discovered, validated, rejected, and errored sources
   - And returns a `task_id`
   - And `GET /api/v1/ingest/sources` returns active and rejected sources with validation metadata for debugging coverage

9. **Coverage Report Artifact**
   - Given a discovery run completes
   - When the run summary is persisted
   - Then the system writes `_bmad-output/implementation-artifacts/source-discovery-report-YYYY-MM-DD.json`
   - And the report includes:
     - `candidate_count`
     - `validated_count`
     - `rejected_count`
     - `error_count`
     - counts by ATS
     - top rejection reasons
     - unsupported URL count
     - active source count after the run
     - source freshness counts: never validated, validated within current run, stale, inactive
     - explicit coverage gaps by reason, including unsupported ATS, blocked provider, empty descriptions, irrelevant postings, and no ATS found

10. **Tests And Regression Protection**
   - Given the implementation is complete
   - When the targeted test suite runs
   - Then it covers URL detection, HN comment parsing, one-hop careers page expansion, seed-file loading, validation success/failure, DB upsert behavior, registry-backed ingestion config, API endpoints, and Workable rejection on `403` or empty `raw_text`
   - And existing parser, scheduler, ingest router, and corpus sanity tests continue passing

## Tasks / Subtasks

- [x] Task 1: Add source registry migration (AC: 1)
  - [x] Create `backend/db/migrations/V005__add_job_source_registry.sql`.
  - [x] Add `job_source_candidates` for every discovered URL/candidate, including rejected and unsupported candidates.
  - [x] Add `job_sources` for normalized ATS sources used by ingestion.
  - [x] Add `source_discovery_runs` for discovery summaries and error accounting.
  - [x] Add indexes on `ats`, `slug`, `validation_status`, `active`, and `last_validated_at`.

- [x] Task 2: Implement ATS detection service (AC: 2)
  - [x] Create `backend/services/source_discovery.py`.
  - [x] Add a typed candidate model/dataclass with `company_hint`, `ats`, `slug`, `source_url`, and `discovery_method`.
  - [x] Implement URL normalization and provider-specific slug extraction using `urllib.parse`, not brittle string splitting.
  - [x] Deduplicate candidates by `(ats, slug)` and retain all source URLs in metadata.
  - [x] Add unit tests for every supported URL pattern and malformed/unsupported URLs.

- [x] Task 3: Implement HN discovery input (AC: 3)
  - [x] Reuse the HN Algolia approach already used in `fetch_hn_jobs`; avoid duplicating incompatible HN query logic.
  - [x] Fetch the latest official Who's Hiring thread with `tags=story,author_whoishiring` and `hitsPerPage=1`.
  - [x] Fetch comments via `https://hn.algolia.com/api/v1/items/{thread_id}`.
  - [x] Extract URLs from comment HTML using standard-library `html.parser.HTMLParser` or a small local helper.
  - [x] Preserve nearby company text as `company_hint` where practical.
  - [x] Add tests using fixture comments with multiple ATS links, normal career links, and malformed HTML.

- [x] Task 4: Implement optional manual-hint discovery input (AC: 4)
  - [x] Implement optional seed/manual-hint provider without requiring a committed corpus file.
  - [x] Treat missing file as a quiet no-op so discovery is not dependent on manual seeds.
  - [x] Preserve loader validation for invalid JSON with a clear error.
  - [x] Add tests for valid, missing, and invalid optional manual-hint files.

- [x] Task 5: Implement one-hop careers page expansion (AC: 5)
  - [x] For non-ATS HTTP(S) URLs from HN or seed inputs, fetch only that page using `httpx.AsyncClient(timeout=5.0, follow_redirects=True)`.
  - [x] Enforce a maximum response size before parsing to avoid large-page memory issues.
  - [x] Parse `href` values, canonical links, and inline text for supported ATS URL patterns.
  - [x] Do not execute JavaScript or add Playwright/Selenium.
  - [x] Add tests for a generic careers page containing Greenhouse, Lever, Ashby, Workable, Recruitee, and Personio links.

- [x] Task 6: Implement validation and persistence (AC: 6)
  - [x] Add `validate_candidate_source(candidate)` that calls existing parser adapters from `backend/services/parser.py`.
  - [x] Enforce success criteria: provider success, job count > 0, usable `raw_text`, and AI/backend/data/product keyword relevance.
  - [x] Persist accepted sources to `job_sources(active = true, validation_status = 'validated')`.
  - [x] Persist rejected/errors to `job_source_candidates` with reason/error fields.
  - [x] Update existing source rows rather than inserting duplicates.
  - [x] Add tests for Greenhouse, Lever, Ashby, Recruitee, Personio success; Workable `403`; Workable authenticated SPI being out of scope; empty `raw_text`; irrelevant postings; duplicate sources.

- [x] Task 7: Make ingestion registry-backed (AC: 7)
  - [x] Add `load_active_source_config(pool)` returning the exact config shape expected by `run_full_ingestion`.
  - [x] Update `run_full_ingestion(pool, config=None)` to call `load_active_source_config(pool)` first.
  - [x] Use `DEFAULT_INGESTION_CONFIG` only if the registry returns no active rows.
  - [x] Ensure explicit user-provided config still bypasses the registry for interview/demo scans.
  - [x] Add tests proving scheduler/default ingestion uses registry rows and manual config still works.

- [x] Task 8: Add discovery endpoints and SSE logging (AC: 8)
  - [x] Add `POST /api/v1/ingest/discover-sources` in `backend/routers/ingest.py`.
  - [x] Reuse `task_manager`, `active_task_id`, and `run_ingestion_task` patterns; do not create a second task infrastructure.
  - [x] Add `GET /api/v1/ingest/sources` returning source registry diagnostics.
  - [x] Keep native `StreamingResponse` SSE; do not add external SSE dependencies.
  - [x] Add router tests for task creation, no pool, and registry listing.

- [x] Task 9: Write discovery report artifact (AC: 9)
  - [x] Write `_bmad-output/implementation-artifacts/source-discovery-report-YYYY-MM-DD.json` at the end of each discovery run.
  - [x] Include counts, freshness, and rejection reasons required by AC 9.
  - [x] Ensure artifact writing failure is logged and does not corrupt DB persistence.

- [x] Task 10: Verification (AC: 10)
  - [x] Run targeted backend tests:
    - `backend/venv/bin/pytest -q backend/tests/services/test_parser.py backend/tests/services/test_source_discovery.py backend/tests/routers/test_ingest.py backend/tests/scripts/test_corpus_sanity.py`
  - [x] Run `backend/venv/bin/python -m compileall backend/services backend/routers backend/scripts`.
  - [x] Run a local discovery dry run and inspect the generated source discovery report.
  - [x] Run corpus sanity after one registry-backed ingestion and confirm `latest_ingestion_run.error_message` is null or only contains explicitly accepted partial-source failures.

### Review Findings

- [x] [Review][Patch] Expand generic HN career URLs before rejecting them [backend/services/source_discovery.py:279]
- [x] [Review][Patch] Fail discovery on invalid committed seed JSON instead of swallowing it as a provider error [backend/services/source_discovery.py:489]
- [x] [Review][Patch] Compute source freshness counts from registry state instead of hard-coding stale and inactive to zero [backend/services/source_discovery.py:665]

## Dev Notes

### Existing Code To Reuse

- Parser adapters already live in `backend/services/parser.py`:
  - `fetch_greenhouse_jobs`
  - `fetch_lever_jobs`
  - `fetch_ashby_jobs`
  - `fetch_workable_jobs`
  - `fetch_recruitee_jobs`
  - `fetch_personio_jobs`
  - `fetch_hn_jobs`
  - `run_full_ingestion`
- HTML stripping already exists as `strip_html`; do not add BeautifulSoup/lxml.
- Background task/SSE infrastructure already exists in:
  - `backend/routers/ingest.py`
  - `backend/utils/tasks.py`
  - `backend/utils/logging.py`
- Corpus diagnostics already exist in `backend/scripts/corpus_sanity.py`.

### Hard Requirements

- Do not add scraping/browser automation dependencies.
- Do not scrape Google/Bing result pages.
- Do not implement general crawling. One-hop page expansion is allowed only for URLs already discovered from HN or seed inputs.
- Do not claim total-market coverage. Report supported coverage and explicit gaps.
- Do not make Workable active unless validation proves non-empty descriptions.
- Do not use Workable's authenticated SPI API in this story; only public/non-authenticated Workable surfaces are allowed.
- Do not call LLM extraction in this story.
- Do not create `V003` or `V006` accidentally for this story; this story owns `V005__add_job_source_registry.sql`.
- Keep all HTTP calls bounded with strict `httpx` timeouts.
- Keep parser failure isolation: one source failure must not abort discovery or ingestion unless every discovery input fails.
- Preserve manual company slug scan as a demo/debug path, but it must not be the default weekly-market workflow.

### Suggested Schema

`job_source_candidates`:

- `id SERIAL PRIMARY KEY`
- `run_id INTEGER REFERENCES source_discovery_runs(id)`
- `raw_url TEXT NOT NULL`
- `normalized_url TEXT`
- `company_hint TEXT`
- `detected_ats VARCHAR(50)`
- `detected_slug VARCHAR(255)`
- `discovery_method VARCHAR(100) NOT NULL`
- `validation_status VARCHAR(50) NOT NULL DEFAULT 'candidate'`
- `rejection_reason TEXT`
- `last_error TEXT`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`

`job_sources`:

- `id SERIAL PRIMARY KEY`
- `company TEXT`
- `ats VARCHAR(50) NOT NULL`
- `slug VARCHAR(255) NOT NULL`
- `source_url TEXT NOT NULL`
- `discovery_method VARCHAR(100) NOT NULL`
- `validation_status VARCHAR(50) NOT NULL`
- `active BOOLEAN NOT NULL DEFAULT false`
- `job_count INTEGER NOT NULL DEFAULT 0`
- `usable_job_count INTEGER NOT NULL DEFAULT 0`
- `last_validated_at TIMESTAMP WITH TIME ZONE`
- `last_success_at TIMESTAMP WITH TIME ZONE`
- `last_error TEXT`
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `UNIQUE (ats, slug)`

`source_discovery_runs`:

- `id SERIAL PRIMARY KEY`
- `run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `status VARCHAR(50) NOT NULL`
- `candidate_count INTEGER NOT NULL DEFAULT 0`
- `validated_count INTEGER NOT NULL DEFAULT 0`
- `rejected_count INTEGER NOT NULL DEFAULT 0`
- `error_count INTEGER NOT NULL DEFAULT 0`
- `source_counts JSONB NOT NULL DEFAULT '{}'::jsonb`
- `rejection_reasons JSONB NOT NULL DEFAULT '{}'::jsonb`
- `coverage_gaps JSONB NOT NULL DEFAULT '{}'::jsonb`
- `error_message TEXT`
- `execution_time_seconds NUMERIC(10, 2) NOT NULL DEFAULT 0.0`

### Relevance Keywords

Use a conservative first-pass keyword list. This is source validation, not final ranking:

- `ai`, `llm`, `machine learning`, `ml`, `rag`, `agent`, `agents`
- `backend`, `platform`, `data`, `mlops`, `inference`, `vector`
- `python`, `fastapi`, `pytorch`, `kubernetes`, `eval`, `evaluation`

A source can be active if at least one posting title or `raw_text` matches these keywords. Store counts so the threshold can be tuned later.

### Project Structure Notes

- New service: `backend/services/source_discovery.py`
- New migration: `backend/db/migrations/V005__add_job_source_registry.sql`
- Router updates: `backend/routers/ingest.py`
- New tests: `backend/tests/services/test_source_discovery.py`
- Existing tests to update: `backend/tests/services/test_parser.py`, `backend/tests/routers/test_ingest.py`, scheduler tests if default ingestion behavior changes through `run_full_ingestion`.
- Optional manual-hint seed path: `_bmad-output/planning-artifacts/source-discovery-seeds.json` (not committed as required corpus)
- Discovery report: `_bmad-output/implementation-artifacts/source-discovery-report-YYYY-MM-DD.json`

### References

- [Epic 2 plan](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md)
- [PRD ingestion requirements](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md)
- [Architecture SSE and parser boundaries](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md)
- [Epic 2 retrospective action items](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/epic-2-retro-2026-05-27.md)
- Greenhouse Job Board API: https://developers.greenhouse.io/job-board
- Lever Postings API: https://github.com/lever/postings-api
- Ashby public job posting API: https://developers.ashbyhq.com/docs/public-job-posting-api
- HN Algolia API: https://hn.algolia.com/api
- Recruitee published offers endpoint: https://docs.recruitee.com/reference/offers
- Personio XML job feed: https://support.personio.de/hc/en-us/articles/207576365-Integrate-jobs-from-Personio-into-your-company-website-via-XML
- Workable careers-page API note: https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-27T16:30:04+05:30 - Story and sprint status moved to in-progress.
- 2026-05-27T16:43:42+05:30 - Local dry-run source discovery generated `_bmad-output/implementation-artifacts/source-discovery-report-2026-05-27.json`.
- 2026-05-27T16:47:00+05:30 - Targeted backend test suite passed: 51 passed.
- 2026-05-27T16:47:00+05:30 - Full backend test suite passed with `PYTHONPATH=.`: 78 passed.
- 2026-05-27 - Code review patch findings fixed; targeted source discovery suite passed, targeted backend suite passed, full backend suite passed, and compileall passed.

### Completion Notes List

- Added V005 source registry migration with discovery run, candidate, and active source tables plus required JSONB/timestamp fields and indexes.
- Implemented ATS URL detection, HN and optional manual-hint discovery inputs, one-hop careers expansion, source validation, DB persistence/upsert, registry-backed ingestion config, and JSON coverage report generation.
- Added discovery task endpoint, source diagnostics endpoint, and task/SSE-compatible background logging.
- Preserved manual company-slug ingestion override; default/scheduled ingestion now uses active validated registry rows and falls back to `DEFAULT_INGESTION_CONFIG` only when the registry is empty.
- Added focused tests for detection, parsing, optional manual-hint handling, expansion, validation/rejection, DB persistence, ingestion config, API endpoints, and regression coverage.

### File List

- `_bmad-output/implementation-artifacts/2-5-automated-ats-source-discovery-and-registry.md`
- `_bmad-output/implementation-artifacts/source-discovery-report-2026-05-27.json`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/db/migrations/V005__add_job_source_registry.sql`
- `backend/routers/ingest.py`
- `backend/services/parser.py`
- `backend/services/source_discovery.py`
- `backend/tests/routers/test_ingest.py`
- `backend/tests/services/test_parser.py`
- `backend/tests/services/test_source_discovery.py`

### Change Log

- 2026-05-27: Implemented automated ATS source discovery and registry; story ready for review.
