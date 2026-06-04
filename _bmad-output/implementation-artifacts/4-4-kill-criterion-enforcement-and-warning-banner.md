# Story 4.4: Kill-Criterion Enforcement and Warning Banner

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a render-blocking middleware or pipeline validation check that blocks report generation if the corpus size is < 100 or extraction accuracy is < 70%, displaying warning notices if only one threshold is breached,
so that faulty ingestion runs do not produce corrupt market metrics.

## Product Context

Story 4.4 establishes the robust operational guardrails and quality assurance gates (the "kill criterion" and "warning mode") for the ingestion and extraction pipeline. In 2026 AI engineering, production readiness requires that automated metrics are not corrupted by pipeline hiccups, API changes, or prompt leakage. Having a strict validation gate prevents contaminated data from displaying on the dashboard and automatically notifies the engineer when human intervention is required.

The system will monitor two key quality thresholds:
1. **Corpus Size**: Total postings in the `jobs` table must be $\ge 100$.
2. **Extraction Accuracy**: The F1 score of the latest evaluation run must be $\ge 70\%$ ($0.70$).

If **both** thresholds are breached (or if the ingestion run fails completely), the weekly report generation is blocked, and the dashboard is locked with a full-page warning magenta alert.
If **exactly one** threshold is breached, the system enters **warning mode (Danger Zone)**: the dashboard remains accessible, but a prominent yellow warning banner is displayed at the top to notify the developer they have 7 days to recover before console lock.

---

## Acceptance Criteria

1. **Database Metrics Retrieval Helpers**
   - Given a database connection
   - When checking quality thresholds
   - Then the backend queries the database:
     - Corpus size is retrieved via `SELECT COUNT(*) FROM jobs`.
     - Evaluation accuracy is retrieved via `SELECT overall_f1 FROM evaluation_runs ORDER BY run_timestamp DESC, id DESC LIMIT 1`. If no evaluation runs exist, it defaults to `1.0` (or `None` handled as `1.0` to prevent false locks).

2. **Weekly Ingestion Pipeline Integration & Kill Artifacts**
   - Given a running weekly ingestion execution in `backend/services/scheduler.py`
   - When the run completes
   - Then it records `eval_accuracy` in the `weekly_reports` database table (matching the existing `eval_accuracy` column in migration `V003`).
   - And it evaluates the quality thresholds:
     - `kill_fired = (corpus_size < 100 AND eval_accuracy < 0.70) OR summary.get("status") != "success" OR fatal_error is not None`
     - `warning_mode = (exactly one of [corpus_size < 100, eval_accuracy < 0.70] is True) AND (summary.get("status") == "success") AND (fatal_error is None)`
   - And if `kill_fired` is `True`:
     - It locks the weekly report state and writes a `kill-criterion-fired-YYYY-WW.json` metadata artifact to the workspace root.
     - It enqueues a delayed-handoff email containing the manual CSV pivot template and diagnostic error to the outbox to be sent via `Resend` within 5 minutes.
   - And if only one threshold is breached, it writes `run-summary-YYYY-WW.json` but marks the run with a warning status and does not lock the report.

3. **FastAPI Health Route System Status Enhancement**
   - Given a client querying `GET /api/v1/health`
   - When the health check queries the database
   - Then it returns:
     - `corpus_size`: (integer) count of jobs
     - `eval_accuracy`: (float | null) F1 score of latest evaluation run
     - `system_state`: (string) `"locked"` (if both thresholds are breached, if the database has 0 jobs, or if the latest ingestion run status is `"failure"`), `"warning"` (if exactly one threshold is breached and the latest ingestion succeeded), or `"nominal"` (if both thresholds are satisfied and the latest ingestion succeeded)
     - `warning_mode`: (boolean) true if `system_state` is `"warning"`
   - And these fields are returned inside the standard `data` health wrapper object.

4. **React Dashboard Locked Forcing & Warning Banner Rendering**
   - Given a running React frontend polling the health status
   - When the health data returns `system_state: "locked"`
     - Then the `/` route renders a full-page warning magenta alert banner: `▲ [KILL CRITERION TRIGGERED] Ingestion corpus or accuracy below minimum quality thresholds. Dashboard locked.`
     - And it blocks rendering of standard console panels (diagnostics, logs).
     - And it maintains full tab navigation, keeping other routes like `/ingest`, `/ledger`, `/profile` accessible so the user can upload a CSV or modify their profile to resolve the lock.
   - When the health data returns `system_state: "warning"`
     - Then the `/` route renders a yellow top banner: `▲ [WARNING] Danger Zone: Ingestion quality thresholds near limit. 7 days to recover before console lock.`
     - And all standard console panels (diagnostics, logs) render and operate normally.
   - When the health data returns `system_state: "nominal"`
     - Then no warning or lock banners are rendered.

5. **Router, Service, and UI Component Tests**
   - Given scheduler tests in `backend/tests/services/test_scheduler.py`
     - When running pytest, they assert `run_weekly_ingestion` correct threshold checking, email dispatching, and `kill-criterion-fired-*.json` file writing.
   - Given health router tests in `backend/tests/routers/test_health.py`
     - When running pytest, they assert `/api/v1/health` returns correct system status, counts, and flags under nominal, warning, and locked conditions.
   - Given frontend tests in `frontend/src/views/DashboardView.test.tsx`
     - When running vitest, they verify that the dashboard renders the locked full-page banner when `system_state` is `"locked"`, and renders the warning banner when `system_state` is `"warning"`.

---

## Tasks / Subtasks

- [x] **Task 1: Retrieve Quality Metrics & Update Scheduler (AC: 1, 2)**
  - [x] Implement `_get_latest_eval_accuracy` in `backend/services/scheduler.py`.
  - [x] Update `_record_weekly_report` to save `eval_accuracy` in `weekly_reports`.
  - [x] Calculate `kill_fired` and `warning_mode` thresholds in `run_weekly_ingestion`.
  - [x] Implement writing `kill-criterion-fired-YYYY-WW.json` to the workspace root when `kill_fired` is True.
  - [x] Ensure delayed-handoff email is sent to outbox when `kill_fired` triggers.

- [x] **Task 2: Enhance Health Router Payload (AC: 3)**
  - [x] Update `GET /api/v1/health` in `backend/routers/health.py` to retrieve jobs count and latest evaluation F1 score.
  - [x] Implement `system_state` logic (`"locked"`, `"warning"`, `"nominal"`) and `warning_mode` boolean check.
  - [x] Include the fields in the health JSON response under the `data` envelope.

- [x] **Task 3: Develop React Frontend Warning and Lock UI (AC: 4)**
  - [x] Modify `frontend/src/views/DashboardView.tsx` to read `system_state` and `warning_mode` from the health data.
  - [x] Render the full-page magenta lock banner when `system_state === "locked"`, blocking other dashboard console elements but allowing tab navigation.
  - [x] Render the yellow Danger Zone top warning banner when `system_state === "warning"`.
  - [x] Update styling rules or reuse `warningBanner` class in `frontend/src/views/Views.module.css`.

- [x] **Task 4: Implement Backend and Frontend Tests (AC: 5)**
  - [x] Update `backend/tests/services/test_scheduler.py` to cover new quality threshold assertions and mock DB responses cleanly.
  - [x] Update `backend/tests/routers/test_health.py` to assert correct health payload fields.
  - [x] Create `frontend/src/views/DashboardView.test.tsx` to assert locked and warning UI layouts using Vitest and React Testing Library.

### Review Findings

- [x] [Review][Patch] Health route allows warning/nominal when latest ingestion did not succeed [backend/routers/health.py:59]
- [x] [Review][Patch] Scheduler persists report HTML before evaluating kill criteria, so locked runs can still generate report content [backend/services/scheduler.py:232]
- [x] [Review][Patch] Locked dashboard is styled as a standard banner rather than a full-page lock surface [frontend/src/views/DashboardView.tsx:74]
- [x] [Review][Patch] Scheduler tests do not cover success-plus-both-thresholds-breached kill or exactly-one-threshold warning artifacts [backend/tests/services/test_scheduler.py:57]
- [x] [Review][Patch] Kill artifact write failure can prevent notification enqueue/email fallback [backend/services/scheduler.py:260]
- [x] [Review][Patch] Runtime kill artifact is present in the working tree and should not ship as source [kill-criterion-fired-2026-22.json:1]

---

## Dev Notes

- **Existing Code to Reuse**:
  - `backend/services/scheduler.py` for cron ingestion logic.
  - `backend/routers/health.py` for health checks.
  - `frontend/src/views/DashboardView.tsx` for the main page.
- **Database Schema**:
  - `weekly_reports` has `eval_accuracy` (FLOAT).
  - `evaluation_runs` has `overall_f1` (NUMERIC).
- **Constraints**:
  - Autoinvalidation / polling in `App.tsx` handles refresh, so the lock status updates dynamically.
  - The UI must keep header, sidebar, and footer layout intact to allow Alt+1 to Alt+5 navigation.

### Project Structure Notes

- **Tests**:
  - Put frontend tests in `frontend/src/views/DashboardView.test.tsx`.
  - Put backend tests in `backend/tests/services/test_scheduler.py` and `backend/tests/routers/test_health.py`.
- **Casing**:
  - All JSON properties and DB columns must maintain `snake_case`.

### References

- [Epics: Story 4.4](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#L471-L484)
- [PRD: Warning Banner Logic](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#L254-L268)
- [Database Schema - Reports Table](file:///home/darko/Code/be-an-ai-engineer/backend/db/migrations/V003__add_weekly_reports_and_access.sql#L2-L14)
- [Scheduler Service Reference](file:///home/darko/Code/be-an-ai-engineer/backend/services/scheduler.py)

---

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

- Ran `npm run test` executing Vitest and pytest suites to ensure 100% correct, green test pass.
- Verified compilation and layout rendering in the Vite/React frontend via `npm run build`.

### Completion Notes List

- Implemented database queries fetching corpus size, latest evaluation F1 score, and latest ingestion run status in backend scheduler and health router.
- Integrated quality threshold checks into scheduler weekly ingestion:
  - Fired kill-criterion: writes `kill-criterion-fired-YYYY-WW.json` to workspace root, locks reports, and enqueues delayed handoff email if corpus < 100 AND accuracy < 70%, OR ingestion status is failure.
  - Warning mode: writes `run-summary-YYYY-WW.json` if exactly one threshold is breached.
- Updated health endpoint payload to include `corpus_size`, `eval_accuracy`, `system_state`, and `warning_mode` inside data envelope.
- Enhanced frontend DashboardView component to read the health system state:
  - If locked, renders a full-page magenta alert banner blocking standard panels while keeping other routes accessible.
  - If warning, renders a yellow warning top banner, keeping console panels functional.
- Authored extensive unit and integration tests covering nominal, warning, and locked state health API responses, scheduler actions, and React dashboard UI states.

### File List

- `backend/services/scheduler.py`
- `backend/routers/health.py`
- `frontend/src/views/Views.module.css`
- `frontend/src/views/DashboardView.tsx`
- `backend/tests/services/test_scheduler.py`
- `backend/tests/routers/test_health.py`
- `frontend/src/views/DashboardView.test.tsx`

### Change Log

- 2026-06-04: Implement Story 4-4 quality gate kill criterion and warning banners. Update scheduler, health endpoints, frontend dashboard, and unit/integration tests.
- 2026-06-04: Retrospective follow-up confirmed final quality-state semantics: `locked` for ingestion failure, empty corpus, or both quality thresholds breached; `warning` for exactly one breached threshold after successful ingestion; `nominal` when ingestion succeeds and both thresholds pass.
