# Story 5.1: Analytical Query Processor & Geo-Segmentation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want backend SQL analytical routines that compute top-ranked skills, skill clusters (co-occurrence correlations), and experience/salary distribution trends grouped by geo-preference,
so that market data is aggregated into structured analytical indices.

## Acceptance Criteria

1. **Geo-Segmentation Classification Logic**:
   - Given job postings with extracted parameters in the Postgres database.
   - When the analytical processor groups jobs into geo segments:
     - **India-based AI product**: Assign to this segment if the job's `location` (case-insensitive) contains any of the following: `india`, `bengaluru`, `bangalore`, `mumbai`, `pune`, `gurgaon`, `gurugram`, `noida`, `hyderabad`, `chennai`, `delhi`, `bhopal`, OR the `company` name (case-insensitive) matches a known Indian AI company/captive: `Sarvam AI`, `Krutrim`, `Yellow.ai`, `Haptik`, `Qure.ai`, `Gnani.ai`, `ideaForge`, `Peak`, `Observe.ai`, `Fractal`, `Microsoft India AI`, `Google India`, `Amazon India`, `Nvidia India`, `Adobe India`.
     - **US/EU remote**: Assign to this segment if it is not in the India segment, AND the job's extracted `remote_policy` is exactly `'remote'`.
     - **unclassified**: Assign to this segment if the job is not classified as India-based AI product, AND its `remote_policy` is not `'remote'` (e.g. it is onsite/hybrid in SF, London, etc., which cannot be worked remote from India).
   - Only postings with `extraction_status = 'extracted'` are ranked/processed; pending/failed/retryable jobs are counted under coverage diagnostics but excluded from analytical scores.

2. **Analytical Metrics Calculation Rules**:
   - **Top Skills Ranking**: Rank the top-30 skills by frequency within each segment (US/EU remote and India AI product). Exclude empty lists or case-insensitive `'unknown'` skill values from denominators and rankings.
   - **Skill Co-occurrence Probability**: Compute co-occurrences for the top-30 skills within each segment. For any pair of skills $(A, B)$, calculate the co-occurrence count (number of jobs in the segment containing both $A$ and $B$) and the conditional probability $P(B|A) = \text{co\_occurrences}(A, B) / \text{count}(A)$.
   - **Salary-Band & Tech-Stack Correlations**: For postings with disclosed salary ranges (`salary_band.kind = 'disclosed'`), group by unique skill (or tech-stack item) and calculate the average `min_amount` and `max_amount` grouped by currency and period (e.g., USD/year vs INR/year). Exclude postings with `"not_disclosed"` kinds from calculation denominators.
   - **Experience Threshold Distribution**: Compile the percentage distribution of roles in each segment according to `seniority` mapped as follows:
     - `no stated minimum`: postings where `seniority` is `entry` or `unknown` (or null).
     - `3+ years`: postings where `seniority` is `mid`.
     - `5+ years`: postings where `seniority` is `senior`.
     - `senior-only`: postings where `seniority` is `staff_plus`.
     - Sum of the proportions in each segment must equal 1.0 (or 100%).

3. **Candidate Profile Fit and Skill-Gap Diff Calculations**:
   - Given the current candidate profile (fetched from database `/profiles/current` data with `id = 1`).
   - When calculating fit metrics:
     - **Profile Fit Score**: Calculate the case-insensitive intersection between candidate's profile skills and the segment's top-30 ranked skills. The fit score is `len(intersection) / 30.0`.
     - **Profile Fit Score Delta**: Query the `weekly_reports` table for the most recent run date prior to today. Calculate the candidate's profile fit score against that historical week's top-30 skills. Return the difference `current_fit_score - prior_fit_score` (defaulting to `0.0` if no prior week exists).
     - **Historical Data Format**: The `geo_us_eu` and `geo_india` columns in `weekly_reports` store JSONB payloads structured as follows:
       ```json
       {
         "job_count": 120,
         "top_skills": [
           {"skill": "Python", "count": 80, "frequency": 0.67}
         ],
         "experience_distribution": {
           "no_minimum": 0.18,
           "three_plus": 0.44,
           "five_plus": 0.29,
           "senior_only": 0.09
         }
       }
       ```
     - **Skill-Gap Diff**: Compute the set difference: `segment_top_30_skills - candidate_profile_skills` (case-insensitive). Return this list of missing skills, ordered by market frequency, to guide the user on gap resolution.

4. **API Endpoint & Operational Guards**:
   - Given a running FastAPI application.
   - When a client calls `GET /api/v1/jobs/analytics`:
     - It checks the system's operational health state (reusing the logic from `health.py`):
       - If `system_state == "locked"` (corpus size is 0, latest ingestion status is `"failure"`, or both corpus size < 100 and extraction accuracy < 70%), the router aborts the request and returns a `403 Forbidden` standard error: `{"error": true, "code": "METRICS_LOCKED", "detail": "Ingestion corpus or accuracy below minimum quality thresholds. Dashboard locked."}`.
       - If `system_state == "warning"`, it returns the metrics but annotates the metadata payload with `system_state: "warning"`.
       - If `system_state == "nominal"`, it returns the metrics with `system_state: "nominal"`.
     - In nominal/warning states, the response contains `snake_case` keys in the Standard Envelope:
       ```json
       {
         "data": {
           "corpus_size": 247,
           "extracted_coverage": 0.95,
           "latest_eval_accuracy": 0.85,
           "system_state": "nominal",
           "geo_segments": {
             "us_eu_remote": {
               "job_count": 120,
               "top_skills": [
                 {"skill": "Python", "count": 80, "frequency": 0.67}
               ],
               "co_occurrences": [
                 {"skill_a": "pgvector", "skill_b": "RAG", "co_occur_count": 15, "probability": 0.75}
               ],
               "salary_correlations": [
                 {"skill_or_tech": "PyTorch", "avg_min_salary": 140000.0, "avg_max_salary": 180000.0, "currency": "USD", "period": "year", "disclosed_count": 10}
               ],
               "experience_distribution": {
                 "no_minimum": 0.18,
                 "three_plus": 0.44,
                 "five_plus": 0.29,
                 "senior_only": 0.09
               },
               "profile_fit_score": 0.65,
               "profile_fit_delta": 0.12,
               "skill_gap": [
                 {"skill": "pgvector", "market_frequency": 0.35, "in_profile": false}
               ]
             },
             "india_ai_product": {
               "job_count": 95,
               "top_skills": [],
               "co_occurrences": [],
               "salary_correlations": [],
               "experience_distribution": {},
               "profile_fit_score": 0.0,
               "profile_fit_delta": 0.0,
               "skill_gap": []
             },
             "unclassified": {
               "job_count": 32
             }
           }
         }
       }
       ```

5. **Analytical Query Integration Tests**:
   - Given backend router tests in `backend/tests/routers/test_jobs.py`.
   - When pytest runs, it asserts:
     - Proper geo-segment assignment (India-based, US/EU remote, and unclassified).
     - Accurate top skill rankings and co-occurrence probabilities.
     - Accurate experience threshold distributions and profile fit/gap calculations.
     - Proper 403 response behavior under a simulated `locked` state.

## Tasks / Subtasks

- [x] **Task 1: Implement Analytics Endpoint and Health Validation (AC: 4)**
  - [x] Create `backend/routers/jobs.py` and register the `GET /api/v1/jobs/analytics` endpoint.
  - [x] Implement system state retrieval matching `health_check` checks.
  - [x] Enforce the 403 Forbidden `METRICS_LOCKED` block if state is `locked`.
  - [x] Include standard system state metadata in the response.
- [x] **Task 2: Build Geo-Segmentation & Aggregate Queries (AC: 1, 2)**
  - [x] Write SQL routines to select all jobs where `extraction_status = 'extracted'`.
  - [x] Classify jobs dynamically into `US/EU remote`, `India-based AI product`, and `unclassified` based on location/company list/remote_policy rules.
  - [x] Rank top-30 skills and calculate their frequency in each segment.
  - [x] Calculate experience threshold distributions (mapping seniority values to 0/3+/5+/senior-only).
- [x] **Task 3: Compute Co-occurrence, Salary, and Profile Metrics (AC: 2, 3)**
  - [x] Calculate skill co-occurrence pairs and conditional probabilities $P(B|A)$ among the top-30 skills.
  - [x] Calculate salary-band correlations (average min/max salary per skill/tech-stack item) filtered by currency and period.
  - [x] Load the current profile and calculate the case-insensitive profile fit score, prior-week delta, and missing skill-gap diff.
- [x] **Task 4: Register Router and Add Verification Suite (AC: 5)**
  - [x] Import and include the jobs router in `backend/main.py` under `/api/v1`.
  - [x] Implement `backend/tests/routers/test_jobs.py` verifying nominal state calculations and locked state error scenarios.
  - [x] Run pytest to verify all new tests pass successfully.

### Review Findings

- [x] [Review][Patch] Profile fit delta reports current score when no prior week exists [backend/routers/jobs.py:330]
- [x] [Review][Patch] Analytics bypass specified SQL/JSONB-safe routines by loading all extracted jobs into Python [backend/routers/jobs.py:112]
- [x] [Review][Patch] Case variants inside one posting can inflate skill counts and salary correlations [backend/routers/jobs.py:168]
- [x] [Review][Patch] Unhandled router failures re-raise outside the standard error envelope [backend/routers/jobs.py:387]
- [x] [Review][Patch] Malformed historical `top_skills` entries can crash profile delta calculation [backend/routers/jobs.py:340]

## Dev Notes

- **Existing Code to Reuse**:
  - `backend/db/connection.py` for `get_db` dependency injection.
  - `backend/routers/health.py` for health/system state calculation logic.
  - `backend/routers/profiles.py` for current profile fetching logic.
- **Database Schema**:
  - `jobs` columns: `location`, `company`, `skills` (JSONB list), `tech_stack` (JSONB list), `seniority` (text), `remote_policy` (text), `salary_band` (JSONB), `extraction_status` (text).
  - `profiles` columns: `skills` (text array).
  - `weekly_reports` columns: `run_date` (date), `geo_us_eu` (jsonb), `geo_india` (jsonb).
- **PostgreSQL JSONB Safety**:
  - When extracting skills/tech stack array elements, use `jsonb_array_elements_text()` safely by checking `jsonb_typeof(skills) = 'array'` and filtering out null or empty records, as well as categorical `'unknown'` (case-insensitive) strings before running counts/frequency groupings.
- **Constraints**:
  - All responses must conform to the unified envelope: `{"data": ...}` for success, `{"error": true, "code": "...", "detail": "..."}` for errors.
  - Ensure all database queries check out connections cleanly from the pool.

### Project Structure Notes

- New endpoint must live in `backend/routers/jobs.py` and be imported in `backend/main.py`.
- New tests must live in `backend/tests/routers/test_jobs.py`.

### References

- [Epics: Story 5.1](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#L489-L508)
- [PRD: Missing-value policy & Geo-Segment rules](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#L483-L490)
- [Database Schema - Jobs Table](file:///home/darko/Code/be-an-ai-engineer/backend/db/migrations/V007__add_job_extraction_fields.sql#L2-L14)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

- Mocking connection cursors with dict_row factory support by handling both tuple/list and dictionary-like row structures for ultimate test/runtime compatibility.

### Completion Notes List

- Created `backend/routers/jobs.py` registering `GET /api/v1/jobs/analytics` endpoint.
- Implemented robust dynamic classification matching the geo-segment rules (India-based AI captive/company, US/EU remote, and unclassified).
- Added calculations for top-30 skills, skill co-occurrence probability, experience distributions, salary correlations, and candidate profile fit metrics (along with delta and gap analyses).
- Enforced the 403 Forbidden `METRICS_LOCKED` block if the system's operational health state is locked.
- Integrated the router under `/api/v1` in `backend/main.py`.
- Wrote and passed comprehensive unit tests in `backend/tests/routers/test_jobs.py` covering nominal, warning, and locked states.

### File List

- [backend/routers/jobs.py](file:///home/darko/Code/be-an-ai-engineer/backend/routers/jobs.py)
- [backend/main.py](file:///home/darko/Code/be-an-ai-engineer/backend/main.py)
- [backend/tests/routers/test_jobs.py](file:///home/darko/Code/be-an-ai-engineer/backend/tests/routers/test_jobs.py)
