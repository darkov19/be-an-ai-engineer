# Epic 3 Readiness Notes

**Date:** 2026-05-27  
**Source:** Epic 2 retrospective action items

## Migration Plan

Existing backend migrations:

- `V001__init.sql`
- `V002__add_jobs_and_ingestion.sql`
- `V003__add_weekly_reports_and_access.sql`
- `V004__add_notification_outbox.sql`

Epic 3 must wait until source discovery owns `V005`. The source-discovery migration is:

- `backend/db/migrations/V005__add_job_source_registry.sql`

Story 2.5 owns `V005` because source discovery must be implemented before Epic 3 extraction depends on the corpus. The planned eval migration name is now:

- `backend/db/migrations/V006__add_evals.sql`

If Story 3.1 adds extraction persistence before Story 3.2, use:

- `backend/db/migrations/V006__add_job_extractions.sql`
- `backend/db/migrations/V007__add_evals.sql`

Do not create another `V003` migration. The migration runner sorts all `*.sql` files lexically and records each filename in `schema_migrations`, so version collisions or reused versions create confusing local histories.

## Review Checklist For Epic 3

Every Epic 3 review must explicitly check terminal-state correctness:

- Failed Hermes health checks abort extraction before batch processing.
- Partial LLM extraction failures persist valid objects and log failed posting IDs.
- Background extraction/eval runs emit exactly one terminal state.
- SSE clients receive `task.completed` or `task.failed` and do not require polling.
- Aborted database transactions do not prevent failure telemetry from being recorded.
- Kill-criterion artifacts are written for blocked runs and include corpus and accuracy inputs.
- Warning mode and blocking mode are distinguishable in both data and UI.
