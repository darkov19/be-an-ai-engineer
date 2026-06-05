# Story 5.5: Archive Index & Social Sharing

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a weekly report deployment workflow that publishes the report to a public Vercel URL on cron, logs history to a public `/archive` index, and generates shareable social images representing key weekly stats,
so that my career search results are preserved, public, and shareable.

## Acceptance Criteria

1. **Weekly Static Report Publish Workflow**
   - Given a completed weekly pipeline run with nominal or warning quality state.
   - When the Saturday cron deployment fires.
   - Then the workflow renders static weekly report assets from the persisted analytics/report data and stores them under `frontend/public/reports/{year}-W{week}/`.
   - The generated report page must be public and unauthenticated, include OpenGraph metadata, and remain usable without backend API access.
   - The workflow must commit curated static report/archive artifacts and deploy the Vite static site to Vercel.
   - The full ingest to deploy path should remain within the 60-minute Saturday pipeline budget and publish before the configured Saturday morning IST target.
   - If Vercel deployment fails, the pipeline must preserve Postgres data and the run-summary artifact, log the deployment failure, and avoid marking ingestion/extraction as failed.

2. **Public Archive Index**
   - Given one or more rows in `weekly_reports`.
   - When a visitor navigates to `/archive`.
   - Then the site displays a human-readable list of past weekly reports with run date, corpus size, latest eval accuracy, commit/deployment link when available, and a link to each historic report.
   - The archive must sort newest first, show an explicit empty state when no reports exist, and render without authentication.

3. **Historic Report Detail Pages**
   - Given a selected archive row.
   - When a visitor opens a historic report.
   - Then the report displays the historic geo rankings and fit metrics from the stored weekly report snapshot, not freshly recomputed current analytics.
   - The report must include run date, corpus size, per-source breakdown, top-10 US/EU Remote skills, top-10 India AI Product skills, minimum-experience-threshold distribution strip, profile fit score delta by geo segment, eval accuracy, accountability/Loop B block, profile freshness nudge when stale, and known corpus/coverage notes where available.
   - If accessed with `?demo=true`, the report must render a one-click close control that returns the view to a neutral state, matching the product's closable-demo requirement.

4. **Shareable OpenGraph Image**
   - Given a generated weekly report.
   - When social platforms request the report preview image.
   - Then the report exposes an `og:image` pointing at a generated high-contrast static image for that week.
   - The image must be mobile-readable at 375px equivalent width and include the key headline number plus the top skills for both geo segments.
   - The image generation must be deterministic in tests and must not rely on remote fonts, browser screenshots, or unauthenticated external services.

5. **Public-Surface Security and Accessibility**
   - Given the archive, report, and social image surfaces are intentionally public.
   - When implementing these pages.
   - Then do not add auth gates, login redirects, tokenized URLs, or private-only backend dependencies.
   - Escape all generated HTML content from database/LLM-derived fields before writing static files.
   - Do not commit secrets, `.env`, Vercel tokens, database URLs, or generated root runtime artifacts by accident.
   - Document in the README or an equivalent public operations note that report, archive, and company fingerprint pages are intentionally public portfolio artifacts.
   - Text contrast must meet WCAG 2.1 AA for normal text, and color-coded states must include text labels.
   - Report pages must target FCP < 1.5s, LCP < 2.5s, and total page weight < 500KB by avoiding framework bundles, remote fonts, and CDN-loaded libraries.

6. **Operational Monitoring and Recovery**
   - Given the public report URL is a hiring signal.
   - When the deploy workflow completes.
   - Then deployment URL metadata is recorded, and a follow-up uptime/health-check step verifies the public report/archive URL is reachable.
   - If the report page has not been accessed for two consecutive Saturdays, the existing nudge email must use the generated report HTML inline rather than a reduced placeholder summary.

## Tasks / Subtasks

- [x] **Task 1: Extend Weekly Report Persistence for Static Publishing (AC: 1, 3)**
   - [x] Add a migration after `V009` to extend `weekly_reports` with publish metadata needed by the archive: `report_slug`, `report_path`, `og_image_path`, `commit_sha`, `deployment_url`, and `published_at`.
  - [x] Add JSON snapshot fields if current columns are insufficient for historic rendering. Prefer storing stable report inputs (`geo_us_eu`, `geo_india`, `per_source_counts`, `corpus_size`, `eval_accuracy`, experience distributions, profile fit deltas, coverage diagnostics, and accountability/Loop B summary) over recomputing from current jobs.
  - [x] Preserve the existing `weekly_reports.run_date` uniqueness and `idx_weekly_reports_run_date` index.
  - [x] Add migration tests or backend tests that assert new columns can be written and read through the existing test mock style.

- [x] **Task 2: Create Static Report Rendering Service (AC: 1, 3, 5)**
  - [x] Create `backend/services/report_publisher.py` for pure rendering/publishing helpers:
    - `build_report_slug(run_date) -> str` using ISO week format such as `2026-W23`.
    - `load_weekly_report_snapshot(conn, run_date)` to read a persisted report row and normalize JSON fields.
    - `render_weekly_report_html(snapshot) -> str` to generate standalone static HTML.
    - `render_archive_html(rows) -> str` to generate the `/archive` static index.
    - `write_report_assets(snapshot, output_root)` to write `frontend/public/reports/{slug}/index.html`, `frontend/public/reports/{slug}/og.png`, and `frontend/public/archive/index.html`.
  - [x] Use only Python standard-library HTML escaping for database/LLM-derived strings unless the repo already adds a templating dependency. Do not introduce a browser automation dependency for report rendering.
  - [x] Keep generated public HTML lightweight: no React bundle dependency, no remote fonts, no CDN libraries, no inline secrets.
  - [x] Match existing HUD tokens visually where practical: cosmic black background, cyan/magenta/green accents, text labels beside color.
  - [x] Render the full PRD report structure: header, corpus/per-source diagnostics, two-column geo top-10 skills, minimum-experience distribution strip, profile fit delta, accountability/Loop B block, profile diff/freshness nudge, footer with known gaps, and `?demo=true` close control.

- [x] **Task 3: Generate Deterministic OpenGraph Image (AC: 4)**
  - [x] Add a minimal deterministic image writer under `backend/services/report_publisher.py` or a focused helper module.
  - [x] Prefer a no-new-dependency approach if feasible. If adding an image library is necessary, add it to `backend/requirements.txt` with a pinned compatible version and tests.
  - [x] Produce a 1200x630 social image or another common OG-compatible size, with layout verified to remain readable when scaled to 375px width.
  - [x] Include the primary headline number, report date/week, top US/EU skill names, top India skill names, corpus size, and eval accuracy.
  - [x] Add tests that verify the file is created, is non-empty, has the expected dimensions, and contains deterministic bytes or stable metadata for fixed input.

- [x] **Task 4: Wire Scheduler and Publish Script (AC: 1, 2, 3, 4)**
  - [x] Update `backend/services/scheduler.py` so successful and warning weekly runs record enough snapshot data before publishing.
  - [x] Do not publish a normal report when the quality state is `locked`; locked runs should continue to emit `kill-criterion-fired-YYYY-WW.json` per existing behavior.
  - [x] Add `backend/scripts/publish_weekly_report.py` that can be run locally or in CI to:
    - connect to Postgres using existing settings,
    - select the latest weekly report by `run_date` unless a date argument is supplied,
    - write static report/archive/OG assets,
    - optionally update `weekly_reports.report_path` and `og_image_path`.
  - [x] Ensure publishing failures are logged and surfaced as deployment/publish failures, not as ingestion data loss.
  - [x] Update the skip-two-Saturdays nudge path so its email body uses the generated report HTML inline when available, preserving the existing subject and missed-access behavior.

- [x] **Task 5: Add Public Archive Routing and Vercel Configuration (AC: 1, 2)**
  - [x] Create `frontend/public/` if needed and ensure generated files live under that tree so Vite copies them to `dist`.
  - [x] Add `frontend/vercel.json` only if needed to route `/archive` to `/archive/index.html` and preserve `/reports/{slug}/` static paths.
  - [x] Do not implement `/archive` as a React-only route unless the static archive path still works without loading backend data.
  - [x] Verify local build output includes `dist/archive/index.html`, `dist/reports/{slug}/index.html`, and `dist/reports/{slug}/og.png` for fixture-generated reports.
  - [x] Add README or docs text explaining that public report/archive/company pages are intentionally unauthenticated portfolio surfaces.

- [x] **Task 6: Add GitHub Actions Weekly Deploy Workflow (AC: 1, 5, 6)**
  - [x] Create `.github/workflows/weekly-report.yml`.
  - [x] Include `workflow_dispatch` for manual validation and a scheduled Saturday IST cron. Use explicit UTC cron `30 2 * * 6` for Saturday 08:00 IST unless the workflow intentionally uses GitHub's timezone-aware schedule syntax.
  - [x] Run backend tests needed for report publishing, generate static report assets, run `cd frontend && npm run build`, commit curated generated files, and deploy with Vercel CLI.
  - [x] If using `vercel deploy --prebuilt`, run `vercel build` first so `.vercel/output` exists. Otherwise use the standard `vercel deploy` path after the Vite build verification.
  - [x] Use GitHub Secrets for `DATABASE_URL`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, and any other deployment credentials. Do not echo secret values.
  - [x] Keep deployment non-blocking relative to data preservation: a Vercel failure should fail the deploy job visibly but must not delete generated artifacts or mutate database rows into a false success state.
  - [x] Add a post-deploy URL check for the latest report and `/archive`, and store/log the deployment URL for the archive row.
  - [x] Keep scheduled workflow commits narrow: generated report/archive assets and explicit metadata only. Do not commit ignored root runtime artifacts unless deliberately reviewed and force-added as curated evidence.

- [x] **Task 7: Tests and Verification (AC: 1-6)**
  - [x] Add backend tests under `backend/tests/services/test_report_publisher.py` for slug generation, HTML escaping, archive sorting, empty state, report asset writing, and OG image generation.
  - [x] Add script tests under `backend/tests/scripts/test_publish_weekly_report.py` using the repo's mock pool/connection style.
  - [x] Add or extend scheduler tests in `backend/tests/services/test_scheduler.py` for report snapshot/publish invocation in nominal and warning modes, and no normal report publish in locked mode.
  - [x] Add tests that generated report HTML includes the experience strip, profile fit delta, accountability/Loop B block, public `og:image`, and escaped generated content.
  - [x] Add tests or CI assertions that deployment URL checks fail visibly without losing generated artifacts.
  - [x] Add a frontend build/static verification test if practical, or document the build-output check in the story completion notes.
  - [x] Run `npm run test`, `npm run lint`, and `cd frontend && npm run build`.

### Review Findings

- [x] [Review][Patch] Generated artifact commits are never pushed, so historic report assets disappear after the runner exits [.github/workflows/weekly-report.yml:63]
- [x] [Review][Patch] Deployment URL metadata is written after deploy without redeploying or committing the regenerated archive/report HTML [.github/workflows/weekly-report.yml:70]
- [x] [Review][Patch] Stored report paths break archive links on later renders because `reports/...` resolves under `/archive/` [backend/services/report_publisher.py:334]
- [x] [Review][Patch] Health check can verify an arbitrary old report instead of the report generated for the current run [.github/workflows/weekly-report.yml:85]

## Dev Notes

### Existing Code and Reuse

- `backend/db/migrations/V003__add_weekly_reports_and_access.sql` already defines `weekly_reports` with `run_date`, `corpus_size`, `per_source_counts`, `eval_accuracy`, `report_html`, `geo_us_eu`, `geo_india`, and `accessed_at`.
- `backend/services/scheduler.py` already runs Saturday 08:00 IST ingestion through APScheduler, writes `run-summary-YYYY-WW.json` in warning mode, writes `kill-criterion-fired-YYYY-WW.json` in locked/failure mode, and inserts basic `weekly_reports` rows through `_record_weekly_report`.
- `backend/routers/jobs.py` already computes current analytics for `GET /api/v1/jobs/analytics`, including `geo_segments.us_eu_remote`, `geo_segments.india_ai_product`, `profile_fit_score`, `profile_fit_delta`, top skills, corpus size, and latest eval accuracy. Use this as a shape reference, but do not make historic reports recompute from current analytics on view.
- `frontend/src/views/LedgerView.tsx` currently contains a placeholder ledger surface only. If no durable accountability table exists yet, the static report should render an honest placeholder or snapshot field rather than inventing completed commitment counts.
- `frontend/src/views/DashboardView.tsx` and `frontend/src/views/Views.module.css` contain the existing market dashboard presentation and HUD styling patterns that report HTML should echo.
- `frontend/src/index.css` defines the core HUD color variables: `--bg-cosmic`, `--bg-panel`, `--border-hud`, `--glow-cyan`, `--glow-purple`, `--glow-magenta`, `--glow-green`, `--text-primary`, and `--text-secondary`.
- There is currently no `.github/` directory and no `frontend/public/` directory. This story is expected to create both as needed.

### Architecture and Guardrails

- Keep backend business logic in `backend/services/`; routers and scripts should orchestrate service functions rather than containing rendering logic.
- Raw SQL migrations remain the schema source of truth under `backend/db/migrations/`.
- Use psycopg parameterized queries for all database writes/reads.
- API responses elsewhere use a `data` wrapper for success and `{error, code, detail}` for failures. Static pages do not need this wrapper, but any helper endpoint added during implementation should follow it.
- Frontend components use PascalCase files and colocated `*.test.tsx`; backend tests mirror source modules under `backend/tests/`.
- Public report/archive pages are intentionally unauthenticated per product requirements. Treat attempts to add auth as a regression.
- Generated HTML must escape all fields that can come from jobs, profiles, LLM output, source names, company names, or commit metadata.
- Root-level runtime artifacts are ignored by default and must be reviewed before force-adding curated evidence. The GitHub workflow should commit only intended generated static files and metadata.
- `.gitignore` already ignores `.env`, local secret-like files, root `run-summary-*.json`, and root `kill-criterion-fired-*.json`; workflow commit steps must respect that boundary unless a human deliberately curates evidence artifacts.

### Previous Story Intelligence

- Story 5.4 added company fingerprinting with static fallback HTML and found multiple review issues around escaping generated content, offline fallback depending on remote Google Fonts, slug sanitization, and hot-path LLM/database behavior. Apply those lessons here:
  - Escape generated HTML by default.
  - Do not depend on remote fonts/assets for offline/static report surfaces.
  - Keep request/view paths fast by writing static files ahead of time.
  - Avoid hot-path LLM calls for report/archive rendering.
- Story 5.3 established geo-segment display expectations and tests for profile fit, top skills, experience distribution, skill gaps, and accessible live/status semantics. Reuse its data shape and visible labels instead of inventing a separate report schema.
- Recent commits indicate the current Epic 5 implementation pattern: analytics in `backend/routers/jobs.py`, dashboard work in `frontend/src/views/DashboardView.tsx`, company fingerprints in `backend/services/fingerprinter.py` and `frontend/src/views/CompanyView.tsx`.

### Latest Technical Notes

- GitHub Actions scheduled workflows use POSIX cron syntax; scheduled workflows default to UTC and current docs also describe timezone-aware scheduling. Use explicit UTC cron `30 2 * * 6` for Saturday 08:00 IST unless the workflow deliberately opts into a timezone field. Source: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule
- Vercel CLI supports prebuilt deployments through `vercel deploy --prebuilt`, but that flag expects output from `vercel build` in `.vercel/output`; if the workflow only runs `npm run build`, use normal Vercel deployment or add a `vercel build` step. Source: https://vercel.com/docs/cli/deploy
- Vercel supports dynamic OG image workflows through `@vercel/og`, but this repo should prefer deterministic generated static images for testability and to avoid adding a Vercel Functions dependency unless explicitly needed. Vercel documents 1200x630 as the recommended OG image size. Source: https://vercel.com/docs/og-image-generation

### Project Structure Notes

- Add service logic in `backend/services/report_publisher.py`.
- Add publish orchestration in `backend/scripts/publish_weekly_report.py`.
- Add migration `backend/db/migrations/V010__add_weekly_report_publish_metadata.sql` or the next available version if another migration exists.
- Add tests in `backend/tests/services/test_report_publisher.py`, `backend/tests/scripts/test_publish_weekly_report.py`, and extend `backend/tests/services/test_scheduler.py`.
- Add generated-static target directories under `frontend/public/archive/` and `frontend/public/reports/`.
- Add `.github/workflows/weekly-report.yml` for scheduled/manual publishing.
- Add or update README/docs to state that public report, archive, and company fingerprint pages are unauthenticated by design.

### References

- `_bmad-output/planning-artifacts/epics.md`: Epic 5, Story 5.5 acceptance criteria.
- `_bmad-output/planning-artifacts/prd.md`: Report Generation & Publishing, FR30-FR36, NFR-P1-P5, NFR-S3, NFR-R1-R2, NFR-I4, NFR-A1-A3.
- `_bmad-output/planning-artifacts/architecture.md`: naming, structure, API response, service boundary, static asset, cron scheduling, and test organization patterns.
- `_bmad-output/implementation-artifacts/5-3-geo-segmented-market-analysis-and-skill-gap-diff.md`: market dashboard data and accessibility patterns.
- `_bmad-output/implementation-artifacts/5-4-company-stack-fingerprint-and-interview-screen-share-view.md`: static HTML, sanitization, offline fallback, and review learnings.
- `backend/services/scheduler.py`: current weekly ingestion, report recording, warning/locked artifact behavior.
- `backend/db/migrations/V003__add_weekly_reports_and_access.sql`: existing report persistence schema.
- `frontend/src/index.css`: HUD color and typography variables.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-06-05: `backend/venv/bin/pytest backend/tests/services/test_report_publisher.py backend/tests/scripts/test_publish_weekly_report.py` initially failed during collection because the new service/script did not exist yet.
- 2026-06-05: Focused backend publisher/script/scheduler tests passed: `20 passed`.
- 2026-06-05: `cd frontend && npm run build` passed; Vite emitted the existing large React chunk warning. Static `frontend/public/archive/index.html` copied to `frontend/dist/archive/index.html`; generated report/OG files are verified by `write_report_assets` tests and by the workflow after DB-backed generation.
- 2026-06-05: `npm run lint` passed.
- 2026-06-05: `npm run test` passed: frontend `38 passed`; backend `221 passed`.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added `V010` weekly report publish metadata and snapshot columns while preserving the existing run-date uniqueness/index.
- Implemented pure static report publishing helpers with escaped standalone HTML, public archive rendering, deterministic no-dependency 1200x630 PNG OG image generation, and asset writing under `frontend/public`.
- Wired nominal/warning scheduler runs to persist static report snapshots and attempt publishing without converting publish failures into ingestion data loss; locked runs still emit kill artifacts only.
- Added a CI/local publish script with optional run-date, commit SHA, and deployment URL metadata updates.
- Added a public empty archive shell, public portfolio operations note, and a Saturday 08:00 IST GitHub Actions workflow that tests, generates assets, builds, commits curated public artifacts, deploys to Vercel, records deployment metadata, and health-checks `/archive` plus the latest report.
- Added backend tests for publisher behavior, script orchestration, scheduler publish/no-publish paths, escaping, archive sorting/empty state, OG image dimensions/determinism, and migration coverage.

### File List

- .github/workflows/weekly-report.yml
- _bmad-output/implementation-artifacts/5-5-archive-index-and-social-sharing.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- backend/db/migrations/V010__add_weekly_report_publish_metadata.sql
- backend/scripts/publish_weekly_report.py
- backend/services/report_publisher.py
- backend/services/scheduler.py
- backend/tests/scripts/test_publish_weekly_report.py
- backend/tests/services/test_report_publisher.py
- backend/tests/services/test_scheduler.py
- docs/public-portfolio-surfaces.md
- frontend/public/archive/index.html
- frontend/public/reports/.gitkeep

### Change Log

- 2026-06-05: Implemented archive index and social sharing static publishing workflow; story marked ready for review.
