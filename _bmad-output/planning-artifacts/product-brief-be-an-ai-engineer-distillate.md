---
title: "Product Brief Distillate: Job Intelligence Agent"
type: llm-distillate
source: "product-brief-be-an-ai-engineer.md"
created: "2026-04-14"
purpose: "Token-efficient context for downstream PRD creation"
---

# Job Intelligence Agent — Detail Pack

Dense context pack for the PRD workflow. Each bullet is self-contained.

## Core Identity

- **Product:** Personal AI tool that ingests AI engineering job postings, extracts structured signals via LLM, ranks skills across the corpus, and outputs a weekly skill-gap report for one user (Darko).
- **Dual purpose:** (a) personal career intelligence for Darko's own job search; (b) public portfolio proof-of-skill for AI engineering interviews.
- **Thesis:** One project doing triple duty (curriculum + intelligence + proof) beats many shallow tutorial projects. The build _is_ the curriculum — every in-demand AI skill gets learned by being used to build the ranker itself.
- **MVP duration:** 4 weeks (cut from originally-scoped 6 weeks after skeptic review).
- **Time budget:** 15–20 hrs/week. Non-negotiable — over-budget weeks steal from sleep + Studio Aalekh (wife's studio).
- **LLM budget cap:** $30 total for first 4 weeks. Forces caching and batching discipline from Day 1.

## User Context (critical for scoping every decision)

- **User = Darko.** Backend developer, 4.5 years at first job, Go / Python / JS. Based in India (night-shift schedule). Toxic workplace, urgent escape motive.
- **Target roles:** AI Engineer, LLM Engineer, Applied AI Engineer, AI Product Engineer. Remote-friendly for US/EU companies (salary-arbitrage play).
- **Salary floor (walk-away line):** +50% over current base. Stretch: 2–3x (from brainstorming). Daytime hours + non-toxic team are non-negotiable.
- **Real blocker named by user in brainstorming:** fear of interviews + confidence-communication loop. NOT skills. Tech can be learned fast; fear requires exposure therapy.
- **User's superpower:** rapid learning by doing. Undervalued by himself. Responds badly to busywork, pushes back on ideas that feel like procrastination, thinks like an engineer even during brainstorming.
- **Procrastination pattern:** strong tendency to plan instead of ship. Brief explicitly treats this as the #1 risk.

## MVP Scope — IN

- **Ingest sources (legally clean, no bot-detection needed):**
    - Greenhouse public job board API: `GET https://api.greenhouse.io/v1/boards/{company}/jobs?content=true` — stable, no auth
    - Lever public job board API — every Lever customer has a public endpoint, no auth
    - Ashby public endpoints — available for customer boards
    - HN "Who's Hiring" monthly thread parser — _monthly source, not weekly_ (brief acknowledges this explicitly)
    - Seed list: hand-curated ~50 AI-forward companies (Anthropic, OpenAI, Perplexity, Replit, Vercel, LangChain, Cohere, Mistral, Scale, etc.)
- **Extraction:** LLM with structured output. Fields: skills, seniority, tech stack, salary band, remote policy, role archetype (LLM App Engineer / AI Product Engineer / Agent Engineer / ML Platform Engineer).
- **Storage:** Postgres + pgvector on Neon.
- **LLM provider:** Anthropic Claude, routed via Vercel AI Gateway (provider-agnostic from Day 1, but _pick one and stop tuning in Week 1_).
- **Eval harness:** 20 hand-labeled postings, extraction accuracy measured and published in the write-up. Non-optional — eval is part of the hireability signal.
- **Ranker:** skill frequency across corpus, skill co-occurrence clusters, salary–stack correlations.
- **Diff:** compare ranked market against Darko's profile → one weekly skill-gap report.
- **Output UI:** static public page showing the latest report. No accounts, no dashboards, no settings, no chat.
- **Public artifact:** GitHub repo public Day 1, honest README, commit history visible throughout build.
- **Communication loop (parallel, equal priority):**
    - 5 job applications/week starting Week 1
    - Voice notes journal
    - Loom recordings
    - Weekly LinkedIn build-in-public post
    - Every interview offered is taken as paid practice

## MVP Scope — OUT (deferred, not "soon")

- **LinkedIn and Indeed scraping** — ToS risk, bot detection, ban risk. Hard rejection.
- **Auto-apply, mass-apply, resume-spam** — brand-wrong, explicit non-goal from original idea brief.
- **Multi-user, accounts, auth, billing, chatbot UI** — not a SaaS launch.
- **Conversational RAG query layer** — was in earlier draft as Week 2 work; cut for scope discipline. Goes to Vision.
- **Interview Prep Agent (voice mock interviews with LLM feedback)** — was Weeks 3–4 in earlier draft; cut. Goes to Vision. Note: this cut is contested — communication is the user's root blocker per brainstorming — but the scope win outweighed it. PRD may reopen this decision.
- **Resume Tailoring Agent** — Vision.
- **Content Pipeline Agent** (git commits → LinkedIn post drafts) — Vision.
- **Studio Aalekh integration** (wife's art studio, studioaalekh.in) — too raw/undata'd currently. Month 3+ territory, post-hire.
- **All 8 other modules from the original 9-module `idea-brief.md`** (Skill Gap Engine, Proof Engine, Application Engine, Interview Simulator, Narrative Engine, Experimentation Layer, Distribution Engine, ROI Skill Planner) — the original idea brief was a product spec wearing a "get hired" costume. It has been radically scoped down. Do not re-propose these in PRD.

## Technical Context & Preferences

- **Language:** Python for backend/ingest/extract; consider TypeScript only if UI deployment needs it. User has Go/Python/JS background — Python leans into the AI ecosystem.
- **Hosting:** Vercel if TS-heavy, or a cheap VPS if Python-only.
- **Database:** Neon Postgres with pgvector extension — one DB, no separate vector store. Reduces complexity.
- **LLM Gateway:** Vercel AI Gateway — provider-agnostic, observability, model fallback. Noted in brief as "pick one and stop tuning."
- **Budget hard cap:** $30 LLM spend over 4 weeks. Implies aggressive prompt caching + batching.
- **Repo must be public Day 1.** Not at the end. The commit history itself is part of the proof.
- **Dataset publication:** Hugging Face dataset planned for Vision phase, not MVP.

## Detailed User Scenarios

- **Scenario 1 — Monday morning skill-gap report:** Darko opens the public URL, sees the top 10 market skills this week, sees his profile fit (e.g., 4/10), sees 3 specific gaps to close _this week_, sees 5 suggested applications with per-company rationale drawn from their actual postings. Acts on all three (learn, apply, post).
- **Scenario 2 — Per-company interview briefing:** Before an interview with, say, Perplexity, Darko runs the tool against Perplexity's Greenhouse board, gets a fingerprint of their stack, walks into the interview opening with _"I noticed your last 8 AI postings all mention eval harnesses but none mention LangChain. Is that deliberate?"_ — instant senior-signal moment.
- **Scenario 3 — "Here's my own posting analyzed by my tool"** as an interview demo. Darko asks the interviewer for their company, runs the tool live, walks them through the insights. Makes the interviewer the user. Unforgettable.
- **Scenario 4 — Cover note generation:** tool diffs a specific job posting against Darko's profile and generates evidence-first application bullets ("Your posting lists X, Y, Z; I built these three things for exactly those") — not adjective-first, not keyword-stuffed.
- **Scenario 5 — Weekly LinkedIn post:** "Week 3: learned LangGraph by rebuilding the extractor as an agent graph. Here's what broke. Here's the commit." Build-in-public distribution flywheel.

## Output Specification — The Weekly Skill-Gap Report

Concrete target output (single most important artifact of the MVP):

```
Darko's AI Engineering Skill Gap — Week of YYYY-MM-DD

Corpus: N postings (Greenhouse + Lever + Ashby + HN). Filter: AI/LLM/Applied AI/Agent Engineer.

Top 10 market skills (frequency-ranked):
1. Python (94%)
2. LLM API integration — OpenAI/Anthropic (87%)
3. RAG pipelines (72%)
4. Vector DBs — pgvector/Pinecone (61%)
5. LangChain or LangGraph (58%)
6. Prompt engineering + structured output (54%)
7. Model evaluation / evals (49%)
8. Agents / tool use (47%)
9. Production deployment (44%)
10. Observability/tracing — Langfuse, LangSmith (31%)

Your profile fit: 4 / 10 confirmed.

Top 3 gaps to close this week:
- RAG pipeline — pgvector + a retrieval eval. (This week's build step does exactly this.)
- LangGraph agent — refactor the extractor into a graph. (Next week's build step.)
- Evals harness — 20 hand-labeled postings, accuracy measured.

Top 5 applications for this week: [company list, per-company one-line rationale]

Salary band across corpus: 50th pct $165k, 75th pct $210k, remote 62%. (Only from ~40% of postings that disclose.)
```

**Rule from the brief:** if this report cannot be produced by end of Week 2, Week 3 is a rewrite, not a feature add.

## Success Criteria

- **Primary success (binary):** credible offer conversation within 16 weeks. Definition of "offer conversation" = past final round, salary discussion in progress.
- **Offer floor:** +50% over current base, daytime hours, non-toxic team. Below = walk.
- **Leading indicators tracked weekly** across three loops: Build, Interview, Communicate. See brief's table for week 1/4/8/16 targets.

## Kill Criteria (Decision Rules, Not Feelings)

- **End of Week 2:** if corpus <100 postings OR extraction accuracy <70% on 20-sample eval → cut ingest, use CSV of manually-collected postings, spend saved days on ranker + write-up.
- **End of Week 4:** if MVP not publicly deployed → ship whatever exists _as-is_, write honest "here's what's broken" post, pivot 80% of time to interviewing.
- **End of Week 8:** if <2 interviews have happened → tool is no longer the bottleneck. Stop building. Start cold-outreaching AI hiring leads using tool insights as conversation starter.
- **"Go fight" mode from Week 5:** application cadence doubles from 5/week to 10/week. Feature work slows to a trickle. Tool becomes resume asset, not active project.

## Competitive Intelligence (from web research, April 2026)

- **Existing job tools are per-job reactive, not aggregate-market:**
    - Teal — per-job-description keyword match vs. resume (paywalled in Teal+). No market aggregation.
    - Jobscan — ATS keyword matching, single-job scope.
    - Careerflow — resume scoring + per-role skill gaps on tracked jobs.
    - Huntr — Kanban tracker only. No gap analysis.
    - Simplify / LazyApply / Sonara — autofill/mass-apply. Not intelligence.
- **Gap Darko can occupy:** "scrape N live postings → LLM-extract → frequency-rank skills across the market → diff against profile." No existing player does this as their core loop. The moat is narrative + execution speed, NOT tech — a competitor could copy in a sprint. Fine, because the goal is getting one person hired, not winning a market.
- **2026 AI engineering most-in-demand skills (validated across multiple sources):** Python, LangChain/LangGraph, RAG, vector DBs (Pinecone/Weaviate/pgvector), evals, agentic frameworks (LangGraph/CrewAI/AutoGen), deployment.
- **Hype-fading:** pure "prompt engineering" as a standalone skill is softening — bundled into RAG/agent work.
- **Salary ranges (directional, blog-aggregator sourced, not primary data):**
    - US mid (3–5 yrs): ~$154k base. Senior: $250–400k+. GenAI specialists: $150–280k+.
    - India domestic mid: ₹10–18 LPA. Senior: ₹20–50+ LPA.
    - India → US/EU remote: $140–180k (~₹1.1–1.5 Cr). **This is Darko's 2–3x target zone.**
- **Hiring manager behavior 2026:** "2–3 deep, well-documented projects with evals beat 10 shallow ones." Recruiters increasingly ask for GitHub/live demo links before resumes. Production instincts (error handling, evals, deployment, structured outputs) signal harder than novelty.
- **Backend-to-AI transition:** multiple sources confirm backend devs have a short transition path to AI engineering roles. The corpus Darko builds will empirically measure this — the brief is careful not to cite unsourced numbers.

## Narrative Angles (Unused Leverage)

- **"I replaced my job search with an agent I built in 6 weeks."** First-person, contrarian, HN-front-page shape.
- **"The tool told me which skills to learn, then I learned them by building the tool."** Recursive, memorable, on-thesis.
- **"Teal tells you to match keywords. I wanted to know which keywords matter."** Direct competitive jab.
- **"Learning in public from Bengaluru night shifts."** Anti-Silicon-Valley underdog arc — LinkedIn algorithm-friendly, especially for Indian AI community.
- **"I walked into every interview having already read the company's job board."** Senior-signal demo moment.

## Rejected Ideas (Do Not Re-Propose)

- **The full 9-module idea brief** (Job Intelligence, Skill Gap, Proof, Application, Interview Simulator, Narrative, Experimentation, Distribution, ROI Skill Planner) — rejected as over-engineered. Only Job Intelligence survives as MVP.
- **LinkedIn / Indeed scraping** — rejected on ToS + bot-detection grounds.
- **Auto-apply bot / mass apply** — rejected as brand-wrong.
- **Generic chatbot / resume-only tool** — rejected as non-differentiated.
- **Academic ML focus** — rejected as off-market-demand for LLM application roles.
- **Studio Aalekh MVP integrations** — deferred Month 3+, currently data-raw.
- **Cold outreach to engineers in Week 1** — brainstorming explicitly skipped; user not ready, communication staircase is graduated exposure. Returns in kill-criterion Week 8.
- **Sequential learn-then-build-then-interview approach** — rejected in brainstorming. Two parallel loops from Day 1 is the thesis.
- **Conversational RAG layer, Interview Prep Agent, Resume Tailoring Agent in MVP** — cut for scope. In Vision.

## Open Questions (Unresolved)

- **Final framing:** personal-first vs. public-platform-first. Current brief sits in the middle (public-by-default, primary user is Darko). Opportunity reviewer argued for flipping harder. Darko declined to decide in the brief-review stage; PRD may revisit.
- **Interview Prep Agent in MVP or not:** cut for scope, but it directly addresses the user's stated root blocker (fear of interviews). PRD may reopen.
- **LLM provider choice:** brief specifies Claude via Vercel AI Gateway, but the underlying "pick one and stop tuning" decision is a point of ongoing discipline, not a final tech lock-in.
- **Which ~50 seed companies** go into the hand-curated ingest list — specific list not yet defined.
- **Profile input format:** how Darko's profile is represented for the diff step (resume parse? structured YAML? LinkedIn export?). Implementation detail for PRD.
- **Eval harness methodology:** 20 hand-labeled postings named, but label schema not specified.
- **Deployment target specifics:** Vercel vs. VPS call deferred to implementation.
- **Cadence of corpus refresh:** weekly report implied, but cron schedule not defined.

## The One Risk That Matters

- **Planning eats execution.** Brief is treated as the last planning artifact before code. Next 7 days: `git init`, public repo, 5 applications filed, first voice note, first LinkedIn post. If those 5 things do not happen in 7 days, nothing else in the brief matters. This is the single highest-priority constraint for anyone downstream consuming this brief.
