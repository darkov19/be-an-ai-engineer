# Epic 6 Frontend Boundaries

Epic 6 adds durable ledger workflows to a dashboard that already contains analytics, the brain visualizer, telemetry, market diffing, and active directives. Keep the new behavior component-scoped.

## Component Ownership

Create ledger-specific frontend modules before changing broad dashboard logic:

- `frontend/src/components/ledger/ActiveOrders.tsx`
- `frontend/src/components/ledger/CommitmentRow.tsx`
- `frontend/src/components/ledger/EvidenceLinker.tsx`
- `frontend/src/hooks/useLedger.ts`
- `frontend/src/hooks/useLedgerSummary.ts`

`DashboardView.tsx` should consume only a compact summary needed for pinned warnings and top-level status. It should not own commitment CRUD, evidence-link form state, validation messages, or public/private rendering rules.

## Integration Rules

- The `/ledger` route owns the full commitment/action workflow.
- The dashboard may show pinned overdue summaries and a fallback-pivot CTA.
- Existing analytics, brain visualizer, telemetry chart, and market skill-gap state should not be refactored as part of ledger implementation unless a test proves a direct integration need.
- Ledger components must preserve existing keyboard, live-region, and reduced-motion patterns.
- Shared styles should be narrow and semantic; avoid adding more unrelated dashboard rules to a general view stylesheet when a ledger module stylesheet is clearer.
