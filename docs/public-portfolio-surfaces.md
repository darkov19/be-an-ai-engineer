# Public Portfolio Surfaces

The weekly report archive, historic weekly report pages, generated OpenGraph images, and company stack fingerprint pages are intentionally public portfolio artifacts.

These pages must remain unauthenticated and usable without backend API access. Do not add login redirects, tokenized URLs, private-only API dependencies, remote fonts, CDN scripts, or secret-bearing inline configuration to these surfaces.

Generated report and archive HTML is written under `frontend/public/` so Vite copies it into the static deployment. Database, LLM, job, company, and commit-derived strings must be escaped before static files are written.
