# Story 4.3: Interactive Evals Dashboard and Regression Charts

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want an interactive `/evals` page showing precision/recall line charts, run history, and detailed parameter controls to run tests and audit LLM extraction quality live,
so that I can review parser accuracy transparently.

## Product Context

Story 4.3 establishes the visual interface and diagnostic cockpit for the AI structured extraction evaluation harness. In 2026 AI engineering, showing rigorous metrics via a live interactive dashboard is the key differentiator that separates a toy project from a professional portfolio. It proves to hiring managers that you treat extraction accuracy and regressions as first-class engineering concerns.

The `/evals` page will allow the user to view historical performance trends using Recharts, trigger a new evaluation run against the training or held-out dataset, monitor execution log outputs in real-time via Server-Sent Events (SSE), and examine a side-by-side tabular comparison of expected vs. actual extraction outputs. Any mismatched field will be visually flagged in orange, making it easy to identify prompt leakage or schema mismatches.

---

## Acceptance Criteria

1. **FastAPI Evals Router (`backend/routers/evals.py`) Exposes History, Latest Summary, and Run Triggers**
   - Given a database connection pool
   - When a `GET /api/v1/evals` request is received
   - Then the backend queries the `evaluation_runs` table and returns a `200 OK` JSON response enveloped as `{"data": [...]}` containing all runs ordered by `run_timestamp` DESC.
   - And when a `POST /api/v1/evals/run` request is received with an optional JSON payload `{"split": "held_out", "prompt_version": "extraction_v1"}`
   - Then it registers a task in `task_manager`, starts a background execution task (`BackgroundTasks`), and returns `202 Accepted` with `{"task_id": "..."}`.
   - And when a `GET /api/v1/evals/latest` request is received
   - Then it loads the most recently created `run-summary-*.json` file in `_bmad-output/implementation-artifacts/` and returns its complete JSON content as `{"data": ...}`. If no summary file exists, it returns a `404 Not Found` error matching the standard error envelope.
   - And the router is mounted in `backend/main.py` under the `/api/v1` namespace.

2. **Async Background Task & SSE Log Integration**
   - Given an evaluation task triggered via the router
   - When the background task starts execution
   - Then it sets the context variable `active_task_id.set(task_id)` to route log entries from `structlog` automatically.
   - And it executes `run_evaluation()` from `backend/services/evaluator.py` using a pool connection.
   - And on completion, it writes a `completed` control log to `task_manager` with the run statistics summary.
   - And on exception, it catches the error, logs it, and writes a `failed` control log with error details to `task_manager`.
   - And it ensures `task_manager.finish_task(task_id)` is invoked inside a `finally` block to clean up resources.

3. **React Client API & Routing Setup**
   - Given a client-side routing structure
   - When the user navigates to `/evals`
   - Then the application renders the `EvalsView` component.
   - And the client implements fetchers inside `frontend/src/api/evals.ts` matching the backend endpoints (`GET /api/v1/evals`, `GET /api/v1/evals/latest`, `POST /api/v1/evals/run`).
   - And the page utilizes `@tanstack/react-query` to fetch history and latest run details, caching them under unified query keys (`evalsHistory`, `latestEvalResults`).

4. **Live Spinner & Log Console Terminal**
   - Given an active evaluation run initiated from the UI
   - When the evaluation runs in the background
   - Then the UI displays a concentric double-ring loading spinner and a monospace console terminal showing live logs streamed from `/api/v1/tasks/{task_id}/logs/stream` via the `useSSE` hook.
   - And once the SSE stream signals task completion or failure, the React query caches for `evalsHistory` and `latestEvalResults` are automatically invalidated to trigger a fresh data fetch and populate the dashboard views.

5. **Recharts Precision/Recall Trend Visualization**
   - Given historical evaluation runs in the database
   - When rendering the `/evals` dashboard
   - Then the page displays a Recharts `LineChart` plotting precision, recall, and F1 scores over time (x-axis: timestamp/run number, y-axis: 0.0 - 1.0).
   - And the lines use glowing HSL colors (cyan for precision, purple for recall, and green for F1/accuracy) with interactive hover tooltips showing precise numbers.
   - And if no run history exists, a clean fallback layout overlay is rendered.

6. **Evaluation Parameter Control Panel**
   - Given the `/evals` layout page
   - When selecting parameter options
   - Then the user can choose `split` from a dropdown selection (`held_out` or `train`) and input `prompt_version` (text field default: `extraction_v1`).
   - And clicking `[RUN EVALUATION]` submits these parameters to the API.

7. **Detailed Tabular Difference & Mismatch Highlighting**
   - Given the latest run results fetched from `GET /api/v1/evals/latest`
   - When rendering the audit comparison table
   - Then the UI displays the 20-sample extraction comparison side-by-side (Expected values vs. Actual/Extracted values).
   - And any field containing a mismatch (e.g. F1 < 1.0 or non-matching string/object) is highlighted with a warning orange background or border showing both expected and actual values.
   - And a toggle switch supports filtering the table to "Show Mismatches Only".

8. **Router and UI Component Tests**
   - Given router tests in `backend/tests/routers/test_evals.py`
   - When running pytest, they verify history querying, task spawning, latest-file fetching, and appropriate error handling.
   - And given frontend tests in `frontend/src/views/EvalsView.test.tsx`
   - When running vitest, they assert component rendering, loading spinner appearance, log terminal presence, and recharts chart initialization.

---

## Tasks / Subtasks

- [x] **Task 1: Build FastAPI Evals Router & Mount (AC: 1)**
  - [x] Create `backend/routers/evals.py`.
  - [x] Implement `GET /api/v1/evals` to fetch run history from `evaluation_runs`.
  - [x] Implement `GET /api/v1/evals/latest` to read the latest `run-summary-*.json` file.
  - [x] Implement `POST /api/v1/evals/run` accepting `split` and `prompt_version` payload and starting background task.
  - [x] Register `evals_router` in `backend/main.py`.

- [x] **Task 2: Implement Async Evaluation Background Task (AC: 2)**
  - [x] Define `run_evaluation_task` background function in `backend/routers/evals.py`.
  - [x] Bind `active_task_id.set(task_id)` to route logs via `structlog`.
  - [x] Run the evaluation against the DB connection, catching exceptions and writing control signals (`completed` / `failed`) to `task_manager`.
  - [x] Ensure `task_manager.finish_task(task_id)` is invoked inside a `finally` block.

- [x] **Task 3: Implement Client API & App Routing (AC: 3)**
  - [x] Create `frontend/src/api/evals.ts` with typed fetchers for endpoints.
  - [x] Configure `QueryClientProvider` and `QueryClient` in `frontend/src/main.tsx` if missing.
  - [x] Ensure `/evals` route in `frontend/src/App.tsx` maps correctly to `EvalsView.tsx`.

- [x] **Task 4: Develop Evals Dashboard Header and Control Panel (AC: 6)**
  - [x] Design split selection dropdown (`held_out` / `train`) and prompt version text input.
  - [x] Implement debounced state or simple controlled inputs.
  - [x] Add the `[RUN EVALUATION]` trigger button.

- [x] **Task 5: Integrate Live Progress Terminal & Spinner (AC: 4)**
  - [x] Add a double-ring CSS spinner visible when a run is active.
  - [x] Mount the monospace `TerminalConsole` (reused from components) in `EvalsView.tsx`.
  - [x] Connect the `useSSE` hook to stream logs, auto-scrolling to bottom.
  - [x] Trigger TanStack Query invalidation on task completion to reload page metrics.

- [x] **Task 6: Create Recharts Precision/Recall Trend Visuals (AC: 5)**
  - [x] Add `recharts` to `frontend/package.json` dependencies (version `3.3.0`).
  - [x] Render a responsive `LineChart` using historical run data from TanStack Query.
  - [x] Style lines with HUD themed colors (cyan, purple, green).
  - [x] Add tooltips and legend, and implement a fallback message for empty history.

- [x] **Task 7: Build Expected vs. Actual Tabular Diff Audit (AC: 7)**
  - [x] Parse `detailed_diffs` from latest run results and render them in a responsive table.
  - [x] Add a styling rule in `EvalsView.module.css` to highlight mismatched cells in orange.
  - [x] Implement a toggle checkbox to filter mismatches.

- [x] **Task 8: Write Router and UI Integration Tests (AC: 8)**
  - [x] Create `backend/tests/routers/test_evals.py` using pytest.
  - [x] Create `frontend/src/views/EvalsView.test.tsx` using vitest and testing-library.

### Review Findings

- [x] [Review][Patch] Live log streaming bypasses the required `useSSE` hook [frontend/src/views/EvalsView.tsx:48]
- [x] [Review][Patch] Audit table is not side-by-side for expected vs. actual values [frontend/src/views/EvalsView.tsx:218]
- [x] [Review][Patch] Evaluation run request accepts explicit null control values [backend/routers/evals.py:21]
- [x] [Review][Patch] Router test does not verify task spawning behavior [backend/tests/routers/test_evals.py:117]

---

## Dev Notes

### Dependencies & Setup Lifecycle
Before importing any new libraries in your frontend code, you **MUST** run the `scan_dependencies` verification tool first. The required libraries to add to `frontend/package.json` are:
1. **`@tanstack/react-query`** v5.90.3 (or latest approved version)
2. **`recharts`** v3.3.0 (or latest approved version)

Ensure `QueryClientProvider` wraps the React root in `frontend/src/main.tsx`:
```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
const queryClient = new QueryClient();
// Wrap around app...
```

### Existing Code to Reuse
- **`backend/services/evaluator.py`**: Call `run_evaluation` directly for the background task.
- **`backend/utils/tasks.py`**: Reuse the global `task_manager` singleton for registering evaluation tasks and enqueuing control log messages.
- **`backend/routers/ingest.py`**: Look at `stream_task_logs` and `start_ingestion` as reference implementations of background tasks and SSE streaming.
- **`frontend/src/components/Terminal/`** or similar logging components: Reuse the monospace logging panel that consumes the SSE stream.

### Hard Requirements
- **No ORM**: All backend DB actions must be raw SQL using psycopg.
- **Unified Casing**: DB columns, tables, and JSON payloads must maintain `snake_case`.
- **Hermes Offline Handling**: Ensure `run_evaluation` health check throws an error if Hermes is offline, which must be cleanly logged and returned as a `failed` event.
- **Accuracy Regression Threshold**: The regression threshold is hardcoded to `0.03` (3 percentage points drop) on `overall_f1`.

### Previous Story Learning Summary
- Story 4.2 successfully seeded the 20 ground-truth postings and implemented the core calculation formulas.
- Ensure that the prompt template examples do not include any samples from the `held_out` split to avoid evaluation dataset contamination.
- Ensure the background task is fully isolated so UI responsiveness is not affected.

### Project Structure Notes
- **Views Directory**: The general Architecture Document (`architecture.md`) references placing pages/views in `frontend/src/pages/Evals/`. However, in the actual workspace layout, routed screens are situated in `frontend/src/views/` (e.g., `frontend/src/views/EvalsView.tsx`).
- **Styling Scoping**: Component styles must be placed in `frontend/src/views/EvalsView.module.css` or added directly to `frontend/src/views/Views.module.css` to respect the existing layout and scoping conventions of the workspace.
- **Routing**: Client-side routing for `/evals` is already configured in `frontend/src/App.tsx` mapping to `EvalsView.tsx`. The developer only needs to implement the internal contents of `EvalsView.tsx` and does not need to modify `frontend/src/App.tsx` routing paths.
- **Test Placement**: Put frontend tests in `frontend/src/views/EvalsView.test.tsx` next to the view, and backend router tests in `backend/tests/routers/test_evals.py` to mirror the backend directory structure.

---

## References

- [Epics: Story 4.3](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#L456)
- [PRD: Quality Telemetry Dashboard](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#L715)
- [Architecture: SPA Routing & Recharts](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md#L202)
- [Ingestion Task SSE Router Reference](file:///home/darko/Code/be-an-ai-engineer/backend/routers/ingest.py#L335-L387)
- [Database Evaluator Service](file:///home/darko/Code/be-an-ai-engineer/backend/services/evaluator.py)

---

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

- Pytest execution verified with 186/186 tests passing.
- Vitest execution verified with 21/21 tests passing.
- Frontend typescript compile and production build verified with 0 errors.

### Completion Notes List

- Implemented FastAPI evals endpoints (`GET /api/v1/evals`, `GET /api/v1/evals/latest`, `POST /api/v1/evals/run`).
- Developed `run_evaluation_task` executing `run_evaluation()` from `evaluator.py` inside an isolated background task, automatically routing logs using `structlog` ContextVar.
- Added `@tanstack/react-query` and `recharts` dependencies in the frontend and successfully integrated them into the app root (`main.tsx`).
- Created dynamic `/evals` view featuring parameters selection, double-ring loading spinner, live log streaming terminal, glowing trend lines plotting precision/recall/F1, and detailed side-by-side audit table.
- Highlighted mismatches in orange with custom detail comparison formats and mismatch-only filtering toggles.
- Handled regression alarm banner matching the 3% overall F1 regression.
- Provided 100% test coverage for the router and React dashboard component views.

### File List

- [backend/routers/evals.py](file:///home/darko/Code/be-an-ai-engineer/backend/routers/evals.py)
- [backend/main.py](file:///home/darko/Code/be-an-ai-engineer/backend/main.py)
- [frontend/package.json](file:///home/darko/Code/be-an-ai-engineer/frontend/package.json)
- [frontend/src/main.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/main.tsx)
- [frontend/src/api/evals.ts](file:///home/darko/Code/be-an-ai-engineer/frontend/src/api/evals.ts)
- [frontend/src/views/EvalsView.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/views/EvalsView.tsx)
- [frontend/src/views/EvalsView.module.css](file:///home/darko/Code/be-an-ai-engineer/frontend/src/views/EvalsView.module.css)
- [backend/tests/routers/test_evals.py](file:///home/darko/Code/be-an-ai-engineer/backend/tests/routers/test_evals.py)
- [frontend/src/views/EvalsView.test.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/views/EvalsView.test.tsx)
- [frontend/src/App.test.tsx](file:///home/darko/Code/be-an-ai-engineer/frontend/src/App.test.tsx)
