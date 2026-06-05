# Ledger Evidence Model

Epic 6 uses the accountability ledger as public-adjacent career evidence. The model must prove commitment follow-through without leaking private job-search details.

## Commitments

Each commitment records what Darko intended to do.

Required fields:

- `id`: stable database identifier.
- `category`: one of `applications`, `build`, `posts`, `voice_notes`, `interviews`, or `learning`.
- `description`: user-entered text describing the commitment.
- `target_count`: integer target for countable commitments.
- `target_date`: ISO 8601 date.
- `status`: one of `planned`, `in_progress`, `completed`, `missed`, `late`, or `partial`.
- `public_visibility`: one of `public`, `redacted`, or `private`.
- `created_at` and `updated_at`: ISO 8601 timestamps.

Optional fields:

- `notes`: private or redacted user-entered context.
- `consecutive_misses`: integer used by dashboard and public report warnings.
- `public_summary`: sanitized summary safe for report/archive/Loop B rendering.

## Actions

Each action verifies progress against a commitment.

Required fields:

- `id`: stable database identifier.
- `commitment_id`: foreign key to `commitments.id`.
- `action_type`: one of `commit`, `application`, `linkedin_post`, `voice_note`, `interview`, `fallback_pivot`, or `manual_note`.
- `status`: one of `verified`, `pending_verification`, `rejected`, or `redacted`.
- `occurred_at`: ISO 8601 timestamp or date.
- `public_visibility`: one of `public`, `redacted`, or `private`.

Evidence fields by action type:

- `commit`: `commit_hash` is required and must match a Git SHA pattern. Optional `commit_url` must use `https://`.
- `application`: store private company/contact details separately from `public_summary`; public output may show count, segment, and role category only.
- `linkedin_post`: `evidence_url` is required and must use `https://www.linkedin.com/` or another explicitly allowed public URL.
- `voice_note`: store only a timestamp, duration marker, and optional private notes by default; do not expose audio paths publicly.
- `interview`: store stage and outcome labels; company/contact names are private unless explicitly marked public.
- `fallback_pivot`: link to a commit, report artifact, or sanitized note explaining the pivot.
- `manual_note`: private by default; public rendering requires `public_summary`.

## Public And Private Boundaries

Public surfaces may render:

- commitment category, target count, target date, status, consecutive miss count, and sanitized public summary;
- verified commit links and explicitly public LinkedIn post links;
- aggregate Loop B counts for applications, interviews, voice notes, and posts;
- redacted labels such as `India AI product application filed` without company/contact details.

Public surfaces must not render:

- recruiter names, email addresses, phone numbers, private company process notes, private application URLs, raw voice-note paths, raw user notes, or unreviewed generated text;
- unvalidated links;
- raw HTML from any ledger field.

## Validation Rules

- Escape every user-entered or generated string before rendering in React, static reports, archive pages, and public Loop B logs.
- Validate URLs before linking them. Unsupported or malformed URLs render as plain text with a `link unavailable` label.
- Validate commit hashes before accepting them as commit evidence.
- Keep API responses in snake_case and use the standard success/error envelopes used elsewhere in the project.
- Snapshot public report data at publish time; do not recompute historic ledger facts from mutable current state.
