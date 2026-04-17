---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain-skipped', 'step-06-innovation-skipped', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish']
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-be-an-ai-engineer.md
  - _bmad-output/planning-artifacts/product-brief-be-an-ai-engineer-distillate.md
  - _bmad-output/brainstorming/brainstorming-session-2026-04-10-01.md
documentCounts:
  briefs: 2
  research: 0
  brainstorming: 1
  projectDocs: 0
workflowType: 'prd'
classification:
  projectType: web_app
  domain: general
  complexity: medium
  projectContext: greenfield
carryForward:
  - "Week-0 empirical spike: visit 15 India AI company careers pages, note ATS used, update seed list before writing ingest code."
  - "Week-2 time-boxed JobSpy spike (2 hours): measure LinkedIn+Indeed unique-posting yield via python-jobspy, single IP, decision rule ≥30% unique + no rate limit → include as secondary source."
  - "Seed-50 list constraint: must include ~15 India AI product + captive-center slots, and ~20 early-stage (YC-batch / seed) slots, to prevent enterprise-skill overweighting bias."
  - "Weekly report output must be geo-segmented (US/EU remote rankings vs India-based AI product rankings side-by-side)."
  - "Known corpus biases to document in Scope/Risks section later: Wellfound-only postings, LinkedIn-only recruiter posts (covered by Loop B not ingest), FAANG/Workday roles, Indian services/consultancies (deliberately excluded), enterprise-skill overweighting risk."
  - "Evals harness must be framed as the primary craft-signal surface of the project, not a minor engineering checkbox — competitive differentiation has shifted to rigorous measurement on a narrow niche."
---

# Product Requirements Document - Job Intelligence Agent

**Author:** Darko
**Date:** 2026-04-15

## Executive Summary

**Job Intelligence Agent** is a single-user Python tool that ingests AI engineering job postings from public ATS APIs, LLM-extracts structured signals (skills, seniority, stack, salary, remote policy, role archetype), ranks those signals across the corpus, diffs against the user's profile, and publishes a weekly skill-gap report to a static public URL. The build is dual-purpose by design: it is simultaneously the user's AI-engineering curriculum (every in-demand 2026 AI skill is learned by being used to construct the ranker), the user's weekly market intelligence feed, and the user's proof-of-skill portfolio artifact. One project, three jobs, four-week MVP.

**Primary user:** one developer (Darko), weekly use. **Secondary audience:** AI hiring managers interviewing the author — they never run the tool; they *encounter* its artifacts (public repo, live URL, LinkedIn thread, and the highest-leverage interview demo of running the tool live against the interviewer's own job board). **Tertiary, post-MVP only:** other backend-to-AI transitioners.

**Target market — two equal-weight segments:**

1. **US / EU remote roles** at AI-forward companies — the 2–3× salary stretch path.
2. **India-based AI product companies** (Sarvam, Krutrim, Yellow.ai, Haptik, Qure.ai, Gnani.ai, ideaForge, Peak, Observe.ai, Fractal, etc.) **and foreign AI captive centers in India** (Microsoft India AI, Google India, Amazon India, Nvidia India, Adobe India) — the +50% floor path with daytime-hours guarantee by default. **Deliberately excluded:** Indian services/consultancy work (TCS, Infosys, Wipro, HCL, Cognizant, Accenture, Capgemini) — this is the exact trap the user is escaping (night-shift US-client delivery, mid-salary).

**The problem solved** is not *find me a job* — it is **market opacity for self-directed learners**. The AI engineering market is fragmented across half a dozen role archetypes with different stacks. Existing consumer job-search tools (Teal, Jobscan, Huntr, Careerflow) operate per-job-description reactively; none rank skills aggregately across the live market. Enterprise labor-market intelligence products (Lightcast, JobsPikr, LinkedIn Economic Graph, Coursera Skills Report 2026) do rank aggregately but are priced for corporate buyers and do not slice specifically to AI engineering as a personal artifact. This product fills the gap between those two layers — and uses its own output to drive the user's weekly learning, interviewing, and build-in-public cadence.

**MVP timeline:** 4 weeks. **LLM budget cap:** $30 total. **Weekly time budget:** 15–20 hours. **Repo:** public from Day 1. **Success = a credible offer conversation within 16 weeks** at +50% over current base minimum, daytime hours, non-toxic team. The tool is explicitly subordinate to that outcome and is killed or frozen per the brief's Week 2 / Week 4 / Week 8 decision rules if it becomes the bottleneck instead of the accelerant.

### What Makes This Special

**1. The build is the curriculum.** Every in-demand 2026 AI engineering skill — structured LLM output, pgvector retrieval, evals harness, agents, prompt discipline, cost-capped batching, production deployment — is learned *by* being used to construct the ranker. One deeply-explained artifact replaces ten shallow tutorial projects. The thirty-minute interview conversation about this project is the portfolio; the GitHub repo is the evidence.

**2. Aggregate-market ranking, not per-job matching — with honest competitive positioning.** The competitive landscape has three layers: (a) consumer per-JD tools (Teal, Jobscan, Huntr, Careerflow) — all reactive, none aggregate-market; (b) enterprise labor-market intelligence (Lightcast's 2.5B postings, JobsPikr, LinkedIn Economic Graph, Coursera Skills Report) — aggregate but corporate-priced and not AI-engineering-sliced; (c) prior art in the personal-artifact shape — Andrej Karpathy's `karpathy.ai/jobs` (March 2026) visualized 342 BLS occupations with LLM-scored AI exposure overlays, validating the shape *"one person ships a personal job-market tool publicly"* but operating on static BLS categories rather than live ATS postings. The gap this product occupies: **a weekly, AI-engineering-specific, live-posting skill-frequency ranker, diffed against one user's profile, shipped as an open-source personal artifact.** No tool found in the April 2026 research survey occupies this intersection. The moat is narrative and execution speed, not technical novelty — LLM skill extraction is an active open-source research area (ESCOX, Skill-LLM, LLM4Jobs, SKILLSPAN dataset), which means **the craft signal in this project lives in the evals harness and the weekly-cadence discipline, not in the extractor architecture itself.**

**3. Data-layer clarification — why this is not a LinkedIn competitor.** Job marketplaces (LinkedIn, Wellfound, Naukri, Indeed) are *distribution surfaces*: they display postings downstream of the employer's canonical source. This product operates **one layer upstream**, consuming canonical postings directly from employer-owned ATS public endpoints (Greenhouse, Lever, Ashby, Workable, Recruitee, Personio), plus early-stage coverage via Y Combinator's `workatastartup.com` public API, plus the HN "Who's Hiring" monthly thread. Distribution marketplaces show one job at a time; this product ranks skills across hundreds of jobs and diffs the result against the user's profile. **Different category — same way Google Trends is a different product from Google Search.**

**4. The product dogfoods its own proof.** Public repo Day 1. Commit history *is* part of the evidence. The tool is used weekly in public, feeding a LinkedIn build-in-public post thread. The single highest-leverage interview demo is running the tool live against the interviewer's own company job board during the first five minutes of the call. The artifact, the narrative, and the distribution loop are the same object viewed from three angles.

**5. Dual-loop execution is a first-class product requirement, not a process note.** Loop A (Build) and Loop B (Interview + Communicate) run simultaneously from Day 1. The PRD treats **"5 applications per week, first voice note recorded, first LinkedIn post live by end of Week 1"** as binding requirements with the same weight as ingest pipeline functionality. The brief names *"planning eats execution"* as the #1 project risk and codifies that risk into kill criteria at Weeks 2 / 4 / 8. **A build milestone that ships without its corresponding interview-loop milestone has failed its specification.**

**6. Cost discipline as a named differentiator.** The $30 / 4-week LLM budget cap is not a footnote — it forces prompt caching, batching, provider abstraction via Vercel AI Gateway, and corpus scoping from Day 1. Production instincts (cost awareness, cache discipline, batching) are baked into the project by budget constraint rather than by preaching. This is exactly the signal AI hiring managers in 2026 are filtering for: the brief's research confirms *"production instincts (error handling, evals, deployment, structured outputs, cost awareness) signal harder than novelty."*

**7. Ingest discipline is a soft rule, not a dogma.** Sources are chosen on a **free-public-API-first rule**: if a source offers a documented unauthenticated endpoint, it is in core ingest; if it requires scraping, it is out of MVP-core but eligible for a time-boxed spike (with a documented decision rule — e.g., the Week-2 JobSpy spike targeting LinkedIn/Indeed) where the marginal signal justifies the reliability and ToS-exposure cost. The governing criterion is not *"public vs. scraped"* — it is *"marginal unique signal ÷ (maintenance cost + ToS exposure + budget burn)."* This framing is defensible in an interview: a reviewer asking *"why didn't you just use JobSpy?"* gets a crisp answer — *"I ran the spike. Here's what it showed. Here's why I kept / dropped it."*

## Project Classification

| Field | Value |
|---|---|
| **Project Type** | Web app (Python batch pipeline + static public HTML report page) |
| **Domain** | General — career / job-market intelligence. No regulatory or compliance surface. |
| **Complexity** | Medium. Domain complexity is low; technical complexity is medium (LLM structured extraction, pgvector retrieval, cost-capped batching, evals harness, dual-loop execution as a product constraint). |
| **Project Context** | Greenfield. No existing codebase. Public GitHub repository from Day 1. |
| **Scope ceiling** | 4-week MVP. Single user. One weekly skill-gap report as the primary output artifact. |
| **Primary ingest sources (MVP core)** | Greenhouse, Lever, Ashby, **Workable, Recruitee, Personio** (all free public ATS APIs), **Y Combinator `workatastartup.com`** (public API), HN "Who's Hiring" monthly thread parser |
| **Secondary ingest (Week-2 experimental spike)** | JobSpy (LinkedIn + Indeed + Glassdoor + Google + ZipRecruiter) — included only if the 2-hour spike produces ≥30% unique AI-engineering postings with no immediate single-IP rate limit |
| **Out of MVP scope (deferred to Vision)** | Wellfound (no public API — scraper-gated), Naukri (same), LinkedIn direct, Workday-hosted boards (FAANG / enterprise — maintenance tax too high), multi-user / accounts / auth / billing / chatbot UI, Interview Prep Agent, Resume Tailoring Agent, Content Pipeline Agent, Studio Aalekh integration |
| **Explicit non-goals** | Not a SaaS. Not a job scraper product. Not an auto-apply bot. Not a generic resume tool. Not a job marketplace. |

## Success Criteria

> **Framing note.** This project has a single user who is also the sole stakeholder. The template's "User Success / Business Success" split does not cleanly apply, so the categories below are renamed to reflect the one-user reality: **Primary Outcome** (the binary career result), **Craft-Signal Success** (independent hireability-artifact success), **Technical Success** (measurable engineering properties), and **Leading Indicators** (the three-loop weekly tracker preserved from the product brief).

### Primary Outcome — binary, 16-week horizon

- **The single pass/fail metric:** a credible offer conversation in progress by end of Week 16. *Offer conversation* = past final round at ≥1 company, salary discussion open.
- **Floor (walk-away line):** +50% over current base, **daytime hours**, non-toxic team. Any offer below any of these three is declined and interviewing continues.
- **Target (acceptable):** +100% to +200% at a US/EU remote AI-forward company, **OR** +50% to +150% at an India-based AI product company or foreign AI captive center in India — both count equally against the Primary Outcome.
- **Disqualified even if above the salary floor:** Indian services / consultancy roles (TCS, Infosys, Wipro, HCL, Cognizant, Accenture, Capgemini and equivalents) — this is the exact trap the user is escaping (night-shift US-client delivery). A "successful" offer in this category is explicitly *not* a success for this project.
- **Emotional success marker (named, not numerically measured):** the first interview in which the user does not freeze during a technical question, answers from actual build experience rather than memorized preparation, and walks out describing it as "a conversation, not an exam." Target: Week 6 or earlier.

### Craft-Signal Success — independent of Primary Outcome

The project also has an independent success criterion: **it must function as a credible hireability artifact on its own**, such that even if the 16-week window closes without an offer conversation, the project has generated enough craft-signal evidence to materially improve the *next* 16 weeks.

- **Public repo with continuous commit history:** ≥1 meaningful commit per working day across Weeks 1–4. Commit messages are legible and explain intent, not just `"update"`.
- **Evals harness as the primary craft-signal surface:** 20 hand-labeled postings, extraction accuracy measured, methodology documented in the public write-up. **Eval methodology is the most important craft-signal artifact on the project** — not the extractor code, not the ranker, not the UI. Because LLM skill extraction is an active open-source research area (ESCOX, Skill-LLM, LLM4Jobs, SKILLSPAN), competitive differentiation has shifted from "novel extraction approach" to "rigorously measured extraction on a narrow niche." A hiring manager reading the README should conclude *"this person treats evals as a first-class concern"* — that is the 2026 AI engineering hiring filter.
- **Public write-up at end of Week 4:** brutally honest, including what broke, what is unfinished, and what extraction accuracy actually was. *"Here's what I learned and what's broken"* is a stronger hiring signal than *"here's my polished demo."*
- **Weekly build-in-public LinkedIn post cadence:** Weeks 1–16 unbroken. Each post documents one thing built and one thing that broke. Primary goal: exposure-therapy for the user's confidence-communication loop. Secondary goal: distribution.

### Technical Success

| Metric | Target | Kill threshold | Measured by |
|---|---|---|---|
| **Corpus size (AI engineering postings)** | ≥200 by end of Week 2 across ingest sources | <100 by end of Week 2 → pivot to manual CSV, ingest frozen | Row count in Postgres |
| **Extraction accuracy on 20-sample eval** | ≥70% on labeled fields (skills, seniority, stack, salary band, remote policy, role archetype) | <70% by end of Week 2 → cut ingest scope, refocus on ranker + write-up | Eval harness run, results committed to repo |
| **LLM spend (total, 4-week MVP)** | ≤$30 | Hard cap — ingest frozen if exceeded | Vercel AI Gateway spend dashboard |
| **MVP deployment** | Public URL live, weekly report visible to unauthenticated visitor | Not deployed by end of Week 4 → ship as-is, pivot 80% to interview loop | External URL health check |
| **Report generation automation** | Weekly report runs without manual intervention by end of Week 4 | Manual-only beyond Week 4 | Cron / scheduled workflow run logs |
| **Public repo visibility** | Day 1, honest README, commit history visible | Non-negotiable | GitHub visibility check |
| **Weekly report segmentation** | Report shows top-10 skills for US/EU remote segment AND top-10 for India-based AI product segment, side-by-side | Must be present in Week 4 output | Report HTML structure |
| **Pre-Week-1 India empirical spike** | 15 India AI company careers pages visited, ATS recorded, seed list updated before ingest code is written | 1-hour binding task | Committed CSV + seed list diff |
| **Week-2 JobSpy spike decision** | 2-hour time-boxed experiment produces a documented go/no-go decision in the repo README | Experiment must close with either outcome | README commit containing decision rule output |

### Leading Indicators — three-loop weekly tracker

| Loop | Week 1 | Week 4 | Week 8 | Week 16 |
|---|---|---|---|---|
| **Build** | Repo public, ingest running on ≥5 companies across ≥2 ATSs, first extraction sample committed | MVP deployed, geo-segmented skill-gap report matches output spec, evals run with accuracy published, write-up posted | JobSpy spike resolved (in or out), corpus ≥500 postings, tool in maintenance not feature work | Tool in maintenance only; used weekly for personal interviews |
| **Interview** | **5 applications filed** (mix of US/EU remote + India-based AI product / captive), ≥2 from the seed-50 company list | 20 applications filed, first real interview completed | 40+ applications, first "didn't freeze the whole time" interview | Offer conversation in progress |
| **Communicate** | First voice note recorded, first build-in-public LinkedIn post live (honest — includes the fear and the 4.5 years) | 4 LinkedIn posts live, 2 Looms recorded | First cold outreach DM sent to a hiring lead at a target company, using tool insight as the opener | First unsolicited inbound recruiter message received |

### Kill Criteria — decision rules, not feelings

- **End of Week 2:** corpus <100 postings OR extraction accuracy <70% → freeze ingest, switch to a manual CSV of ~50 hand-collected postings, redirect saved days to ranker + write-up quality.
- **End of Week 4:** MVP not publicly deployed → ship whatever exists *as-is*, publish the honest "here's what's broken" post, pivot 80% of remaining time to interviewing. **The tool does not deserve a Week 5 if it has failed its Week 4 deployment checkpoint.**
- **End of Week 8:** fewer than 2 real interviews completed → the tool is no longer the bottleneck. Stop all feature work. Begin direct cold outreach to hiring leads at target companies, using tool insights as the conversation opener. **Go Fight Mode:** application cadence doubles from 5 / week to 10 / week; feature work stops.

### Measurable Outcomes Summary

- Repo public Day 1 → verifiable by GitHub visibility check.
- 5 applications filed by end of Week 1 → verifiable by application tracker (spreadsheet or Huntr).
- Corpus ≥200 AI engineering postings by end of Week 2 → verifiable by Postgres row count.
- Extraction accuracy ≥70% on 20-sample eval by end of Week 2 → verifiable by eval harness output in repo.
- LLM spend ≤$30 by end of Week 4 → verifiable by Vercel AI Gateway dashboard.
- Public URL live by end of Week 4 → verifiable by external health check.
- Public write-up posted by end of Week 4 → verifiable by LinkedIn + personal blog URL.
- Weekly report geo-segmented by end of Week 4 → verifiable by HTML structure.
- 1 LinkedIn post per week, Weeks 1–16 unbroken → verifiable by LinkedIn profile activity.
- First non-frozen interview by Week 6 → self-reported, journaled.
- Offer conversation in progress by Week 16 → self-reported, externally confirmable via recruiter/company.

## Product Scope

### MVP — 4-week build (Weeks 1–4)

**Week 0 — pre-code empirical spike (1 hour, binding)**

- Visit the careers pages of 15 India-based AI companies: **Sarvam AI, Krutrim, Yellow.ai, Haptik, Qure.ai, Gnani.ai, ideaForge, Peak, Observe.ai, Niramai, SigTuple, Turing, Fractal**, plus 2 additional chosen in-session.
- Record which ATS backs each company (Greenhouse / Lever / Ashby / Workable / Recruitee / Personio / Workday / in-house).
- Companies on supported ATSs go into the ingest seed list. Companies on unsupported ATSs go into the Known Corpus Gaps doc.
- **Output:** a committed 15-row CSV + seed-list diff. This replaces assumptions with evidence before any ingest code is written.

**Weeks 1–4 — ingest and extraction**

- **Ingest sources (primary, free public APIs — zero ToS risk):**
  - Greenhouse public job board API
  - Lever public job board API
  - Ashby public job board API
  - **Workable, Recruitee, Personio public APIs** — catches European and long-tail AI startups
  - **Y Combinator `workatastartup.com` public API** — closes the early-stage AI startup gap
  - HN "Who's Hiring" monthly thread parser
- **Seed-50 company list constraints (product decisions, not code):**
  - ~20 US/EU AI-forward companies (Anthropic, OpenAI, Perplexity, Vercel, LangChain, Cohere, Mistral, Scale, Replit, Hugging Face, etc.)
  - ~15 India-based AI product companies and foreign AI captive centers in India (derived from Week 0 empirical spike)
  - ~15 early-stage (pre-seed, seed, YC-batch) AI startups to prevent enterprise-skill overweighting bias
- **Extraction:** Claude (via Vercel AI Gateway) with structured output — skills, seniority, tech stack, salary band, remote policy, role archetype (LLM App Engineer / AI Product Engineer / Agent Engineer / ML Platform Engineer).
- **Storage:** Neon Postgres + pgvector.
- **Eval harness:** 20 hand-labeled postings. Accuracy measured and committed to repo. **Framed as primary craft-signal surface of the project.**
- **Ranker:** skill frequency aggregation, skill co-occurrence clusters, salary–stack correlations.
- **Diff:** ranked market vs. user profile → skill-gap report.
- **Output (the single most important artifact):** static public HTML page showing the weekly report, **geo-segmented** (US/EU remote top-10 + India-based AI product top-10, side-by-side).
- **Corpus bias disclosure:** weekly report footer lists ingest sources, N postings per source, and named known gaps (Wellfound, LinkedIn direct, Workday-hosted, Indian services/consultancies excluded). Honesty-first product design as a craft-signal demonstration.
- **Public GitHub repo:** Day 1. Honest README. Commit history visible throughout.
- **Public write-up:** End of Week 4. LinkedIn + personal blog post. Results + what's broken + eval methodology.

**Week 2 — JobSpy experimental spike (time-boxed 2 hours)**

- `pip install python-jobspy`. Run one LinkedIn query + one Indeed query for AI / LLM Engineer roles, limit 50 postings each, single IP, no proxies.
- Measure: unique-posting yield vs. existing ATS corpus, dedup rate, whether LinkedIn rate-limits on first run.
- **Decision rule:**
  - **≥30% unique postings + no immediate rate limit** → include JobSpy as a Week 3 secondary ingest source with reliability disclaimer. Budget ≤20% of remaining LLM spend for the extra postings.
  - **<30% unique OR immediate rate-limit OR proxy required** → defer permanently. Document spike result in repo README.
- Either outcome is published as part of the write-up — the documented decision itself is a craft-signal artifact.

**Loop B — parallel execution from Week 1 (binding, not optional companion)**

- **5 job applications per week** starting Week 1 (mix of US/EU remote and India-based AI product / captive). ≥2 from the seed-50 list.
- **Daily voice notes journal** — 60-second memos about learnings, bugs, insights.
- **First Loom recording by end of Week 1** — explain something the user already knows, private at first.
- **Weekly build-in-public LinkedIn post, Weeks 1–16 unbroken.** Honest. Includes the fear and the 4.5 years in the first post.
- **Every interview offered is taken as paid practice.** No waiting for "ready."

**Why this sequence, and why it starts tonight:** Loop B is not a list of marketing tasks — it is a graduated exposure therapy staircase designed around the confidence-communication loop identified in the brainstorming as the real root blocker. Each layer normalizes the next: voice notes are private, Looms are low-stakes, LinkedIn is medium-fear, real interviews are the top of the stair. The staircase works because Darko already knows the answer ("give lots of interviews and fail lots") — the sequence exists to get him there without requiring courage he may not have on a given week. The accountability ledger enforces the staircase discipline mechanically. The design supports the version of Darko who is scared, not the one who has already resolved the fear.

### Growth — Post-MVP (Weeks 5–12, Go Fight Mode)

These are **not MVP scope** and must not leak into Weeks 1–4.

- **Application cadence doubles to 10 / week.** Feature work slows to ≤5 hr / week. The tool is now a resume asset, not an active project.
- **Interview Prep Agent (reopened from the brief's deferred list).** Takes a posting, generates likely questions, supports voice-based mock interviews with LLM feedback. The brief cut this from MVP for scope discipline, but it is the direct countermeasure to the user's named root blocker (fear of interviews). The PRD reopens it for Growth as a deliberate product decision.
- **Per-company interview briefing (Scenario 2 from the brief).** Ingest a specific company's entire public job board on demand, generate a stack fingerprint the user can quote in the first five minutes of the interview. Highest-leverage interview demo in the project.
- **Cover note generation (Scenario 4 from the brief).** Diffs a specific posting against user profile, generates evidence-first application bullets.
- **Weekly "State of AI Hiring" auto-post.** Corpus delta → LinkedIn post, auto-generated. Distribution flywheel on one cron job.
- **Public Hugging Face dataset.** Weekly update. Inbound researcher traffic, citation surface.
- **JobSpy integration in production** — only if the Week 2 spike cleared the ≥30% threshold.

### Vision — Post-Hire (Month 3+)

- **Unified personal AI platform.** Shared backend across Job Intelligence + Interview Prep + Cover Note + Content Pipeline. The bottom-up, earned version of the original 9-module idea brief.
- **Content Pipeline Agent.** Git commits → LinkedIn post drafts → distribution queue. Closes the build-in-public loop without manual content effort.
- **Studio Aalekh integration.** Art catalog, pricing agent, client chatbot. Month 3+ post-hire territory (currently too data-raw per the brief).
- **Open-source artifact for other backend-to-AI transitioners.** Honest documentation, templated seed list, reusable eval harness.
- **Wellfound / Naukri / Workday ingest via paid scrapers** — only if, post-hire, the maintenance cost is justified by a use case that did not exist during MVP.

## User Journeys

> **Scoping note.** This product has one real user (Darko) and one secondary audience (AI hiring managers who *encounter* the artifact asynchronously). There are no admins, no API consumers, no support staff, no multi-tenant roles. The step template's default "primary happy + primary edge + admin + support + API" coverage does not apply and is deliberately not force-fit. The five journeys below are the real interaction surfaces. They were pressure-tested via Pre-mortem Analysis and Red Team adversarial review before being appended to this document; both passes produced concrete hardening changes that are reflected in the Journey Requirements Summary at the end of this section.

### Journey 1 — Saturday Morning Skill-Gap Report *(primary user, happy path)*

**Opening.** Saturday, 8:12 AM IST. Darko is at the kitchen table with coffee — *not* post-night-shift, deliberately. The weekly report cron runs Friday night US/EU time, which is Saturday morning Bengaluru time, which is the only window in the week when Darko has genuine focus and weekend bandwidth. He opens `job-intelligence-agent.vercel.app`. His emotional state: cautiously awake, half-braced for "another boring week."

**Rising action.** The page loads. Two-column geo-segmented header: **US/EU remote** | **India AI product**. Corpus: 247 postings across Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, YC-WaaS, and HN. Top 10 skills per segment. Profile fit: 5/10 on US/EU, 6/10 on India AI product. Minimum-experience-threshold distribution strip at the top — 18% of postings list "no minimum stated," 44% "3+ years," 29% "5+ years," 9% "senior only." The accountability ledger block below the rankings shows **last week's commitments against last week's actions**: ✓ shipped the pgvector retrieval module (commit linked), ✗ did not file the 5th application, ✓ shipped the LinkedIn build-in-public post. Profile last updated: 2 weeks ago — a soft nudge appears: *"profile is stale, refresh takes 2 minutes before the diff can be trusted."*

**Climax.** Darko is tempted to close the tab — the numbers are close to last week's, and the novelty of Monday-morning data lift has already worn off by Week 7. **Something in the design pulls him back in: the accountability ledger shows the un-acted-on application gap from last week is *still* in the top 3, now flagged red.** The product is not selling him new information. It is reminding him what he committed to and did not do. This is the fight against user inertia — and it is the product's job, not Darko's.

**Resolution.** He refreshes the profile (2 minutes — adds the pgvector module and the evals doc he shipped this week). Re-runs the diff. Profile fit ticks 5 → 6 on US/EU. Files two applications before lunch — one Sarvam, one the seed-stage YC AI company flagged in last week's red-row. Records a 60-second voice note. Drafts the week's LinkedIn build-in-public post from the accountability ledger itself: *"Week 7: shipped the thing I promised, skipped the application I promised, here's why, here's the commit, here's the new commitment."* The ritual is not magical. It is structural.

**Week 8 retrospective beat.** By Week 8, this journey has changed shape. Profile fit has settled at 6–7 on both segments. The top-10 rankings barely move week over week. The journey's value has migrated entirely from *skill-ranking insight* to *accountability ledger* — which was the point. The product is no longer a newspaper; it is a contract Darko wrote with himself and that the product enforces.

**Capabilities revealed by this journey:**
- Saturday-morning IST cron schedule (not Monday — this is a real product decision)
- Static public HTML report with no auth
- Geo-segmented dual-column output (US/EU + India AI product)
- **Accountability ledger** tracking commitments vs. actions week-over-week
- Profile diff module with **"last updated N weeks ago" freshness nudge**
- **Minimum-experience-threshold distribution strip** at top of report
- Per-company application rationale drawn from actual posting text
- Week-over-week profile fit delta + prior-week report archival
- **Archived past-reports index page** (one-line-per-week history)
- The product must actively fight user inertia via visible un-acted-on commitments (design responsibility, not user discipline)

### Journey 2 — Corpus Is Bad, Kill Criterion Fires *(primary user, failure path)*

**Opening.** Same Saturday morning. Same kitchen. Darko opens the report. The usual two-column layout is replaced by a red banner: *"Kill criterion triggered: corpus 67 postings (below 100 threshold). Extraction accuracy 68% (below 70% threshold). Weekly report generation blocked until recovery action is committed."* Below the banner: a diagnostic block naming the failure source (Greenhouse API returned a 4xx schema change on Thursday's scheduled run), last successful run timestamp, per-source posting counts for the broken run.

**Rising action.** Darko's first instinct is to open the ingest code and debug. The product anticipates this. The banner presents a choice: **`[Fix ingest — 60 minutes allowed]`** or **`[Pivot to CSV fallback — 15 minutes]`**. Clicking "Fix ingest" starts a timer committed to the repo (`debug-attempt-YYYY-MM-DD.log`). When the timer expires, the CSV fallback is forced automatically and the debug attempt is logged. *The product does not trust Darko to follow the kill criterion; it enforces it structurally.*

**Climax.** The tool honestly tells him it is broken and names why. There is no fake top-10 generated from a bad corpus. There is no silent padding with last week's data. There is no "close tab, come back later, pretend it's fine" escape. **The weekly report page refuses to render until the pivot action is committed**, so "avoiding it for an hour" is not an option because there is no report to avoid to.

**Resolution — tired variant.** Darko is already low-state. He does not have the emotional energy to post publicly about failure *in the moment*. He closes the laptop and goes to sleep. **24 hours later, the product emails him automatically**: *"Kill criterion fired yesterday. Here is the 15-minute CSV pivot template. Posting about it is optional and can wait. Do the pivot now."* The email removes the emotional barrier of having to start the pivot and the content in the same session. He does the pivot Sunday morning. Posts about it Tuesday, after the feeling settles. The failure becomes content — on Tuesday's timetable, not Saturday's.

**Ambiguous threshold variant.** What if corpus = 103 (above 100) but extraction accuracy = 68% (below 70%)? One threshold breached, one OK. **The product enters warning mode**, not full-kill mode: banner is yellow not red, report still renders, header reads *"You are in the danger zone — 7 days to recover before full kill fires on next run."* This is more honest than a binary fire.

**Week 8 retrospective beat.** By Week 8, the kill criterion has fired exactly once (this Journey 2 moment in Week 2). The Week-4 public write-up named it as *the most hireable day of the MVP*. A reader of the repo sees: a system designed to fail loudly, a forcing mechanism that prevented the user's reflex to debug past the kill, a tired-variant recovery path that still produced the pivot, and a documented before/after that a tutorial project would never contain.

**Capabilities revealed:**
- Kill-criterion detection as a pipeline stage, checking corpus-size AND per-field eval accuracy before report render
- **Render-blocking forcing mechanism** — kill mode blocks weekly report render entirely
- **60/15 debug-time-box** inside the tool with committed log artifact
- **Warning mode** for ambiguous threshold breaches (one metric breached, one OK)
- **Delayed-handoff email** 24 hours after kill fires, with inline 15-minute pivot template
- Honest failure banner + per-source ingest diagnostic block
- CSV-fallback ingest path (plumbed in Week 1, not added later)
- Auditable corpus-size + eval-accuracy metrics committed per run
- **README section explaining the render-blocking design choice** as signal ("I don't trust myself when I'm tired")

### Journey 3 — The Live Interview Demo *(primary user, Growth-phase, MVP-informing)*

**Preparation beat — dry run with wife (the night before).** Darko explains the tool to his wife across the kitchen table in 2 minutes. Not the full story — just the 60-second version he plans to show in the interview. She asks one clarifying question. He answers. The Rubber Duck Teaching loop from the brainstorming session has rehearsed his mouth at least once before the interview begins. *This is both a behavioral requirement (rehearse) and a product requirement (the demo must be explainable in 2 minutes to a non-technical person).*

**Opening (the interview).** Zoom call with a hiring manager at a seed-stage AI company. Hiring manager: *"Tell me about yourself."* Darko has 45 seconds of a standard opener prepared — 4.5 years backend, Go / Python / JS, recent focus on LLM application engineering. **At the 45-second mark he pivots, deliberately, into a closable offer:** *"The thing I've been doing to learn this space is building a tool — and because I knew we were talking today I ran it against your Ashby board this morning. Want me to show you 60 seconds of it?"* Hiring manager, surprised: *"Yes — go ahead."* This is a closable demo offered inside an *expected* beat, not a cold standing start.

**Rising action.** Darko shares screen. The tool shows a **one-screen stack fingerprint**: company name, 5-bullet role-archetype summary, top-10 technologies extracted from the last 12 public postings, one-sentence LLM-generated observation (*"your last 8 postings all mention eval harnesses but none mention LangChain — is that deliberate?"*). Legible in 10 seconds. Not a dashboard. Not a treemap. One screen.

**Bandwidth-fallback contingency.** Darko's home internet load-sheds at 9 AM IST and the screen share lags. **The product anticipated this.** Before the call, the tool cached a static local HTML of the target company's fingerprint to disk. Darko drops the file onto Google Drive in 10 seconds and pastes the shareable link in the Zoom chat. The demo proceeds without screen-share. *This is an MVP capability hiding inside a Growth-phase journey.*

**Climax (the rewritten honest version).** The hiring manager may or may not be impressed — that is not in Darko's control, and framing it as the success marker is dishonest. **The honest climax is this: Darko opened his mouth to pitch himself, showed the tool instead, and the moment-of-freeze passed — regardless of whether the interviewer engaged with it.** The demo's value is *not freezing*, even if the demo falls flat. That is a robust success definition and it puts the capability squarely inside the confidence-communication loop the brief identified as the root blocker.

**Demo-bombed failure variant.** The hiring manager says *"great, but let's stick to the script."* Darko closes the demo in one action — the tool has a **one-click "close and return to neutral state"** button. Screen-share ends cleanly. No dangling window. 15 seconds lost, not 5 minutes. The freeze did not happen. The interview proceeds normally from a neutral starting point, not from a worse position than if he had never offered the demo. **The demo is closable, not sticky** — this is the core product requirement the journey reveals.

**Resolution.** Darko leaves the call with a second-round invitation *or* he doesn't. Either outcome counts as success if the freeze did not happen. The confidence-communication loop has broken by exposure, not by pitch outcome. He records a voice note in the car on the way back from the office.

**Week 8 retrospective beat.** By Week 8, Darko has offered the demo in 6 interviews. 3 accepted, 3 declined politely. None produced the freeze. Two of the interviews moved to final round. One rejected him after the demo with the comment *"cute but not production scale"* — which he logged as evidence for the Red Team attack he'd already anticipated in the PRD, and which informed a Week-9 improvement to the fingerprint to emphasize extraction accuracy numbers alongside technology names.

**Capabilities revealed:**
- **On-demand single-company ingest** — MVP pipeline must be parameterized by company, not hardcoded to the seed list (architectural requirement that must not be precluded in Week 1)
- **Stack fingerprint one-screen view** (concrete spec: company · 5-bullet archetype summary · top-10 tech · one-sentence observation · legible in 10 seconds)
- **Bandwidth-fallback local HTML cache** of the fingerprint — Growth → **MVP** (moved up)
- **One-click "close and return to neutral state"** for the demo — MVP requirement
- Demo must be rehearse-able in 2 minutes to a non-technical listener
- Fast page load suitable for live demo (no spinners, no 10-second corpus reruns)
- Profile diff must work against a single-company corpus, not just aggregate

### Journey 4a — The Resume Reviewer *(async, reactive, 90-second budget)*

**Prequel beat — the keyword filter.** A non-technical recruiter at a target AI company runs an ATS keyword filter over the resume stack. Darko's resume passes the filter because the top 3 bullets contain every high-signal term: *"Built LLM structured-output extraction pipeline on 500+ live AI engineering job postings, with pgvector retrieval, 20-sample held-out eval harness (10 train / 10 held-out, per-field precision/recall), and a $30 LLM-budget-capped cost profile documented in public write-up."* Every term is an ATS keyword; every term is evidence-backed and hyperlinkable to the repo. **The resume does the first round of hiring-manager-encounter work before the tool ever loads.** Without this, nothing downstream in Journey 4a fires — see **Resume Prerequisite** below.

**Opening (the real scene).** 10:47 PM Thursday. A staff AI engineer at a target company is screening resumes. She has 30 candidates left in a stack of 80. Her default is reject. She has 90 seconds per candidate. Darko's resume is one of them.

**Rising action (stopwatch — everything fits in 90 seconds).** 
- **Seconds 0–15:** She clicks the GitHub link. README loads. First 3 sentences: *"This tool ingests AI engineering job postings from 8 public ATS APIs and ranks skills across the corpus. Eval accuracy: 73% on a held-out set of 10 samples with per-field precision/recall documented in `docs/eval-methodology.md`. Built under a hard $30 LLM spend cap across 4 weeks — spend breakdown in `docs/budget.md`."* **Every sentence contains an empirical differentiator a tutorial project would not have.**
- **Seconds 15–40:** She clicks the live URL. It loads — uptime has been maintained at 99.2% across Weeks 4–16 via Vercel health check + alerting. The Saturday report renders. She scans the two columns and the accountability ledger block.
- **Seconds 40–70:** She scrolls two commit messages. `feat: week-2 kill criterion fired — corpus below threshold, pivoted to CSV fallback per PRD` and `chore: eval accuracy 73% on held-out set, methodology doc committed`. She opens the `docs/eval-methodology.md` file. Three paragraphs explain the train/held-out split, the per-field metrics, the failure cases. She notes that the failure-cases section names 3 specific extractions that went wrong and *why* — annotated.
- **Seconds 70–90:** She opens `loop-b-log.md`. Weekly rows: applications filed, interviews completed, non-frozen interviews, LinkedIn posts. 16 weeks of rows. The file is updated weekly and committed like code. She closes the laptop.

**Climax.** She pings the hiring manager: *"This one's real. Production instincts, evals-first discipline, documented failures, parallel job-search discipline tracked publicly. Not another tutorial portfolio. Talk to him."* The scan took 87 seconds. The decision was made in the first 40.

**Resolution.** Darko's phone buzzes three days later with an interview invitation. The scan happened while he was asleep after night shift. **This is the journey the entire product is architected around** — not the Saturday ritual, not the live demo. This is the moment a stranger encounters the artifact and decides *"this person thinks like us"* on the strength of the README's first three sentences.

**Week 8 retrospective beat.** By Week 8, 12 weeks still remain in the hiring window. The live URL has not gone down. The README has been rewritten twice based on learnings from the Red Team attacks (hypothetical and real). Two of the 9 interviews that happened in Weeks 4–8 traced directly to the GitHub link being clicked during a resume screen — verifiable from interview conversation threads where the reviewer mentioned the repo specifically.

**Capabilities revealed:**
- **README first-paragraph spec** — 3 sentences, each containing one empirical differentiator, load-bearing for the 90-second scan
- **URL uptime ≥99% during Weeks 4–16** + Vercel health check + alert integration — **MVP requirement, not Growth**
- **`docs/eval-methodology.md`** — explicit, committed, read by reviewer
- **Upgraded eval harness** — 10 train / 10 held-out split, per-field precision/recall for 6 fields, regression flag, documented failure cases annotated
- **`docs/budget.md`** — breakdown of $30 spend by ingest / eval / report, with 2–3 decisions the cap forced
- **`loop-b-log.md`** as MVP deliverable — weekly-updated public log of applications filed, interviews, non-frozen interviews, LinkedIn posts, voice notes. **This is the concrete rebuttal to the Red Team attack "you built a tool instead of getting a job."**
- Commit message discipline (legibility as a product property)
- Archived past-reports index page (visible trajectory, not one snapshot)
- Anti-tutorial-project signal requirement in README (empirical differentiators, not adjectives)

### Journey 4b — The LinkedIn Scroll-By *(async, push — validation, not discovery)*

**Framing reset.** The original Journey 4 conflated two distinct distribution paths. This one is explicitly *secondary validation*, not primary discovery. The hiring-lead audience for this journey does not *find* Darko via LinkedIn — they *confirm* Darko via LinkedIn after finding him somewhere else (resume review, referral, event, prior application). The LinkedIn build-in-public thread is a corroboration surface, not an inbound lead-gen channel.

**Opening.** Tuesday afternoon. A VP of Engineering at a mid-stage AI company is considering four candidates for a Week-3 interview slot. Two of the four came through a recruiter. One came through a referral. One (Darko) came through a cold application two weeks ago that passed the keyword filter. The VP does not remember the name. She searches *"Darko job intelligence agent"* on LinkedIn to check whether the GitHub link on the resume is supported by anything else.

**Rising action.** LinkedIn returns Darko's profile. Headline: *"Backend engineer transitioning to AI engineering — building a job market intelligence tool in public. Open to roles in India AI product + US/EU remote."* Below the headline: a **16-post thread** of weekly build-in-public posts, Weeks 1 through current. Week 1 post is honest about the 4.5-year night shift, the fear of interviews, and the plan. Week 2 post is *"I wrote a kill criterion. The kill criterion fired. Here's what I did."* Week 5 post has a **screenshot of the Saturday report** — mobile-legible, publishable, self-contained, no auth required. Week 7 post reflects on the first non-frozen interview.

**Climax.** The VP scrolls fast. She does not read carefully. She does not need to. What she is checking is **consistency** — does the LinkedIn thread match the repo, the commit dates, the claims in the resume bullets? It does. The posts are dated, the commits are dated, the repo is live, the resume bullets are backed. She stops at the Week-5 screenshot and forwards it to the hiring manager with one line: *"This candidate is real. Confirmed."* The candidate advances to the interview slot.

**Resolution.** Darko's interview happens Friday. He never knows that a LinkedIn screenshot tilted a decision on Tuesday. The distribution channel worked in exactly the way it was supposed to: as a *consistency signal* triggered by *primary discovery* elsewhere, not as the originator of the lead.

**Week 8 retrospective beat.** By Week 8, Darko has 8 unbroken weekly LinkedIn posts. Three of them have more than 500 impressions (none viral). One generated an inbound recruiter DM from a second-tier company that he interviewed with but did not advance past second round. But three of the interviews he *did* convert from primary discovery channels were, upon post-interview debrief, confirmed to have been influenced by the LinkedIn thread's consistency. The channel's value is *not its reach*. It is its *corroboration weight on candidates already in consideration*.

**Capabilities revealed:**
- **Shareable weekly visuals as MVP output** — screenshot-friendly, mobile-legible, no-auth-required format of the Saturday report, embeddable in LinkedIn posts
- 16-week unbroken LinkedIn post cadence (user behavior requirement, not code)
- LinkedIn profile headline containing both segments of the dual-geography framing
- Commit dates + post dates + resume bullet dates must remain consistent (auditability of the build-in-public claim)
- Screenshot-style output spec: one image per report, mobile-legible, one headline number (profile fit or accuracy), small-legend footer — optimized for social scroll, not desktop dashboard

### Cross-cutting beat — Tired-Darko recovery capability

The pre-mortem surfaced the single biggest hidden assumption across all four journeys: **they were drafted for the best-case version of the user, not the tired / frozen / demotivated one.** The brief explicitly names discipline as Darko's weakness. A product that depends on sustained user discipline has already failed the brief's #1 risk check.

Concrete product response:
- **Skip-2-weeks nudge email.** If Darko does not open the weekly report page for two consecutive Saturdays, the product emails him on the second Saturday *with the report inline in the email body* — not a link to click. The recovery action requires zero friction.
- **Delayed-handoff email on kill criterion** (already specified in Journey 2) — 24-hour async nudge removes the need to act in-the-moment.
- **Accountability ledger as inertia fighter** (already specified in Journey 1) — the product fights user inertia via visible un-acted-on commitments, not via the user's own discipline.
- **Render-blocking kill criterion** (Journey 2) — enforces the pivot structurally because Darko cannot be trusted to enforce it voluntarily when tired.
- **60/15 debug time-box** (Journey 2) — bounds the developer reflex to fight the kill criterion.
- **Saturday-morning schedule** (Journey 1) — not Monday-morning post-shift, because the ritual must fit the real user, not the fantasy user.

**These are load-bearing product requirements, not soft behavioral hopes.** They are the difference between a tool that depends on Darko's discipline (which will fail) and a tool that actively supports the version of Darko who just finished a night shift (which has a chance).

### Resume Prerequisite *(binding, stated explicitly)*

**This product assumes Darko maintains a resume that survives non-technical ATS keyword screens.** The resume is not a deliverable of this project, but it is a binding prerequisite: if the resume cannot get past the keyword filter at the target companies, nothing downstream in Journey 4a fires and the entire hiring-manager-encounter architecture is inert.

Concrete implication: the Week 0 pre-code spike must include a **resume-bullet rewrite pass** producing 3 evidence-backed top bullets (similar to the example in Journey 4a's prequel beat) that contain the high-signal ATS keywords *and* that are hyperlinkable to the live repo + live URL + `docs/eval-methodology.md`. This is a user action, not a code deliverable, but naming it here prevents the PRD from implicitly assuming the distribution funnel starts at the GitHub link — it actually starts at the resume bullet.

**Growth-scope capability:** The same tool that extracts skills from job postings can extract skills from Darko's own experience bullets and suggest ATS-keyword-optimized rewrites. This is promoted from Vision → Growth in Product Scope (was implicit in Scenario 4 of the brief; now explicit).

### Journey Requirements Summary

| # | Capability | Revealed by | MVP / Growth / Vision | Notes |
|---|---|---|---|---|
| 1 | Saturday-morning IST cron schedule (not Monday) | J1 | **MVP** | Real schedule change, not narrative flourish |
| 2 | Static public HTML report with no auth | J1, J2, J4a | **MVP** | |
| 3 | Geo-segmented dual-column output (US/EU + India AI product) | J1, J4b | **MVP** | Binding — must ship in Week 4 |
| 4 | **Accountability ledger** — tracks commitments vs. actions week-over-week | J1 | **MVP** | New from Pre-mortem — core inertia fighter |
| 5 | Profile diff module + **profile freshness nudge** ("last updated N weeks ago") | J1 | **MVP** | Nudge fires at N ≥ 3 |
| 6 | **Minimum-experience-threshold distribution strip** at top of report | J1 | **MVP** | New from Red Team — defeats credential-bias attack with data |
| 7 | Per-company application rationale drawn from actual posting text | J1 | **MVP** | |
| 8 | Week-over-week profile fit delta + prior-week report archival | J1, J4a | **MVP** | |
| 9 | **Archived past-reports index page** (one-line-per-week history) | J1, J4a | **MVP** | New from Red Team — longitudinal proof no tutorial project has |
| 10 | Kill-criterion detection as a pipeline stage (corpus size + per-field eval accuracy) | J2 | **MVP (binding)** | |
| 11 | **Render-blocking forcing mechanism** — kill mode blocks report render entirely | J2 | **MVP** | Non-negotiable — the point is to remove the option to not act |
| 12 | **60/15 debug time-box** inside the tool with committed log | J2 | **MVP** | Bounds the developer reflex to debug past kill |
| 13 | **Warning mode** for ambiguous threshold breaches | J2 | **MVP** | 7-day recovery window before full kill |
| 14 | **Delayed-handoff email** 24 hours after kill fires with inline pivot template | J2 | **MVP** | Tired-Darko recovery path |
| 15 | Honest failure banner + per-source ingest diagnostic block | J2 | **MVP** | |
| 16 | CSV-fallback ingest path | J2 | **MVP** | Plumbed Week 1, not added later |
| 17 | Auditable corpus-size + eval-accuracy metrics committed per run | J2, J4a | **MVP** | |
| 18 | **README section explaining render-blocking design choice** ("I don't trust myself tired") | J2, J4a | **MVP** | Anti-performance-of-rigor signal |
| 19 | Extraction pipeline parameterized by company (not baked to seed list) | J3 | **MVP (architectural)** | Must not be precluded in Week 1 — enables Growth single-company ingest |
| 20 | On-demand single-company ingest endpoint | J3 | **Growth** | Required for live demo use case |
| 21 | **Stack fingerprint one-screen view** (concrete spec: company · 5-bullet archetype summary · top-10 tech · one-sentence observation) | J3 | **Growth** | Must be rehearse-able in 2 min to a non-technical listener |
| 22 | **Bandwidth-fallback local HTML cache** of target company fingerprint | J3 | **MVP** | Moved from Growth → MVP by pre-mortem |
| 23 | **One-click "close and return to neutral state"** for live demo | J3 | **MVP** | Demo must be closable, not sticky |
| 24 | Fast page load suitable for live demo (no spinners on hot path) | J3 | **MVP** | |
| 25 | Profile diff must work against a single-company corpus | J3 | **Growth** | |
| 26 | **README first-paragraph spec** — 3 sentences, each containing one empirical differentiator | J4a | **MVP** | Load-bearing for the 90-second scan |
| 27 | **URL uptime ≥99% during Weeks 4–16** + Vercel health check + alert | J4a | **MVP** | Moved from "nice to have" → binding |
| 28 | **`docs/eval-methodology.md`** — explicit committed methodology doc | J4a | **MVP** | Craft-signal surface per Red Team |
| 29 | **Upgraded eval harness spec**: 10 train / 10 held-out split, per-field precision/recall (6 fields), regression flag, annotated failure cases | J4a | **MVP** | Upgraded from naive accuracy-only after Red Team Attack #2 |
| 30 | **`docs/budget.md`** — $30 spend breakdown + 2–3 decisions the cap forced | J4a | **MVP** | Reframes $30 from "poverty cosplay" to "constraint in experiment" |
| 31 | **`loop-b-log.md`** — weekly-updated public log of applications, interviews, non-frozen interviews, posts, voice notes | J4a | **MVP** | Concrete rebuttal to "procrastination with commit history" attack |
| 32 | Commit message discipline (legibility as a product property) | J4a | **MVP** | |
| 33 | **Anti-tutorial-project signal requirement** — first 3 README sentences must contain empirical differentiators a tutorial would not have | J4a | **MVP** | |
| 34 | **Shareable weekly visuals** — screenshot-friendly, mobile-legible, no-auth-required format of the Saturday report | J4b | **MVP** | Enables LinkedIn build-in-public corroboration path |
| 35 | 16-week unbroken LinkedIn post cadence | J4b | **MVP (behavioral)** | User action, not code |
| 36 | LinkedIn profile headline containing both dual-geography segments | J4b | **MVP (behavioral)** | |
| 37 | **Skip-2-weeks nudge email** with inline report (not a link) | Cross-cutting | **MVP** | Tired-Darko recovery — zero-friction |
| 38 | **Resume-bullet ATS optimization capability** (extract skills from user experience bullets, suggest optimized rewrites) | Resume Prerequisite | **Growth** | Promoted from Vision → Growth |
| 39 | Resume-bullet rewrite pass as a Week 0 user action (not code) | Resume Prerequisite | **MVP (user action)** | Named prerequisite, not deliverable |

> **Note on the growth-to-MVP migrations.** Five items moved from Growth or Vision up to MVP as a result of the Pre-mortem and Red Team pressure-testing: bandwidth-fallback local HTML (#22), one-click demo close (#23), URL uptime monitoring (#27), shareable weekly visuals (#34), and the upgraded eval harness spec (#29). These migrations increase Week 1–4 scope by roughly 4–6 hours of implementation work. This is a real scope trade and must be reflected in the Sprint Plan / Implementation section later in this PRD.

## Web App–Specific Requirements

### Project-Type Overview

This product is classified as a `web_app` but deviates from the standard single-page or multi-page app pattern in a meaningful way: **the frontend is static HTML generated by a Python batch pipeline**, not a live server-rendered or client-rendered application. There is no JavaScript framework, no API layer the browser calls, and no authentication surface. The "web app" is the output artifact — a read-only HTML page that the cron job writes to Vercel-hosted storage once per week.

Key answers to the web_app template questions:

| Question | Answer |
|---|---|
| **SPA or MPA?** | Neither — static HTML generated by Python (Jinja2 or f-strings). One index.html + one archive.html. |
| **Browser support** | Modern browsers only (Chrome, Firefox, Safari — last 2 major versions). No IE, no polyfills. |
| **SEO** | Not applicable. No public discovery surface. Skipped per `skip_sections` config. |
| **Real-time data** | No. Weekly batch output — no websockets, no live polling. |
| **Accessibility** | Basic WCAG 2.1 Level A. Contrast ratios on the report color-coding. Screen-reader-safe. |
| **Responsive design** | Three surfaces: desktop dashboard (primary), mobile scroll (LinkedIn screenshot source), Zoom screen-share (legible at 1080p with half-screen share). |

**Performance targets (static HTML, Vercel CDN):**

| Metric | Target | Rationale |
|---|---|---|
| First Contentful Paint (FCP) | < 1.5 s | Live demo surface — reviewer is watching |
| Largest Contentful Paint (LCP) | < 2.5 s | Core Web Vitals passing (Vercel Analytics) |
| Total page weight | < 500 KB | No bundler, no JS framework — this should be trivially achievable |
| Time to interactive | Same as FCP | Static HTML with no JS = instant interaction |

**Skipped sections (not applicable to this project type):** SEO strategy, progressive web app (PWA) manifest, service workers, client-side routing, internationalization (i18n), third-party script management.

### Technical Architecture Considerations

This section documents the full technical stack discovered across all previous PRD steps. It goes beyond the standard `web_app` template to capture the backend pipeline architecture that drives the frontend output.

#### 1. Python Ingest Pipeline

- **Runtime:** Python 3.12+, structured as a monorepo with clearly separated modules: `ingest/`, `extract/`, `rank/`, `diff/`, `report/`, `eval/`, `notify/`.
- **Source adapters:** 8 source adapters, each parameterized by company slug (not hardcoded seed list): Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, YC WaaS, HN thread parser.
- **Key constraint:** adapters must accept a company slug parameter so that on-demand single-company ingest (for the live interview demo) works without a different code path.
- **Cron schedule:** Saturday morning IST (Friday evening UTC/US time) via GitHub Actions.
- **Run logging:** per-run corpus size, per-source count, LLM spend, and eval accuracy committed to the repo as a JSON artifact — auditable, not just dashboard-visible.

#### 2. LLM Extraction Layer

- **Provider:** Claude (claude-haiku-4-5 for cost-efficiency, fallback to claude-sonnet-4-6 for edge cases) accessed via **Vercel AI Gateway** — single endpoint, spend tracking, model abstraction layer.
- **Structured output:** JSON schema with 6 target fields: `skills` (list), `seniority` (enum), `tech_stack` (list), `salary_band` (dict with currency + range), `remote_policy` (enum), `role_archetype` (enum: LLM App Engineer / AI Product Engineer / Agent Engineer / ML Platform Engineer).
- **Batching:** 20 postings per LLM call. Prompt includes batch of 20 posting texts, returns array of 20 structured objects.
- **Caching:** prompt-level caching via Vercel AI Gateway. Postings seen in a prior run are not re-extracted — Postgres `extracted_at` timestamp is the cache key.
- **Budget enforcement:** total spend tracked against $30 hard cap. If spend ≥ $28 (buffer), ingest is frozen and an alert email fires before the cron runs the next batch.
- **Extraction configuration:** all prompts versioned in `prompts/` directory. Prompt version recorded with each posting row in Postgres — enables before/after eval comparison when prompts change.

#### 3. Storage — Neon Postgres + pgvector

- **Schema (minimum viable):**
  - `postings(id, company_slug, ats_source, posting_text, extracted_at, prompt_version, skills jsonb, seniority text, tech_stack jsonb, salary_band jsonb, remote_policy text, role_archetype text, geo_segment text)`
  - `weekly_reports(id, run_date, corpus_size, per_source_counts jsonb, eval_accuracy float, llm_spend_usd float, report_html text, geo_us_eu jsonb, geo_india jsonb)`
  - `profile(id, updated_at, skills jsonb, experience_bullets text, seniority_self_assessed text)`
  - `accountability_log(id, week_date, commitments jsonb, actions jsonb, gap_flags jsonb)`
  - `eval_samples(id, posting_id, label_set text, labeled_at, fields jsonb, is_train bool)`
- **pgvector:** `postings.embedding vector(1536)` — enables semantic skill clustering and profile semantic diff (Growth feature; column added in MVP migration, populated in Growth).
- **Connection:** Neon serverless driver. No persistent connection pool needed for weekly batch.

#### 4. Eval Harness

- **Structure:** 20 hand-labeled postings — 10 train (prompt tuning), 10 held-out (accuracy measurement). Split is fixed; the 10 held-out postings are never used to tune prompts.
- **Metrics:** per-field precision and recall for each of the 6 target fields. Aggregate accuracy = mean across fields. Regression flag fires if aggregate accuracy drops > 3 percentage points from prior run.
- **Output:** `eval/results/YYYY-WW.json` committed to repo after each run. `docs/eval-methodology.md` explains the split, the metrics, and 3 annotated failure cases.
- **Kill criterion integration:** if held-out accuracy < 70% on any weekly run, the pipeline sets `kill_criterion_fired = True` before generating the report. Report render is blocked (Journey 2 render-blocking mechanism).

#### 5. Profile Diff Engine

- **Input:** `profile.yaml` (human-edited, version-controlled). Tracks: skills list, seniority, tech stack, years of experience, geo preference.
- **Diff logic:** set intersection / set difference against the week's ranked skill list per geo segment. Profile fit = (skills in top-30 market list) / 30.
- **Freshness tracking:** `profile.updated_at` timestamp. If `now - updated_at > 21 days`, a soft nudge renders above the profile-fit block on the report.

#### 6. Accountability Ledger

- **Storage:** `accountability_log` Postgres table (schema above) — or equivalent JSONL committed to repo if Postgres feels heavyweight for this use case (implementation decision, not PRD decision).
- **Schema per week:** `{ week_date, commitments: [{type, description, committed_at}], actions: [{type, description, completed_at, linked_commit}], gap_flags: [{commitment_id, status: "missed"|"late"|"partial"}] }`.
- **Report rendering:** accountability block always renders below the skill rankings, even if gap_flags is empty. The block is never hidden — this is a product constraint, not a UI preference.
- **Red-flagging:** commitments with `status: "missed"` for 2+ consecutive weeks are rendered in red with a count badge.

#### 7. Email Notifications

- **Provider:** Resend free tier (100 emails/day, more than sufficient for 1 user).
- **Two notification types:**
  - **Kill-criterion delayed-handoff email:** fires 24 hours after `kill_criterion_fired = True`. Subject: *"Kill criterion fired yesterday — 15-minute CSV pivot template inside."* Body includes the inline pivot template and the diagnostic block from the failed run.
  - **Skip-2-weeks nudge email:** fires if `weekly_reports.run_date` has no row for the current Saturday AND the prior Saturday. Subject: *"Two Saturdays missed — here's your report."* Body includes the full report HTML inline (not a link).
- **Implementation:** GitHub Actions step after the cron run, conditioned on `kill_criterion_fired` or `consecutive_missed_runs >= 2`.

#### 8. Report Generation + Deployment

- **Templating:** Jinja2 (preferred) or Python f-strings. No JavaScript templating engine — output is server-side HTML.
- **Report structure (one page per weekly run):**
  - Header: run date, corpus size, per-source breakdown
  - Two-column geo-segmented section: US/EU remote top-10 / India AI product top-10
  - Minimum-experience-threshold distribution strip
  - Accountability ledger block
  - Profile diff block with freshness nudge if stale
  - Footer: known corpus gaps, ingest source list, N postings per source
  - One-click demo close button (visible when accessed from a specific URL parameter — `?demo=true`)
- **Archive page (`/archive`):** one row per week, date + corpus size + accuracy + commit link. Human-readable longitudinal history.
- **Static screenshot export:** a shareable OpenGraph image (`og:image`) auto-generated per weekly report — cropped to the two-column top-10 block, mobile-legible, embeddable in LinkedIn posts without any manual screenshot step.
- **Deployment:** Vercel. `vercel --prod` triggered from GitHub Actions after report HTML is written. Vercel health check + alert configured for ≥99% uptime during Weeks 4–16.
- **Local bandwidth-fallback:** the pipeline also writes a local HTML snapshot of the target-company fingerprint to `cache/fingerprint-{company_slug}-{date}.html` before each run completes — enables the Zoom-demo offline fallback (Journey 3).

### Implementation Considerations

- **Monorepo layout:** `src/ingest/`, `src/extract/`, `src/rank/`, `src/diff/`, `src/report/`, `src/eval/`, `src/notify/`, `prompts/`, `data/`, `docs/`, `cache/`, `tests/`.
- **Testing strategy:** unit tests for each module's pure functions (extraction schema validation, diff logic, ranking aggregation). Integration test for one full pipeline run against a 5-posting fixture corpus. No mocking of the LLM call in integration tests — use a real Haiku call against a fixed prompt to catch schema regressions.
- **CI/CD:** GitHub Actions. Two workflows: (1) cron — Saturday 02:00 UTC, runs full pipeline, commits eval result, deploys to Vercel; (2) PR check — runs unit tests + eval regression check on any branch touching `src/` or `prompts/`.
- **Local dev:** `.env.local` for `ANTHROPIC_API_KEY`, `DATABASE_URL`, `RESEND_API_KEY`. `make run-local` runs the full pipeline against the seed-50 list without deploying. `make eval` runs the eval harness only (no ingest, no report gen).
- **Secrets management:** GitHub Actions secrets for production. No secrets in repo. `.env.example` committed with placeholder keys and comments explaining each variable.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-solving MVP — the minimum automation that solves one user's market-opacity problem and functions as a credible hireability artifact. The MVP is done when the weekly geo-segmented skill-gap report is live at a public URL, the eval harness reports accuracy on a held-out set, and the accountability ledger is rendering. Not a moment earlier. Not a line of Growth code sooner.

**MVP Philosophy constraint (carried from the brief):** Any build milestone that ships without its corresponding Loop B milestone (applications, voice notes, LinkedIn post) has failed its specification. The tool is subordinate to the career outcome. If the tool is ever the reason interviewing is not happening, it has failed — regardless of technical completeness.

**Resource requirements:** 1 developer (Darko), 15–20 hr/week, 4-week build window. Hard LLM budget: $30 total. No external collaborators, no contractors, no reviewers until the public write-up.

### MVP Feature Set (Phase 1) — Weeks 0–4

**Core journeys supported:** Journey 1 (Saturday Skill-Gap Report), Journey 2 (Kill Criterion + Recovery), and the asynchronous hiring-manager encounter embedded in Journey 4a. Journey 3 (Live Interview Demo) and 4b (LinkedIn Scroll-By) are MVP-informing (architectural constraint from J3, shareable visual from J4b) but the journeys themselves are Growth.

**Must-Have Capabilities — consolidated from Journey Requirements Summary:**

| Capability | Week target | Notes |
|---|---|---|
| Week 0 empirical spike: 15 India careers pages → ATS CSV | Week 0 | Blocking prerequisite for seed list |
| Week 0 resume-bullet ATS optimization pass | Week 0 | User action, not code |
| 8-source ingest pipeline, parameterized by company | Week 1 | Architectural constraint — not hardcoded |
| Neon Postgres schema (postings, weekly_reports, profile, accountability_log, eval_samples) | Week 1 | Full schema migrated in Week 1 even if Growth columns are empty |
| LLM extraction via Vercel AI Gateway (Claude Haiku), 6-field schema, 20-posting batches | Week 1–2 | Prompt v1 committed to `prompts/` |
| CSV-fallback ingest path plumbed | Week 1 | Plumbed early, not bolted on after kill criterion fires |
| 20-sample eval harness (10 train / 10 held-out), per-field P/R, regression flag | Week 2 | Held-out set locked before prompts are tuned |
| Kill-criterion detection as pipeline stage (corpus < 100 OR accuracy < 70%) | Week 2 | Fires before report render |
| Render-blocking forcing mechanism (kill mode blocks report HTML generation) | Week 2 | Non-negotiable — removes option to ignore |
| 60/15 debug time-box with committed log | Week 2 | Bounds developer reflex |
| Warning mode for ambiguous threshold breaches | Week 2 | Yellow banner, 7-day recovery window |
| Delayed-handoff email (24h after kill, inline pivot template) | Week 2 | Resend free tier |
| Week-2 JobSpy spike (2 hours, documented decision rule) | Week 2 | Either outcome is a craft-signal artifact |
| Skill ranker + co-occurrence clusters + salary-stack correlations | Week 3 | Core product output |
| Profile diff engine + profile freshness nudge (≥ 21 days stale) | Week 3 | |
| Accountability ledger (Postgres table, commitments vs. actions, gap flags) | Week 3 | Renders below rankings — never hidden |
| Geo-segmented report (US/EU remote top-10 + India AI product top-10, side-by-side) | Week 4 | Binding — must ship in Week 4 |
| Minimum-experience-threshold distribution strip | Week 4 | Defeats credential-bias attack with data |
| Shareable static OpenGraph image auto-generated per weekly report | Week 4 | LinkedIn embed without manual screenshot |
| Archived past-reports index page (`/archive`) | Week 4 | Longitudinal proof |
| Bandwidth-fallback local HTML cache of company fingerprint | Week 4 | Demo offline fallback |
| One-click "close and return to neutral state" for demo | Week 4 | URL parameter `?demo=true` triggers close button |
| Static public HTML deployed to Vercel + Vercel health check + ≥99% uptime alert | Week 4 | |
| Saturday IST cron via GitHub Actions | Week 4 | Not Monday |
| Skip-2-weeks nudge email with inline report | Week 4 | Zero-friction recovery |
| `docs/eval-methodology.md`, `docs/budget.md`, `loop-b-log.md` committed | Week 4 | Craft-signal documents, not afterthoughts |
| Public write-up (honest, includes what broke and accuracy numbers) | End of Week 4 | LinkedIn + blog |

**Must-Have Loop B (behavioral, binding):**
- 5 applications/week from Week 1, every week
- First voice note, Week 1
- First LinkedIn build-in-public post, Week 1 (honest — includes fear + 4.5 years)
- `loop-b-log.md` updated weekly like code

### Post-MVP Features

**Phase 2 — Growth (Weeks 5–12, Go Fight Mode)**

Trigger: MVP deployed and Loop B running. Feature work capped at ≤5 hr/week. Priority is applications (10/week), not shipping.

| Capability | Notes |
|---|---|
| On-demand single-company ingest endpoint | Required for live interview demo (Growth journey) |
| Stack fingerprint one-screen view (company · 5-bullet archetype · top-10 tech · one-sentence observation) | Live interview demo surface |
| Interview Prep Agent | Takes a posting, generates likely questions, supports voice-based mock interviews with LLM feedback. Direct countermeasure to the user's named root blocker (fear of interviews). Deliberately cut from MVP for scope discipline. |
| Per-company interview briefing | Ingest a specific company's full job board on demand, generate a stack fingerprint quotable in the first 5 minutes of the call. Highest-leverage interview demo. |
| Cover note generation | Diff a specific posting against profile, generate evidence-first application bullets. |
| Weekly "State of AI Hiring" auto-post | Corpus delta → LinkedIn post, auto-generated. Distribution flywheel on one cron job. |
| Profile diff against single-company corpus | Required for cover note generation. |
| JobSpy integration in production | Only if Week-2 spike cleared ≥30% unique threshold. |
| Resume-bullet ATS optimization | Extract skills from user experience bullets, suggest optimized rewrites. Promoted from Vision → Growth per Resume Prerequisite section. |
| pgvector embeddings populated | Column added in MVP schema; populated in Growth for semantic clustering. |
| Public Hugging Face dataset | Weekly update. Inbound researcher traffic, citation surface. |

**Phase 3 — Vision (Post-Hire, Month 3+)**

| Capability | Notes |
|---|---|
| Unified personal AI platform | Shared backend across Job Intelligence + Interview Prep + Cover Note + Content Pipeline. The bottom-up earned version of the 9-module idea brief. |
| Content Pipeline Agent | Git commits → LinkedIn post drafts → distribution queue. Closes the build-in-public loop without manual content effort. |
| Studio Aalekh integration | Art catalog, pricing agent, client chatbot. Month 3+ post-hire territory. |
| Open-source artifact for other backend-to-AI transitioners | Documented seed list template, reusable eval harness, honest case study. |
| Wellfound / Naukri / Workday ingest via paid scrapers | Only if, post-hire, the maintenance cost is justified by a use case that did not exist during MVP. |
| Multi-user / accounts / auth / billing | Not before there is evidence of demand from the Growth-phase public artifact. |

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Likelihood | Mitigation |
|---|---|---|
| LLM extraction accuracy < 70% on held-out set | Medium | Kill criterion fires → CSV fallback. Prompt v1 tuned on 10 train samples before held-out is ever measured. If accuracy stalls at 65–68%, cut scope (fewer fields, better prompts) rather than chase 70% on 6 fields. |
| Public ATS API schema change mid-run | Medium | Per-source ingest logged. `debug-attempt-YYYY-MM-DD.log` committed. 60/15 debug time-box prevents over-investment in fixing broken adapters. |
| India company corpus coverage weaker than assumed | Medium | Week-0 empirical spike is a binding pre-code action. If ≥6 of the 15 India companies use unsupported ATSs, adjust geo-weighting expectations and document in Known Corpus Gaps. |
| $30 LLM budget exceeded before Week 4 | Low | Batching (20 postings/call), prompt caching, Haiku model default, budget alert at $28, ingest freeze if cap hit. Architecture forces cost discipline. |
| Vercel build or deployment failure | Low | Standard Vercel CI. Static HTML — no runtime errors possible at serve time. Health check alert catches any deployment outage within 5 minutes. |

**Market / Career Risks:**

| Risk | Likelihood | Mitigation |
|---|---|---|
| 16-week window closes without offer conversation | Medium | Kill criteria at Weeks 2/4/8 progressively shift time from build to interview. Week 8 trigger: Go Fight Mode (applications double, feature work stops). The tool is not the career outcome — it is one of three levers. |
| AI engineering hiring market contracts or freezes | Low-medium | Dual-geography framing (US/EU remote + India AI product) provides two independent market segments. India AI captive centers (Microsoft India AI, Google India, etc.) are more insulated from US hiring cycles. |
| Hiring managers dismiss the project as "toy" | Low | Predicted Red Team attack. Mitigated by: eval harness with per-field accuracy, `docs/eval-methodology.md`, $30 spend discipline, `loop-b-log.md` as parallel job-search evidence. The README first paragraph names the empirical differentiators explicitly. |

**Resource Risks:**

| Risk | Likelihood | Mitigation |
|---|---|---|
| Night shift schedule leaves insufficient build time | High | Saturday-morning IST cron + Saturday ritual is the primary weekly engagement window. Weekly 15-20 hr estimate assumes 3 weekday evenings + Saturday. Kill criteria protect against over-building under time pressure. |
| Scope creep from interesting technical problems | High (#1 named risk in the brief) | Kill criteria. Loop B binding requirements (5 apps/week is a requirement, not a goal). Explicit non-goals in Project Classification. The render-blocking kill criterion removes the "I'll just fix this one more thing" escape route. |
| Energy depletion from simultaneous build + job search | Medium | Tired-Darko recovery paths (delayed-handoff email, skip-2-weeks nudge, Saturday ritual not Monday) are product features explicitly designed for this scenario. The tool works for low-energy Darko, not just ideal Darko. |

## Functional Requirements

### Job Data Ingestion

- **FR1:** Pipeline can fetch job postings from the Greenhouse public API for any company slug
- **FR2:** Pipeline can fetch job postings from the Lever public API for any company slug
- **FR3:** Pipeline can fetch job postings from the Ashby public API for any company slug
- **FR4:** Pipeline can fetch job postings from the Workable, Recruitee, and Personio public APIs for any company slug
- **FR5:** Pipeline can fetch job postings from the Y Combinator WaaS public API
- **FR6:** Pipeline can parse the current HN "Who's Hiring" monthly thread and extract AI engineering postings
- **FR7:** Pipeline can ingest postings for a single specified company on demand, outside the weekly seed-list run
- **FR8:** Pipeline can fall back to a user-supplied CSV of postings when live ingest sources are unavailable or kill-criterion-frozen
- **FR9:** Pipeline records per-source posting counts, run timestamp, and success/failure status per source per run

### Skill Extraction & Analysis

- **FR10:** Pipeline can extract structured signals — skills, seniority, tech stack, salary band, remote policy, role archetype — from a job posting via LLM
- **FR11:** Pipeline can process postings in batches and skip postings already extracted in a prior run
- **FR12:** Pipeline can record which prompt version produced each posting's extraction result
- **FR13:** Pipeline can rank skills by frequency across the full corpus, separately per geo segment
- **FR14:** Pipeline can compute skill co-occurrence clusters from the weekly corpus
- **FR15:** Pipeline can compute salary-band / tech-stack correlations from postings with disclosed salary data
- **FR16:** Pipeline can assign each posting to a geo segment (US/EU remote or India-based AI product) based on extracted remote policy and company location
- **FR17:** Pipeline can compute a minimum-experience-threshold distribution across the corpus (% postings with no stated minimum / 3+ / 5+ / senior-only)

### Profile Management & Diffing

- **FR18:** User can update their skills, seniority, tech stack, years of experience, and geo preference via a version-controlled profile file
- **FR19:** Pipeline can compute a profile fit score against the weekly top-30 ranked skills per geo segment
- **FR20:** Pipeline can generate a skill-gap diff showing which top-ranked market skills are absent from the user's profile, per geo segment
- **FR21:** Report can display a profile freshness warning when the profile has not been updated in ≥21 days

### Accountability & Behavioral Enforcement

- **FR22:** User can log weekly commitments and actions (applications filed, interviews completed, LinkedIn posts, voice notes, commits) against a structured schema
- **FR23:** Report can display the accountability ledger showing prior-week commitments vs. actions, with gap flags, below the skill rankings — always visible, never hidden
- **FR24:** Report can visually distinguish commitments that have been missed for 2 or more consecutive weeks
- **FR25:** Pipeline can enforce a render-blocking kill criterion that prevents the weekly report from being generated when corpus size < 100 OR extraction accuracy < 70%
- **FR26:** Pipeline can enter a non-blocking warning mode when exactly one of the two kill-criterion thresholds is breached, displaying a 7-day recovery notice on the report
- **FR27:** Pipeline can bound a user-initiated ingest debug session to 60 minutes before forcing a CSV fallback and committing a debug log to the repository
- **FR28:** System can send an email to the user 24 hours after a kill criterion fires, containing an inline CSV pivot template and the run diagnostic block
- **FR29:** System can send an email to the user with the weekly report body inline when the report page has not been accessed for 2 consecutive Saturdays

### Report Generation & Publishing

- **FR30:** Report viewer can access the weekly skill-gap report at a public URL without authentication
- **FR31:** Report can display top-10 skills for the US/EU remote segment and top-10 for the India-based AI product segment, side-by-side in a two-column layout
- **FR32:** Report can display the minimum-experience-threshold distribution strip at the top of each weekly report
- **FR33:** Report can display the week-over-week profile fit score delta vs. the prior week per geo segment
- **FR34:** Pipeline can publish the weekly report to a public URL via an automated deployment on the weekly cron schedule
- **FR35:** Pipeline can generate a shareable static image per weekly report, sized and formatted for mobile readability and social-platform embedding
- **FR36:** Report viewer can browse an archived index of all past weekly reports at a public `/archive` URL
- **FR37:** Report can render a one-click demo-close button that returns the view to a neutral state when the page is accessed with a designated URL parameter

### Evaluation & Quality Assurance

- **FR38:** User can create and maintain a hand-labeled evaluation set of job postings annotated against the 6-field extraction schema, with a fixed train/held-out split
- **FR39:** Pipeline can measure per-field precision and recall on the held-out evaluation set after each extraction run and produce a structured result artifact committed to the repository
- **FR40:** Pipeline can detect a regression when aggregate extraction accuracy drops more than 3 percentage points from the prior run and flag it in the run output
- **FR41:** Pipeline can commit a run-summary artifact per weekly execution (corpus size, per-source counts, LLM spend, extraction accuracy) to the public repository
- **FR42:** Pipeline can track cumulative LLM spend against a $30 hard budget cap and freeze ingest before the next batch run if spend has reached a configurable alert threshold

### Demo & Portfolio Artifacts

- **FR43:** Pipeline can generate a company stack fingerprint on demand (role-archetype summary, top-10 extracted technologies, one-sentence LLM-generated observation) for any company in the ingest corpus
- **FR44:** Pipeline can write a static local HTML copy of the most recently generated company fingerprint to disk for offline use
- **FR45:** User can view the company stack fingerprint in a single-screen layout suitable for live screen-share presentation
- **FR46:** User can view a publicly accessible weekly log of Loop B execution metrics — applications filed, interviews completed, non-frozen interviews, LinkedIn posts, voice notes — updated weekly
- **FR47:** Pipeline can commit required craft-signal documentation artifacts (eval methodology, LLM spend breakdown with decisions forced by the cap, annotated extraction failure cases) to the public repository as versioned files

## Non-Functional Requirements

### Performance

Performance matters for two surfaces: the live interview demo (a reviewer is watching the page load in real time) and the static report (a hiring manager has a 90-second attention budget). The batch pipeline has a secondary performance constraint driven by the $30 LLM budget ceiling.

- **NFR-P1:** Report page First Contentful Paint < 1.5s measured from Vercel CDN edge for users in India and the US (the two primary viewer segments)
- **NFR-P2:** Report page Largest Contentful Paint < 2.5s (Core Web Vitals green on Vercel Analytics)
- **NFR-P3:** Total report page weight < 500KB — no JavaScript framework, no CDN-loaded libraries, no web fonts with large subset ranges
- **NFR-P4:** Company stack fingerprint page renders in < 2s on the hot path — the pipeline must not re-run corpus extraction during a live demo session; fingerprint data is pre-computed and cached
- **NFR-P5:** Full weekly pipeline run (ingest → extract → rank → diff → report → deploy) completes within 60 minutes of the Saturday cron trigger, ensuring the report is live before Darko opens his laptop Saturday morning IST

### Security

This product has an intentionally minimal security surface. There is no authentication layer, no user account system, and no personally identifiable information beyond a single user's own skills profile. The primary security risk is accidental credential exposure in a public repository.

- **NFR-S1:** No API keys, database connection strings, or service credentials appear in the public repository at any time — enforced via `.gitignore` and a pre-commit hook that blocks commits containing strings matching known credential patterns
- **NFR-S2:** All external service credentials (Anthropic via Vercel AI Gateway, Neon Postgres, Resend) are stored in GitHub Actions secrets for production runs and in a gitignored `.env.local` for local development; `.env.example` with placeholder values is the only credential-related file committed
- **NFR-S3:** The weekly report, archive index, and company fingerprint pages are intentionally public and unauthenticated — this is an explicit product decision (portfolio artifact), not a security gap; it must be documented as such in the README to prevent future "fix" attempts

### Reliability

Reliability is a product requirement for this project, not just an engineering concern. A hiring manager who clicks the URL and finds it down has completed the 90-second scan negatively. The cron run must produce an auditable result with no silent failures.

- **NFR-R1:** Public report URL maintains ≥99% availability during Weeks 4–16 — monitored via Vercel uptime health checks; an alert triggers within 5 minutes of any outage exceeding 2 consecutive failed checks
- **NFR-R2:** Every weekly pipeline run produces a committed output — either a `run-summary-YYYY-WW.json` artifact (success) or a `kill-criterion-fired-YYYY-WW.json` artifact (failure) — with no silent or partial failures that leave the repository in an ambiguous state
- **NFR-R3:** Kill-criterion delayed-handoff email delivers within 5 minutes of the kill condition being logged (not 24 hours — the 24-hour delay is a deliberate product decision for Darko's recovery path, but the system must reliably trigger at the right moment)
- **NFR-R4:** Skip-2-weeks nudge email delivers on the second consecutive missed Saturday within a 30-minute window of the cron run completing

### Integration

Eight ingest adapters, one LLM provider (via gateway), one email provider, one deployment platform, and one database. Each integration has a distinct failure mode; the pipeline must not treat any single adapter failure as a total run failure.

- **NFR-I1:** A single ingest adapter failure does not abort the pipeline run — the failed source is logged with its error, the run continues with the remaining sources, and the per-source diagnostic block in the report reflects the failure honestly
- **NFR-I2:** All LLM calls route exclusively through Vercel AI Gateway — no direct Anthropic API calls in application code; this is a hard rule enforced by the gateway being the only location where `ANTHROPIC_API_KEY` is configured
- **NFR-I3:** LLM extraction batches tolerate partial structural failures — if a batch of 20 postings returns fewer than 20 valid structured objects, the valid objects are committed and the failed posting IDs are logged; the pipeline does not retry indefinitely or block the run
- **NFR-I4:** Vercel deployment step is non-blocking for the pipeline logic — if the Vercel deploy fails, the pipeline commits the run-summary artifact and sends an alert, but the ingest and extraction data are preserved in Postgres regardless of deploy outcome

### Accessibility

This product is not a broad public web service, but it has three specific accessibility requirements tied to its distribution function: Zoom demo legibility, LinkedIn screenshot readability, and basic screen-reader compatibility for the public portfolio signal.

- **NFR-A1:** All color-coded report elements (skill rankings, gap flags, kill-criterion status) include text labels or icons alongside color — color is never the sole differentiator; contrast ratio ≥ 4.5:1 on all primary text (WCAG 2.1 Level AA for text, Level A overall)
- **NFR-A2:** Report layout is legible during a Zoom screen-share at 1080p with the browser window occupying approximately half the screen (effective viewport width ≥ 640px) — the two-column geo-segmented layout must not collapse to an unreadable single column at this width
- **NFR-A3:** The auto-generated OpenGraph static image displays the key headline number (profile fit score or top skill) in text legible at mobile thumbnail sizes (minimum 16px rendered equivalent at 375px width)

