# Source Discovery Provider Module Decision

**Decision:** Do not split `backend/services/source_discovery.py` during the Epic 3 retrospective action cleanup.

## Rationale

- The current change adds orchestration guardrails, planning corrections, and review/process artifacts. It does not add another provider family.
- Splitting provider classes now would create broad import churn across a large, heavily tested service without changing behavior.
- The file is large enough to justify a split during the next provider-related change: `backend/services/source_discovery.py` is over 3,000 lines and its mirrored test file is over 2,600 lines.

## Trigger For Split

Split provider classes out of `source_discovery.py` when the next change adds or materially rewrites provider logic.

Recommended target shape:

- `backend/services/source_discovery.py`: orchestration, persistence, report writing, shared contracts
- `backend/services/source_discovery_providers/search.py`: Vertex AI Search
- `backend/services/source_discovery_providers/social.py`: GitHub and Reddit
- `backend/services/source_discovery_providers/company_directories.py`: YC, VC, Wellfound
- `backend/services/source_discovery_providers/archives.py`: Common Crawl

Keep public contracts stable: `DiscoveryProviderResult`, `SourceCandidate`, `ValidationResult`, `default_discovery_providers`, `discover_sources`, and report format compatibility.
