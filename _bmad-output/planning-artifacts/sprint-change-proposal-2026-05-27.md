# Sprint Change Proposal - Company Discovery Epic Insertion

Date: 2026-05-27
Project: be-an-ai-engineer
Scope: Moderate backlog reorganization

## 1. Issue Summary

Story 2.5 implemented ATS source discovery and registry-backed ingestion, but follow-up product discussion identified a larger gap: ATS discovery alone does not answer which companies should be checked. The market scanner needs a company discovery layer that can identify likely hiring companies from HN, Google Custom Search, constrained Wellfound signals, Common Crawl, YC, VC portfolios, GitHub, and Reddit, then verify hiring through canonical company or ATS sources.

The original plan moved directly from Epic 2 ingestion into LLM extraction. That sequence risks extracting and analyzing a corpus that is too narrow or seed-dependent. The correction inserts a new epic before AI extraction so the corpus acquisition layer becomes strong enough to support downstream analytics.

## 2. Impact Analysis

### Epic Impact

- Epic 2 remains valid. Story 2.5 becomes the foundation for active source registry and ATS validation.
- A new Epic 3 is added: **Company Discovery & Canonical Source Expansion (The "Company Radar")**.
- Existing Epic 3 is renumbered to Epic 4.
- Existing Epic 4 is renumbered to Epic 5.
- Existing Epic 5 is renumbered to Epic 6.

### Story Impact

New Epic 3 contains four stories:

1. `3.1 Company Signals and Canonical Source Resolver`
2. `3.2 Google and Wellfound Direct Hiring Signal Providers`
3. `3.3 Common Crawl, YC, and VC Scale Discovery Providers`
4. `3.4 Long-Tail Signals and Provider Yield Reporting`

Existing future story IDs are shifted:

- `3.1-3.4` AI extraction stories become `4.1-4.4`
- `4.1-4.5` cockpit stories become `5.1-5.5`
- `5.1-5.4` ledger stories become `6.1-6.4`

### Artifact Impact

- `_bmad-output/planning-artifacts/epics.md` updated with new FRs, new Epic 3, and renumbered future epics/stories.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` updated to reflect the new backlog order.
- `_bmad-output/planning-artifacts/source-discovery-channel-strategy.md` already captures the strategic source discovery approach.

No completed code needs rollback.

## 3. Recommended Approach

Use direct backlog adjustment: insert the new company discovery epic before AI extraction and renumber the remaining planned epics.

Rationale:

- The corpus quality problem is upstream of extraction, evals, and analytics.
- Story 2.5 created the registry and validation base, so the next logical work is expanding discovery into companies and canonical sources.
- Deferring this until after LLM extraction would make downstream metrics less trustworthy.
- Renumbering is safe because old Epics 3-5 were still backlog and have no implementation story files yet.

Effort: Medium
Risk: Medium
Timeline impact: Adds one epic before AI extraction, but reduces risk of analyzing an under-covered corpus.

## 4. Detailed Change Proposals

### Epic List

OLD:

```text
Epic 3: AI Signal Extraction & Interactive Evals
Epic 4: Geo-Segmented Job Intelligence & Search
Epic 5: Weekly Commitment Tracker & Exposure Therapy
```

NEW:

```text
Epic 3: Company Discovery & Canonical Source Expansion
Epic 4: AI Signal Extraction & Interactive Evals
Epic 5: Geo-Segmented Job Intelligence & Search
Epic 6: Weekly Commitment Tracker & Exposure Therapy
```

### Functional Requirements

Added FR48-FR55 covering:

- company discovery signal registry,
- canonical source resolver,
- Google Custom Search signal provider,
- constrained Wellfound signal provider,
- Common Crawl ATS index provider,
- YC and VC company discovery providers,
- GitHub and Reddit signal providers,
- provider yield, freshness, and coverage reporting.

### Sprint Tracking

Added backlog entries for new Epic 3 stories and shifted future backlog entries to Epic 4, 5, and 6.

## 5. Implementation Handoff

Classification: Moderate

Recommended next handoff:

1. Run story creation for `3.1-company-signals-and-canonical-source-resolver`.
2. Validate story 3.1 before development because it introduces schema and orchestration boundaries.
3. Implement Epic 3 in sequence; do not start Google/Wellfound providers before the canonical resolver exists.
4. Keep weekly ingestion pointed only at validated `job_sources`.

Success criteria:

- New Epic 3 appears before AI extraction in epics and sprint status.
- Future epics are consistently renumbered.
- No completed work is invalidated or rolled back.
- Story 3.1 is the next backlog item to create.
