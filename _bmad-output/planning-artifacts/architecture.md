---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/product-brief-be-an-ai-engineer.md
  - _bmad-output/planning-artifacts/source-discovery-channel-strategy.md
  - _bmad-output/brainstorming/brainstorming-session-2026-04-10-01.md
  - docs/business-os-genai-spec.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-05-26T13:05:00Z'
project_name: 'be-an-ai-engineer'
user_name: 'Darko'
date: '2026-05-25'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
- **Mission Control UI**: A local React SPA dashboard to trigger tasks, edit user profiles, visualize skills/gaps, run evaluations, and update the accountability ledger.
- **Local API Backend**: A Python backend (FastAPI) to expose services to the React UI and manage the data pipeline.
- **Multi-Source Ingestion**: Ingest AI engineering job postings from active source-registry rows backed by Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, YC `workatastartup.com`, HN threads, and validated company `JobPosting` JSON-LD. Triggerable on-demand via the React UI.
- **Company Discovery & Canonical Source Resolution**: Discover companies from HN, Google Custom Search, constrained Wellfound signals, Common Crawl ATS indexes, YC directories, VC portfolio pages, GitHub organization metadata, and Reddit hiring posts, then activate only canonical employer or ATS sources after validation.
- **Structured LLM Extraction**: Extract job fields (skills, seniority, tech stack, salary band, remote policy, and role archetype) using the local Hermes proxy pointing to the Codex subscription.
- **Evaluation Harness UI**: Trigger evals and audit extraction accuracy (precision/recall) directly on the dashboard.
- **Storage & Vector Search**: Local Neon Postgres/pgvector instance for vector embedding storage and profile matching.
- **Geo-Segmented Analytics**: Side-by-side US/EU remote and India AI product rankings visualized in React.
- **Accountability Ledger**: Interactive UI tracker for weekly commitments vs. actions.

**Non-Functional Requirements:**
- **Local-Only Web Stack**: 100% local deployment. The React app, FastAPI backend, and Postgres must all run on localhost.
- **Zero-Cost LLM Budget**: Route API requests through the local Hermes proxy using active browser sessions.
- **Data Quality & Evals**: Strict structured output compliance (valid JSON schemas).
- **Interface Responsiveness**: Fast page transitions and live logging feedback in the UI for running tasks.

**Scale & Complexity:**
- Project complexity appears to be: **High-Medium** (moving from automated batch scripts to a full-stack local web application with React state and FastAPI-driven task execution).
- Primary technical domain: **Full-Stack Local Application (React + FastAPI + Postgres)**
- Estimated architectural components: **9** (React UI, API Backend, Ingest Engine, Company Discovery/Canonical Resolver, Extraction Client, Local Vector DB, Evaluation Harness, Analytical Processor, Accountability Ledger Manager).

### Technical Constraints & Dependencies
- **No Cloud Services**: Postgres must run in Docker or locally natively.
- **No CSV Fallback**: Pipeline must be robust to source errors.
- **LLM Proxy Dependency**: All LLM interactions depend on the local Hermes proxy endpoint (running on localhost).
- **Local Dev Server Setup**: Vite (React) dev server + Uvicorn (FastAPI) backend.
- **Canonical Source Rule**: Google is allowed only through Custom Search JSON API, with explicit caps and optional credentials. Wellfound is constrained to company/domain/evidence signals. LinkedIn and Indeed are manual-signal surfaces only. No browser automation or marketplace scraping becomes part of the trusted corpus.

### Cross-Cutting Concerns Identified
- **State Synchronization**: Syncing UI edits (like profile updates) immediately to recalculate rankings in the database.
- **Task Management**: Managing long-running ingestion/eval scripts in the background without locking the UI thread.
- **Schema Evolution**: LLM JSON schema changes.
- **Error Handling**: API transient errors, rate limits, and proxy disconnects.
- **Discovery Provider Isolation**: Provider failures, quota exhaustion, and low-confidence results must be isolated per provider so one noisy channel cannot block the weekly ingest.
- **Discovery Auditability**: Every discovered company/source must preserve evidence URL, provider, validation status, rejection reason, and last-seen timestamp.

## Starter Template Evaluation

### Primary Technology Domain

**Full-Stack Local Application** — React SPA frontend (Mission Control UI) + Python API backend (data pipeline engine), both running locally on the developer's machine.

### Starter Options Considered

| Option | Verdict | Reason |
|---|---|---|
| **Next.js + FastAPI** | ❌ Rejected | Next.js brings SSR/SSG complexity that adds zero value to a local tool. Requires Node.js server + Python server = double overhead. |
| **Create React App (CRA)** | ❌ Rejected | Deprecated, no longer maintained. Vite supersedes it entirely. |
| **Vite + React (TypeScript) SPA + FastAPI** | ✅ Selected | Minimal surface area, maximum control. Vite is the industry standard for React SPAs. FastAPI is the canonical Python API framework for async, type-safe backend services. |

### Selected Starter: Vite (React-TS) + FastAPI Monorepo

**Rationale:**
Vite + React (TypeScript) provides a lightning-fast dev server with HMR for the Mission Control dashboard. FastAPI is natively async, has first-class Pydantic integration for JSON schema validation (critical for structured LLM extraction outputs), and exposes auto-generated OpenAPI docs at `/docs` with zero config. The monorepo layout keeps frontend and backend co-located without forcing a shared runtime.

**Verified Versions (as of 2026-05-26):**
- `create-vite` → **v8.0.14** (vitejs/vite)
- `FastAPI` → **0.136.3** (fastapi/fastapi)

**Initialization Commands:**

```bash
# 1. Inspect Vite options (safety-first)
npx -y create-vite@latest --help

# 2. Initialize React frontend
npx -y create-vite@latest frontend --template react-ts

# 3. Install frontend dependencies
cd frontend && npm install && cd ..

# 4. Initialize Python backend
mkdir backend && cd backend
python3 -m venv venv
source venv/bin/activate
pip install "fastapi==0.136.3" "uvicorn[standard]" "pydantic>=2.0" \
    "psycopg2-binary" "pgvector" "httpx"
cd ..
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- Frontend: TypeScript (ESNext) in browser, compiled by Vite/ESBuild
- Backend: Python 3.11+ with virtual environment (`venv`)

**Styling Solution:**
- Vanilla CSS (`index.css` + CSS Modules `*.module.css`) — maximum control, zero framework lock-in, suitable for the dark-mode Mission Control aesthetic

**Build Tooling:**
- Frontend: Vite **8.0.14** (ESBuild for dev, Rollup for prod bundles; Node ≥ v20 required)
- Backend: Uvicorn **`[standard]`** latest — includes uvloop, httptools, watchfiles for hot-reload

**Testing Framework:**
- Frontend: Vitest **v4.1.6** (Vite-native, Jest-compatible API; requires Vite ≥ v6 — satisfied by Vite 8)
- Backend: pytest **9.0.0** + pytest-asyncio + HTTPX (via `httpx.ASGITransport` for in-process FastAPI testing — no network overhead required)

**Code Organization (Monorepo):**

```
be-an-ai-engineer/
├── frontend/          # Vite + React-TS SPA (Mission Control UI)
│   ├── src/
│   │   ├── pages/     # Dashboard, Ingest, Evals, Ledger, Profile
│   │   ├── components/
│   │   ├── hooks/
│   │   └── api/       # Typed fetch wrappers for FastAPI endpoints
│   └── vite.config.ts
├── backend/           # FastAPI backend (pipeline engine + API)
│   ├── routers/       # ingest.py, extraction.py, evals.py, ledger.py
│   ├── services/      # Business logic layer
│   ├── db/            # Postgres + pgvector connection and models
│   ├── llm/           # Hermes proxy client wrapper
│   └── main.py        # FastAPI app entrypoint
└── docker-compose.yml # Local Postgres + pgvector container
```

**Development Experience:**
- HMR in browser on every React save (< 50ms)
- Auto-generated Swagger UI at `http://localhost:8000/docs`
- Frontend dev proxy in `vite.config.ts` routes `/api/*` → FastAPI at `localhost:8000`

**Note:** Project initialization using the above commands is the first implementation story (Story 1.1).

**Verified Install Commands (Context7):**

```bash
# Frontend testing
npm install -D vitest

# Backend testing
pip install "pytest==9.0.0" pytest-asyncio httpx
```

## Core Architectural Decisions

### Decision Priority Analysis

**Critical (Block Implementation):**
- Local Postgres 16 via Docker Compose with pgvector extension
- FastAPI BackgroundTasks + SSE for long-running task feedback to React UI
- No authentication (localhost-only single-user tool)

**Important (Shape Architecture):**
- TanStack Query v5 for React server-state management
- react-router-dom v7 for SPA routing
- APScheduler 4 in-process for weekly cron (FastAPI lifespan)
- structlog for structured backend logging

**Deferred (Post-MVP):**
- Alembic for database migrations — plain versioned SQL scripts for MVP
- Redis/queue worker for task isolation — APScheduler sufficient for MVP scale

### Data Architecture

- **Database**: Local Postgres 16 + pgvector via `docker-compose.yml` (`pgvector/pgvector:pg16` image) — one command: `docker compose up -d`
- **Query Layer**: Raw `psycopg` **3.2.10** (psycopg3) + `pgvector-python` — no ORM. Explicit SQL committed to repo is a stronger portfolio signal than abstracted ORM calls.
- **Schema Migrations**: Versioned SQL scripts (`db/migrations/V001__init.sql`) committed to repo. No Alembic for MVP.
- **Discovery Tables**: Source discovery uses `job_sources`, `job_source_candidates`, and `source_discovery_runs`; Company Radar extends this with `company_signals` and `company_discovery_runs` so signals stay separate from validated active ingest sources.
- **Caching**: None in MVP. Local DB + corpus ≤500 rows = no latency issue.

### Authentication & Security

- **Auth**: None. Single-user localhost-only tool. Auth is pure overhead with zero security benefit.
- **CORS**: FastAPI CORS middleware locked to `http://localhost:5173` only — prevents any accidental network exposure.

### API & Communication Patterns

- **Style**: REST. FastAPI auto-generates OpenAPI docs at `http://localhost:8000/docs`.
- **Long-Running Tasks**: FastAPI `BackgroundTasks` — each task gets a UUID; React polls `GET /tasks/{id}/status`.
- **Real-Time Log Streaming**: Server-Sent Events (SSE) via `GET /tasks/{id}/logs/stream`. Custom `useSSE(taskId)` React hook consumes the stream for live terminal output in the Mission Control UI.
- **Error Envelope**: All errors return `{"error": true, "code": "ERROR_CODE", "detail": "..."}` via FastAPI exception handlers across all endpoints.

### Frontend Architecture

- **Routing**: `react-router-dom` **7.6.2** (Context7: `/remix-run/react-router`) — 5 top-level routes: `/` Dashboard, `/ingest`, `/evals`, `/ledger`, `/profile`
- **Server State**: `@tanstack/react-query` **v5.90.3** (Context7: `/tanstack/query`) — API fetching, polling, background refresh, cache invalidation
- **UI State**: React `useState` + `useContext` for local UI state (modals, form inputs, log buffers)
- **Live Logs**: Custom `useSSE(taskId)` hook — subscribes to FastAPI SSE stream, appends log lines to local state
- **Charts**: `recharts` **v3.3.0** (Context7: `/recharts/recharts`) — skill frequency bar charts, precision/recall line charts, profile fit gauges

### Infrastructure & Local Dev

- **Local DB**: `docker-compose.yml` with `pgvector/pgvector:pg16` — `docker compose up -d` starts everything
- **Dev Startup**: `make dev` via `concurrently` npm package — launches Vite dev server (`localhost:5173`) + Uvicorn (`localhost:8000`) in a single command
- **Env Config**: `.env` at repo root — `DATABASE_URL`, `HERMES_PORT`, `HERMES_HOST`; Vite reads via `import.meta.env`, FastAPI reads via `python-dotenv`
- **Logging**: `structlog` latest stable (Context7: `/hynek/structlog`, score 94.1) — JSON in prod, colored human-readable in dev
- **Scheduling**: APScheduler 4 (Context7: `/agronholm/apscheduler`) inside FastAPI lifespan event — weekly Saturday IST ingest cron, no external process required

### Decision Impact Analysis

**Implementation Sequence:**
1. `docker-compose.yml` + `db/migrations/V001__init.sql` → local Postgres 16 + pgvector running
2. FastAPI skeleton with CORS, `.env` loading, health endpoint
3. Vite React scaffold + react-router-dom 7.6.2 routes + TanStack Query v5.90.3 provider
4. Vite proxy config (`/api/*` → `localhost:8000`) in `vite.config.ts`
5. First ingest router + BackgroundTask lifecycle + SSE log stream endpoint
6. React Ingest page consuming SSE via `useSSE` hook + live log terminal UI
7. Extraction client (Hermes proxy wrapper in `backend/llm/client.py`)
8. Eval harness router + React Evals page with recharts precision/recall charts
9. Accountability Ledger router + React Ledger page (CRUD + history view)
10. Dashboard aggregation endpoint + React Dashboard with recharts skill-frequency bars
11. APScheduler weekly cron wired to ingest router inside FastAPI lifespan

**Cross-Component Dependencies:**
- SSE streaming requires BackgroundTask lifecycle to remain open until task completes → task state machine must emit a `done` event to signal stream close
- TanStack Query cache invalidation must trigger when task-status polling returns `completed`
- `.env` `HERMES_PORT` must be populated before any extraction call is made
- `recharts` v3.3.0 charts in Evals page depend on extraction + eval data being present in Postgres

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
8 critical conflict areas have been identified where different AI agents could make diverging choices:
1. DB vs API casing (DB and JSON both using snake_case, avoiding camelCase translation layer complexity).
2. API routing plurals vs singulars (strict plurals /api/v1/tasks, /api/v1/profiles).
3. Test co-location vs separate test directories.
4. Python vs TypeScript naming styles (FastAPI backend uses snake_case, React frontend uses PascalCase for components and camelCase for hooks).
5. Date and time representation formats (ISO 8601 strings only, zero Unix timestamps).
6. Server-Sent Events (SSE) streaming structure (task state events using structured JSON).
7. Error response structure consistency.
8. State loading/fetching conventions in React (TanStack Query vs manual state).

### Naming Patterns

**Database Naming Conventions:**
- Table naming: Plural `snake_case` (e.g., `jobs`, `evaluation_runs`, `commitments`).
- Column naming: `snake_case` (e.g., `job_id`, `salary_band_min`, `remote_policy`).
- Foreign key format: `snake_case` referencing singular parent table with suffix `_id` (e.g., `jobs.profile_id` referencing `profiles.id`).
- Index naming: Prefixed with `idx_` followed by table name and column names (e.g., `idx_jobs_profile_id`).

**API Naming Conventions:**
- REST endpoint naming: Plural `snake_case` (e.g., `/api/v1/jobs`, `/api/v1/evaluation_runs`).
- Route parameter format: `{parameter_name}` (e.g., `/api/v1/jobs/{job_id}`).
- Query parameter naming: `snake_case` (e.g., `/api/v1/jobs?min_salary=100000`).
- Header naming conventions: Standard headers, custom ones prefixed with `X-` (e.g., `X-Hermes-Session-ID`).

**Code Naming Conventions:**
- Component naming: `PascalCase` matching their file name (e.g., `JobList.tsx` exports `JobList`).
- File naming: Matches the component name exactly (e.g., `JobCard.tsx` / `JobCard.test.tsx`).
- Function naming: `camelCase` in TypeScript (e.g., `getUserData`), `snake_case` in Python (e.g., `get_user_data`).
- Variable naming: `camelCase` in TypeScript (e.g., `userId`), `snake_case` in Python (e.g., `user_id`).

### Structure Patterns

**Project Organization:**
- Where do tests live? Frontend: co-located next to component with `*.test.tsx` / `*.test.ts`. Backend: Placed in a mirrored `tests/` subdirectory matching the root source directory (e.g., `backend/tests/routers/test_ingest.py` tests `backend/routers/ingest.py`).
- Component organization: By page/feature folder under `frontend/src/pages/` or general reusable components under `frontend/src/components/`.
- Shared utilities: Frontend uses `frontend/src/utils/`, Backend uses `backend/utils/`.
- Services: Backend business logic lives in `backend/services/` (e.g., `backend/services/parser.py`, `backend/services/source_discovery.py`, and future `backend/services/company_discovery.py` / `backend/services/canonical_resolver.py`).

**File Structure Patterns:**
- Config file locations and naming: `.env` at repo root for global settings. Frontend uses `vite.config.ts`, Backend configuration lives in `backend/config.py`.
- Static asset organization: Frontend static assets live in `frontend/public/` or `frontend/src/assets/`.
- Documentation placement: Design files, user guides, and architecture specifications live in `docs/` and `_bmad-output/`.

### Format Patterns

**API Response Formats:**
- API response wrapper: Successful Responses are wrapped in a `data` object:
  ```json
  {
    "data": {
      "id": "123",
      "status": "completed"
    }
  }
  ```
- Error format: Uniform payload returning details:
  ```json
  {
    "error": true,
    "code": "ENTITY_NOT_FOUND",
    "detail": "Job with ID 123 does not exist."
  }
  ```

**Data Exchange Formats:**
- JSON field naming: Strict `snake_case` on both frontend and backend. No automatic conversion to `camelCase` in API boundaries.
- Boolean representations: Native boolean types (`true` / `false`).
- Null handling patterns: Omit missing fields or use `null` explicitly where fields are optional. Avoid empty strings `""` to represent null.
- Date format in JSON: UTC ISO 8601 strings (e.g., `2026-05-26T13:00:00Z`).

### Communication Patterns

**Event Systems:**
- Event naming convention: Use `{resource}.{action}` (e.g., `task.started`, `task.log`, `task.completed`).
- Event payload structure standards: Standard SSE payloads wrapping task state information.
- Logging formats and levels: `structlog` levels mapping to `debug`, `info`, `warning`, `error`, `critical`.

**State Management:**
- State update patterns: React Query caches for server state, local React hooks/state for transient UI variables.
- Action naming conventions: `camelCase` prefixing action intent (e.g., `handleTabChange`).

### Process Patterns

**Error Handling:**
- Backend: FastAPI controllers raise `HTTPException` with clear error codes. An exception handler catches them and returns the uniform error envelope.
- Frontend: Global `QueryClient` default error handler triggers a toast notification showing the error detail. Specific UI screens can implement error boundaries to catch unexpected render crashes.

**Loading States:**
- Loading state handling: React Query states (`isLoading`, `isFetching`) are utilized directly instead of manual local flags.
- Task execution loaders: Live log terminal widget UI that connects to SSE log stream.

### Enforcement Guidelines

**All AI Agents MUST:**
- Use the uniform JSON `snake_case` serialization for all endpoints.
- Store dates as UTC ISO 8601 strings in database timestamp columns.
- Ensure every endpoint returning error codes matches the standard schema.

**Pattern Enforcement:**
- Use automated linting (`eslint`, `ruff`) before committing code.
- Continuous Integration/tests will fail if schemas diverge from predefined formats.
- Document any exceptions or version bumps in `architecture.md`.

### Pattern Examples

**Good Examples:**
```python
# backend/routers/jobs.py
@router.get("/api/v1/jobs/{job_id}", response_model=JobResponseEnvelope)
async def get_job(job_id: str, db=Depends(get_db)):
    job = await db.fetch_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404, 
            detail=f"Job {job_id} not found"
        )
    return {"data": job}
```

**Anti-Patterns:**
```python
# AVOID: Returning raw lists/dictionaries without wrapping in a 'data' key or using camelCase keys
@router.get("/api/v1/job/{jobId}")
async def get_job(jobId: str):
    return {"jobId": jobId, "salaryBand": "100k"}  # AVOID camelCase and singular resource /job
```

### Step 5: FastAPI Ingestion Engine & SSE Log Streaming

**Implementation Logic:**
- **BackgroundTask Lifecycle**: The ingestion task is triggered via a POST request to `/api/v1/ingest`. FastAPI creates a `BackgroundTasks` entry. The task ID is returned immediately to the frontend.
- **Log Buffering**: We utilize a thread-safe queue (`asyncio.Queue`) within the task service to store log messages in memory for the duration of the task.
- **SSE Endpoint**: A GET endpoint `/api/v1/tasks/{task_id}/logs/stream` returns Starlette's native `StreamingResponse` with `media_type="text/event-stream"` and streams log events from the `asyncio.Queue` to the frontend. Do not add an external SSE package; the implemented dependency policy uses framework-native SSE formatting.
- **Frontend Integration**: A custom hook `useSSE(taskId)` manages the connection state (connecting/disconnecting) and maintains an array of log objects in component state, enabling the live-scrolling terminal UI.
- **Task Completion**: Once the ingestion process completes (or encounters a fatal error), the task service emits terminal control events as SSE records (`task.completed` or `task.failed`) so the React frontend can close the connection and update task status without polling.

### Step 5b: Company Discovery & Canonical Source Resolution

**Implementation Logic:**
- **Provider Interface**: Discovery providers return structured signals with provider name, evidence URL, confidence, optional company domain, and category hints. Providers are independently enabled and capped.
- **Canonical Resolver**: Company-domain signals are resolved only through bounded careers paths, declared sitemaps, supported ATS links, and `JobPosting` JSON-LD. This is not a crawler.
- **Registry Boundary**: `company_signals` and `job_source_candidates` are evidence layers. Only validated canonical rows become active `job_sources`, and weekly ingestion reads from `job_sources`.
- **API Surface**: Existing `/api/v1/ingest/discover-sources` remains the operational entrypoint for source discovery; future provider diagnostics expose yield, rejection reasons, freshness, and quota status.
- **Marketplace Constraint**: Google is an official API provider, Wellfound is a constrained company-signal provider, and LinkedIn/Indeed are not automated providers.

## Project Structure & Boundaries

### Complete Project Directory Structure
```
be-an-ai-engineer/
├── README.md
├── Makefile            # Root task orchestrator (make dev, make test)
├── package.json        # Root workspace configuration for concurrently dev orchestration
├── docker-compose.yml  # Local Postgres 16 + pgvector container definition
├── .env.example        # Reference environment variables
├── .env                # Local active environment variables (DB_URL, HERMES_PORT, etc.)
├── .gitignore          # Repository ignore lists
├── docs/               # System and API documentation
│   └── api-endpoints.md
├── frontend/           # Vite + React (TypeScript) SPA
│   ├── package.json
│   ├── vite.config.ts  # Vite configs, ESBuild rules, API dev proxy setup
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx    # App initialization and bootstrap
│   │   ├── App.tsx     # Router configuration and global provider layout
│   │   ├── index.css   # Global design system variables & CSS rules
│   │   ├── pages/      # Route-level page layouts
│   │   │   ├── Dashboard/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Dashboard.module.css
│   │   │   │   └── Dashboard.test.tsx
│   │   │   ├── Ingest/
│   │   │   │   ├── Ingest.tsx
│   │   │   │   ├── Ingest.module.css
│   │   │   │   └── Ingest.test.tsx
│   │   │   ├── Evals/
│   │   │   │   ├── Evals.tsx
│   │   │   │   ├── Evals.module.css
│   │   │   │   └── Evals.test.tsx
│   │   │   ├── Ledger/
│   │   │   │   ├── Ledger.tsx
│   │   │   │   ├── Ledger.module.css
│   │   │   │   └── Ledger.test.tsx
│   │   │   └── Profile/
│   │   │       ├── Profile.tsx
│   │   │       ├── Profile.module.css
│   │   │       └── Profile.test.tsx
│   │   ├── components/  # Shared reusable design components
│   │   │   ├── Sidebar/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Sidebar.module.css
│   │   │   ├── Terminal/
│   │   │   │   ├── Terminal.tsx
│   │   │   │   └── Terminal.module.css
│   │   │   └── Toast/
│   │   │       ├── Toast.tsx
│   │   │       └── Toast.module.css
│   │   ├── hooks/      # Custom React hooks (useSSE, useDebounce)
│   │   │   └── useSSE.ts
│   │   ├── api/        # Fetch wrappers interacting with FastAPI endpoints
│   │   │   ├── client.ts
│   │   │   ├── jobs.ts
│   │   │   ├── evals.ts
│   │   │   ├── ledger.ts
│   │   │   └── profile.ts
│   │   ├── types/      # Global TypeScript interface definitions
│   │   │   └── index.ts
│   │   └── utils/      # Client helper functions (formatting, date utilities)
│   │       └── helpers.ts
│   └── public/         # Static assets (favicons, logos)
└── backend/            # FastAPI Python application
    ├── requirements.txt
    ├── main.py         # App entrypoint and lifecycle events registration
    ├── config.py       # Pydantic BaseSettings class loading .env variables
    ├── db/             # Database connectivity & raw migration scripts
    │   ├── connection.py  # psycopg3 connection pool management
    │   └── migrations/
    │       └── V001__init.sql  # Database init setup (tables, vector indexes)
    ├── routers/        # FastAPI endpoint controllers
    │   ├── ingest.py       # Ingest controls, SSE log streamer
    │   ├── jobs.py         # Main jobs index, search & geo analytics
    │   ├── evals.py        # Eval harness trigger & statistics
    │   ├── ledger.py       # Commitment logs API
    │   └── profile.py      # Profile management and vector scoring triggers
    ├── services/       # Core business logic processing
    │   ├── parser.py       # Parsers for Greenhouse, Lever, Ashby, Workable, etc.
    │   ├── evaluator.py    # Logic calculating precision/recall metrics
    │   └── scheduler.py    # APScheduler cron tasks
    ├── llm/            # Structured extraction client
    │   ├── client.py       # Connector targeting local Hermes proxy
    │   └── schemas.py      # Pydantic schemas validating LLM JSON extraction
    ├── utils/          # Logging configurations and task utilities
    │   ├── logging.py      # structlog configurations
    │   └── tasks.py        # Thread-safe in-memory SSE logging queues
    └── tests/          # pytest unit/integration directory (mirrors backend src)
        ├── conftest.py
        ├── routers/
        │   ├── test_ingest.py
        │   └── test_jobs.py
        └── services/
            └── test_parser.py
```

### Architectural Boundaries

**API Boundaries:**
- FastAPI exposes endpoints under the `/api/v1` namespace.
- Accessing the API from Vite is proxy-configured within `vite.config.ts` mapping local request pathways starting with `/api` directly to `localhost:8000`.
- All requests and responses are strictly validated through Pydantic schemas (representing requests/responses input-output contracts).

**Component Boundaries:**
- The React SPA communicates with the backend exclusively via HTTP REST endpoints (GET, POST, PUT, DELETE) and SSE (for server logs).
- No direct component-to-component data mutations exist. All shared server data must be synced using TanStack Query cache keys. Local UI-state is decoupled inside leaf components or Context Providers.

**Service Boundaries:**
- Controllers in `routers/` should not query the database or invoke third-party services directly. They route commands to standard service modules in `services/`.
- The `services/` namespace contains stateless business logic functions which operate on connections received from psycopg3 pool injection.

**Data Boundaries:**
- Raw SQL files in `db/migrations` act as the database schema's sole source of truth.
- Access to Postgres tables happens exclusively via standard parameters in psycopg3 (`execute(...)`), preventing SQL injection.
- Vector matching is confined to the profile module executing cosine-similarity math natively in Postgres using `pgvector`.

### Requirements to Structure Mapping

**Feature/Epic Mapping:**
- **Mission Control Dashboard**: Front-end components in `frontend/src/pages/Dashboard/`, API logic in `backend/routers/jobs.py` (analytics aggregation queries).
- **Multi-Source Ingest**: Ingestion triggering in `frontend/src/pages/Ingest/`, routing logic in `backend/routers/ingest.py`, parsing functions in `backend/services/parser.py`.
- **Company Discovery & Source Registry**: Discovery orchestration in `backend/services/source_discovery.py`; future company signal providers in `backend/services/company_discovery.py`; canonical validation/resolution in `backend/services/canonical_resolver.py`; persistence through `job_sources`, `job_source_candidates`, `source_discovery_runs`, `company_signals`, and `company_discovery_runs`.
- **Structured Extraction**: LLM client in `backend/llm/client.py`, structured JSON schemas in `backend/llm/schemas.py`, proxy routing via Hermes, and first-class proxy health verification in `backend/llm/hermes.py`.
- **Evaluation Harness**: UI dashboard in `frontend/src/pages/Evals/`, testing/comparison rules in `backend/services/evaluator.py`, endpoints in `backend/routers/evals.py`.
- **Accountability Ledger**: Front-end layout in `frontend/src/pages/Ledger/`, backend queries in `backend/routers/ledger.py`.

**Cross-Cutting Concerns:**
- **SSE Logging Stream**: Stream hooks in `frontend/src/hooks/useSSE.ts`, terminal display widget in `frontend/src/components/Terminal/`, background queues managed in `backend/utils/tasks.py`.
- **Structured Logging**: Standardizer in `backend/utils/logging.py` configured via structlog.
- **Cron Scheduling**: Internal task manager setup via APScheduler in `backend/services/scheduler.py` initialized during lifespan startup in `backend/main.py`.

### File Organization Patterns

**Configuration Files:**
- Single `.env` file at project root contains global keys. Dev files (e.g., `package.json`, `tsconfig.json`) are maintained locally inside respective workspaces.

**Source Organization:**
- Frontend logic is partitioned by routing pages first (`pages/`), followed by atomic shared visuals (`components/`).
- Backend logic isolates entrypoints (`main.py`) from endpoints (`routers/`), business functions (`services/`), and data storage configuration (`db/`).

**Test Organization:**
- Frontend Vitest tests are co-located next to target components.
- Backend pytest tests are structured in a mirrored directory pattern inside `backend/tests/`.

**Asset Organization:**
- Dynamic user uploads/downloads are not used. Static images (logos) are stored in `frontend/public/assets/`.

### Development Workflow Integration

**Development Server Structure:**
- Running `make dev` uses the root `package.json` script executing `concurrently "cd frontend && npm run dev" "cd backend && venv/bin/uvicorn main:app --reload --port 8000"`.

**Build Process Structure:**
- The frontend builds into `frontend/dist/` using `npm run build` which triggers Rollup compilation.
- The Python backend does not require compilation.

**Deployment Structure:**
- For local execution, the container is started with `docker compose up -d`, setting up Postgres + pgvector. Frontend and backend are ran via node and python environments respectively.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
- All core framework selections are fully compatible.
- React Router v7.6.2 and TanStack Query v5.90.3 integrate cleanly into the Vite 8 SPA template.
- psycopg 3.2.10 provides high-performance async database pool integration for PostgreSQL 16.
- The use of the local Hermes proxy endpoint removes external API latency issues.

**Pattern Consistency:**
- All code naming patterns (camelCase for JS/TS frontend, snake_case for Python backend and PostgreSQL DB) align with modern standards.
- Response payloads follow a single unified envelope pattern (`{ data: ... }` or `{ error: true, code: ..., detail: ... }`), preventing data parsing conflicts among client code.

**Structure Alignment:**
- The monorepo setup splits frontend code and backend code cleanly, avoiding runtime overlap.
- Colocated tests in the frontend and mirrored tests in the backend prevent testing confusion.

### Requirements Coverage Validation ✅

**Epic/Feature Coverage:**
- **Mission Control Dashboard**: Fully covered by `Dashboard.tsx` UI and `backend/routers/jobs.py` analytics queries.
- **Multi-Source Ingest**: Fully covered by `Ingest.tsx` UI, `backend/routers/ingest.py`, and `backend/services/parser.py`.
- **Company Discovery & Canonical Source Expansion**: Covered by `backend/services/source_discovery.py`, the future provider/resolver service boundary, source-registry migrations, and provider yield reporting artifacts.
- **Structured Extraction**: Managed via `backend/llm/client.py` and validated using Pydantic in `backend/llm/schemas.py`.
- **Evaluation Harness**: Handled by `backend/routers/evals.py` and visualized using recharts in the Evals page.
- **Accountability Ledger**: Addressed via `backend/routers/ledger.py` CRUD endpoints.

**Functional Requirements Coverage:**
- All ingestion sources (Greenhouse, Lever, Ashby, Workable, etc.) will be supported by specialized parser blocks in `backend/services/parser.py`.
- Company discovery requirements FR48-FR55 are covered by provider contracts, canonical resolver validation, source registry tables, capped Google/Wellfound constraints, and discovery reporting.
- Task tracking logs utilize an in-memory queue streaming to SSE without locking the server thread.

**Non-Functional Requirements Coverage:**
- **Local-Only**: Satisfied by local Docker compose Postgres instance and localhost-only server binds.
- **Zero-Cost LLM**: Satisfied by local Hermes proxy routing.

### Implementation Readiness Validation ✅

**Decision Completeness:**
- All critical versions and installation rules have been looked up and verified using the Context7 library resolution system.
- Explicit examples of routers, naming conversions, and anti-patterns are documented.

**Structure Completeness:**
- A detailed file tree mapping every feature to its respective directory is complete.

**Pattern Completeness:**
- Naming, communication, error-handling, and log streaming patterns have been defined.

### Gap Analysis Results
- **Critical Gaps**: None.
- **Important Gaps**: None. The local SQLite file option has been rejected in favor of Postgres + pgvector to provide first-class vector scoring natively.
- **Nice-to-Have Gaps**: Production dockerization (e.g., containerizing the backend service). Deferred for post-MVP optimization since it is run purely on localhost.

### Validation Issues Addressed
- **Version Compatibility**: Verified that Vitest v4.1.6 is fully compatible with Vite 8.
- **Library resolution**: Verified psycopg3 compatibility and raw SQL execution protocols.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**✅ Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** HIGH (Visions verified using Context7, raw SQL provides direct database control, and SSE stream endpoints are mapped out.)

**Key Strengths:**
- Clean separation of frontend and backend.
- Local vector capabilities using Postgres pgvector.
- SSE task logging enables highly interactive real-time visual output.

**Areas for Future Enhancement:**
- Database backup scripts for local Postgres.

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented.
- Use implementation patterns consistently across all components.
- Respect project structure and boundaries.
- Refer to this document for all architectural questions.

**First Implementation Priority:**
- Initialize the Vite 8 frontend and setup Python virtual environment using the commands defined in the Starter Template section.
