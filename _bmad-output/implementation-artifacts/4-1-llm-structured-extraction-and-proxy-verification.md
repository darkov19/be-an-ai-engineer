# Story 4.1: LLM Structured Extraction and Proxy Verification

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a Pydantic-validated extraction client that sends job text to the local Hermes proxy and returns structured JSON, batching calls, versioning prompts, and verifying proxy health before processing,
so that extraction is structured, audit-logged, and fails safely if the proxy is offline.

## Product Context

Epic 4 starts the Prognosis Engine: structured extraction, evals, regression charts, and kill-criterion enforcement. Story 4.1 is the extraction foundation. It must turn existing `jobs.raw_text` rows into audited structured fields without trusting raw provider signals or bypassing the Hermes health boundary.

The first extraction corpus must be selected from validated active job sources using provider yield, not from raw source volume. Current planning selects `hn_who_is_hiring`, `vertex_ai_search`, and `common_crawl_ats` as the initial high-yield slice, while excluding raw `company_signals`, unsupported URLs, disabled providers, unresolved companies, and low-yield providers until later reports justify them.

## Acceptance Criteria

1. **Extraction Storage Migration Is Added Without Breaking Existing Jobs**
   - Given the current `jobs` table has `id`, `url`, `title`, `company`, `location`, `raw_text`, `source_slug`, `status`, `created_at`, and `updated_at`
   - When migrations run
   - Then a new migration after `V006__add_company_discovery.sql`, expected to be `V007__add_job_extraction_fields.sql`, adds extraction fields to `jobs`: `extracted_at`, `prompt_version`, `extraction_schema_version`, `skills`, `seniority`, `tech_stack`, `salary_band`, `remote_policy`, `role_archetype`, `extraction_status`, and `extraction_error`
   - And it adds `extraction_run_id` or equivalent run/correlation metadata so extracted rows can be audited back to a local extraction run summary
   - And the migration adds indexes needed for selecting unextracted rows, at minimum `extracted_at`, `extraction_status`, and the existing source/status filter path
   - And extraction updates explicitly update `updated_at` or add a reusable trigger so Epic 3's known stale `jobs.updated_at` risk is resolved.

2. **Pydantic Schemas Define The Extraction Contract**
   - Given `backend/llm/schemas.py`
   - When the module is imported
   - Then it defines strict Pydantic v2 models for a single extracted posting and a batch response
   - And the schema includes `skills`, `seniority`, `tech_stack`, `salary_band`, `remote_policy`, and `role_archetype`
   - And enums match the eval rubric: seniority `entry`, `mid`, `senior`, `staff_plus`, `unknown`; remote policy `remote`, `hybrid`, `onsite`, `flexible`, `unknown`; role archetype `llm_app_engineer`, `ai_product_engineer`, `agent_engineer`, `ml_platform_engineer`, `data_ai_engineer`, `research_engineer`, `unknown`
   - And `salary_band` supports `not_disclosed` plus disclosed currency/range fields without forcing fabricated salary data
   - And invalid LLM output raises a validation error before any successful extraction fields are persisted.

3. **Versioned Prompt Artifact Exists And Is Used**
   - Given a new `prompts/` directory
   - When extraction runs
   - Then the client loads a versioned prompt file such as `prompts/extraction_v1.md`
   - And the prompt embeds or references the JSON schema from `ExtractionBatch.model_json_schema()`
   - And each updated job row records the prompt version ID and extraction schema version
   - And prompt examples must not tune against held-out eval rows.

4. **Hermes Proxy Health Is Verified Before Any Batch Work**
   - Given `HERMES_HOST` and `HERMES_PORT` are configured through existing settings
   - When the extraction pipeline starts
   - Then it calls the existing `check_hermes_proxy_health()` from `backend/llm/hermes.py` before selecting or posting extraction batches
   - And if the proxy is unreachable, it aborts the run before mutating rows, logs the target URL and safe error text through structlog, and raises `HermesProxyConnectionError`
   - And it does not reimplement a parallel Hermes health client or a second exception hierarchy.

5. **Extraction Client Batches Unextracted Jobs Through Hermes**
   - Given unextracted `jobs` rows with non-empty `raw_text`
   - When `backend/llm/client.py` runs an extraction batch
   - Then it selects only rows where `extracted_at IS NULL` or `extraction_status` is retryable
   - And it defaults to 20 postings per LLM call
   - And it sends a JSON request to the local Hermes proxy using `httpx.AsyncClient`
   - And each request includes enough input identity to map each model output back to the correct `jobs.id`
   - And every returned object must map to a requested `jobs.id`; unknown, duplicate, or malformed IDs are rejected
   - And duplicate or already extracted postings are skipped using `extracted_at` as the cache key.

6. **Database Updates Are Atomic And Auditable**
   - Given Hermes returns a valid extraction batch
   - When rows are updated
   - Then successful rows persist JSONB/list fields, scalar enum fields, `extracted_at`, `prompt_version`, `extraction_schema_version`, and `extraction_status = 'extracted'`
   - And if a batch returns fewer valid objects than requested, valid objects are committed and missing/invalid posting IDs are marked `failed` or `retryable_error` with redacted `extraction_error`, matching PRD NFR-I3 partial-failure behavior
   - And rows with validation or per-item extraction errors record `extraction_status = 'failed'` or `retryable_error` plus a redacted `extraction_error`
   - And partial failures do not corrupt successful rows or leave the batch in an ambiguous state
   - And raw Hermes responses are not stored wholesale in the database or story artifacts.

7. **Extraction Script Provides A Local Developer Entry Point**
   - Given the backend virtual environment and database are configured
   - When running a script such as `backend/scripts/run_extraction.py`
   - Then the script runs Hermes health verification, selects an optional bounded batch, prints a summary of selected, extracted, skipped, failed, retryable errors, prompt version, schema version, and elapsed time, and exits non-zero on proxy failure
   - And it writes a local run summary artifact such as `_bmad-output/implementation-artifacts/extraction-run-YYYY-MM-DD.json` or returns equivalent structured data from the script for later eval/report integration
   - And it supports a dry-run or limit option so the first run can validate prompt/schema behavior without processing the whole corpus.

8. **Tests Cover Schema, Proxy Failure, Batching, Persistence, And No-Reinvention Boundaries**
   - Given implementation is complete
   - When targeted backend tests run
   - Then tests cover Pydantic valid/invalid outputs, enum rejection, salary disclosed/not-disclosed cases, unknown/duplicate returned IDs, partial valid batches, Hermes connection failure aborting before row mutation, HTTP/status errors, malformed JSON, already-extracted row skipping, prompt version persistence, atomic row updates, run summary output, and extraction error redaction
   - And tests assert the implementation reuses `backend/llm/hermes.py`
   - And existing Hermes, parser, source discovery, ingestion, corpus sanity, and migration tests continue passing.

## Tasks / Subtasks

- [x] Task 1: Add extraction storage migration (AC: 1, 6)
  - [x] Create `V007__add_job_extraction_fields.sql` unless another migration has already taken `V007`; do not reuse `V006`.
  - [x] Add extraction columns to the existing `jobs` table rather than creating a parallel `postings` table.
  - [x] Use JSONB for `skills`, `tech_stack`, and `salary_band`; use text/enum-like constrained text for `seniority`, `remote_policy`, and `role_archetype`.
  - [x] Add extraction run/correlation metadata (`extraction_run_id` or equivalent) for auditability.
  - [x] Add `extraction_status` values that can distinguish pending, extracted, failed, and retryable errors.
  - [x] Add indexes for unextracted/retryable selection and prompt/version diagnostics.
  - [x] Fix the `updated_at` freshness issue with explicit update logic or a reusable trigger.

- [x] Task 2: Implement structured schema models (AC: 2)
  - [x] Add `backend/llm/schemas.py`.
  - [x] Define `SalaryBand`, `ExtractedJobSignal`, and `ExtractionBatch` or equivalent Pydantic v2 models.
  - [x] Use enum/Literal constraints for rubric-backed categorical fields.
  - [x] Include a schema version constant such as `EXTRACTION_SCHEMA_VERSION = "v1"`.
  - [x] Add unit tests under `backend/tests/llm/test_schemas.py`.

- [x] Task 3: Add versioned prompt artifact (AC: 3)
  - [x] Create `prompts/extraction_v1.md`.
  - [x] Include instructions matching the six-field eval rubric and the product role archetypes.
  - [x] Require one output object per input job ID and no extra commentary.
  - [x] Record prompt version as `extraction_v1` or an equivalent stable ID in every row update.

- [x] Task 4: Implement Hermes extraction client (AC: 4, 5, 6)
  - [x] Add `backend/llm/client.py`.
  - [x] Reuse `check_hermes_proxy_health()` and `HermesProxyConnectionError` from `backend/llm/hermes.py`.
  - [x] Use `httpx.AsyncClient` with explicit timeout and JSON payloads; handle `httpx.RequestError`, `httpx.HTTPStatusError`, and invalid JSON with safe custom errors where needed.
  - [x] Validate the returned content with Pydantic before persistence.
  - [x] Enforce the default batch size of 20, reject unknown/duplicate returned IDs, and support PRD-required partial successes when the model returns fewer valid objects than requested.
  - [x] Redact raw prompt text, large raw job text, and proxy response bodies from logs.

- [x] Task 5: Implement extraction orchestration and script entry point (AC: 5, 7)
  - [x] Add a service function or client method that selects unextracted jobs with bounded `LIMIT`.
  - [x] Filter initial extraction to validated corpus slices from high-yield providers where practical; do not extract raw `company_signals`.
  - [x] Account for current schema reality: existing `jobs` rows have `source_slug` but do not reliably preserve `job_sources.discovery_method` or `job_sources.id`. If exact provider attribution cannot be joined safely, use the selected ATS/source mix from the corpus decision and document the limitation in the run summary instead of inventing an unreliable join.
  - [x] Add `backend/scripts/run_extraction.py` with limit/dry-run options.
  - [x] Return and/or write a structured summary for script output, tests, and later eval/report integration.

- [x] Task 6: Add persistence tests and regression coverage (AC: 1, 6, 8)
  - [x] Add tests under `backend/tests/llm/` for client behavior.
  - [x] Add migration assertions for new columns and indexes if existing migration test helpers allow it.
  - [x] Mock Hermes responses instead of requiring a live proxy in automated tests.
  - [x] Verify no database mutation occurs when Hermes health fails.
  - [x] Run `backend/venv/bin/pytest -q backend/tests/llm backend/tests/scripts/test_diagnose_hermes.py backend/tests/scripts/test_corpus_sanity.py`.
  - [x] Run the broader backend targeted suite touched by extraction: `backend/venv/bin/pytest -q backend/tests/routers/test_ingest.py backend/tests/services/test_parser.py backend/tests/services/test_source_discovery.py`.
  - [x] Run `backend/venv/bin/python -m compileall backend/llm backend/scripts backend/services`.

### Review Findings

- [x] [Review][Patch] High-yield corpus selection joins incompatible identifiers [backend/llm/client.py:127]
- [x] [Review][Patch] Already-extracted rows can be selected and counted as extracted instead of skipped [backend/llm/client.py:126]
- [x] [Review][Patch] Malformed, duplicate, or unknown response items abort partial valid batches before persistence [backend/llm/client.py:207]
- [x] [Review][Patch] Batch-level response failures leave selected rows pending and unaudited [backend/llm/client.py:354]
- [x] [Review][Patch] Extraction script does not catch extraction client failures [backend/scripts/run_extraction.py:65]
- [x] [Review][Patch] Direct script execution fails to import the backend package [backend/scripts/run_extraction.py:12]
- [x] [Review][Patch] Extraction error redaction misses common credential formats [backend/llm/client.py:91]

## Dev Notes

### Existing Code To Reuse

- `backend/llm/hermes.py`
  - Existing exception hierarchy: `HermesProxyError`, `HermesProxyConnectionError`, `HermesProxyHTTPError`, `HermesProxyResponseError`.
  - Existing health URL and check: `hermes_health_url()` and `check_hermes_proxy_health()`.
- `backend/scripts/diagnose_hermes.py`
  - Existing CLI pattern for proxy diagnostics and user-facing failure messages.
- `backend/config.py`
  - Existing `settings.hermes_host` and `settings.hermes_port`; do not add duplicate environment readers.
- `backend/db/migrations/V002__add_jobs_and_ingestion.sql`
  - Current `jobs` table is the source of extracted rows. Extend it in place.
- `backend/services/source_discovery.py`
  - `load_active_source_config()` proves weekly ingestion uses only `active = true AND validation_status = 'validated'`; preserve this trust boundary.
- `backend/db/migrations/V005__add_job_source_registry.sql`
  - `job_sources.discovery_method` and metadata hold provider attribution, but current `jobs` rows only store `source_slug`. Treat this as a selection/reporting limitation unless implementation adds a reliable source reference.
- `backend/scripts/corpus_sanity.py`
  - Existing pattern for local script summaries against the database.

### Hard Requirements

- Do not create a second Hermes health module or bypass `backend/llm/hermes.py`.
- Do not create a new trusted corpus from raw `company_signals`, GitHub/Reddit/Wellfound snippets, unsupported URLs, or unresolved companies.
- Do not pretend per-job provider attribution exists if the database only has `jobs.source_slug`; either add a reliable reference or make the extraction run summary explicit about the attribution limitation.
- Do not introduce an ORM; keep raw SQL through psycopg.
- Do not create a frontend UI in this story. `/evals` comes later in Story 4.3.
- Do not add external LLM SDK dependencies for this story unless Hermes explicitly requires them; the local proxy boundary should be an HTTP client boundary.
- Do not store full prompts, full proxy responses, credentials, or large raw job texts in logs, report artifacts, or `extraction_error`.
- Keep API/data field names snake_case in backend and database.
- Keep automated tests independent of a live Hermes proxy.

### Architecture Compliance

- Backend LLM code belongs in `backend/llm/client.py`, `backend/llm/schemas.py`, and existing `backend/llm/hermes.py`.
- Database schema changes belong in `backend/db/migrations/`.
- Local scripts belong in `backend/scripts/`.
- Backend tests mirror source paths under `backend/tests/`.
- Use Pydantic v2 and existing `pydantic>=2.0` dependency.
- Use existing `httpx` dependency and `AsyncClient` for Hermes calls.
- Use `structlog` for structured logging.

### Previous Story Intelligence

- Epic 3 established that provider outputs are evidence, not corpus truth. Extraction must operate on ingested `jobs` rows only.
- Provider yield should guide the first extraction slice. The current decision file selects `hn_who_is_hiring`, `vertex_ai_search`, and `common_crawl_ats` and warns against raw active-source count alone.
- Provider attribution is available on `job_sources.discovery_method`, but the current ingestion insert path stores only `jobs.source_slug`; the dev agent must not assume a direct per-job provider join exists.
- Epic 3 retrospective flags `jobs.updated_at` as stale unless extraction updates handle it. Address this in Story 4.1.
- Hermes health exists from earlier preparation work. The developer should build on it, not replace it.
- Workable remains unreliable in local verification; only include Workable rows when parser validation reports non-empty usable postings.
- Migration numbering must stay sequential after `V006__add_company_discovery.sql`. This story should own `V007` for extraction storage if available; Story 4.2 eval storage now references the following migration, expected as `V008__add_evals.sql`.

### Git Intelligence Summary

- Recent commits are Epic 3 focused: `3cf4073 Complete Epic 3 retrospective actions`, `63866b1 Implement long-tail discovery provider yield reporting`, `416e395 Implement scale discovery providers`, `9f0976a Add Vertex AI Search discovery provider`, and `2bf7d24 Add company signal resolver`.
- The most recent work touched planning artifacts, sprint status, `.env.example`, `backend/config.py`, `backend/services/source_discovery.py`, and source discovery tests. Story 4.1 should be much narrower: `backend/llm/`, `backend/db/migrations/`, `backend/scripts/`, `prompts/`, and backend tests.
- Story 3.4 verification used focused backend suites plus `compileall`; use the same targeted verification discipline and expand it for `backend/llm`.

### Latest Technical Information

- Pydantic v2 supports validating JSON strings directly with `BaseModel.model_validate_json()` and validating Python objects with `BaseModel.model_validate()`. Use this for raw Hermes JSON content and parsed payloads, and catch `pydantic.ValidationError` before persistence.
- Pydantic v2 models expose JSON Schema through `model_json_schema()`. Use that to keep the prompt schema and validation schema aligned instead of hand-maintaining a separate schema.
- HTTPX `AsyncClient` supports async `post(..., json=...)`, explicit timeout configuration, and `response.raise_for_status()`. Use the existing dependency rather than adding an SDK.
- HTTPX network failures and timeouts are request errors; HTTP 4xx/5xx after `raise_for_status()` are status errors. Keep logs redacted and map proxy connectivity failures to safe extraction errors.
- PRD NFR-I3 requires partial structural failure tolerance: if a 20-posting batch returns fewer valid objects, commit valid objects, log/mark failed posting IDs, and do not retry indefinitely.

### Project Structure Notes

- Expected new files:
  - `backend/db/migrations/V007__add_job_extraction_fields.sql` or the next available migration name if `V007` is already taken when implementing. If this story uses `V007`, future eval work must use `V008` or later.
  - `backend/llm/schemas.py`
  - `backend/llm/client.py`
  - `backend/scripts/run_extraction.py`
  - `prompts/extraction_v1.md`
  - `backend/tests/llm/test_schemas.py`
  - `backend/tests/llm/test_client.py`
  - `backend/tests/scripts/test_run_extraction.py`
- Existing files likely touched:
  - `backend/llm/__init__.py`
  - `.env.example` only if new optional extraction settings are added.
- No `project-context.md` file exists in this repo at story creation time.

### References

- [Epics: Story 4.1](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md:424)
- [PRD: LLM Extraction Layer](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md:454)
- [Architecture: Structured Extraction Mapping](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md:513)
- [Architecture: Validation Coverage](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md:570)
- [Current Jobs Migration](/home/darko/Code/be-an-ai-engineer/backend/db/migrations/V002__add_jobs_and_ingestion.sql:1)
- [Existing Hermes Health Client](/home/darko/Code/be-an-ai-engineer/backend/llm/hermes.py:1)
- [Existing Hermes Diagnostic Script](/home/darko/Code/be-an-ai-engineer/backend/scripts/diagnose_hermes.py:1)
- [Hermes Settings](/home/darko/Code/be-an-ai-engineer/backend/config.py:4)
- [Backend Dependencies](/home/darko/Code/be-an-ai-engineer/backend/requirements.txt:1)
- [Epic 4 Corpus Selection](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epic-4-extraction-corpus-selection.md:1)
- [Eval Set Rubric](/home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/eval-set-rubric.md:1)
- [Epic 3 Retro: Epic 4 Prep](/home/darko/Code/be-an-ai-engineer/_bmad-output/implementation-artifacts/epic-3-retro-2026-05-28.md:150)
- [Pydantic JSON Validation Docs](https://docs.pydantic.dev/latest/concepts/json/)
- [Pydantic Models Docs](https://docs.pydantic.dev/latest/concepts/models/)
- [HTTPX Async Client Docs](https://www.python-httpx.org/async/)
- [HTTPX Exceptions Docs](https://www.python-httpx.org/exceptions/)

## Story Completion Status

Ultimate context engine analysis completed - comprehensive developer guide created.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-28T20:25:31+05:30 - Started fresh implementation for Story 4.1; sprint status and story status moved to in-progress.
- 2026-05-28T20:30:22+05:30 - Added failing extraction schema/client/script tests, then implemented migration, prompt, schemas, Hermes client, and extraction script.
- 2026-05-28T20:32:29+05:30 - Verification passed: focused LLM/script suite, touched backend suites, compileall, and full backend regression.
- 2026-06-04T11:38:40+05:30 - Code review patches applied for corpus selection, cache-key skipping, response auditing, CLI failures, direct script execution, and redaction.

### Completion Notes List

- Added `V007__add_job_extraction_fields.sql` to extend `jobs` with extraction JSONB/scalar fields, run correlation, indexes, constrained statuses/enums, and a reusable `updated_at` trigger.
- Added strict Pydantic v2 extraction schemas, a versioned prompt artifact that injects `ExtractionBatch.model_json_schema()`, and a Hermes-backed async extraction client that reuses existing proxy health checks before selecting rows.
- Implemented bounded selection from active validated high-yield source slices, dry-run/limit support, structured run summaries, partial-success persistence, retryable/failed row marking, unknown/duplicate/malformed ID rejection, and error redaction.
- Added schema, client, migration, and script tests covering validation, salary shapes, proxy health failure, batching, partial persistence, malformed responses, HTTP failures, prompt version persistence, run-summary artifacts, and Hermes boundary reuse.
- Code review patches fixed high-yield ATS matching, already-extracted row skipping/counting, retryable audit state for batch response failures, CLI extraction-error handling, direct script execution imports, and broader credential redaction.

### File List

- `_bmad-output/implementation-artifacts/4-1-llm-structured-extraction-and-proxy-verification.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `backend/db/migrations/V007__add_job_extraction_fields.sql`
- `backend/llm/client.py`
- `backend/llm/schemas.py`
- `backend/scripts/run_extraction.py`
- `backend/tests/llm/test_client.py`
- `backend/tests/llm/test_schemas.py`
- `backend/tests/scripts/test_run_extraction.py`
- `prompts/extraction_v1.md`

### Change Log

- 2026-05-28: Implemented Story 4.1 extraction storage, schema, prompt, Hermes client, script entry point, and regression tests.
- 2026-06-04: Addressed code review findings and moved story to done.
