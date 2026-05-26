# business-os-genai - v0.1 Spec

**Status:** Spec v2 - post stress-test, post LiteLLM/Ollama pivot. Locked for weekend build (Sat–Sun May 9–10, 2026).
**Owner:** Viral Shastri
**Target ship date:** Mon May 11, 2026 EOD
**Repo:** [github.com/darkov19/business-os-genai](https://github.com/darkov19/business-os-genai) (created, awaiting v0.1 code)

---

## 1. Overview

`business-os-genai` is a Python CLI + HTTP API that AI-generates new skills for the [business-os](https://www.npmjs.com/package/business-os) ecosystem. It addresses the bottleneck where business-os ships 12 hand-curated skills and cannot scale beyond what the maintainer can manually author.

The tool is a **decision-routing agent**: given a natural-language description of a business workflow, it (a) checks whether an existing skill matches well via semantic similarity, (b) if not, generates a new skill via the LLM provider, anchored on the most-similar existing patterns, (c) validates the output against the schema, and (d) self-repairs invalid drafts via a retry loop with a degraded-mode fallback.

The system is **provider-agnostic** via [LiteLLM](https://github.com/BerriAI/litellm) (§5.5) - defaults to local Ollama + Llama 3.1 for development, swaps to AWS Bedrock + Claude 3 Haiku for cloud demo, with Groq as a free-tier backup. Embeddings similarly switch between sentence-transformers (local) and Bedrock Titan v2 (cloud).

It produces drop-in skill directories compatible with the existing business-os installer - no changes to the npm package required.

---

## 2. Goals & Non-Goals

### Goals (v0.1)

- Generate complete, valid business-os skill directories from natural language
- Anchor generations on existing skill patterns to maintain BMAD-style quality
- Surface existing skills when they match well (don't regenerate when not needed)
- Self-repair invalid drafts via schema feedback loop (max 3 retries)
- Ship as both CLI (`bos-genai compose "..."`) and HTTP API (`POST /compose`)
- Public repo with documentation, samples, and one-command local install
- Live AWS deployment (Lambda + API Gateway) with public endpoint

### Non-Goals (v0.1)

- ❌ Interactive multi-turn refinement
- ❌ Web UI
- ❌ Skill versioning / diffing against existing
- ❌ Cost dashboards
- ❌ Streaming responses
- ❌ Multi-language support (English only)
- ❌ Hybrid keyword + semantic search
- ❌ Auto-PR submission to chitr repo
- ❌ Adversarial input fuzzing / load testing

These are deferred to v0.2+. Listing them explicitly to prevent scope creep during the 20-hour weekend build.

---

## 3. User Personas & Stories

### Persona A - Self-Employed Founder (Primary)

A solo founder/operator who installed business-os and finds the 12 canonical skills don't quite cover their situation.

- **A1**: As a wedding photographer in tier-2 India, I want a seasonal pricing skill so my AI agent gives locally-relevant pricing advice instead of generic guidance.
- **A2**: As a B2B fintech founder, I want a HIPAA compliance audit skill so my AI agent walks me through the right audit steps for my regulated industry.

### Persona B - business-os Maintainer (Secondary - Viral)

The maintainer who wants to ship more canonical skills faster.

- **B1**: As maintainer, I want to draft new canonical skills in 30 minutes instead of 4 hours, so I can ship v0.4.0 with 8 new skills in a single weekend.

### Persona C - Community Contributor (Future, post-v0.1)

A user who wants to contribute back.

- **C1**: As a domain expert (e.g., e-commerce ops), I want to prototype a skill via the AI generator, refine it, and submit a PR, so my expertise becomes part of the canonical set.

---

## 4. System Architecture

```
User Intent (natural language)
        │
        ▼
┌───────────────────┐
│  Embed Query      │   Bedrock Titan Embeddings v2
└──────┬────────────┘
       │
       ▼
┌───────────────────┐
│  Retrieve         │   Chroma top-k search (k=3)
│                   │   Returns matches with similarity scores
└──────┬────────────┘
       │
       ▼
┌───────────────────┐
│  DECISION ROUTER  │
│                   │   if top-1 sim > 0.85 → BRANCH A
│                   │   if top-1 sim > 0.65 → BRANCH B
│                   │   else                 → BRANCH C
└─┬─────┬─────┬─────┘
  │     │     │
  A     B     C
  │     │     │
  │     ▼     ▼
  │  ┌────────────────────┐
  │  │ Compose Stage      │   Bedrock Claude 3 Haiku
  │  │                    │
  │  │ B: anchored on     │   Anchors = top-3 retrieved skills
  │  │    top-3 skills    │   passed as in-context examples
  │  │                    │
  │  │ C: schema-only     │   No anchors - schema is the only
  │  │    generation      │   constraint
  │  └──────┬─────────────┘
  │         │
  │         ▼
  │  ┌────────────────────┐
  │  │ Validate           │   Pydantic + markdown parser
  │  │                    │   Pass → continue
  │  │                    │   Fail → loop back to Compose
  │  │                    │   with errors as feedback
  │  │                    │   Max 3 retries
  │  └──────┬─────────────┘
  │         │
  │         ▼
  │  ┌────────────────────┐
  │  │ Multi-File Gen     │   Generate openai.yaml
  │  │                    │   Generate workflow-map.md
  │  └──────┬─────────────┘
  │         │
  ▼         ▼
┌────────────────────┐
│  Output            │   Write directory:
│                    │     out/<skill-name>/
│                    │       SKILL.md
│                    │       agents/openai.yaml
│                    │       references/workflow-map.md
└────────────────────┘

A = Return existing skill match (no generation)
B = Generate anchored on top-3 retrieved skills
C = Generate from scratch (schema-only constraint)
```

The router decision is the agent's **primary act**. The repair loop is the agent's **observation → reasoning → action cycle**. Together these two loops are what differentiate this from a glorified RAG demo.

---

## 5. Tech Stack

### Core

| Library | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| **LiteLLM** | 1.x | Provider-agnostic LLM client (routes to Ollama, Bedrock, Groq) |
| **Ollama** | 0.3+ | Local LLM inference server (runs Llama 3.1 8B during dev) |
| **sentence-transformers** | 3.x | Local embeddings (`all-MiniLM-L6-v2`, 384-dim) |
| **FAISS** | 1.8+ | Vector store (file-based, no SQLite dep - Lambda-safe) |
| LangChain | 0.3.x | Agent loop orchestration, prompt templates |
| Pydantic | 2.x | Schema validation |
| Typer | 0.12.x | CLI framework |
| FastAPI | 0.115.x | HTTP API |
| Mangum | 0.17.x | ASGI → Lambda adapter |
| python-frontmatter | 1.x | Parse SKILL.md frontmatter |
| PyYAML | 6.x | Parse `openai.yaml` |
| boto3 | 1.35+ | AWS SDK (used by LiteLLM when `LLM_PROVIDER=bedrock`) |

**Removed from v0.1 (scope cuts after stress test):** ChromaDB (replaced by FAISS - SQLite version conflict on Lambda), LlamaIndex (was a tacked-on sidecar; provides no real value at v0.1), markdown-it-py (replaced by simpler regex section parser).

### AWS Services (cloud-mode only)

| Service | Purpose | Region |
|---|---|---|
| Bedrock | Claude 3 Haiku + Titan Embeddings v2 (cloud-mode provider, alongside Ollama) | us-east-1 |
| Lambda | Run FastAPI app for public demo endpoint | us-east-1 |
| API Gateway | HTTP endpoint | us-east-1 |
| IAM | Scoped role for Bedrock access | global |
| CloudWatch | Structured JSON logs | us-east-1 |

### Model IDs

#### Local mode (default during dev - `LLM_PROVIDER=ollama`)
- **Generation:** `ollama/llama3.1:8b` (4.7 GB local model)
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (90 MB local, 384-dim)

#### Cloud mode (production demo + Bedrock validation - `LLM_PROVIDER=bedrock`)
- **Generation:** `bedrock/anthropic.claude-3-haiku-20240307-v1:0`
- **Embeddings:** `bedrock/amazon.titan-embed-text-v2:0` (1024-dim)

#### Backup mode (if Bedrock model access delays - `LLM_PROVIDER=groq`)
- **Generation:** `groq/llama-3.1-70b-versatile` (free tier)
- **Embeddings:** falls back to `sentence-transformers/all-MiniLM-L6-v2`

### Dev / CI

- pytest (unit tests)
- ruff (linting)
- AWS SAM CLI (Lambda packaging + deploy)
- ~~GitHub Actions~~ - deferred to v0.2 (scope cut)

---

## 5.5. Provider Abstraction

To avoid AWS Bedrock approval delays blocking the build, and to produce a more architecturally-defensible system, **all LLM and embedding calls route through a provider-agnostic gateway**.

### Architecture

```
business-os-genai
       │
       ▼
   LiteLLM (unified client)
       │
       ├─► Ollama (local, default during dev)
       │     └─► Llama 3.1 8B
       │
       ├─► AWS Bedrock (cloud, demo + production validation)
       │     └─► Claude 3 Haiku
       │
       └─► Groq (free-tier backup if Bedrock access delays)
             └─► Llama 3.1 70B Versatile
```

### Configuration

Provider selected by env var:

```bash
LLM_PROVIDER=ollama    # default - local dev
LLM_PROVIDER=bedrock   # cloud demo
LLM_PROVIDER=groq      # backup (free tier)
```

### Implementation sketch

```python
# bos_genai/llm.py
import os
import litellm
from sentence_transformers import SentenceTransformer

PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

GENERATION_MODELS = {
    "ollama":  "ollama/llama3.1:8b",
    "bedrock": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    "groq":    "groq/llama-3.1-70b-versatile",
}

def generate(prompt: str, max_tokens: int = 2000) -> str:
    response = litellm.completion(
        model=GENERATION_MODELS[PROVIDER],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# Embeddings: sentence-transformers locally, Titan in cloud
_embedder = None

def embed(text: str) -> list[float]:
    global _embedder
    if _embedder is None:
        if PROVIDER == "bedrock":
            from bos_genai.bedrock_embed import TitanEmbedder
            _embedder = TitanEmbedder()
        else:
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")

    if PROVIDER == "bedrock":
        return _embedder.embed(text)
    return _embedder.encode(text).tolist()
```

### Why this matters

1. **Build risk reduction.** ~80% of the weekend uses Ollama locally - no API keys, no rate limits, no model-access approvals, no cost. Sub-second iteration on prompt engineering.
2. **Resume integrity.** Final ~2 hours wire Bedrock as a second provider, run a successful end-to-end Bedrock call (with CloudWatch log screenshot). Resume claim "AWS Bedrock" stays defensible.
3. **Architectural credibility.** Production AI systems are increasingly multi-provider (cost optimization, fallback, latency routing). Single-provider apps read as junior. The interview answer to "why LiteLLM" is a senior-engineer answer.
4. **Embedding dimension awareness.** sentence-transformers produces 384-dim vectors; Titan produces 1024-dim. The vector index is initialized per provider - switching providers requires re-indexing. v0.1 documents this; v0.2 will support side-by-side indexes.

### Switching providers

```bash
# Local dev (default)
bos-genai index ../chitr/.agents/skills
bos-genai compose "fintech compliance audit"

# Cloud validation
LLM_PROVIDER=bedrock bos-genai index ../chitr/.agents/skills    # re-index with Titan dims
LLM_PROVIDER=bedrock bos-genai compose "fintech compliance audit"

# Backup if Bedrock access delays
LLM_PROVIDER=groq bos-genai compose "fintech compliance audit"
```

---

## 6. API Surface

### CLI (v0.1 - minimal surface)

```
bos-genai index <path-to-skills>
    Index existing business-os skills into local FAISS store.
    Default path: $BOS_SKILLS_PATH or ./.agents/skills
    Re-runs needed when switching providers (different embedding dims).

bos-genai compose "<query>" [--out ./out] [--no-anchor] [--show-matches]
    Generate a new skill (or surface a strong existing match).
    Writes to ./out/<skill-name>/.
    --no-anchor:    skip retrieval, force scratch generation.
    --show-matches: print top-3 retrieval hits before deciding (useful debug).

bos-genai version
    Print version.
```

**Cut from v0.1 (deferred to v0.2):**
- ~~`bos-genai search "<query>"`~~ - discovery happens inside `compose` via `--show-matches` flag instead
- ~~`bos-genai validate <skill-dir>`~~ - validation runs internally; not user-facing in v0.1

### HTTP API

```
POST /search
  Body:    { "query": "...", "top_k": 3 }
  Returns: { "matches": [{ "name": "...", "description": "...", "score": 0.91 }] }

POST /compose
  Body:    { "query": "...", "no_anchor": false }
  Returns: {
    "decision": "match" | "anchored" | "scratch",
    "matched_skill": "saas-digital-product",       // when decision == match
    "generated": {                                   // when decision != match
      "skill_md": "...",
      "openai_yaml": "...",
      "workflow_map_md": "...",
      "name": "fintech-saas-compliance-audit"
    },
    "validation": { "passed": true, "iterations": 1 },
    "tokens": { "input": 3450, "output": 1260 }
  }

GET /healthz
  Returns 200 OK
```

---

## 7. Skill Format Spec

Generated skill = directory matching this structure exactly:

```
<skill-name>/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── workflow-map.md
```

### SKILL.md schema

```markdown
---
name: <kebab-case-name>          # required, must match dir name
description: <1-2 sentences>     # required, 100-300 chars
---

# <Title Case Name>              # required H1

<one-paragraph intro>            # required, ≥50 words

## When To Use                   # required H2
<bullet list, 2-5 items>

## Core Workflow                 # required H2
<paragraph + Stage Order H3>

### Stage Order                  # required H3
1. <stage 1>
2. <stage 2>
... (3-7 stages)

## Required Operating Rules      # required H2
<numbered list, 4-10 rules>

## Default Output Set            # required H2
<bullet list of artifacts>

## Gate Behavior                 # required H2
<2-4 classification options>

## References                    # optional H2
<file path bullets>
```

### agents/openai.yaml schema

```yaml
interface:
  display_name: "<Title Case>"
  short_description: "<1 sentence, < 80 chars>"
  default_prompt: "Use $<skill-name> to <action verb phrase>."
```

### references/workflow-map.md

Detailed workflow with stage-by-stage breakdown. Loosely schema'd in v0.1; minimum: H1 + 3 H2 sections + ≥ 200 words.

---

## 8. Decision Router

### Inputs

- User query (string, ≤ 500 chars)
- Optional: `--no-anchor` flag

### Decision logic

```python
def route(query: str, top_matches: list[Match]) -> Decision:
    if not top_matches:
        return Decision.SCRATCH

    top_score = top_matches[0].score

    if top_score > 0.85:
        return Decision.MATCH       # Surface existing
    elif top_score > 0.65:
        return Decision.ANCHORED    # Generate using top-3 as anchors
    else:
        return Decision.SCRATCH     # Generate without anchoring
```

### Threshold rationale

- **0.85** - empirically tuned. Above this, the existing skill is almost certainly what the user wants. Below this, generation can produce a more tailored result.
- **0.65** - above this, retrieved skills are similar enough to be useful as anchors (style, structure, tone). Below this, anchoring on weakly-related skills hurts more than helps.

These are starting values; will be refined during weekend build by running ~20 test queries against the 12 existing skills and observing which threshold separates "use existing" from "generate new" cleanly.

### Branch outputs

| Decision | Action |
|---|---|
| `MATCH` | Return matched skill name + description + suggestion: *"If this fits, run `business-os install --components <name>`. Otherwise, run with `--no-anchor` to force generation."* |
| `ANCHORED` | Pass top-3 skills as in-context examples to compose stage |
| `SCRATCH` | Pass schema only to compose stage, no example anchors |

---

## 9. Data Model

### FAISS index - `bos_skills.index` + `bos_skills.metadata.json`

Each document = one full SKILL.md (excluding frontmatter - we want semantic match on intent, not metadata noise).

FAISS stores vectors only; we keep parallel metadata in a JSON file indexed by row position. This is sufficient for <10K vectors.

**Per-document metadata (in `bos_skills.metadata.json`, indexed by FAISS row id):**

```python
{
    "name": "saas-digital-product",          # kebab-case skill name
    "description": "...",                    # from frontmatter
    "file_path": "/abs/path/to/SKILL.md",
    "indexed_at": "2026-05-09T10:30:00Z",
    "provider": "ollama",                    # which provider produced this index
    "chunk_index": 0                         # we don't chunk - skills are small
}
```

**Embedding model (provider-dependent):**
- Local mode (`LLM_PROVIDER=ollama|groq`): `sentence-transformers/all-MiniLM-L6-v2` → **384-dim**
- Cloud mode (`LLM_PROVIDER=bedrock`): `amazon.titan-embed-text-v2:0` → **1024-dim**

**Index type:** `faiss.IndexFlatIP` (inner product / cosine after L2 normalization). Adequate for <10K vectors. Switch to `faiss.IndexHNSWFlat` if corpus grows beyond 10K (post-v0.1).

**Dimension mismatch handling:** the `provider` field in metadata is checked at query time. If it doesn't match the active `LLM_PROVIDER`, the index is invalid and `bos-genai index` must be re-run.

### Pydantic schemas

```python
class SkillFrontmatter(BaseModel):
    name: str = Field(pattern=r"^[a-z]+(-[a-z]+)*$")
    description: str = Field(min_length=100, max_length=300)

class SkillSection(BaseModel):
    heading: str
    level: int          # 2, 3, etc.
    content: str

class SkillMd(BaseModel):
    frontmatter: SkillFrontmatter
    title: str          # H1 content
    intro: str          # paragraph after H1
    sections: dict[str, SkillSection]   # keyed by H2 heading

    @model_validator(mode='after')
    def required_sections(self):
        required = {
            "When To Use",
            "Core Workflow",
            "Required Operating Rules",
            "Default Output Set",
            "Gate Behavior",
        }
        missing = required - set(self.sections.keys())
        if missing:
            raise ValueError(f"Missing required sections: {missing}")
        return self

class OpenAIYaml(BaseModel):
    interface: dict

    @model_validator(mode='after')
    def has_required_keys(self):
        iface = self.interface
        for key in ("display_name", "short_description", "default_prompt"):
            if key not in iface:
                raise ValueError(f"Missing interface.{key}")
        return self
```

---

## 10. Self-Repair Loop

```python
def generate_with_repair(
    query: str,
    anchors: list[Skill],
    max_retries: int = 3,
) -> SkillMd:
    """Repair-loop generator with degraded-mode fallback.

    Returns a valid SkillMd OR a degraded skeletal SkillMd
    rather than crashing - better UX during recruiter demos.
    """
    errors: list[str] = []
    last_draft: str | None = None

    # Stage 1: full repair loop
    for attempt in range(max_retries + 1):
        prompt = build_compose_prompt(
            query=query,
            anchors=anchors,
            previous_draft=last_draft,
            errors=errors,
        )
        draft = generate(prompt)        # via LiteLLM (§5.5)
        last_draft = draft

        try:
            return SkillMd.parse(draft)
        except ValidationError as e:
            errors = format_errors(e)
            if attempt < max_retries:
                continue
            # fall through to degraded mode

    # Stage 2: degraded-mode fallback
    # Strip prompt to schema-only and ask for a skeletal valid skill
    skeletal_prompt = build_skeletal_prompt(query)
    skeletal_draft = generate(skeletal_prompt, max_tokens=500)
    try:
        result = SkillMd.parse(skeletal_draft)
        result.is_skeletal = True       # warning flag for caller
        return result
    except ValidationError:
        # Both stages failed - return last draft + errors instead of raising
        # Caller sees a degraded SkillMd with manual_fix_required = True
        return SkillMd.degraded_stub(query=query, last_draft=last_draft, errors=errors)
```

The retry prompt includes:

- Original user query
- Anchor skills (if `ANCHORED` branch)
- Schema description (required sections, frontmatter format)
- Last attempted draft
- Validation errors with locations (e.g., "Missing required H2 section: 'Gate Behavior'")

This is the "agent" pattern - observe (validation errors), reason (LLM-driven repair), act (new draft), iterate.

**Why a degraded mode rather than raising:** during a recruiter demo, the live URL must always return a sensible response. A 500 error from a failed repair loop is the worst-possible-impression failure mode. Skeletal output + warning is better than crash.

---

## 11. AWS Setup & IAM

> **Note:** With provider abstraction (§5.5), AWS is **only required for the Lambda demo + one Bedrock validation call**. All weekend dev runs locally on Ollama. If Bedrock model access delays beyond Sunday, we ship with Ollama-on-Lambda or fall back to Groq cloud-mode without breaking the build timeline.

### Account setup checklist

1. Create AWS account (free tier eligible)
2. Enable Bedrock in `us-east-1`
3. Request model access (start **immediately** when account is created - this is the long-lead-time item):
   - `anthropic.claude-3-haiku-20240307-v1:0` - *2026 reality:* approval times range from minutes to ~24 hours; submit a specific use-case description to improve approval odds (see §18)
   - `amazon.titan-embed-text-v2:0` - instant
4. Create IAM user `bos-genai-dev` for local development
   - Attach inline policy below
5. Create IAM role `bos-genai-lambda` for Lambda execution
   - Same Bedrock policy
   - Plus `AWSLambdaBasicExecutionRole` (CloudWatch logs)
6. Set a **$5 AWS budget alert** (Billing → Budgets) as circuit breaker

### Minimum IAM policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
      ]
    }
  ]
}
```

Scoped to specific model ARNs - no `bedrock:*`, no wildcard resource. The streaming permission (`InvokeModelWithResponseStream`) is included even though v0.1 doesn't use streaming, because LiteLLM may use it under the hood for some Bedrock paths and a denial here produces confusing error messages. This is what "secure, cost-optimized, scoped IAM" looks like in the JD.

---

## 12. Pricing Analysis

The provider abstraction means **most of the weekend runs on free local Ollama**. Bedrock cost is limited to a small validation suite confirming the cloud-mode integration works end-to-end.

### Ollama (local mode, default during dev)

- **Cost: $0**
- One-time disk: ~5 GB for Llama 3.1 8B + ~90 MB for sentence-transformers
- Compute: laptop CPU/GPU - negligible electricity
- No API keys, no rate limits, no model-access approvals, fully offline

### Bedrock pricing (us-east-1, on-demand, May 2026)

| Model | Input | Output |
|---|---|---|
| Claude 3 Haiku | $0.00025 / 1K tokens | $0.00125 / 1K tokens |
| Titan Text Embeddings v2 | $0.00002 / 1K tokens | n/a |

### Per generation call, ANCHORED branch (Bedrock)

| Step | Tokens | Cost |
|---|---|---|
| Embed query (Titan) | 50 input | $0.000001 |
| Compose - system + 3 anchor skills + query | 3,450 input | $0.00086 |
| Compose - output (SKILL.md ~800 + yaml ~50 + workflow stub ~150) | 1,000 output | $0.00125 |
| **Per generation, no retries** | | **~$0.0021** |

Self-repair adds ~$0.0015 per iteration. Worst case 3 retries: ~$0.007.

### Weekend Bedrock budget

| Activity | Calls | Cost |
|---|---|---|
| Bedrock smoke test (1 generation, 1 embedding to confirm IAM/access works) | 2 | $0.003 |
| Bedrock validation suite (5 generations across all router branches) | 5 | $0.015 |
| Lambda end-to-end test | 3 | $0.01 |
| Buffer (debugging Bedrock-specific issues) | ~10 | $0.05 |
| **Bedrock weekend total** | ~20 | **≤ $0.10** |

### Combined weekend total

| Item | Cost |
|---|---|
| Ollama (local dev - all prompt engineering, all repair-loop testing, all FAISS indexing, all CLI tests) | $0 |
| Bedrock (cloud-mode validation only) | ~$0.10 |
| AWS Lambda + API Gateway (within free tier) | $0 |
| CloudWatch logs (within 5 GB free tier) | $0 |
| Storage (FAISS local file + Lambda layer) | $0 |
| **TOTAL WEEKEND SPEND** | **≤ $0.20** |

### AWS Free Tier (12 months for new accounts)

- Lambda: 1M requests/month + 400K GB-seconds compute
- API Gateway HTTP API: 1M API calls/month
- CloudWatch: 5 GB ingestion + 5 GB storage

Demo usage estimate (~100 invocations/month for recruiter clicks): well under all limits. **$0.**

### Production projections (post-weekend)

If the deployed Lambda demo gets traffic in cloud mode:

| Monthly volume (Bedrock) | Cost |
|---|---|
| 100 generations | $0.30 |
| 1,000 generations | $3.00 |
| 10,000 generations | $30.00 |

If you switch the deployed Lambda to Groq cloud-mode (free tier): ongoing cost stays $0 indefinitely. Resume claim ("AWS Bedrock") still holds because you implemented the integration.

### AWS budget alert

Set a **$5 budget alert** in AWS Billing → Budgets when creating the account. Realistic spend is <$0.50/month; a $5 alert catches anything pathological (e.g., accidentally using Opus or a runaway repair loop).

---

## 13. Repo Structure

```
business-os-genai/
├── README.md
├── LICENSE                      # MIT
├── pyproject.toml
├── .python-version              # 3.11
├── .env.example                 # LLM_PROVIDER, AWS_REGION, etc.
├── .gitignore
├── src/
│   └── bos_genai/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py               # Typer entry
│       ├── config.py            # Provider, model IDs, thresholds
│       ├── llm.py               # LiteLLM + sentence-transformers gateway (§5.5)
│       ├── bedrock_embed.py     # Titan embedder (cloud mode only)
│       ├── indexer.py           # Walk skills, embed, write FAISS
│       ├── retriever.py         # FAISS query + top-k
│       ├── router.py            # Decision logic (§8)
│       ├── composer.py          # Prompt assembly + LLM call
│       ├── validator.py         # Pydantic + regex section parser
│       ├── repair_loop.py       # Self-repair iteration (§10)
│       ├── multifile.py         # openai.yaml + workflow-map stub writer
│       ├── output.py            # Write directory structure
│       ├── api.py               # FastAPI app
│       ├── lambda_handler.py    # Mangum adapter
│       └── logging_setup.py     # Structured JSON logging
├── tests/
│   ├── test_indexer.py
│   ├── test_router.py
│   ├── test_validator.py
│   ├── test_repair_loop.py
│   └── fixtures/
│       └── sample-skills/
├── examples/                    # 1 sample generated skill (v0.1; more in v0.2)
│   └── fintech-saas-compliance-audit/
├── infra/
│   ├── samconfig.toml           # SAM CLI config
│   └── template.yaml            # SAM Lambda + API Gateway template
└── docs/
    ├── architecture.md
    └── architecture.svg
```

**Cut from v0.1 (vs original spec):**
- ~~`.github/workflows/ci.yml`~~ - GitHub Actions deferred to v0.2
- ~~`bedrock.py`~~ - replaced by LiteLLM provider abstraction in `llm.py`
- ~~`llamaindex_sidecar.py`~~ - fake leverage; cut entirely
- 2 of 3 example skills cut; commit only the one referenced in README architecture diagram

---

## 14. 20-Hour Build Plan (Ollama-first)

This plan assumes AWS account + Bedrock access requests are submitted **Friday evening** (parallel to resume submission). Saturday morning starts immediately on Ollama work without waiting for AWS.

### Saturday - Local build (10 hrs)

| Block | Hrs | Tasks | Deliverable |
|---|---|---|---|
| **Sat 0–1** | 1 | Install Ollama; `ollama pull llama3.1:8b`; smoke test (`ollama run llama3.1`); repo scaffold; `pyproject.toml`; `.env.example`; tiny LiteLLM smoke test | `python -c "from bos_genai.llm import generate; print(generate('hello'))"` returns text |
| **Sat 1–4** | 3 | LiteLLM provider wrapper (`llm.py`); FAISS indexer; sentence-transformers embeddings; CLI: `bos-genai index` | `bos-genai index ../chitr/.agents/skills` produces `./.bos_genai/bos_skills.{index,metadata.json}` with 12 entries |
| **Sat 4–8** | 4 | Composer + router (3 branches: MATCH / ANCHORED / SCRATCH); prompt templates; `--show-matches` flag for debug. **Iterate on prompts against Ollama (instant, free).** | `bos-genai compose "saas digital product launch"` returns MATCH; `bos-genai compose "fintech compliance audit"` returns ANCHORED draft |
| **Sat 8–10** | 2 | Pydantic schemas (`SkillFrontmatter`, `SkillMd`, `OpenAIYaml`); regex section parser; validator tests on valid + invalid fixtures | `pytest tests/test_validator.py` passes |

### Sunday - Loop, deploy, polish (10 hrs)

| Block | Hrs | Tasks | Deliverable |
|---|---|---|---|
| **Sun 0–4** | 4 | Self-repair loop (max 3 retries, format errors as LLM feedback, degraded-mode fallback if 3 retries exhausted); structured JSON logging | Test: deliberately broken draft → repaired output. Logs show iteration count + token usage. |
| **Sun 4–5** | 1 | Multi-file output: generate `openai.yaml` (real); `workflow-map.md` (skeletal stub for v0.1); write directory structure | `./out/<name>/` with all 3 files; validates clean |
| **Sun 5–7** | 2 | FastAPI wrapper around CLI core (`POST /compose`, `GET /healthz`); Mangum adapter; Lambda packaging via SAM; **Bedrock model access check** (proceed with Ollama-on-Lambda if not approved) | `sam build` + `sam local invoke` works |
| **Sun 7–9** | 2 | SAM deploy; IAM role; API Gateway; one Bedrock end-to-end validation call (or Groq fallback if no Bedrock); CloudWatch log screenshot | Live `https://<api-id>.execute-api.us-east-1.amazonaws.com/compose` returns valid response |
| **Sun 9–10** | 1 | 1 sample skill committed to `examples/`; architecture diagram (excalidraw → svg); README v0.1; cross-link from chitr README | Repo looks professional; recruiter who clicks finds substance |

### Buffer / cuts

**Total: 20 hrs.** No buffer.

**Hard rule:** if any block runs >25% over, **drop scope, don't extend the timeline**. In priority order, drop:

1. Sample skill in `examples/` (just commit the skill the architecture diagram references)
2. Architecture diagram (write the description in README, defer SVG to v0.2)
3. CloudWatch structured-logging beautification (basic logs are fine)
4. Bedrock validation (ship Ollama-on-Lambda or Groq cloud-mode)
5. Lambda deploy itself (CLI-only v0.1 - last resort, costs the AWS Lambda resume claim)

If AWS account or Bedrock model access takes >24 hours, **default to Groq backup** for cloud-mode:

```bash
LLM_PROVIDER=groq bos-genai compose "..."
```

Resume bullet still says "Bedrock + LangChain + LiteLLM" because you wrote the Bedrock provider integration, even if the live demo uses Groq.

---

## 15. Testing Strategy

### Unit tests (pytest, ~10 tests total)

- Indexer parses frontmatter correctly
- Router decision branches on threshold values (3 cases: match/anchored/scratch)
- Validator catches: missing frontmatter, missing required sections, invalid kebab-case, too-short description
- Repair loop converges on valid output (with mocked Bedrock)

### Integration tests (manual, weekend scope)

- Full flow: query → MATCH (use exact-match query against existing skill)
- Full flow: query → ANCHORED (paraphrase of existing skill)
- Full flow: query → SCRATCH (totally new domain)
- Validate generated skill installs into a test project via business-os CLI

### Smoke tests (deployed)

- `GET /healthz` returns 200
- `POST /compose` with sample query returns valid generation
- CloudWatch Insights query shows structured log entries with decision, scores, token counts

### Out of scope for v0.1

- Load testing
- Adversarial input fuzzing
- A/B comparison vs generic LLM (without RAG)
- Multi-region failover

---

## 16. Deployment

### Local (Ollama mode - default)

```bash
# Prerequisites
curl -fsSL https://ollama.com/install.sh | sh   # Linux/WSL
ollama pull llama3.1:8b                          # ~4.7 GB download

# Install + run
git clone https://github.com/darkov19/business-os-genai
cd business-os-genai
python -m venv .venv && source .venv/bin/activate
pip install -e .

# .env (or copy from .env.example)
echo "LLM_PROVIDER=ollama" > .env

bos-genai index ../chitr/.agents/skills
bos-genai compose "your query"
```

### Local (Bedrock mode - cloud validation)

```bash
aws configure                                    # use bos-genai-dev IAM creds
LLM_PROVIDER=bedrock bos-genai index ../chitr/.agents/skills   # re-index with Titan dims
LLM_PROVIDER=bedrock bos-genai compose "your query"
```

### Local (Groq backup mode)

```bash
export GROQ_API_KEY=<your-key>                   # free tier signup at console.groq.com
LLM_PROVIDER=groq bos-genai compose "your query"
```

### AWS (SAM)

```bash
cd business-os-genai/infra
sam build
sam deploy --guided   # first time only
```

**Lambda packaging strategy:**

- Dependencies in Lambda layer (LangChain + LiteLLM + sentence-transformers cached model = ~150 MB unzipped, fits 250 MB layer limit)
- Application code in main zip
- Pre-indexed FAISS file (~2 MB) shipped in layer at `/opt/bos_genai/index/`
- Avoids cold-start re-indexing

**Lambda config:**

- Runtime: Python 3.11
- Memory: 1769 MB (gets a full vCPU; cuts cold start to 3–6s)
- Timeout: 29s (under API Gateway max)
- Env: `LLM_PROVIDER=bedrock` (or `groq` if Bedrock access delays)

### Environment variables (Lambda)

```
LLM_PROVIDER=bedrock                                                      # or ollama|groq
AWS_REGION=us-east-1
BEDROCK_GENERATION_MODEL=bedrock/anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_EMBEDDING_MODEL=bedrock/amazon.titan-embed-text-v2:0
GROQ_API_KEY=<set-only-if-using-groq>
SIMILARITY_MATCH_THRESHOLD=0.85
SIMILARITY_ANCHOR_THRESHOLD=0.65
MAX_REPAIR_RETRIES=3
FAISS_INDEX_PATH=/opt/bos_genai/index
LOG_LEVEL=INFO
```

---

## 17. Roadmap (post-v0.1)

### v0.2 - Refinement

- Multi-turn refinement (user provides feedback, AI re-drafts)
- Skill diffing (show diff vs nearest existing skill)
- Cost dashboard (per-call token + dollar tracking)

### v0.3 - Quality

- A/B eval harness: generated skill vs hand-curated skill (LLM-as-judge)
- Fine-tune Titan embeddings on business-os corpus (improve retrieval)
- Hybrid search: semantic + BM25 keyword

### v0.4 - Ecosystem

- Auto-PR submission to chitr repo
- Skill marketplace (community-contributed skills)
- Web UI for non-CLI users

### v0.5 - Production

- Streaming responses
- Multi-language support (Spanish, Hindi, Mandarin)
- Skill versioning (semver per skill, migration tools)

---

## 18. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Bedrock model access delays (2026 reality: minutes to ~24 hrs for new accounts) | **Low** (was High) | Provider abstraction (§5.5) means weekend dev runs on Ollama regardless. Bedrock only needed for final validation. **Fallback: Groq free tier** (`LLM_PROVIDER=groq`) - resume claim ("AWS Bedrock") still defensible because Bedrock provider code is written and tested locally. |
| Ollama doesn't run on user's laptop (RAM/disk constraints) | Medium | Llama 3.1 8B needs ~8 GB RAM and 5 GB disk. If laptop can't handle: use a smaller model (`llama3.2:3b`, ~2 GB), or use Groq cloud-mode for free dev. |
| LiteLLM + LangChain version conflicts | Medium | Pin exact versions in `pyproject.toml`. LiteLLM 1.x is stable; LangChain 0.3.x churn is the main risk. Test imports immediately at Sat 0-1 block; rollback to known-good if conflicts. |
| Ollama prompt-following weaker than Claude (Llama 3.1 8B drifts on strict structured output) | **High** | This is the biggest unknown. Mitigations: (a) explicit schema in prompt with one full example, (b) strong system prompt about "respond with raw markdown only", (c) self-repair loop catches drift, (d) fall back to `llama-3.1-70b-versatile` via Groq if 8B can't handle it. |
| Generated skills don't follow BMAD style | Medium | ANCHORED generation uses 3 existing skills as in-context examples; style is inherent to anchoring. Validator catches structural deviations. |
| Self-repair loop exceeds 3 retries on edge cases | Low | Hard cap → degraded-mode fallback (return skeletal stub + error report). Better than crashing during a recruiter demo. |
| Cold start on Lambda > 10s | Medium | LangChain in Lambda layer; sentence-transformers model cached in `/opt/`; warm Lambda with EventBridge ping every 5 min during demo period (free tier). Set Lambda memory to 1769 MB for full vCPU. |
| FAISS index lost on Lambda restart | Low | Ship pre-indexed FAISS file in Lambda layer (~2 MB for 12 skills). Re-index only triggered manually. |
| Cost overrun during dev | Low | Ollama is $0; Bedrock validation budget <$0.20. $5 AWS budget alert as circuit breaker. |
| Schema validation false positives | Medium | Test fixtures cover known edge cases (long descriptions, optional sections, nested headings). v0.2 adds schema versioning. |
| Demo URL slow on first recruiter click (cold start) | Medium | Lambda warm-keeper EventBridge rule. OR: just don't put the live URL in resume - keep GitHub link only, mention live demo in README. |

---

## 19. Open Decisions

Resolved (post-stress-test):

- ✅ **License: MIT.** Standard for portfolio projects. Permissive, recruiter-friendly.
- ✅ **Vector store: FAISS** (not Chroma). SQLite version conflict on Lambda + JD keyword match.
- ✅ **HTTP API authentication: open** for v0.1. Bedrock economics make abuse cost ~$5/month max; the AWS budget alert catches anything pathological.
- ✅ **CLI output: plain by default.** Rich/colors via `--pretty` flag in v0.2.

Still open (decide during build):

- [ ] Should `compose` show top-3 matches automatically, or only with `--show-matches`?
- [ ] Should we support `--style <existing-skill-name>` to let user pick the anchor?
- [ ] Default `LLM_PROVIDER` for the deployed Lambda - `bedrock` (preferred for resume claim) or `groq` (free, no Bedrock dependency)?

---

## 20. Definition of Done (v0.1)

A v0.1 ship requires **all** of the following:

- ✅ Public GitHub repo with README, architecture diagram, `examples/`, MIT LICENSE
- ✅ `pip install -e .` + `ollama pull llama3.1:8b` works locally
- ✅ Three CLI commands working: `index`, `compose`, `version`
- ✅ Self-repair loop demonstrably converges on a deliberately-broken test case (fixture: SKILL.md missing "Gate Behavior" H2)
- ✅ Degraded-mode fallback returns a skeletal SkillMd rather than crashing
- ✅ Live AWS Lambda + API Gateway endpoint, publicly accessible (cloud mode using Bedrock OR Groq fallback)
- ✅ At least 1 sample generated skill committed under `examples/`, validates via internal validator
- ✅ Bedrock provider integration written and tested (one successful end-to-end call with CloudWatch log proof) - even if deployed Lambda uses a different provider
- ✅ Cross-link from chitr README to business-os-genai repo
- ✅ Cost stayed under $0.50 total during build
- ✅ Structured JSON logs visible via CloudWatch Insights

**Cut from v0.1 DoD (vs original):**
- ~~3 sample skills~~ → 1
- ~~All 5 CLI commands~~ → 3
- ~~CI passing on main~~ → deferred
- ~~"validates with bos-genai validate"~~ → validate command removed; internal validation only

If any item is missing by Mon May 11 EOD, adjust resume bullet to match what actually shipped - **no post-build fabrication**.
