# Epic 4 Extraction Corpus Selection

**Decision:** Use provider yield from the latest source-discovery report to choose the first extraction corpus slice. Do not select the first extraction corpus from raw active-source count alone.

## Evidence Source

- Report: `_bmad-output/implementation-artifacts/source-discovery-report-2026-05-28.json`
- Active sources after run: 94
- Validated candidates: 98
- Company signals resolved: 10
- High-yield providers: `common_crawl_ats`, `hn_who_is_hiring`, `vertex_ai_search`
- Low-yield or not-yet-useful providers in the report: `unsupported`, `vc_portfolio`, `yc_company_directory`
- Disabled providers in the report: `github_org_signal`, `reddit_hiring_signal`, `wellfound_signal`

## Selected Initial Extraction Slice

Epic 4 should start extraction from active, validated `job_sources` attributed to:

1. `hn_who_is_hiring`
2. `vertex_ai_search`
3. `common_crawl_ats`

The first extraction run should exclude raw `company_signals`, unsupported URLs, disabled providers, unresolved companies, and low-yield providers until they produce validated active sources in a later discovery report.

## ATS Mix Guidance

Prefer sources from the ATS families with meaningful validated representation in the latest report:

- Ashby
- Greenhouse
- Lever
- Recruitee
- Personio
- Workable only where parser validation reports non-empty usable postings

## Eval Seed Guidance

The hand-labeled eval set should sample from the selected high-yield providers and avoid tuning prompts against unsupported or unresolved discovery noise. If the selected corpus lacks enough usable postings for a field, reduce extraction scope or add manual CSV-backed postings rather than widening to unvalidated provider evidence.

## Epic 4 Entry Condition

Before Story 4.1 implementation, rerun source discovery or confirm this report remains the current baseline. If high-yield providers change, update this file before selecting extraction rows.
