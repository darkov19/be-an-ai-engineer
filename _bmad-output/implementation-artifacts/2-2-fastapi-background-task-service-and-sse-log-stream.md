# Story 2.2: FastAPI Background Task Service and SSE Log Stream

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a FastAPI backend task service that runs ingestion asynchronously, buffering structured logs in a thread-safe `asyncio.Queue` and streaming them to the client via Server-Sent Events (SSE),
so that scraping runs do not block API operations and can be monitored live.

## Acceptance Criteria

1. **Background Tasks Ingestion (`backend/routers/ingest.py`)**:
   - Expose endpoint `POST /api/v1/ingest` which accepts an optional JSON body: `{"company_slug": "..."}`.
   - The handler must generate a task UUID (`task_id`).
   - It must register a new task with a thread-safe `asyncio.Queue` mapped to that `task_id` in a global `TaskManager` (or equivalent structure).
   - It must initiate a FastAPI `BackgroundTasks` execution running the parser's ingestion logic.
   - It must return a `202 Accepted` status immediately with `{"task_id": "..."}`.

2. **Real-Time Log Interception & Queueing**:
   - Create `backend/utils/tasks.py` which contains `task_manager` (a singleton or utility class) and a ContextVar `active_task_id`.
   - Implement a custom processor/middleware or logging handler for `structlog` (configured in `backend/utils/logging.py`) that captures logs during the background task run.
   - When any log is produced via `structlog.get_logger()`, the processor checks if `active_task_id` is set.
   - If set, it formats the log detail as a JSON-serializable dictionary and queues it in the task's `asyncio.Queue`.
   - The queue must be thread-safe/async-safe and prevent memory leaks (meaning tasks and queues are cleared from memory once the task is finished and logs are consumed, or after a reasonable timeout).

3. **SSE Streaming Endpoint (`backend/routers/ingest.py`)**:
   - Expose endpoint `GET /api/v1/tasks/{task_id}/logs/stream` returning a `text/event-stream` response.
   - The response must stream messages using standard SSE syntax (`event: <event_name>`, `data: <json_data>`).
   - The stream must start by emitting event `task.started` with `{"task_id": "..."}`.
   - It must yield event `task.log` for each log captured in the queue, where data is the JSON-serializable log dictionary.
   - Upon successful completion, it must yield `task.completed` with the ingestion summary (source counts, status, execution time) and close the connection.
   - Upon task failure (unhandled exception or error), it must yield `task.failed` with the error details and close the connection.

4. **Debug Session Timeout (60-minute limit)**:
   - The background task execution must be bounded to a maximum of 60 minutes (3600 seconds) using `asyncio.wait_for`.
   - If the timeout is reached, the execution must raise a timeout exception, write a failure summary to `ingestion_runs` table, dump all accumulated task logs to a file named `debug-attempt-YYYY-MM-DD.log` (with current date) at the root of the workspace directory, and raise `task.failed` event to any connected SSE clients.

5. **No New Dependencies / Standard SSE Implementation**:
   - Implement the SSE stream generator using FastAPI/Starlette's built-in `StreamingResponse` rather than pulling in external libraries like `sse-starlette` to avoid dependency bloat.

6. **Robust Integration and Registration**:
   - Register the new `ingest` router in `backend/main.py`.
   - Clean up state and close queues on task completion/failure to prevent resource/memory leaks.

## Tasks / Subtasks

- [x] Task 1: Implement Task Manager and Logger Redirection (AC: 2)
  - [x] Create `backend/utils/tasks.py` defining `TaskManager` and `active_task_id`.
  - [x] Implement `task_log_processor` in `backend/utils/logging.py` to forward active task logs.
  - [x] Add `task_log_processor` to the `structlog` configuration processors list before `JSONRenderer`.
- [x] Task 2: Build Ingest Router and Native SSE Streaming (AC: 1, 3, 5)
  - [x] Create `backend/routers/ingest.py` defining the `IngestRequest` model, `POST /api/v1/ingest`, and `GET /api/v1/tasks/{task_id}/logs/stream`.
  - [x] Implement async generator yielding event streams in SSE format using `StreamingResponse`.
  - [x] Ensure cleanup of task queues after streaming finishes to prevent memory leaks.
- [x] Task 3: Build Background Task Wrapper and Timeout Handling (AC: 1, 4)
  - [x] Implement `run_ingestion_task` wrapper in `backend/routers/ingest.py` or a service module.
  - [x] Wrap `run_full_ingestion` call in `asyncio.wait_for` with a 3600-second timeout.
  - [x] Handle completion and exceptions, saving correct status/errors to `ingestion_runs` table.
  - [x] Implement dump to `debug-attempt-YYYY-MM-DD.log` upon timeout.
- [x] Task 4: Integration and Verification (AC: 6)
  - [x] Include `ingest_router` in `backend/main.py`.
  - [x] Write router unit/integration tests in `backend/tests/routers/test_ingest.py`.
  - [x] Verify background execution concurrency, SSE logs streaming, log queue interception, and timeout handling.

### Review Findings

- [x] [Review][Patch] Premature Queue Cleanup on Client Disconnect [backend/routers/ingest.py:184]
- [x] [Review][Patch] Unsafe json.dumps on Log Serialization [backend/routers/ingest.py:177]
- [x] [Review][Patch] Missing validation on company_slug input [backend/routers/ingest.py:107]
- [x] [Review][Patch] Inline import of copy inside log processor [backend/utils/logging.py:13]

## Dev Notes

- **Existing Database Utilities**: Use the `psycopg` connection pool from `app.state.pool` (passed down to the background task) to perform queries.
- **Dependency Bloat Prevention**: Do NOT install `sse-starlette`. Implement the SSE endpoint natively by returning `StreamingResponse` with `media_type="text/event-stream"` and yielding properly formatted string buffers.
- **Log Processor Precedence**: The custom structlog processor must be placed before `JSONRenderer()` in `structlog.configure`'s processors list to ensure it receives Python dictionaries rather than string-serialized JSON.
- **Resource Leak Prevention**: In both successful and failed execution flows, `TaskManager` must cleanup the registry for `task_id` once the streaming client consumes the final termination event (`task.completed` or `task.failed`).

### Project Structure Notes

- New utilities live in `backend/utils/tasks.py`.
- New router lives in `backend/routers/ingest.py`.
- Router tests live in `backend/tests/routers/test_ingest.py`.
- Ingestion orchestrator (`run_full_ingestion`) in `backend/services/parser.py` is invoked with optional `config` dictionary derived from `company_slug`.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Step 5: FastAPI Ingestion Engine & SSE Log Streaming](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md#Step-5:-FastAPI-Ingestion-Engine-&-SSE-Log-Streaming)
- [Source: _bmad-output/planning-artifacts/prd.md#mvp--4-week-build-weeks-14](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#mvp--4-week-build-weeks-14)
- [Source: _bmad-output/planning-artifacts/epics.md#epic-2-multi-source-job-ingestion--live-log-tracking-the-market-scanner](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#epic-2-multi-source-job-ingestion--live-log-tracking-the-market-scanner)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

- Verified all 35 backend tests pass successfully.
- Validated threadsafe queueing and early client disconnection cleanup.

### Completion Notes List

- Implemented `TaskManager` singleton in `backend/utils/tasks.py` to manage live SSE queues and memory-safe histories.
- Implemented `task_log_processor` in `backend/utils/logging.py` to forward active logs to the active queue before serialization.
- Created `backend/routers/ingest.py` with the asynchronous ingest queue executor, wait_for timeout limits, database run metadata updates, timeout file logging (`debug-attempt-YYYY-MM-DD.log`), and Starlette-native SSE streaming.
- Registered `/api/v1/ingest` and `/api/v1/tasks/{task_id}/logs/stream` in `backend/main.py`.
- Authored comprehensive test suite in `backend/tests/routers/test_ingest.py`.

### File List

- `backend/utils/tasks.py`
- `backend/utils/logging.py`
- `backend/routers/ingest.py`
- `backend/main.py`
- `backend/tests/routers/test_ingest.py`

### Change Log

- Completed implementation and verification of Story 2.2 background task service and SSE log stream (Date: 2026-05-27).
