---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# be-an-ai-engineer - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for be-an-ai-engineer, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

- **FR1:** Pipeline can fetch job postings from the Greenhouse public API for any company slug
- **FR2:** Pipeline can fetch job postings from the Lever public API for any company slug
- **FR3:** Pipeline can fetch job postings from the Ashby public API for any company slug
- **FR4:** Pipeline can fetch job postings from the Workable, Recruitee, and Personio public APIs for any company slug
- **FR5:** Pipeline can fetch job postings from the Y Combinator WaaS public API
- **FR6:** Pipeline can parse the current HN "Who's Hiring" monthly thread and extract AI engineering postings
- **FR7:** Pipeline can ingest postings for a single specified company on demand, outside the weekly seed-list run
- **FR8:** Pipeline can fall back to a user-supplied CSV of postings when live ingest sources are unavailable or kill-criterion-frozen
- **FR9:** Pipeline records per-source posting counts, run timestamp, and success/failure status per source per run
- **FR10:** Pipeline can extract structured signals — skills, seniority, tech stack, salary band, remote policy, role archetype — from a job posting via LLM
- **FR11:** Pipeline can process postings in batches and skip postings already extracted in a prior run
- **FR12:** Pipeline can record which prompt version produced each posting's extraction result
- **FR13:** Pipeline can rank skills by frequency across the full corpus, separately per geo segment
- **FR14:** Pipeline can compute skill co-occurrence clusters from the weekly corpus
- **FR15:** Pipeline can compute salary-band / tech-stack correlations from postings with disclosed salary data
- **FR16:** Pipeline can assign each posting to a geo segment (US/EU remote or India-based AI product) based on extracted remote policy and company location
- **FR17:** Pipeline can compute a minimum-experience-threshold distribution across the corpus (% postings with no stated minimum / 3+ / 5+ / senior-only)
- **FR18:** User can update their skills, seniority, tech stack, years of experience, and geo preference via a version-controlled profile file
- **FR19:** Pipeline can compute a profile fit score against the weekly top-30 ranked skills per geo segment
- **FR20:** Pipeline can generate a skill-gap diff showing which top-ranked market skills are absent from the user's profile, per geo segment
- **FR21:** Report can display a profile freshness warning when the profile has not been updated in ≥21 days
- **FR22:** User can log weekly commitments and actions (applications filed, interviews completed, LinkedIn posts, voice notes, commits) against a structured schema
- **FR23:** Report can display the accountability ledger showing prior-week commitments vs. actions, with gap flags, below the skill rankings — always visible, never hidden
- **FR24:** Report can visually distinguish commitments that have been missed for 2 or more consecutive weeks
- **FR25:** Pipeline can enforce a render-blocking locked state that prevents weekly report generation when ingestion fails, corpus size is 0, or both corpus size < 100 and extraction accuracy < 70%
- **FR26:** Pipeline can enter a non-blocking warning mode when exactly one of the two kill-criterion thresholds is breached, displaying a 7-day recovery notice on the report
- **FR27:** Pipeline can bound a user-initiated ingest debug session to 60 minutes before forcing a CSV fallback and committing a debug log to the repository
- **FR28:** System can send an email to the user 24 hours after a kill criterion fires, containing an inline CSV pivot template and the run diagnostic block
- **FR29:** System can send an email to the user with the weekly report body inline when the report page has not been accessed for 2 consecutive Saturdays
- **FR30:** Report viewer can access the weekly skill-gap report at a public URL without authentication
- **FR31:** Report can display top-10 skills for the US/EU remote segment and top-10 for the India-based AI product segment, side-by-side in a two-column layout
- **FR32:** Report can display the minimum-experience-threshold distribution strip at the top of each weekly report
- **FR33:** Report can display the week-over-week profile fit score delta vs. the prior week per geo segment
- **FR34:** Pipeline can publish the weekly report to a public URL via an automated deployment on the weekly cron schedule
- **FR35:** Pipeline can generate a shareable static image per weekly report, sized and formatted for mobile readability and social-platform embedding
- **FR36:** Report viewer can browse an archived index of all past weekly reports at a public `/archive` URL
- **FR37:** Report can render a one-click demo-close button that returns the view to a neutral state when the page is accessed with a designated URL parameter
- **FR38:** User can create and maintain a hand-labeled evaluation set of job postings annotated against the 6-field extraction schema, with a fixed train/held-out split
- **FR39:** Pipeline can measure per-field precision and recall on the held-out evaluation set after each extraction run and produce a structured result artifact committed to the repository
- **FR40:** Pipeline can detect a regression when aggregate extraction accuracy drops more than 3 percentage points from the prior run and flag it in the run output
- **FR41:** Pipeline can commit a run-summary artifact per weekly execution (corpus size, per-source counts, extraction latency, extraction accuracy) to the public repository
- **FR42:** Pipeline can verify active local Hermes proxy connection health status and abort the batch run if the proxy is unresponsive
- **FR43:** Pipeline can generate a company stack fingerprint on demand (role-archetype summary, top-10 extracted technologies, one-sentence LLM-generated observation) for any company in the ingest corpus
- **FR44:** Pipeline can write a static local HTML copy of the most recently generated company fingerprint to disk for offline use
- **FR45:** User can view the company stack fingerprint in a single-screen layout suitable for live screen-share presentation
- **FR46:** User can view a publicly accessible weekly log of Loop B execution metrics — applications filed, interviews completed, non-frozen interviews, LinkedIn posts, voice notes — updated weekly
- **FR47:** Pipeline can commit required craft-signal documentation artifacts (eval methodology, local Hermes proxy configuration guide, annotated extraction failure cases) to the public repository as versioned files
- **FR48:** Pipeline can store company discovery signals from multiple providers, including company name, domain, evidence URL, provider name, confidence, and category hints
- **FR49:** Pipeline can resolve discovered company domains to canonical careers or ATS sources using bounded careers paths, sitemap parsing, ATS URL detection, and JobPosting JSON-LD parsing
- **FR50:** Pipeline can use Vertex AI Search Discovery Engine `searchLite` as an optional capped signal provider for careers and ATS page discovery without scraping search result pages
- **FR51:** Pipeline can use Wellfound as a constrained company-signal provider, extracting company/domain/evidence only and never treating Wellfound job text as trusted corpus data
- **FR52:** Pipeline can query Common Crawl indexes for supported public ATS URL patterns, deduplicate ATS slugs, and validate candidates before activation
- **FR53:** Pipeline can discover company signals from YC company directories and VC portfolio pages, then verify hiring through canonical company or ATS sources
- **FR54:** Pipeline can discover lower-confidence company signals from GitHub organization metadata and Reddit hiring posts using official APIs where available
- **FR55:** Discovery reports can compare provider yield, source freshness, active source growth, rejected reasons, and coverage gaps across all discovery providers


### NonFunctional Requirements

- **NFR-P1 (NFR1):** Report page First Contentful Paint < 1.5s measured from Vercel CDN edge for users in India and the US.
- **NFR-P2 (NFR2):** Report page Largest Contentful Paint < 2.5s (Core Web Vitals green on Vercel Analytics).
- **NFR-P3 (NFR3):** Total report page weight < 500KB — no JavaScript framework, no CDN-loaded libraries, no web fonts with large subset ranges.
- **NFR-P4 (NFR4):** Company stack fingerprint page renders in < 2s on the hot path — the pipeline must not re-run corpus extraction during a live demo session; fingerprint data is pre-computed and cached.
- **NFR-P5 (NFR5):** Full weekly pipeline run (ingest → extract → rank → diff → report → deploy) completes within 60 minutes of the Saturday cron trigger.
- **NFR-S1 (NFR6):** No API keys, database connection strings, or service credentials appear in the public repository at any time — enforced via `.gitignore` and a pre-commit hook.
- **NFR-S2 (NFR7):** All external service credentials are stored in GitHub Actions secrets for production runs and in a gitignored `.env.local` for local development.
- **NFR-S3 (NFR8):** The weekly report, archive index, and company fingerprint pages are intentionally public and unauthenticated.
- **NFR-R1 (NFR9):** Public report URL maintains ≥99% availability during Weeks 4–16 — monitored via Vercel uptime health checks.
- **NFR-R2 (NFR10):** Every weekly pipeline run produces a committed output — either a `run-summary-YYYY-WW.json` artifact (success) or a `kill-criterion-fired-YYYY-WW.json` artifact (failure).
- **NFR-R3 (NFR11):** Kill-criterion delayed-handoff email delivers within 5 minutes of the kill condition being logged.
- **NFR-R4 (NFR12):** Skip-2-weeks nudge email delivers on the second consecutive missed Saturday within a 30-minute window of the cron run completing.
- **NFR-I1 (NFR13):** A single ingest adapter failure does not abort the pipeline run — the failed source is logged with its error, the run continues with the remaining sources.
- **NFR-I2 (NFR14):** All LLM calls route exclusively through the local Hermes proxy endpoint — no direct cloud LLM provider calls in application code.
- **NFR-I3 (NFR15):** LLM extraction batches tolerate partial structural failures — valid objects are committed and the failed posting IDs are logged.
- **NFR-I4 (NFR16):** Vercel deployment step is non-blocking for the pipeline logic — if the Vercel deploy fails, the pipeline commits the run-summary artifact and sends an alert.
- **NFR-A1 (NFR17):** All color-coded report elements include text labels or icons alongside color; contrast ratio ≥ 4.5:1 on all primary text.
- **NFR-A2 (NFR18):** Report layout is legible during a Zoom screen-share at 1080p with the browser window occupying approximately half the screen (effective viewport width ≥ 640px).
- **NFR-A3 (NFR19):** The auto-generated OpenGraph static image displays the key headline number in text legible at mobile thumbnail sizes.

### Additional Requirements

- Selection of Vite (React-TS) + FastAPI Monorepo starter template.
- Local Postgres 16 via Docker Compose with `pgvector` extension (`pgvector/pgvector:pg16`).
- psycopg 3.2.10 and `pgvector-python` for raw SQL database queries (no ORM).
- Versioned SQL migration files stored in `db/migrations/` for schema management.
- FastAPI BackgroundTasks for long-running tasks (ingest/eval).
- Server-Sent Events (SSE) streaming logs to the React UI via `asyncio.Queue` and custom `useSSE` hook.
- Unified JSON casing: snake_case for all DB tables, DB columns, and JSON payloads (no camelCase mapping).
- TanStack Query v5 for server-state management, cache invalidation, and polling.
- react-router-dom v7 for client-side routing across 5 views (/ Dashboard, /ingest, /evals, /ledger, /profile).
- recharts v3.3.0 for all data visualizations (gauges, bar charts, line graphs).
- APScheduler 4 runs in-process inside FastAPI lifespan for scheduled jobs.
- structlog for structured logging (JSON in prod, colored console in dev).
- No authentication layer; Single-user localhost deployment only.
- FastAPI CORS middleware restricted to http://localhost:5173.
- Monorepo structure with frontend/ and backend/ directories.

### UX Design Requirements

- **UX-DR1:** Implement design token system with cosmic HSL values (cosmic black background, semi-transparent grey panel background, electric cyan/purple/magenta/green glow accents, thin slate-cyan borders).
- **UX-DR2:** Set JetBrains Mono or Fira Code as font-family for monospace elements (logs, numbers, telemetry tags) and Outfit for sans-serif UI elements.
- **UX-DR3:** Add tactile bracket-style borders to ConsolePanel containers using CSS pseudo-elements (::before/::after) with target-lock hover animations.
- **UX-DR4:** Implement BrainVisualizer custom component: an SVG mesh of connected skill nodes (RAG, Evals, Agents, pgvector) with CSS-based continuous 3D rotation, scanning sweep effect, and interactive tooltips showing fit status.
- **UX-DR5:** Implement TelemetryChart custom component: an SVG path generator that draws a smooth, glowing ECG-like waveform of learning rates and ingestion volumes.
- **UX-DR6:** Implement TerminalConsole custom component: a monospace panel streaming real-time logs via SSE, with color-coded syntax highlighting (green for INFO, orange for WARN, magenta for ERROR) and manual pause/download logs buttons.
- **UX-DR7:** Implement ActiveOrders custom component: a ledger checklist card displaying weekly commitments (applications, commits, etc.) linked to actual git commit hashes, with visual overdue flags.
- **UX-DR8:** Style buttons according to high-contrast HUD hierarchy (Primary solid cyan with drop shadow glow, Secondary outline cyan, Tertiary monospace underline text, Critical solid warning magenta with flicker hover).
- **UX-DR9:** Implement status notifications as HSL LED status indicators (nominal green, warning magenta, alert/active process pulsing cyan).
- **UX-DR10:** Design drop-zone upload area for resume ingestion with dashed slate brackets and green sweep animation on file hover.
- **UX-DR11:** Apply 250ms debounced auto-saving to all form inputs, displaying visual feedback states ([COMPILING...] during typing, [SAVED] in green, and [SAVE_ERR] in magenta).
- **UX-DR12:** Configure console navigation tabs with brackets and glowing vertical selectors, supporting Alt+1 to Alt+5 keyboard shortcuts.
- **UX-DR13:** Implement CRT horizontal scan line page sweep transition on navigation page swaps.
- **UX-DR14:** Implement fail-safe top banner showing Timeout Detected, offering a one-click button to load offline cached company fingerprints if remote APIs lag.
- **UX-DR15:** Ensure 3-column desktop layout collapses to 2-column on tablet (768px-1023px) and 1-column on mobile (<767px) with bottom tab bar.
- **UX-DR16:** Enforce WCAG 2.1 AA accessibility guidelines (contrast ratios > 7:1, dual-coding text labels alongside colors, prefers-reduced-motion media query wrappers for animations, polite aria-live for logs terminal, and keyboard support).

### FR Coverage Map

- **FR1:** Epic 2 - Greenhouse ingestion
- **FR2:** Epic 2 - Lever ingestion
- **FR3:** Epic 2 - Ashby ingestion
- **FR4:** Epic 2 - Workable, Recruitee, and Personio ingestion
- **FR5:** Epic 2 - Y Combinator WaaS ingestion
- **FR6:** Epic 2 - HN "Who's Hiring" monthly thread parser
- **FR7:** Epic 2 - Single company on-demand ingestion
- **FR8:** Epic 2 - CSV fallback ingestion
- **FR9:** Epic 2 - Run telemetry logging
- **FR10:** Epic 4 - Structured LLM signal extraction
- **FR11:** Epic 4 - Batch processing and deduplication
- **FR12:** Epic 4 - Prompt version tracking
- **FR13:** Epic 5 - Skill frequency ranking by geo
- **FR14:** Epic 5 - Skill co-occurrence clusters calculation
- **FR15:** Epic 5 - Salary-band / tech-stack correlations
- **FR16:** Epic 5 - Geo-segment assignment
- **FR17:** Epic 5 - Experience threshold distribution
- **FR18:** Epic 1 - Candidate profile management
- **FR19:** Epic 5 - Profile fit score computation
- **FR20:** Epic 5 - Skill-gap diff calculation
- **FR21:** Epic 1 - Profile freshness warning
- **FR22:** Epic 6 - Weekly commitment and action logging
- **FR23:** Epic 6 - Accountability ledger UI display
- **FR24:** Epic 6 - Consecutive missed commitment flags
- **FR25:** Epic 4 - Render-blocking kill criterion enforcement
- **FR26:** Epic 4 - Non-blocking warning mode banner
- **FR27:** Epic 2 - Bounded 60-min ingest debug session
- **FR28:** Epic 2 - Delayed-handoff CSV pivot email
- **FR29:** Epic 2 - Inactive-Saturday email reports
- **FR30:** Epic 5 - Public unauthenticated report URL
- **FR31:** Epic 5 - Geo-segmented two-column report layout
- **FR32:** Epic 5 - Experience-threshold distribution strip
- **FR33:** Epic 5 - Fit score delta tracking
- **FR34:** Epic 5 - Automated weekly report deployment
- **FR35:** Epic 5 - Social/mobile shareable report image
- **FR36:** Epic 5 - Archived past-reports index page
- **FR37:** Epic 5 - One-click demo close URL parameter
- **FR38:** Epic 4 - Labeled evaluation dataset management
- **FR39:** Epic 4 - Precision and recall extraction audits
- **FR40:** Epic 4 - Regression detection
- **FR41:** Epic 4 - Committed run-summary artifacts
- **FR42:** Epic 4 - Local Hermes proxy connection health checks
- **FR43:** Epic 5 - On-demand company stack fingerprint
- **FR44:** Epic 2 - Static local HTML fingerprint export
- **FR45:** Epic 5 - Single-screen fingerprint presentation view
- **FR46:** Epic 6 - Publicly accessible Loop B execution log
- **FR47:** Epic 4 - Committed craft-signal documentation artifacts
- **FR48:** Epic 3 - Company discovery signal registry
- **FR49:** Epic 3 - Canonical source resolver
- **FR50:** Epic 3 - Vertex AI Search signal provider
- **FR51:** Epic 3 - Wellfound constrained signal provider
- **FR52:** Epic 3 - Common Crawl ATS index provider
- **FR53:** Epic 3 - YC and VC company discovery providers
- **FR54:** Epic 3 - GitHub and Reddit signal providers
- **FR55:** Epic 3 - Provider yield, freshness, and coverage reporting

## Epic List

### Epic 1: Candidate Profile & Target Geographies (The "Career Identity")
*   **User Outcome**: The developer can define their professional profile (skills, tech stack, experience) and configure target geographies (US/EU remote vs India AI Product). The system provides immediate baseline analysis (visual freshness indicators, baseline fit score targets) and a placeholder workspace to prepare for subsequent analyses.
*   **FRs covered**: FR18, FR21

### Epic 2: Multi-Source Job Ingestion & Live Log Tracking (The "Market Scanner")
*   **User Outcome**: The developer can trigger live job ingestion from public ATS platforms (Greenhouse, Lever, Ashby, Workable, Recruitee, Personio), Y Combinator, and HN threads, observing the execution details in a live terminal window. They can fall back to a manual CSV upload if the parser is offline or if a kill criterion is active.
*   **FRs covered**: FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR27, FR28, FR29, FR44

### Epic 3: Company Discovery & Canonical Source Expansion (The "Company Radar")
*   **User Outcome**: The developer can expand the market scanner beyond manual seeds by discovering companies from HN, Google, Wellfound, Common Crawl, YC, VC portfolios, GitHub, and Reddit, then validating only canonical company or ATS sources before weekly ingestion uses them.
*   **FRs covered**: FR48, FR49, FR50, FR51, FR52, FR53, FR54, FR55

### Epic 4: AI Signal Extraction & Interactive Evals (The "Prognosis Engine")
*   **User Outcome**: The system automatically extracts structured data (skills, seniority, stack, salary, policy, archetype) from job descriptions using an LLM. The developer can verify and audit the extraction quality using a hand-labeled evaluation dataset, tracking precision/recall metrics on a visual graph to prevent accuracy regressions. The system enforces render-blocking kill criteria and warning modes based on extraction precision.
*   **FRs covered**: FR10, FR11, FR12, FR25, FR26, FR38, FR39, FR40, FR41, FR42, FR47

### Epic 5: Geo-Segmented Job Intelligence & Search (The "Career Cockpit")
*   **User Outcome**: The developer can view a unified dashboard showing top-ranked skills, skill clusters, and salary-stack correlations across US/EU remote and India AI product markets side-by-side. They can search the corpus, look up single-company tech stack fingerprints, and diff the market trends directly against their profile to identify skill gaps.
*   **FRs covered**: FR13, FR14, FR15, FR16, FR17, FR19, FR20, FR30, FR31, FR32, FR33, FR34, FR35, FR36, FR37, FR43, FR45

### Epic 6: Weekly Commitment Tracker & Exposure Therapy (The "Accountability Partner")
*   **User Outcome**: The developer can define weekly job application targets and learning goals, logging their progress by linking real Git commits or applications. The dashboard enforces accountability by displaying missed targets prominently in red, helping the developer stay focused on the transition.
*   **FRs covered**: FR22, FR23, FR24, FR46

## Epic 1: Candidate Profile & Target Geographies (The "Career Identity")

The developer can define their professional profile (skills, tech stack, experience) and configure target geographies (US/EU remote vs. India AI Product). The system provides immediate baseline analysis (visual freshness indicators, baseline fit score targets) and a placeholder workspace to prepare for subsequent analyses.

### Story 1.1: Local Monorepo and Database Scaffold

As a developer,
I want to initialize the local Vite (React-TS) + FastAPI Python monorepo structure with Docker Compose Postgres 16 + pgvector,
So that I have a clean development environment and a working database connection.

**Acceptance Criteria:**

**Given** a clean project workspace directory `/home/darko/Code/be-an-ai-engineer`
**When** running the initialization commands
**Then** the directory structure is created with `frontend/` (Vite, React, TypeScript, Vitest) and `backend/` (FastAPI, virtual env, pytest, psycopg 3.2.10)
**And** a root `docker-compose.yml` configures a local Postgres 16 database with the `pgvector` extension running on port `5432`
**And** a root `Makefile` exposes `make dev` which concurrently runs the Vite dev server at `http://localhost:5173` and Uvicorn at `http://localhost:8000`
**And** running `GET http://localhost:8000/api/v1/health` returns a `200 OK` status with database connectivity status and current timestamp

### Story 1.2: Console Shell, Navigation, and CSS HUD Theme Tokens

As a transitioning developer,
I want a responsive, sci-fi HUD theme dashboard layout with scoped CSS modules, JetBrains Mono/Outfit typography, navigation tabs with keyboard shortcuts, and CRT scan-sweep transitions,
So that my cockpit looks and feels like a premium developer tool that encourages daily engagement.

**Acceptance Criteria:**

**Given** a running React frontend application
**When** the app renders
**Then** it applies CSS custom properties for the HUD theme (cosmic black background `--bg-cosmic`, panel overlays, and glowing accent borders in cyan, purple, green, and warning magenta)
**And** it uses Google Fonts **Outfit** for labels and headings, and **JetBrains Mono** for numeric telemetry and monospace log lines
**And** the UI contains a layout with a sidebar navigation showing 5 tabs: `[ Dashboard ]`, `  Ingestion  `, `  Evals  `, `  Ledger  `, `  Profile  `
**And** pressing `Alt+1` to `Alt+5` triggers instant page transitions between the respective routing pages
**And** page transitions trigger a hardware-accelerated horizontal CRT scan line sweep transition across the view
**And** the layout is fully responsive, collapsing the sidebar to a bottom tab dock at viewport widths `< 768px`
**And** all color-coded states include text labels or icons to ensure Level AA contrast ratios and accessibility

### Story 1.3: Candidate Profile Management & Freshness Monitor

As a transitioning developer,
I want to edit my profile (skills, stack, years of experience) in a form that automatically debounces updates and displays a warning banner if it has not been updated in 21 days,
So that my career matching data is version-controlled and accurate.

**Acceptance Criteria:**

**Given** a database migration `V001__init.sql` that creates a `profiles` table containing `skills` (text array), `seniority` (text), `tech_stack` (text array), `years_of_experience` (integer), `geo_preference` (text), and `updated_at` (timestamp)
**When** navigating to the `/profile` view
**Then** the app renders input fields for my profile values, populated by a call to `GET /api/v1/profiles/current`
**And** entering data debounces for `250ms` before triggering a `PUT /api/v1/profiles/current` request, displaying `[COMPILING...]` then `[SAVED]` in mint green upon a successful database save
**And** if the backend API returns a database error or invalid schema, the inputs display a warning border in magenta and show `[SAVE_ERR: <error_message>]` in red
**And** if `updated_at` is greater than or equal to 21 days ago, a yellow dashboard notification banner displays: `▲ [WARNING] Profile is stale (last updated 21+ days ago). Refresh recommended.`

## Epic 2: Multi-Source Job Ingestion & Live Log Tracking (The "Market Scanner")

The developer can trigger live job ingestion from public ATS platforms (Greenhouse, Lever, Ashby, Workable, Recruitee, Personio), Y Combinator, and HN threads, observing the execution details in a live terminal window. They can fall back to a manual CSV upload if the parser is offline or if a kill criterion is active.

### Story 2.1: Multi-Source Ingest Parsers & Database Schema

As a developer,
I want a database migration `V002__add_jobs_and_ingestion.sql` that defines tables `jobs` (raw text, source_slug, url, status) and `ingestion_runs` along with Python parser adapters for Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, YC WaaS, and HN,
So that job postings are fetched and saved to the local database with full telemetry.

**Acceptance Criteria:**

**Given** a database migration file `backend/db/migrations/V002__add_jobs_and_ingestion.sql`
**When** migrations are run
**Then** tables `jobs` and `ingestion_runs` are created with correct columns, keys, and indexes
**And** Python modules in `backend/services/parser.py` implement parser adapters that connect to Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, YC WaaS, and parse the HN monthly thread
**And** each parser writes fetched posting details to the `jobs` table, marking duplicate URLs as skipped
**And** running a test ingestion records a row in `ingestion_runs` with the source counts, timestamps, and execution status (success/failure)

### Story 2.2: FastAPI Background Task Service and SSE Log Stream

As a developer,
I want a FastAPI backend task service that runs ingestion asynchronously, buffering structured logs in a thread-safe `asyncio.Queue` and streaming them to the client via Server-Sent Events (SSE),
So that scraping runs do not block API operations and can be monitored live.

**Acceptance Criteria:**

**Given** a running FastAPI backend
**When** a `POST /api/v1/ingest` request is triggered (optionally specifying a single company slug for on-demand scans)
**Then** the backend starts a `BackgroundTasks` execution with a generated task UUID
**And** all parser logs generated by `structlog` are captured in a thread-safe `asyncio.Queue` mapped to that task UUID
**And** a client connecting to `GET /api/v1/tasks/{task_id}/logs/stream` receives a stream of events (`task.started`, `task.log` with JSON log detail, and `task.completed` or `task.failed`)
**And** if a user-initiated ingest debug session exceeds `60 minutes`, the background task automatically terminates, commits a failure summary, and writes a debug log to disk

### Story 2.3: Live Log Ingest Dashboard with Drag-Drop CSV Fallback

As a transitioning developer,
I want a `/ingest` cockpit view with LED status indicators, a monospace terminal log window, and a drag-and-drop CSV upload area,
So that I can monitor parser runs live and supply fallback job listings when external APIs are offline.

**Acceptance Criteria:**

**Given** an unauthenticated visitor on `/ingest` in the React app
**When** clicking `[INITIATE REMOTE SCAN]`
**Then** the UI triggers the API, connects a `useSSE` hook to the stream endpoint, and displays running percentages and status LEDs (pulsing cyan for scanning, mint green for complete, magenta warning for error)
**And** the `TerminalConsole` component streams syntax-highlighted logs (green for INFO, orange for WARN, magenta for ERROR), supporting scroll locking and manual pause/download logs buttons
**And** if a network timeout of 3 seconds is reached, a top banner slides down displaying `[TIMEOUT DETECTED - PARSER OFFLINE]` with a button offering placeholder error recovery or retry options (to be integrated with offline fingerprints in Epic 5)
**And** dragging a CSV file over the drop-zone displays a green border sweep animation and, on drop, parses and uploads the CSV data via `POST /api/v1/ingest/csv` to update the database

### Story 2.4: Scheduled Ingestion Cron & Diagnostic Alerts

As a developer,
I want an in-process APScheduler cron job that triggers ingestion weekly on Saturday morning IST, writing local run diagnostics and emailing me diagnostic logs,
So that my data aggregation runs automatically and alerts me of issues.

**Acceptance Criteria:**

**Given** a running FastAPI application
**When** starting up the app
**Then** APScheduler initializes inside the lifespan event, registering a cron job to trigger ingestion every Saturday at 8:00 AM IST
**And** when the cron run finishes, it logs the run summary in the database and updates system status
**And** if the ingestion triggers a kill criterion, a delayed-handoff email containing the CSV pivot template and diagnostic error is sent using `Resend` within 5 minutes
**And** if the cockpit is not accessed for 2 consecutive Saturdays, an email report containing the inline weekly report is delivered.

### Story 2.5: Automated ATS Source Discovery and Registry

As a transitioning developer,
I want the app to discover, validate, and persist public ATS job-board sources automatically,
So that weekly ingestion scans the widest practical AI-engineering market corpus without requiring me to manually provide company slugs.

**Acceptance Criteria:**

**Given** public discovery inputs such as HN Who's Hiring comments and a committed seed URL file
**When** source discovery runs
**Then** the backend detects supported ATS patterns for Greenhouse, Lever, Ashby, Workable, Recruitee, and Personio
**And** validates each detected source by calling the existing parser adapter and checking for usable non-empty job text
**And** stores validated active sources in a `job_sources` registry and rejected candidates with rejection reasons
**And** default weekly ingestion uses active registry rows instead of hardcoded company slugs
**And** discovery produces a run report showing found, validated, rejected, errored, and unsupported sources.

## Epic 3: Company Discovery & Canonical Source Expansion (The "Company Radar")

The developer can expand market scanning beyond manual seeds by discovering companies and direct ATS sources from HN, Vertex AI Search, constrained Wellfound signals, Common Crawl, YC, VC portfolios, GitHub, and Reddit. The system resolves company signals to canonical careers or ATS sources, validates live relevant jobs, and reports provider yield before sources become active in weekly ingestion.

### Story 3.1: Company Signals and Canonical Source Resolver

As a transitioning developer,
I want discovered company signals to be persisted and resolved to canonical careers or ATS sources,
So that later provider integrations can identify which companies are worth checking without directly trusting third-party job boards.

**Acceptance Criteria:**

**Given** a new migration after `V005__add_job_source_registry.sql`
**When** migrations run
**Then** tables for company discovery signals and company discovery runs are created with provider metadata, evidence URLs, confidence/category hints, status, rejection reason, and timestamps
**And** the backend exposes a company signal model/provider contract that can emit company domains, careers URLs, direct ATS URLs, and evidence metadata
**And** a canonical resolver checks only bounded company paths (`/careers`, `/jobs`, `/join-us`, `/work-with-us`, `/company/careers`), declared sitemaps, supported ATS URLs, and `JobPosting` JSON-LD
**And** the resolver never executes JavaScript, uses browser automation, follows unbounded links, or activates a source without existing ATS/JSON-LD validation
**And** rejected or unresolved companies persist visible rejection reasons for diagnostics.

### Story 3.2: Vertex AI Search and Wellfound Direct Hiring Signal Providers

As a transitioning developer,
I want Vertex AI Search and constrained Wellfound signals to identify companies that may be hiring,
So that the market scanner can discover fresh startup and AI/backend opportunities while still validating jobs from canonical company sources.

**Acceptance Criteria:**

**Given** optional Vertex AI Search credentials are configured
**When** source discovery runs
**Then** `VertexAISearchSignalProvider` uses only the official Discovery Engine `searchLite` API with durable local daily/monthly caps
**And** Vertex AI Search results store query text, result URL, title, snippet, rank, provider metadata, and evidence URL as signals only
**And** no search result page, Google Jobs page, or unofficial SERP endpoint is scraped or treated as trusted job data
**And** `WellfoundSignalProvider` is disabled by default unless explicitly enabled
**And** Wellfound extraction supports manual/imported company URLs first and, if automated public extraction is enabled, enforces no login, no browser automation, no pagination crawling, no disallowed `/_jobs/` crawling, max 5 pages/run by default, and 5+ second request delay
**And** Wellfound output stores only company name, domain/homepage if visible, evidence URL, and confidence before canonical validation.

### Story 3.3: Common Crawl, YC, and VC Scale Discovery Providers

As a transitioning developer,
I want scale-oriented discovery providers to find direct ATS boards and relevant startup/company domains,
So that the scanner can grow beyond a small set of obvious companies without relying on manual seeds.

**Acceptance Criteria:**

**Given** Common Crawl indexes are reachable
**When** the Common Crawl provider runs
**Then** it queries capped URL patterns for supported ATS hosts including Greenhouse, Lever, Ashby, Workable, Recruitee, and Personio
**And** it normalizes discovered ATS URLs into source candidates, deduplicates by `(ats, slug)`, and validates through existing parser adapters before activation
**And** YC provider extracts company name, website, YC evidence URL, tags, and category hints from selected public YC categories such as AI, developer tools, infrastructure, data engineering, databases, open source, and search
**And** VC portfolio providers extract company names and homepage URLs from configured public portfolio pages such as a16z, Sequoia, Index, Accel, Greylock, Lightspeed, and Conviction
**And** YC and VC outputs are treated as company signals and must pass canonical source resolution before any source is activated.

### Story 3.4: Long-Tail Signals and Provider Yield Reporting

As a transitioning developer,
I want GitHub, Reddit, provider yield metrics, and freshness reporting to improve coverage over time,
So that I can see which discovery channels produce useful validated sources and which companies need rechecking or retirement.

**Acceptance Criteria:**

**Given** GitHub API access is available
**When** GitHub organization signal discovery runs
**Then** it searches relevant AI/backend/devtools topics, extracts org/repo website and README links, and treats findings as relevance signals rather than hiring proof
**And** Reddit signal discovery uses Reddit API/search for configured hiring communities and extracts company names, domains, careers URLs, and evidence URLs with lower default confidence
**And** discovery reports compare provider yield, source freshness, active source growth, rejected reasons, and coverage gaps across all discovery providers
**And** diagnostics identify stale, inactive, repeatedly rejected, and high-yield companies/sources
**And** weekly ingestion still reads only active validated rows from `job_sources`.

## Epic 4: AI Signal Extraction & Interactive Evals (The "Prognosis Engine")

The system automatically extracts structured data (skills, seniority, stack, salary, policy, archetype) from job descriptions using an LLM. The developer can verify and audit the extraction quality using a hand-labeled evaluation dataset, tracking precision/recall metrics on a visual graph to prevent accuracy regressions. The system enforces render-blocking kill criteria and warning modes based on extraction precision.

### Story 4.1: LLM Structured Extraction and Proxy Verification

As a developer,
I want a Pydantic-validated extraction client that sends job text to the local Hermes proxy and returns structured JSON, batching calls, versioning prompts, and verifying proxy health before processing,
So that extraction is structured, audit-logged, and fails safely if the proxy is offline.

**Acceptance Criteria:**

**Given** un-extracted rows in the `jobs` database table and configured environment variables (`HERMES_HOST`, `HERMES_PORT`)
**When** running the extraction pipeline script
**Then** raw job texts are passed in batches to the local Hermes proxy endpoint using a structured JSON schema prompt
**And** the output matches the Pydantic schema defined in `backend/llm/schemas.py` containing `skills`, `seniority`, `tech_stack`, `salary_band`, `remote_policy`, and `role_archetype`
**And** database records are updated with the extraction results and prompt version ID
**And** if the local Hermes proxy connection is unresponsive, the pipeline aborts the batch run, logs the connection error, and raises a custom `HermesProxyConnectionError`


### Story 4.2: Labeled Eval Set Management & Accuracy Audits

As a developer,
I want a database migration after the Story 4.1 extraction-field migration, expected as `V008__add_evals.sql`, that defines tables `evaluation_runs` and `eval_postings`, along with backend logic to compute per-field precision, recall, and regression detection against a 20-sample hand-labeled ground-truth evaluation set,
So that extraction accuracy is measured mathematically and regression is flagged automatically.

**Acceptance Criteria:**

**Given** a database migration `backend/db/migrations/V008__add_evals.sql` unless `V008` is already taken
**When** migrations are run
**Then** tables `evaluation_runs` and `eval_postings` are created
**And** `backend/services/evaluator.py` can load a 20-sample hand-labeled ground-truth dataset (10 training / 10 held-out) with known classifications
**And** triggering an evaluation calculates per-field precision, recall, and overall F1 score for the 6 extracted parameters
**And** if the overall accuracy drops by more than 3 percentage points compared to the last run, a regression flag `accuracy_regression: true` is saved
**And** the run summary is committed as `run-summary-YYYY-WW.json` to the repo history

### Story 4.3: Interactive Evals Dashboard and Regression Charts

As a transitioning developer,
I want an interactive `/evals` page showing precision/recall line charts, run history, and detailed parameter controls to run tests and audit LLM extraction quality live,
So that I can review parser accuracy transparently.

**Acceptance Criteria:**

**Given** a running React frontend
**When** navigating to the `/evals` view
**Then** the UI fetches evaluation run histories using TanStack Query from `GET /api/v1/evals`
**And** it renders a line chart using `recharts` showing precision, recall, and F1 scores over time
**And** clicking `[RUN EVALUATION]` triggers the async background execution, showing a concentric double-ring spinner and printing live progress
**And** a detailed tabular audit view displays the 20-sample extraction diffs side-by-side (expected vs. actual fields) with mismatch values highlighted in orange

### Story 4.4: Kill-Criterion Enforcement and Warning Banner

As a developer,
I want a render-blocking middleware or pipeline validation check that blocks report generation if the corpus size is < 100 or extraction accuracy is < 70%, displaying warning notices if only one threshold is breached,
So that faulty ingestion runs do not produce corrupt market metrics.

**Acceptance Criteria:**

**Given** a completed pipeline execution run
**When** the pipeline checks the run metrics
**Then** if ingestion fails, the corpus size is `0`, or both the database corpus size is `< 100` postings and the F1 extraction accuracy from the evaluation run is `< 70%`, the system locks the weekly report state and writes `kill-criterion-fired-YYYY-WW.json` to disk
**And** attempting to view the dashboard renders a full-page alert banner: `▲ [KILL CRITERION TRIGGERED] Ingestion corpus or accuracy below minimum quality thresholds. Dashboard locked.`
**And** if only one threshold is breached, the dashboard is not blocked but renders a yellow top banner: `▲ [WARNING] Danger Zone: Ingestion quality thresholds near limit. 7 days to recover before console lock.`

## Epic 5: Geo-Segmented Job Intelligence & Search (The "Career Cockpit")

The developer can view a unified dashboard showing top-ranked skills, skill clusters, and salary-stack correlations across US/EU remote and India AI product markets side-by-side. They can search the corpus, look up single-company tech stack fingerprints, and diff the market trends directly against their profile to identify skill gaps.

### Story 5.1: Analytical Query Processor & Geo-Segmentation

As a developer,
I want backend SQL analytical routines that compute top-ranked skills, skill clusters (co-occurrence correlations), and experience/salary distribution trends grouped by geo-preference,
So that market data is aggregated into structured analytical indices.

**Acceptance Criteria:**

**Given** extracted job posting parameters in the Postgres database
**When** running the weekly analytical aggregation query in `backend/routers/jobs.py`
**Then** postings are grouped into two geo segments: `US/EU remote` and `India-based AI product` based on location and remote policy fields
**And** top-30 skills are ranked by frequency within each segment
**And** skill co-occurrence groups are computed (e.g., probability of `pgvector` appearing with `RAG`)
**And** salary-band and tech-stack correlations are calculated for listings with disclosed salary ranges
**And** the experience threshold distribution (% of roles requiring 0/3+/5+/senior-only) is compiled
**And** the aggregation refuses to publish market metrics when the health state is `locked`, annotates results when the health state is `warning`, and records corpus size, extracted-row coverage, and latest eval accuracy in the analytics response
**And** postings with `extraction_status != "extracted"` are excluded from rankings and counted as coverage gaps
**And** empty list fields, categorical `unknown` values, and `salary_band.kind = "not_disclosed"` are excluded from ranking/correlation denominators while remaining visible in coverage and disclosure diagnostics
**And** postings that cannot be assigned to `US/EU remote` or `India-based AI product` are placed in an `unclassified` diagnostic bucket rather than being forced into either segment

### Story 5.2: Volumetric Brain Visualizer & ECG Telemetry Chart

As a transitioning developer,
I want a central dashboard panel displaying an interactive, rotating 3D SVG brain mesh that highlights skill anomalies in magenta and turns green when they are cleared, accompanied by an SVG-drawn ECG waveform showing active ingestion and learning telemetry,
So that I have a highly engaging visual centerpiece representing my pathway diagnostic status.

**Acceptance Criteria:**

**Given** a running React app rendering the `/` dashboard
**When** the page loads
**Then** the central panel renders the `BrainVisualizer` displaying skill nodes connected by low-opacity vector lines, rotating continuously via CSS 3D transforms
**And** node colors display green for proven skills, gray for nominal, and pulsing warning magenta for identified profile anomalies (skill gaps)
**And** hovering over a node expands its lines and opens a diagnostic tooltip showing the skill name, cosine similarity fit score, and a CTA to accept its project directive
**And** the `TelemetryChart` renders a smooth Bezier SVG path that spikes or flatlines representing commit and parsing telemetry over a panning grid backdrop
**And** on mobile views (`< 768px`), the 3D rotation deactivates, displaying a static SVG to conserve battery

### Story 5.3: Geo-Segmented Market Analysis & Skill-Gap Diff

As a transitioning developer,
I want a dual-column market dashboard displaying top-10 US/EU remote skills side-by-side with India AI product skills, calculating a cosine-similarity profile fit score delta, and outputting an actionable skill-gap diff table,
So that I can scan my market position and identify specific missing skills.

**Acceptance Criteria:**

**Given** analytical metrics and candidate profile data
**When** viewing the main dashboard
**Then** the UI displays two side-by-side columns: "US/EU Remote" and "India AI Product" showing top-10 skills
**And** the top of the page displays the experience distribution strip and your profile fit score delta compared to the previous week (e.g., `+12%`)
**And** a detailed tabular diff highlights which top-ranked market skills are missing from your profile, prioritizing them in red
**And** the dashboard header includes a profile freshness nudge if the profile has not been updated in 21+ days

### Story 5.4: Company Stack Fingerprint & Interview Screen-Share View

As a transitioning developer,
I want a single-screen company stack fingerprint page (top technology list, role archetypes, and an AI-generated Stack observation) that renders in < 2s for live interview screen-shares, including a one-click close parameter to exit clean,
So that I can share my screen and present real-time company insights during live interviews.

**Acceptance Criteria:**

**Given** a URL request `/company/{company_slug}` (optionally with a query parameter `?demo=true`)
**When** the company page loads
**Then** the app renders a high-density, single-screen stack fingerprint containing: company name, 5-bullet role archetype summary, top-10 extracted technologies, and a one-sentence LLM-generated observation
**And** the page loads in `< 2s` by utilizing cached database query projections rather than triggering real-time extraction
**And** if `demo=true` is present in the URL, a prominent `[CLOSE DEMO]` button is displayed in warning magenta, which returns the browser to the default neutral dashboard state
**And** the system pre-computes and writes static local HTML copies of the company stack fingerprints to `frontend/public/cached-fingerprints/{company_slug}.html` for offline fallback during live screen-share runs
**And** the `/ingest` page timeout banner's offline fallback button is updated to load these cached company stack fingerprints when a timeout occurs

### Story 5.5: Archive Index & Social Sharing

As a developer,
I want a weekly report deployment workflow that publishes the report to a public Vercel URL on cron, logs history to a public `/archive` index, and generates shareable social images representing key weekly stats,
So that my career search results are preserved, public, and shareable.

**Acceptance Criteria:**

**Given** a completed weekly pipeline run
**When** the cron deployment fires
**Then** the system commits the static report files and publishes the site to the public, unauthenticated Vercel URL
**And** navigating to `/archive` displays a list of all past weekly reports, allowing visitors to click any week and view its historic rankings
**And** the system auto-generates a high-contrast OpenGraph static image (375px equivalent mobile text legibility) representing the week's top skills and profile fit score for social preview embedding.

## Epic 6: Weekly Commitment Tracker & Exposure Therapy (The "Accountability Partner")

The developer can define weekly job application targets and learning goals, logging their progress by linking real Git commits or applications. The dashboard enforces accountability by displaying missed targets prominently in red, helping the developer stay focused on the transition.

### Story 6.1: Database Ledger Schema and REST Endpoints

As a developer,
I want a database migration `V011__add_ledger.sql` that defines tables `commitments` and `actions` along with backend endpoints to CRUD commitments,
So that my weekly career goals and progress records are persisted.

**Acceptance Criteria:**

**Given** a database migration file `backend/db/migrations/V011__add_ledger.sql`
**When** migrations are run
**Then** tables `commitments` and `actions` are created
**And** `backend/routers/ledger.py` exposes REST endpoints `GET /api/v1/ledger`, `POST /api/v1/ledger/commitments`, and `PUT /api/v1/ledger/commitments/{id}` (to link a commit or verify an action)
**And** Pydantic schemas validate that commitments contain category (e.g. `applications`, `build`, `posts`), target count, target date, and status
**And** the schema follows the ledger evidence model in `docs/ledger-evidence-model.md`, including public/private field boundaries and evidence-link validation rules
**And** API, React, static report, and public Loop B rendering tests cover HTML-like or malicious accountability text according to `docs/epic-6-quality-checklist.md`

### Story 6.2: Interactive Accountability Ledger & Git Linker

As a transitioning developer,
I want a `/ledger` view that displays weekly goals formatted as "Active Directives" prescriptions, featuring a commit linker panel to link Git commits or applications,
So that I can verify my progress with hard evidence.

**Acceptance Criteria:**

**Given** a running React frontend
**When** navigating to the `/ledger` view
**Then** the UI renders the `ActiveOrders` component showing weekly targets as clinical prescriptions
**And** unassigned goals display in warning crimson with a pulsing alert dot
**And** clicking `[LINK COMMIT]` opens a small toggle panel to paste a Git commit hash or enter application details
**And** submitting a valid hash triggers a loading animation that updates the row to a mint green verified state with status `✓ [PATHWAY VERIFIED]`
**And** ledger-specific UI and state are isolated in dedicated components/hooks rather than expanding unrelated analytics, brain visualizer, or market-diff logic in `DashboardView.tsx`

### Story 6.3: Visual Alerts for Overdue Commitments

As a transitioning developer,
I want the dashboard and ledger views to highlight commitments missed for 2 or more consecutive weeks in warning crimson, pinning them to the top of the dashboard,
So that I cannot avoid or hide from my missed commitments.

**Acceptance Criteria:**

**Given** weekly commitments in the database
**When** the dashboard analytics are processed
**Then** the system checks for goals where status is uncompleted and target date is older than 7 days
**And** if a commitment has been missed for 2 or more consecutive weeks, the ledger row is styled in crimson and pinned to the top of the dashboard
**And** a soft warning nudge displays a button: `▲ [ACTIVATE 15-MIN FALLBACK PIVOT]` to quickly resolve the gap
**And** dashboard integration reuses the component-scoped ledger surface from Story 6.2 and preserves existing live-region, reduced-motion, and keyboard-navigation behavior

### Story 6.4: Public Loop B Progress Logs

As a developer,
I want a public URL `/loop-b` (and `loop-b-log.md` committed to the repo) that logs weekly Loop B execution metrics (applications filed, interviews, voice notes, LinkedIn posts),
So that hiring managers can verify my consistent job-search activity in a 90-second scan.

**Acceptance Criteria:**

**Given** a public visitor to the live website
**When** navigating to `/loop-b`
**Then** the UI renders a publicly accessible log of all Loop B weekly metrics (applications, interviews, voice notes, LinkedIn posts) loaded from `loop-b-log.md` or a database
**And** a link is provided to open `loop-b-log.md` directly in the GitHub repository
**And** each weekly row includes links to public commits or LinkedIn posts, proving consistent build-in-public progression.
**And** public Loop B output escapes user-entered text, validates evidence URLs before linking them, renders explicit empty states, and remains usable without backend API access
