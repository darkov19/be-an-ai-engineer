# Public Portfolio Surfaces

The weekly report archive, historic weekly report pages, generated OpenGraph images, and company stack fingerprint pages are intentionally public portfolio artifacts.

These pages must remain unauthenticated and usable without backend API access. Do not add login redirects, tokenized URLs, private-only API dependencies, remote fonts, CDN scripts, or secret-bearing inline configuration to these surfaces.

Generated report and archive HTML is written under `frontend/public/` so Vite copies it into the static deployment. Database, LLM, job, company, and commit-derived strings must be escaped before static files are written.

## Weekly Publishing Verification

Before treating the public report workflow as operationally proven, run the GitHub Actions `Weekly Public Report` workflow through `workflow_dispatch` with repository secrets configured:

- `DATABASE_URL`
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

The workflow is expected to:

- run report publisher, script, and scheduler tests;
- generate static report, archive, and OpenGraph assets;
- build the Vite site and verify generated files exist in `frontend/dist`;
- commit curated files under `frontend/public/archive` and `frontend/public/reports`;
- deploy once, record deployment metadata, rebuild and recommit metadata-enriched assets, then redeploy;
- health-check `/archive/` and the report path produced by the same workflow run.

Do not mark a report as publicly verified from local tests alone. The public verification is complete only when the final deployed `/archive/` URL and the latest report URL both return successful HTTP responses for the run being published.

If `gh workflow run weekly-report.yml` returns `no git remotes found`, configure the GitHub remote for this checkout first. Without a remote, the local workspace cannot dispatch the GitHub Actions workflow or verify the deployed public URLs.
