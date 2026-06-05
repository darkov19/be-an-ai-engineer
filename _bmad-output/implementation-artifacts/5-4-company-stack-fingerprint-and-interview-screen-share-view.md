# Story 5.4: Company Stack Fingerprint & Interview Screen-Share View

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want a single-screen company stack fingerprint page (top technology list, role archetypes, and an AI-generated Stack observation) that renders in < 2s for live interview screen-shares, including a one-click close parameter to exit clean,
so that I can share my screen and present real-time company insights during live interviews.

## Acceptance Criteria

1. **Company Page Routing & View (AC: 1, 3)**:
   - Given a URL request `/company/{company_slug}` (optionally with a query parameter `?demo=true`).
   - When the company page loads.
   - Then the app renders a high-density, single-screen stack fingerprint containing: company name, 5-bullet role archetype summary, top-10 extracted technologies, and a one-sentence LLM-generated observation.
   - The view must be optimized for Zoom screen-sharing at 1080p and follow the HUD Sci-Fi Cockpit theme (Outfit/JetBrains Mono typography, cosmic HSL color theme: black background, cyan/purple/magenta glowing accents).
   - If `demo=true` is present in the URL (e.g. `/company/stripe?demo=true`), a prominent `[CLOSE DEMO]` button is displayed in warning magenta, which returns the browser to the default neutral dashboard state (`/` route) upon click.

2. **Hot Path Performance & Query Projections (AC: 2)**:
   - Given a requested company stack fingerprint page.
   - When loading the page.
   - Then it loads in `< 2s` by utilizing pre-computed and cached database query projections rather than triggering real-time extraction or LLM calls on the request path.

3. **Static Local HTML Caching for Fallback (AC: 4)**:
   - Given a weekly cron run or an on-demand ingestion run.
   - When executed successfully.
   - Then the system pre-computes and writes static local HTML copies of the company stack fingerprints to `frontend/public/cached-fingerprints/{company_slug}.html` for offline fallback during live screen-share runs.

4. **Offline Fallback Button Integration (AC: 5)**:
   - Given a network timeout of 3 seconds occurs on the `/ingest` page.
   - When the top banner slides down displaying `[TIMEOUT DETECTED - PARSER OFFLINE]`.
   - Then the banner's offline fallback button is updated to load these cached company stack fingerprints (either loading the static file `frontend/public/cached-fingerprints/{company_slug}.html` directly or offering a link to it).

5. **Security & Data Sanitization (AC: 6)**:
   - Given a company slug parameter supplied by the user via URL.
   - When resolving it in the backend or reading/writing files from disk.
   - Then the backend MUST sanitize the company slug (e.g., validate it against an alphanumeric and dash regex `^[a-z0-9\-]+$`, reject any path traversal characters like `../` or `..\`) to prevent SQL Injection and Path Traversal vulnerabilities.
   - Parameterized SQL queries MUST be used to query the database.
   - Database error details MUST NOT be exposed to the frontend (return generic errors to the client while logging detailed diagnostic information).
   - The fingerprint and cached pages are intentionally public and unauthenticated per design decisions.

## Tasks / Subtasks

- [x] **Task 1: Database Migration & Schema Setup (AC: 1, 2)**
  - [x] Create database migration file [V009__add_company_fingerprints.sql](file:///home/darko/Code/be-an-ai-engineer/backend/db/migrations/V009__add_company_fingerprints.sql) to define the `company_fingerprints` table:
    ```sql
    CREATE TABLE company_fingerprints (
        id SERIAL PRIMARY KEY,
        company_slug VARCHAR(255) UNIQUE NOT NULL,
        company_name VARCHAR(255) NOT NULL,
        role_archetypes JSONB NOT NULL,
        top_technologies JSONB NOT NULL,
        llm_observation TEXT NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_company_fingerprints_slug ON company_fingerprints(company_slug);
    ```
- [x] **Task 2: Fingerprinter Service & Generation Script (AC: 2, 4)**
  - [x] Create [fingerprinter.py](file:///home/darko/Code/be-an-ai-engineer/backend/services/fingerprinter.py) containing:
    - `generate_fingerprint_data(pool, company_slug)`: aggregates parsed/extracted job postings for a given company slug, prompts the LLM proxy to generate the 5-bullet role archetype summary and one-sentence stack observation (e.g., by prompting Hermes with the company's job texts), computes the top-10 extracted technologies and their count, and saves/updates it in the `company_fingerprints` table.
    - `write_static_html(company_slug, fingerprint_data)`: formats the fingerprint data into a clean, standalone, responsive static HTML page matching the HUD theme and writes it to `frontend/public/cached-fingerprints/{company_slug}.html`.
    - **Security:** Ensure that writing the HTML file uses `path.basename` and validates that the path stays within the `frontend/public/cached-fingerprints` directory boundary to prevent path traversal.
  - [x] Create [precompute_fingerprints.py](file:///home/darko/Code/be-an-ai-engineer/backend/scripts/precompute_fingerprints.py) to query the database for all unique company slugs in the `jobs` table, generate their fingerprints, and write the static HTML copies.
  - [x] Update [scheduler.py](file:///home/darko/Code/be-an-ai-engineer/backend/services/scheduler.py)'s `run_weekly_ingestion` task to run the precomputation script after successful ingestion.
- [x] **Task 3: Backend API Endpoint for Fingerprints (AC: 1, 2, 6)**
  - [x] Create endpoint `GET /api/v1/company/{company_slug}` in [jobs.py](file:///home/darko/Code/be-an-ai-engineer/backend/routers/jobs.py) (or a new router).
  - [x] Retrieve pre-computed records from the `company_fingerprints` table based on the slug.
  - [x] Return the fingerprint data in `< 2s` (no hot-path LLM calls). If not found, return a 404.
  - [x] **Security:** Sanitize `company_slug` using a strict regex allowlist `^[a-z0-9\-]+$`. Use parameterized queries and avoid raw string formatting/concatenation.
- [x] **Task 4: Frontend Company View & Demo Close (AC: 1, 3)**
  - [x] Register the `/company/:companySlug` route in React router [App.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/App.tsx).
  - [x] Create a new view file [CompanyView.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/views/CompanyView.tsx) and styling file [CompanyView.module.css](file:///home/darko/Code/be-an-ai-engineer/frontend/src/views/CompanyView.module.css).
  - [x] Fetch fingerprint data from `/api/v1/company/{companySlug}` using TanStack Query.
  - [x] Render a high-density, single-screen dashboard layout containing the company name, a 5-bullet role archetype summary, a top-10 technologies list, and the one-sentence observation.
  - [x] Parse `demo=true` from URL query parameters and conditionally render the warning-magenta `[CLOSE DEMO]` button. Clicking it navigates back to `/`.
- [x] **Task 5: Ingestion Timeout Fallback Integration (AC: 5)**
  - [x] Update the `[LOAD OFFLINE FALLBACK CACHE]` click action on the `/ingest` page timeout banner in [IngestionView.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/views/IngestionView.tsx).
  - [x] Instead of a placeholder, load the cached static HTML file `frontend/public/cached-fingerprints/{company_slug}.html` if it exists, or redirect to `/company/{company_slug}?demo=true`.
- [x] **Task 6: Tests and Verification**
  - [x] Add backend tests in `backend/tests/services/test_fingerprinter.py` and `backend/tests/routers/test_company.py` to assert correct aggregation, LLM call logic, SQL execution, slug validation, and endpoint responses.
  - [x] Add frontend tests in `frontend/src/views/CompanyView.test.tsx` to verify that the page renders correctly, shows/hides the close demo button based on URL parameters, and handles routing.
  - [x] Run `npm run test` to confirm all tests pass.

### Review Findings

- [x] [Review][Patch] Static fallback HTML renders unescaped database and LLM content [backend/services/fingerprinter.py:531]
- [x] [Review][Patch] On-demand ingestion does not precompute or write cached fingerprints after successful runs [backend/routers/ingest.py:48]
- [x] [Review][Patch] Company name derivation is broken because the jobs projection omits `company` [backend/services/fingerprinter.py:338]
- [x] [Review][Patch] Offline fallback navigation uses an unsanitized slug and does not recover when the static file is absent [frontend/src/views/IngestionView.tsx:308]
- [x] [Review][Patch] Company API fetch does not encode the route slug before constructing the URL [frontend/src/views/CompanyView.tsx:36]
- [x] [Review][Patch] Slug validation uses `re.match`, allowing trailing newline-style inputs through the allowlist [backend/routers/jobs.py:527]
- [x] [Review][Patch] Static fallback HTML depends on remote Google Fonts despite being an offline fallback [backend/services/fingerprinter.py:21]
- [x] [Review][Patch] Company view bypasses the established TanStack Query fetch path required by the story [frontend/src/views/CompanyView.tsx:29]
- [x] [Review][Patch] Company view renders arbitrary role archetype counts instead of enforcing the five-bullet contract [frontend/src/views/CompanyView.tsx:132]

## Dev Notes

- **Aesthetics & Theme**:
  - Re-use HUD design tokens (e.g. `--bg-cosmic`, `--bg-panel`, `--glow-cyan`, `--glow-magenta`, `--glow-purple`) and ConsolePanel wrapper.
  - Maintain typography hierarchy (Outfit for headers, JetBrains Mono for monospaced lists/stats).
  - The company fingerprint page should fit on a single screen without vertical scrolling where possible.
- **Security & Data Sanitization**:
  - Treat all user inputs (including the `company_slug` from URL) as untrusted.
  - Reject slugs containing traversal sequences (`../`, `..\`) or characters outside of `^[a-z0-9\-]+$`.
  - Do NOT expose backend SQL errors to the frontend.
  - Treat the endpoints as public and unauthenticated per product constraints.

### Project Structure Notes

- Keep view logic inside `frontend/src/views/CompanyView.tsx` with scoped CSS Modules.
- Ingestion logic update goes to `backend/services/parser.py` and `backend/services/scheduler.py`.
- Ensure new migrations are registered in `backend/db/migrations/` and run successfully on startup.

### References

- [Epics: Story 5.4](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#L540-L555)
- [PRD: Scenario 2 - Per-company interview briefing](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#L274-L288)
- [UX Design Specification: Live Interview Demo Mode](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/ux-design-specification.md#L262-L288)
- [Mandatory Secure Web Skills: Security Guidelines](file:///home/darko/.gemini/config/plugins/Google.securecoder.securecoder/skills/securecoder_generation/SKILL.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

- Story implementation added precomputed company fingerprint persistence, static fallback generation, and interview demo routing. Review patches later tightened generated HTML escaping, slug validation, route encoding, offline fallback behavior, and TanStack Query usage.

### Completion Notes List

- Added `V009__add_company_fingerprints.sql` for cached company stack fingerprint records.
- Implemented backend fingerprint generation and static fallback HTML writing in `backend/services/fingerprinter.py`.
- Added `backend/scripts/precompute_fingerprints.py` and wired successful scheduled/on-demand ingestion to precompute cached fingerprints.
- Added `GET /api/v1/company/{company_slug}` with strict slug validation, parameterized lookup, generic client errors, and no hot-path LLM work.
- Added React `/company/:companySlug` route and `CompanyView` screen-share layout with demo-close behavior.
- Updated ingest timeout fallback to load cached fingerprint HTML when present or fall back to `/company/{slug}?demo=true`.
- Added backend and frontend tests covering service generation, static write safety, company endpoint behavior, route rendering, demo close, invalid slugs, and fallback paths.

### File List

- `backend/db/migrations/V009__add_company_fingerprints.sql`
- `backend/services/fingerprinter.py`
- `backend/scripts/precompute_fingerprints.py`
- `backend/services/scheduler.py`
- `backend/routers/jobs.py`
- `backend/routers/ingest.py`
- `backend/tests/services/test_fingerprinter.py`
- `backend/tests/routers/test_company.py`
- `backend/tests/routers/test_ingest.py`
- `frontend/src/App.tsx`
- `frontend/src/views/CompanyView.tsx`
- `frontend/src/views/CompanyView.module.css`
- `frontend/src/views/CompanyView.test.tsx`
- `frontend/src/views/IngestionView.tsx`
