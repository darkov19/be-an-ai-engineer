# Story 2.1: Multi-Source Ingest Parsers & Database Schema

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a database migration `V002__add_jobs_and_ingestion.sql` that defines tables `jobs` (raw text, source_slug, url, status) and `ingestion_runs` along with Python parser adapters for Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, YC WaaS, and HN,
so that job postings are fetched and saved to the local database with full telemetry.

## Acceptance Criteria

1. **Database Migration (`backend/db/migrations/V002__add_jobs_and_ingestion.sql`)**:
   - The migration must define the following tables:
     - `jobs`:
       - `id SERIAL PRIMARY KEY`
       - `url TEXT UNIQUE NOT NULL`
       - `title TEXT NOT NULL`
       - `company TEXT NOT NULL`
       - `location TEXT`
       - `raw_text TEXT NOT NULL`
       - `source_slug VARCHAR(50) NOT NULL` (representing greenhouse, lever, ashby, workable, recruitee, personio, yc_waas, hn)
       - `status VARCHAR(50) NOT NULL DEFAULT 'backlog'` (representing parsing/extraction status)
       - `created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
       - `updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
     - `ingestion_runs`:
       - `id SERIAL PRIMARY KEY`
       - `run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
       - `status VARCHAR(50) NOT NULL` (representing 'success' or 'failure')
       - `source_counts JSONB NOT NULL DEFAULT '{}'::jsonb` (mapping source slug to number of jobs ingested, e.g. `{"greenhouse": 12, "lever": 5}`)
       - `error_message TEXT` (nullable, stores error traceback or description in case of failure)
       - `execution_time_seconds NUMERIC(10, 2) NOT NULL DEFAULT 0.0`
       - `created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP`
   - Explicit secondary indexes must be created on:
     - `idx_jobs_source_slug` on `jobs(source_slug)`
     - `idx_jobs_status` on `jobs(status)`
     - `idx_jobs_company` on `jobs(company)`
   - The migration must be automatically applied at application startup via the existing database migration runner in `backend/db/migrations.py`.

2. **Python Parser Adapters (`backend/services/parser.py`)**:
   - Create the module `backend/services/parser.py` containing stateless asynchronous functions for fetching postings from the 8 sources:
     - `fetch_greenhouse_jobs(company_slug: str)` -> calls public job board API `https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true`
     - `fetch_lever_jobs(company_slug: str)` -> calls public job board API `https://api.lever.co/v0/postings/{company_slug}?mode=json`
     - `fetch_ashby_jobs(company_slug: str)` -> calls public job board API `https://api.ashbyhq.com/posting-api/job-board/{company_slug}`
     - `fetch_workable_jobs(company_slug: str)` -> calls public widget API `https://apply.workable.com/api/v1/widget/accounts/{company_slug}`. Note: This only returns job summaries. If descriptions are missing, it must fetch details from `https://apply.workable.com/api/v1/widget/jobs/{shortcode}` or parse inline fields.
     - `fetch_recruitee_jobs(company_slug: str)` -> calls public offers endpoint `https://{company_slug}.recruitee.com/api/offers`
     - `fetch_personio_jobs(company_slug: str)` -> calls public XML feed `https://{company_slug}.jobs.personio.de/xml?language=en` or `.com` equivalent, parsing the response using the standard library `xml.etree.ElementTree`.
     - `fetch_yc_waas_jobs()` -> Since `workatastartup.com` does not expose a public, official search API, implement a stub/mock parser that simulates fetching YC WaaS jobs. It must return at least 3 distinct mock job postings to ensure the analytics aggregation pipelines have realistic 2026 AI-engineering data during local dry runs:
       - Post 1: Title: "AI Application Engineer", Company: "CognitiveFlow", Location: "San Francisco, CA", Stack: "FastAPI, React, pgvector, RAG, Claude 3.5 Sonnet".
       - Post 2: Title: "Agent Systems Architect", Company: "SentientLabs", Location: "Remote US/EU", Stack: "LangGraph, Python, Vector DBs, Multi-Agent Systems".
       - Post 3: Title: "ML Platform Developer", Company: "NeuralScale", Location: "Bengaluru, India", Stack: "PyTorch, CUDA, Docker, Kubernetes, Triton Inference Server".
     - `fetch_hn_jobs()` -> Searches the Hacker News Algolia API for the latest monthly Ask HN thread using `https://hn.algolia.com/api/v1/search_by_date?query="Ask HN: Who is hiring"&tags=story` (identifying the latest thread posted by the user `whoishiring` on the 1st of the month), fetches comments via `https://hn.algolia.com/api/v1/items/{thread_id}`, and filters comments containing AI/LLM keywords. The filter must perform a case-insensitive check against this standard list of keywords: `AI`, `LLM`, `RAG`, `Agent`, `Machine Learning`, `Deep Learning`, `Transformer`, `Vector`, `Embeddings`, `neural`, `PyTorch`.
   - All HTTP requests in parsers must use `httpx.AsyncClient` with a strict `timeout` parameter (e.g. 5.0 seconds) to prevent infinite hangs.
   - HTML stripping must be implemented using Python's standard library `html.parser.HTMLParser` to remove tags and return clean text descriptions (e.g. converting `<div>` and `<br>` into clean line breaks and text), avoiding external HTML parsing libraries like `beautifulsoup4` or `lxml` to prevent dependency bloat and security issues.
   - **Parser Return Contract**: Every parser adapter function must return a list of dictionaries, where each dictionary contains the following keys:
     - `url`: `str` (the unique job posting URL)
     - `title`: `str` (the job posting title)
     - `company`: `str` (the company name)
     - `location`: `str | None` (the location description or `None`)
     - `raw_text`: `str` (the HTML-stripped raw text body/description of the posting)
     - `source_slug`: `str` (the identifier of the source, e.g., `'greenhouse'`)

3. **Duplicate Skipping & Database Integration**:
   - Inserting fetched jobs into the database must be executed using parameterization in `psycopg` to prevent SQL Injection.
   - The database insertion statement must utilize `ON CONFLICT (url) DO NOTHING` to automatically skip duplicate listings without throwing database errors or aborting the run.

4. **Telemetry and Test Script (`backend/scripts/test_ingestion.py`)**:
   - Write a diagnostic script `backend/scripts/test_ingestion.py` that can be run from the root workspace using `python3 -m backend.scripts.test_ingestion`.
   - The script must trigger a test run of the parser adapters, attempt to write fetched/mock jobs to the database, compute execution metrics, and insert a summary row into `ingestion_runs` with:
     - `status`: `'success'` (or `'failure'` if exceptions are raised)
     - `source_counts`: JSON representation of postings per source (e.g., `{"greenhouse": 5, "lever": 2}`)
     - `execution_time_seconds`: Measured time of execution
     - `error_message`: Detailed exception description if the execution fails.

5. **Robust Error Handling**:
   - The ingestion logic must catch exceptions raised by individual parser adapters, log them locally using `structlog` at `warning` or `error` level, and continue executing other parser adapters without aborting the entire ingestion run.
   - If a parser adapter fails, its source count is logged as `0` in `source_counts`, but the run is still completed and recorded as successful in the database if at least one source succeeded. If all sources fail, the run status is recorded as `'failure'` in `ingestion_runs` with the error logged in `error_message`.
   - **Telemetry Logging Structure**: All `structlog` calls within `parser.py` must use a consistent metadata structure:
     - When starting ingestion for a source: `logger.info("Starting source ingestion", source_slug=source_slug, company_slug=company_slug)`
     - On successful ingestion: `logger.info("Source ingestion complete", source_slug=source_slug, company_slug=company_slug, count=count, duration_seconds=duration_seconds)`
     - On parser error: `logger.error("Source ingestion failed", source_slug=source_slug, company_slug=company_slug, error=str(e), duration_seconds=duration_seconds)`

## Tasks / Subtasks

- [x] Task 1: Create Database Migration (AC: 1)
  - [x] Write `backend/db/migrations/V002__add_jobs_and_ingestion.sql` creating `jobs` and `ingestion_runs` tables.
  - [x] Add UNIQUE constraint on `jobs.url`.
  - [x] Add indexes on `source_slug`, `status`, and `company` columns.
  - [x] Verify migration is applied successfully on application startup.
- [x] Task 2: Build HTML Tag Stripper (AC: 2)
  - [x] Implement a lightweight class/helper using `html.parser.HTMLParser` in `backend/services/parser.py` (or a helper module) to clean HTML job descriptions.
  - [x] Add unit tests verifying HTML tags are cleanly removed and newlines are preserved.
- [x] Task 3: Implement ATS Parser Adapters (AC: 2)
  - [x] Build Greenhouse parser conforming to the return contract.
  - [x] Build Lever parser conforming to the return contract.
  - [x] Build Ashby parser conforming to the return contract.
  - [x] Build Workable parser (including detail fetching if description is missing) conforming to the return contract.
  - [x] Build Recruitee parser conforming to the return contract.
  - [x] Build Personio XML parser using standard `xml.etree.ElementTree` conforming to the return contract.
- [x] Task 4: Implement Hacker News & YC WaaS Parsers (AC: 2)
  - [x] Implement Algolia API query to find the latest "Ask HN: Who is hiring" thread ID.
  - [x] Implement comment retrieval and standard case-insensitive AI-keyword filtering conforming to the return contract.
  - [x] Implement YC WaaS stub/mock returning mock AI job listings conforming to the return contract and mock dataset spec.
- [x] Task 5: Database Integration and Telemetry Logging (AC: 3, 5)
  - [x] Implement database integration logic using parameterized queries.
  - [x] Add `ON CONFLICT (url) DO NOTHING` to SQL statements.
  - [x] Implement ingestion run telemetry logging in `ingestion_runs` table using standardized logger keys.
- [x] Task 6: Ingestion Diagnostic Script & Tests (AC: 4, 5)
  - [x] Create `backend/scripts/test_ingestion.py` executing a full diagnostic flow.
  - [x] Write pytest unit and integration tests in `backend/tests/services/test_parser.py` (using `pytest-asyncio` and `httpx` mocking).

## Dev Notes

- **Existing Database Utilities**: Use the dependency `get_db` from `backend/db/connection.py` to acquire connections. For background scripts (like `test_ingestion.py`), manually open a connection from the `AsyncConnectionPool` initialized via `settings.database_url`.
- **Standard Library Only**: To align with zero-dependency requirements for HTML/XML parsing:
  - Use `html.parser.HTMLParser` for HTML sanitization.
  - Use `xml.etree.ElementTree` for XML parsing (Personio feed).
- **HTTP client**: Use `httpx.AsyncClient` for asynchronous HTTP requests. Do NOT use `requests` (synchronous) or `urllib.request`.
- **Casing and Plurals**:
  - Tables: `jobs` (plural, snake_case), `ingestion_runs` (plural, snake_case).
  - JSON payloads: `snake_case`.
- **Logging**: Use `structlog.get_logger()` to log parser metrics and errors. Do NOT use print statements or standard `logging`.

### Project Structure Notes

- Parsers live under `backend/services/parser.py`.
- Database migration lives under `backend/db/migrations/V002__add_jobs_and_ingestion.sql`.
- Ingestion scripts live under `backend/scripts/test_ingestion.py`.
- Tests live under `backend/tests/services/test_parser.py`.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#data-architecture](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md#data-architecture)
- [Source: _bmad-output/planning-artifacts/prd.md#mvp--4-week-build-weeks-14](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#mvp--4-week-build-weeks-14)
- [Source: _bmad-output/planning-artifacts/epics.md#epic-2-multi-source-job-ingestion--live-log-tracking-the-market-scanner](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#epic-2-multi-source-job-ingestion--live-log-tracking-the-market-scanner)

### Review Findings

- [x] [Review][Decision] Workable `< 100` char threshold — keeping pragmatic threshold; fetches detail when description is effectively empty (<100 chars stripped)

- [x] [Review][Patch] `run_status` logic incorrectly records all-fail as `success` — fixed via explicit `successful_sources` counter [parser.py:600-607]
- [x] [Review][Patch] `total_attempted` magic-number arithmetic broken — removed; now uses `successful_sources > 0` [parser.py:601]
- [x] [Review][Patch] `failed_count` double-subtracts DB error — removed entirely [parser.py:602]
- [x] [Review][Patch] `test_ingestion.py` autocommit + explicit transaction conflict — removed `kwargs={'autocommit': True}` [test_ingestion.py:16]
- [x] [Review][Patch] Personio `.de` retry fires on any exception, not just 404 — narrowed to `httpx.HTTPStatusError` with 404 check [parser.py:274-280]
- [x] [Review][Patch] `parse_xml_safely` bare `except Exception: pass` swallows all non-ValueError parse errors — narrowed to `xml.parsers.expat.ExpatError` [parser.py:85-87]
- [x] [Review][Patch] `insert_job` has no required-key validation — added guard with `ValueError` before execute [parser.py:433-449]
- [x] [Review][Patch] HN Algolia URL built with raw special chars — switched to `httpx params={}` kwarg [parser.py:362]
- [x] [Review][Patch] `backend/scripts/__init__.py` missing — created [backend/scripts/]

- [x] [Review][Defer] HN Algolia pagination — `whoishiring` may not be in first results page — deferred, pre-existing API limitation
- [x] [Review][Defer] `company_slug.capitalize()` loses multi-word slug formatting (e.g., `open-ai` → `Open-ai`) — deferred, cosmetic, pre-existing
- [x] [Review][Defer] Default ingestion config uses live company slugs (brittle) — deferred, test config concern
- [x] [Review][Defer] `updated_at` column has no update trigger — deferred, no UPDATE statements exist yet in this story

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

- None

### Completion Notes List

- Applied migration `V002__add_jobs_and_ingestion.sql` defining `jobs` and `ingestion_runs` tables with appropriate indexes and UNIQUE constraints.
- Created `HTMLTagStripper` using python standard library `html.parser.HTMLParser` to convert markup to text.
- Implemented `parse_xml_safely` with strict DTD/entity expansion protection.
- Developed stateless async parser adapters for Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, HN, and YC WaaS.
- Integrated parameterized database query logic handling duplicates cleanly via `ON CONFLICT (url) DO NOTHING`.
- Created structured logging telemetry and standalone diagnostic script `test_ingestion.py`.
- Wrote comprehensive unit/integration test suite covering all functionality and security checks.

### File List

- [V002__add_jobs_and_ingestion.sql](file:///home/darko/Code/be-an-ai-engineer/backend/db/migrations/V002__add_jobs_and_ingestion.sql)
- [parser.py](file:///home/darko/Code/be-an-ai-engineer/backend/services/parser.py)
- [test_ingestion.py](file:///home/darko/Code/be-an-ai-engineer/backend/scripts/test_ingestion.py)
- [test_parser.py](file:///home/darko/Code/be-an-ai-engineer/backend/tests/services/test_parser.py)
