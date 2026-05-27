# Source Discovery Channel Strategy

Date: 2026-05-27

## Position

The app should not depend on `source-discovery-seeds.json` as a maintained market corpus. Seeds are optional manual hints only. The source of truth for weekly ingestion is the validated registry in `job_sources`.

The strategy is:

1. discover companies or direct ATS sources,
2. resolve each company to its canonical careers/ATS source,
3. validate that live, relevant jobs exist,
4. activate only validated sources in the registry,
5. report rejected, unsupported, stale, and errored sources explicitly.

Google, Wellfound, HN, YC, GitHub, Reddit, Common Crawl, and VC portfolios are all allowed as signal sources. They are not trusted job sources by themselves. LinkedIn and Indeed are not automated providers.

## Architecture Layers

### Layer 1: Company And Source Discovery Providers

Providers produce hints:

- company names,
- company domains,
- careers URLs,
- direct ATS URLs,
- evidence URLs,
- provider metadata,
- confidence/category hints.

Providers do not activate ingestion sources directly.

### Layer 2: Canonical Source Resolver

Given a company domain or careers URL, the resolver finds where the company actually publishes jobs.

Resolver behavior:

- Try bounded paths only: `/careers`, `/jobs`, `/join-us`, `/work-with-us`, `/company/careers`.
- Fetch each page once with strict timeout and maximum response size.
- Parse anchors, canonical links, visible text, and script/config text.
- Check `/robots.txt` sitemap declarations and `/sitemap.xml` for career/job URLs.
- Parse `JobPosting` JSON-LD when no supported ATS is found.
- Do not execute JavaScript.
- Do not browser-automate.
- Do not crawl recursively.

### Layer 3: Validation

Validation is the trust boundary.

A source becomes active only if:

- provider/API request succeeds,
- at least one job exists,
- at least one job has non-empty `raw_text`,
- at least one job matches AI/backend/data/product relevance keywords.

### Layer 4: Registry And Reporting

Validated sources go into `job_sources` with `active = true`.

Rejected, unsupported, stale, and errored inputs stay visible through candidate/signal tables and reports. Weekly ingestion reads only active validated registry rows.

## Provider Build Order

### 1. HN Who's Hiring

Purpose: direct hiring signal.

HN Who's Hiring is a monthly Hacker News thread where companies post hiring comments directly. It is already implemented through the HN Algolia API.

Keep it because:

- companies are actively hiring,
- comments often include direct careers or ATS links,
- signal is strong for startups, AI, backend, devtools, and infrastructure.

### 2. Google Custom Search Signal Provider

Purpose: fresh careers/ATS page discovery through an official API.

Use Google only through the Custom Search JSON API. Do not scrape Google result pages or Google Jobs.

Implementation rules:

- Provider name: `google_search_api`.
- Disabled unless `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` are configured.
- Default query cap: 100 queries/day, matching the free quota boundary.
- Paid Google usage remains disabled unless explicitly configured.
- Store query text, result URL, title, snippet, rank, provider metadata, and evidence URL.
- Treat results as company/source signals only.

Initial query templates:

- `site:jobs.lever.co "AI Engineer" "Python"`
- `site:boards.greenhouse.io "LLM" "Backend"`
- `site:jobs.ashbyhq.com "RAG" "Engineer"`
- `"AI Engineer" "careers" "Greenhouse"`
- `"Machine Learning Platform Engineer" "careers"`
- `"FastAPI" "Backend Engineer" "jobs"`

### 3. Wellfound Signal Provider

Purpose: startup company discovery.

Wellfound is important enough to use, but not as a trusted job corpus. Use it as a constrained company-signal source.

Implementation rules:

- Provider name: `wellfound_signal`.
- Disabled by default behind `WELLFOUND_DISCOVERY_ENABLED=false`.
- Start with manual/imported Wellfound company URLs or search results supplied by the user.
- If automated public-page extraction is enabled:
  - no login,
  - no browser automation,
  - no pagination crawling,
  - no disallowed `/_jobs/` crawling,
  - default max 5 pages/run,
  - default 5+ second delay between requests.
- Extract only company name, company domain/homepage if visible, evidence URL, and confidence.
- Do not ingest Wellfound job text directly.
- Feed extracted domains into the canonical resolver.

### 4. Common Crawl ATS Index Provider

Purpose: large-scale direct ATS source discovery.

Common Crawl can find public ATS URL patterns at scale. This provider can bypass company discovery when it finds direct ATS board URLs.

Target URL patterns:

- `boards.greenhouse.io/*`
- `job-boards.greenhouse.io/*`
- `jobs.lever.co/*`
- `jobs.ashbyhq.com/*`
- `apply.workable.com/*`
- `*.recruitee.com/*`
- `*.jobs.personio.de/*`
- `*.jobs.personio.com/*`

Implementation rules:

- Query Common Crawl indexes with hard caps per ATS/provider.
- Normalize discovered URLs into `SourceCandidate`s.
- Deduplicate by `(ats, slug)`.
- Validate through existing parser adapters before activation.

### 5. YC Company Directory Provider

Purpose: startup/company universe discovery.

YC is useful because it exposes company names, websites, tags, and categories for startup-heavy markets.

Initial categories:

- AI,
- developer tools,
- infrastructure,
- data engineering,
- databases,
- open source,
- search.

Implementation rules:

- Extract company name, website, YC evidence URL, tags, and category hints.
- Feed websites into the canonical resolver.
- Do not use logged-in-only Work at a Startup flows.

### 6. VC Portfolio Providers

Purpose: company universe discovery.

VC portfolios identify relevant companies but do not prove current hiring.

Initial targets:

- a16z,
- Sequoia,
- Index,
- Accel,
- Greylock,
- Lightspeed,
- Conviction.

Implementation rules:

- Extract company names and homepage URLs from public portfolio pages.
- Treat portfolio job-board links as evidence only unless they point to a company-owned or supported ATS URL.
- Deduplicate against existing company signals.
- Track freshness because portfolios include inactive/exited companies.

### 7. GitHub Organization Signals

Purpose: AI/backend/devtools company discovery.

GitHub is useful for finding companies building relevant technical products, especially open-source AI infrastructure, vector databases, MLOps, agents, eval tooling, data platforms, and devtools.

Implementation rules:

- Use the official GitHub API.
- Search repos/orgs by topics such as `llm`, `rag`, `vector-database`, `mlops`, `agents`, `fastapi`, `developer-tools`.
- Extract org website, repo homepage, and README links.
- Look for careers/jobs/ATS links in org profile README and top repositories.
- Cap work per org to avoid rate-limit pressure.
- Treat GitHub as relevance signal, not direct hiring proof.

### 8. Reddit Hiring Signals

Purpose: direct but noisy hiring signal.

Reddit can surface direct hiring posts and small-company opportunities, but it is noisier than HN, Google, Wellfound, and YC.

Initial targets:

- `r/MachineLearningJobs`,
- `r/PythonJobs`,
- `r/forhire`,
- `r/remotepython`,
- relevant hiring threads when available.

Implementation rules:

- Use Reddit API/search rather than scraping pages.
- Search for hiring markers and target terms: `hiring`, `AI Engineer`, `LLM`, `RAG`, `Python`, `FastAPI`, `backend`, `remote`.
- Extract company names, domains, careers URLs, and evidence URLs.
- Feed domains/URLs into canonical resolver.
- Assign lower default confidence than HN or canonical ATS results.

## Excluded Or Constrained Sources

- LinkedIn: no automated scraping or crawling. Manual company clues can be imported as user-provided signals.
- Indeed: no automated scraping or crawling. Manual company clues can be imported as user-provided signals.
- Google: official Custom Search JSON API only; no result-page scraping.
- Wellfound: constrained signal extraction only; no trusted job ingestion from Wellfound pages.
- RapidAPI job APIs: excluded from the main pipeline for now.

## Implementation Roadmap

1. Add company-signal data model and discovery run telemetry.
2. Build canonical source resolver with bounded careers paths, sitemap parsing, ATS detection, and JSON-LD `JobPosting` parsing.
3. Keep HN provider active and migrate its output into the company/source signal model where useful.
4. Add Google Custom Search signal provider.
5. Add constrained Wellfound signal provider.
6. Add Common Crawl ATS index provider.
7. Add YC company directory provider.
8. Add VC portfolio providers.
9. Add GitHub organization signal provider.
10. Add Reddit hiring signal provider.
11. Add provider yield reporting and freshness scoring.

## Quality Gates

- Every provider reports `discovery_method` or `source_provider`.
- Every signal has an evidence URL when available.
- Every rejected URL or company has a rejection reason.
- Provider failure does not fail the whole discovery run.
- Registry activation always requires canonical validation.
- Weekly ingestion never reads seed files directly.
- Google API usage is capped and optional.
- Wellfound extraction stores company signals only.
- LinkedIn and Indeed remain manual-signal imports only.
