---
title: "Product Brief: Job Intelligence Agent"
status: "complete"
created: "2026-04-14"
updated: "2026-04-14"
inputs:
    - idea-brief.md
    - _bmad-output/brainstorming/brainstorming-session-2026-04-10-01.md
    - web research (April 2026): AI hiring trends, competitive landscape, scraping legality
reviewers:
    - skeptic (scope, vagueness, failure modes)
    - opportunity (narrative, dataset, flywheels)
    - go-to-interview (conversion path from artifact to offer)
---

# Product Brief: Job Intelligence Agent

## Executive Summary

Job Intelligence Agent is a small, sharp AI tool that pulls live AI engineering job postings from public sources, uses an LLM to extract structured signals (skills, seniority, stack, salary), and ranks them across the market to produce a brutally specific skill-gap report for the user. It is built **by** a backend developer breaking into AI, **for** that same developer — and deliberately shipped in public so the tool itself becomes the first portfolio proof of AI engineering capability.

The thesis is one sentence: **one project, built in public, doing triple duty as curriculum, intelligence, and proof beats any trail of tutorials.** Every skill the 2026 AI market is ranking highest gets learned by being used to build the ranker itself. The build is the curriculum; the output is the roadmap; the artifact is the resume.

This brief scopes a 4-week MVP (not 6) to ingest → extract → rank → diff → report, deployed to a public URL, used weekly by the author, and — critically — matched by an equally committed interviewing cadence starting Week 1. Build and interview run as **two parallel loops**, not sequential phases. The brief will be considered a failure if the tool ships and no offer conversation is in progress within 16 weeks.

## The Problem

Darko is a backend developer — Go, Python, JS — 4.5 years in at his first job. The work is toxic, the hours are night shift, and the salary is far below what his core skill (rapid learning) is worth in the 2026 AI market. He has tried to escape before and stalled every time, not because the skills were out of reach, but because of a **confidence-communication loop** that made every interview feel like an exam he would fail.

The market is telling a clear story: LLM application engineers, RAG specialists, and agent builders are in severe demand, and in the 2026 ecosystem backend developers have a genuinely short path into AI roles — the stack overlap is high and production instincts transfer directly (this is claim-level, not numerically precise; the corpus the tool builds will actually measure it). But the door does not open on its own. Three concrete frictions are currently in the way:

1. **No market visibility.** The "AI engineer" title hides half a dozen different actual roles with different stacks. Darko does not know which skills are table-stakes vs. hype.
2. **No proof artifact.** His resume says "backend dev." Nothing on it demonstrates AI engineering instincts.
3. **No forcing function.** Left to himself he will keep reading, keep preparing, and keep not applying. **Planning has become the procrastination.** This is the root risk.

The status quo cost is brutal: another six months of night shifts, another six months of Studio Aalekh (wife's art studio) serving as a reason to stay, and another six months watching the AI hiring window widen for peers with half the raw learning speed.

## The Solution

**Two parallel loops. Equal weight. Both start Week 1.**

**Loop A — Build the Job Intelligence Agent (MVP: 4 weeks).** A single tool that does four things:

1. **Ingest.** Pull AI/LLM engineering postings from legally-clean public sources — Greenhouse, Lever, and Ashby public job-board APIs (per-company endpoints), plus the monthly HN "Who's Hiring" thread. Start from a hand-curated list of ~50 AI-forward companies (Anthropic, OpenAI, Perplexity, Replit, Vercel, LangChain, Cohere, Mistral, Scale, etc.). Target: 200+ relevant postings in the corpus by end of Week 2 — the exact number is an empirical question, not a promise.
2. **Extract.** Feed each posting through an LLM with structured output to pull skills, seniority, tech stack, salary band, remote policy, and role archetype (LLM App Engineer, AI Product Engineer, Agent Engineer, ML Platform Engineer). LLM budget cap: **$30 total for the first 4 weeks** — if extraction exceeds that, batch harder, cache harder, shrink the corpus.
3. **Rank.** Aggregate across the corpus: skill frequency, skill combinations, salary–stack correlations. Store in Postgres (Neon) with pgvector.
4. **Diff.** Compare the ranked market against Darko's profile and output a specific skill-gap report (see "What the Output Actually Looks Like" below).

**Loop B — Interview and communicate (continuous from Day 1).** The build is useless without exposure. Non-negotiable weekly cadence:

- **Week 1:** 5 applications filed. First voice note recorded. First LinkedIn build-in-public post live (honest, including the fear and the 4.5 years).
- **Weeks 2–4:** 5 applications per week. Every interview offered is taken as paid practice. One LinkedIn post per week documenting what got built and what broke.
- **Week 5 onward — "go fight" mode:** the moment the MVP is deployed and the write-up is live, application cadence doubles to 10/week and feature work slows to a trickle. The tool is a _resume asset_ from that point, not an active project.

The fifth thing — the thing that makes this more than a script — is that building the extractor means learning structured LLM outputs; building the ranker means learning embeddings and aggregation; building the diff means learning retrieval and prompt design. Every skill the market is ranking highest gets learned by being used to build the ranker itself. **The build is the curriculum.**

## What the Output Actually Looks Like

The single most important artifact this tool produces is one weekly report. An honest mock of that report:

> **Darko's AI Engineering Skill Gap — Week of 2026-05-04**
>
> **Corpus:** 214 postings (Greenhouse + Lever + Ashby + HN). Filter: "AI Engineer" / "LLM Engineer" / "Applied AI" / "Agent Engineer."
>
> **Top 10 market skills (frequency-ranked):**
>
> 1. Python (94%) 2. LLM API integration — OpenAI/Anthropic (87%) 3. RAG pipelines (72%) 4. Vector DBs — pgvector/Pinecone (61%) 5. LangChain or LangGraph (58%) 6. Prompt engineering + structured output (54%) 7. Model evaluation / evals (49%) 8. Agents / tool use (47%) 9. Production deployment (cloud functions, containers) (44%) 10. Observability / tracing (Langfuse, LangSmith) (31%)
>
> **Your profile fit:** 4 / 10 confirmed (Python, deployment, structured outputs-ish from backend work, basic LLM API).
>
> **Top 3 gaps to close this week:**
>
> - **RAG pipeline** — pgvector + a retrieval eval. _This week's build step does exactly this._
> - **LangGraph agent** — refactor the extractor into a graph. _Next week's build step._
> - **Evals harness** — write a proper eval for extraction accuracy on 20 hand-labeled postings. _Learn by fixing your own extractor._
>
> **Top 5 applications for this week:** [company list, with per-company one-line rationale drawn from their actual public postings]
>
> **Salary band across corpus:** 50th percentile $165k, 75th percentile $210k, remote-friendly 62%. _(Pulled only from postings that disclose — ~40% of corpus.)_

If Darko cannot produce a report that looks like this by end of Week 2, the plan is broken and Week 3 is a rewrite, not a feature add.

## What Makes This Different

**Versus existing job tools (Teal, Jobscan, Huntr, Careerflow, Simplify):** every one of those is _per-job-description reactive_ — paste one posting, get one keyword match. None aggregate _across_ the live market to tell you which skills are actually moving the needle right now. The gap is real because existing players have priced their products around single-job workflows. _Caveat:_ the moat is narrative and execution speed, not tech — a competitor could copy the approach in a sprint. That is fine, because the goal is not to win a market; it is to get Darko hired before anyone copies it.

**Versus "learn AI from a course":** a course ends with a certificate nobody reads. This ends with a deployed URL, a public GitHub repo with dated commits, a weekly LinkedIn post thread, and — if Opportunity Review is right — a **public dataset on Hugging Face** that other people can cite.

**Versus "build ten portfolio projects":** one project explained deeply for 30 minutes in an interview beats ten projects nobody asks about. This one touches Python, LLM APIs, structured outputs, RAG, vector DB, evals, and deployment — i.e., every skill on the 2026 AI engineer job description — and has a legible story: _"I built my own job intelligence because the SaaS tools don't do this, and I used it to get hired."_

**The unfair advantages are real but boring:** (a) backend production instincts transfer directly, (b) radical-honesty narrative ("Bengaluru night-shift backend dev builds the tool that finds him his next job") is contrarian and distributable, and (c) the project dogfoods itself — every week Darko uses his own tool in public, which is inherently a better demo than any pitch.

## Who This Serves

**Primary user: Darko himself.** One user, one workflow, weekly use. "Weekly use" means: generate a fresh skill-gap report, act on the top 3 gaps (either learn or apply), and ship a LinkedIn post about it. Open-the-tab does not count.

**Secondary audience: AI hiring managers interviewing Darko.** They never run the tool, but they _encounter_ it: the URL on the resume, the GitHub repo, the LinkedIn thread, the "here's my tool, here are the insights I pulled from your own job board before walking in" moment in the interview. Their implicit question is _"does this person think like an AI engineer?"_ and the product's job is to answer yes before they finish reading.

**Tertiary, far later: other backend devs trying the same jump.** Only relevant post-hire as an open-source artifact. Not a constraint on MVP design.

## Success Criteria

**Primary success (binary): a credible offer conversation within 16 weeks.** An offer conversation = past final round with at least one company, salary discussion in progress. Minimum acceptable offer floor: **+50% over current base**, daytime hours, non-toxic team. Below that floor, Darko walks and keeps interviewing.

**Leading indicators (tracked weekly):**

| Loop            | Week 1                                              | Week 4                                                                               | Week 8                                                                        | Week 16                                                                    |
| --------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Build**       | Repo public, ingest pipeline working on 5 companies | MVP deployed to public URL, skill-gap report matches the mock above, write-up posted | Dataset on Hugging Face, weekly auto-generated "State of AI Hiring" post live | Tool in maintenance; used weekly for personal interviews, not feature work |
| **Interview**   | 5 applications filed, 1 voice note, 1 LinkedIn post | 20 applications filed, first real interview done                                     | 40+ applications, first "didn't freeze" interview                             | Offer conversation in progress                                             |
| **Communicate** | First voice note recorded                           | 4 LinkedIn posts live, 2 Looms                                                       | First cold outreach DM sent                                                   | Inbound recruiter message received                                         |

**Kill criteria (decision rules, not feelings):**

- **End of Week 2**, if the corpus is <100 postings OR the extraction accuracy is <70% on a 20-sample eval → cut ingest scope to a CSV of manually-collected postings and spend the saved days on the ranker and the write-up.
- **End of Week 4**, if the MVP is not publicly deployed → ship whatever exists _as-is_, write the honest "here's what I learned and what's broken" post, and pivot 80% of time to interviewing.
- **End of Week 8**, if fewer than 2 interviews have happened → the tool is no longer the bottleneck; stop building, start cold-outreaching hiring managers directly using the tool's insights as a conversation starter.

**Weekly time budget:** 15–20 hours. Night shift takes the rest. This is non-negotiable — over-budget weeks steal from sleep and from Studio Aalekh, both of which are more important than any feature.

## Scope

**In scope — 4-week MVP:**

- Ingest from Greenhouse + Lever + Ashby public APIs, hand-curated list of ~50 AI-forward companies to start
- HN "Who's Hiring" monthly parser (explicit acknowledgement: this is a monthly source, not weekly)
- LLM extraction with structured output (Anthropic Claude via Vercel AI Gateway — provider-agnostic, but pick one and stop tuning in Week 1)
- Postgres + pgvector (Neon) for storage
- Simple eval harness: 20 hand-labeled postings, extraction accuracy measured and published in the write-up
- Skill-frequency ranker + profile diff → one weekly report matching the mock above
- Minimal web UI — static page showing the latest report. No accounts, no dashboards, no settings
- Public GitHub repo (public Day 1), honest README, commit history visible
- Public write-up after MVP deploy
- Weekly LinkedIn build-in-public post
- **Loop B runs in parallel:** 5 applications/week, voice notes, Looms, interviews taken as offered

**Out of scope — MVP (genuinely deferred, not "soon"):**

- LinkedIn, Indeed, or any scraper requiring bot-detection bypass
- Auto-apply, mass-apply, resume-spam
- Multi-user support, accounts, auth, billing, chatbot UI
- Conversational RAG query layer (was Week 2 in an earlier draft — cut)
- Interview Prep Agent (was Weeks 3–4 in an earlier draft — cut; see Vision)
- Resume Tailoring Agent (Vision)
- Content Pipeline Agent (Vision)
- Studio Aalekh integration (future, post-hire)
- All 8 other modules of the original 9-module idea brief

**Explicitly NOT this product:**

- Not a SaaS launch
- Not a job scraper product
- Not an auto-apply bot
- Not a generic resume tool

## Vision

If the 4-week MVP ships and is used weekly for 3–4 months, it quietly grows into a **unified personal AI platform** — one shared backend hosting several narrow agents, all reading from the same corpus and skill graph:

- **Weekly "State of AI Hiring" post**, auto-generated from the corpus delta. One cron job, perpetual distribution.
- **Public dataset on Hugging Face**, updated weekly. Instant citation surface, inbound researcher traffic.
- **Per-company briefings** — walk into every interview having ingested that company's entire public job board: _"I noticed your last 8 postings all mention eval harnesses but none mention LangChain. Is that deliberate?"_ Instant senior-signal, and the single highest-leverage hiring-side use of the tool.
- **Interview Prep Agent** — takes a posting, generates likely questions, runs voice-based mock interviews with LLM feedback. Built post-MVP as a direct extension of the extractor.
- **Resume Tailoring Agent** — takes a job + Darko's skill graph + his GitHub and rewrites bullets with evidence. Meta, honest, persuasive.
- **Content Pipeline Agent** — converts git commits into LinkedIn post drafts, feeding the build-in-public staircase with minimal friction.

The two-year version of this is the thing the original 9-module idea brief imagined — career intelligence + execution system — but built bottom-up from one working agent instead of top-down from a spec. By then, the Job Intelligence Agent will have done its real job: Darko will be working as an AI engineer at +50% minimum, daytime hours, with calluses from real interviews instead of fear of imaginary ones. At that point the tool becomes either (a) an open-source artifact for other devs making the same jump, or (b) retired — because it already paid for itself in the single offer that made it unnecessary. Both outcomes are wins.

## The One Risk That Matters

**Planning will eat execution.** This brief is the last planning artifact before code. The very next actions after signing off:

1. `git init` on the ingest service within 24 hours.
2. Public GitHub repo created within 48 hours, honest README committed.
3. First 5 applications filed by end of Week 1 — _regardless of tool progress_.
4. First voice note and first LinkedIn post live by end of Week 1.

If those four things do not happen in the next 7 days, none of the rest of this document matters. The brief is a contract against procrastination, and the kill criteria above exist so that "the tool isn't ready" never becomes a reason not to interview.
