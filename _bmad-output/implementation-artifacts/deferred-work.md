## Deferred from: code review of 1-3-candidate-profile-management-and-freshness-monitor.md (2026-05-26)

- **Alt-navigation suppression may be bypassed by capture-phase listeners [ProfileView.tsx:161]**: The global keydown navigation handler might capture hotkeys in the capture phase, bypassing `e.stopPropagation()` in the bubble phase.

## Deferred from: code review of 2-1-multi-source-ingest-parsers-and-database-schema (2026-05-27)

- ~~**HN Algolia pagination**: `whoishiring` may not appear in the first results page.~~ **Resolved 2026-05-27** — fixed by adding `tags=story,author_whoishiring&hitsPerPage=1` to the Algolia query. Author tag pre-filters results; first hit is always the latest thread. No pagination needed.
- **`company_slug.capitalize()` lossy for multi-word slugs**: Slugs like `open-ai` → `Open-ai`. Company display names will be inaccurate. Consider a slug-to-name mapping or title-case normalization.
- **Default ingestion config uses live company slugs**: Hardcoded live ATS slugs can silently fail if boards go private or slugs change. Current defaults were refreshed on 2026-05-27 for the reliable live adapters, but they should still move to a maintained seed-list config.
- **Workable default seed disabled**: Workable's public widget endpoint returned 403 responses and empty descriptions from the local verification environment on 2026-05-27. Keep the adapter implemented, but do not include Workable in scheduled defaults until a seed slug reliably returns non-empty `raw_text`.
- **`updated_at` column has no update trigger**: The `jobs` table defines `updated_at` but no `UPDATE` logic exists yet. It will become stale when job status changes in future stories.

## Deferred from: code review of 3-1-company-signals-and-canonical-source-resolver.md (2026-05-27)

- **Resolver has no per-run company signal cap [backend/services/source_discovery.py:582]**: Story 3.1 bounds each company resolution path, but does not specify a global provider yield cap. Revisit when Story 3.2+ introduce real providers and observed yield volume.
