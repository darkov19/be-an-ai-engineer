# Epic 6 Quality Checklist

Use this checklist for every Epic 6 story that reads, writes, or displays accountability data.

## Data Safety

- User-entered `description`, `notes`, `public_summary`, application details, and manual notes are treated as untrusted input.
- HTML-like strings such as `<script>alert(1)</script>` are covered in backend and frontend tests.
- Generated public HTML escapes all ledger-derived strings before writing static files.
- Public Loop B logs escape Markdown/HTML-sensitive text and do not allow raw link injection.
- Private fields are never copied into static report, archive, OpenGraph, or Loop B outputs.

## Evidence Validation

- Commit hashes are validated before verification succeeds.
- Evidence URLs are validated before rendering as links.
- Unsupported URLs render as labeled text instead of clickable anchors.
- LinkedIn post URLs, GitHub commit URLs, and public report URLs are tested separately.
- Application and interview evidence can be counted publicly without exposing recruiter or company-private details.

## API And Persistence

- Ledger endpoints use the standard success envelope `{"data": ...}` and error envelope `{"error": true, "code": "...", "detail": "..."}`.
- SQL uses parameterized queries.
- Status transitions are tested for `planned`, `in_progress`, `completed`, `missed`, `late`, and `partial`.
- Consecutive missed commitments are calculated deterministically and covered by tests.
- Historic report snapshots store the public ledger state used for that report.

## React And Accessibility

- Ledger UI state lives in ledger-specific components or hooks.
- Dashboard integration consumes a small ledger summary API/model rather than owning ledger workflow internals.
- Repeated action buttons have commitment-specific accessible names.
- Live status updates use polite live regions.
- Keyboard users can link evidence, resolve fallback pivots, and recover from validation errors.
- Reduced-motion preferences disable continuous or pulsing ledger animations.
- Color-coded states also include text labels.

## Static And Public Surfaces

- `/archive`, `/reports/{slug}/`, `/company/{slug}`, and `/loop-b` remain unauthenticated by design.
- Public pages have explicit empty states.
- Static pages do not require backend API access, remote fonts, CDN scripts, or secret-bearing inline configuration.
- Report and Loop B output use publish-time snapshots for historic rows.
- Tests cover missing, stale, malicious, partially verified, and redacted ledger entries.
