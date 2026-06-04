# Story 4.2: Labeled Eval Set Management & Accuracy Audits

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a database migration after the Story 4.1 extraction-field migration, expected as `V008__add_evals.sql`, that defines tables `evaluation_runs` and `eval_postings`, along with backend logic to compute per-field precision, recall, and regression detection against a 20-sample hand-labeled ground-truth evaluation set,
so that extraction accuracy is measured mathematically and regression is flagged automatically.

## Product Context

Story 4.2 builds the core validation engine for the AI signal extraction pipeline. The MOAT of this project resides in the evaluation harness—it shows production engineering instincts by proving extraction quality mathematically instead of relying on subjective verification.

We will create two tables: `eval_postings` to house the 20 ground-truth postings (10 train for prompting, 10 held_out for scoring), and `evaluation_runs` to store precision, recall, F1, and regression flags for every evaluation execution. The evaluator service will process the held-out postings through the Hermes extraction proxy and compare the output fields against ground truth using standard information retrieval formulas. It will flag accuracy drops of >3 percentage points as regressions and write a versioned `run-summary-YYYY-WW.json` report to the workspace repository.

---

## Acceptance Criteria

1. **Database Migration `V008__add_evals.sql` Defines Evaluation Storage**
   - Given a database migration file `backend/db/migrations/V008__add_evals.sql`
   - When migrations run
   - Then the table `eval_postings` is created with:
     - `eval_id` VARCHAR(50) PRIMARY KEY (e.g., 'eval-001')
     - `split` VARCHAR(20) NOT NULL (CHECK constraint: 'train', 'held_out')
     - `job_url` TEXT NOT NULL
     - `source_slug` VARCHAR(50) NOT NULL
     - `title` TEXT NOT NULL
     - `company` TEXT NOT NULL
     - `raw_text_excerpt` TEXT NOT NULL
     - `expected_skills` JSONB NOT NULL DEFAULT '[]'::jsonb
     - `expected_seniority` VARCHAR(50) NOT NULL
     - `expected_tech_stack` JSONB NOT NULL DEFAULT '[]'::jsonb
     - `expected_salary_band` JSONB NOT NULL DEFAULT '{"kind": "not_disclosed"}'::jsonb
     - `expected_remote_policy` VARCHAR(50) NOT NULL
     - `expected_role_archetype` VARCHAR(100) NOT NULL
     - `annotation_notes` TEXT,
     - `created_at` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
     - `updated_at` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   - And the table `evaluation_runs` is created with:
     - `id` BIGSERIAL PRIMARY KEY
     - `run_timestamp` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
     - `prompt_version` VARCHAR(100) NOT NULL,
     - `extraction_schema_version` VARCHAR(50) NOT NULL,
     - `overall_accuracy` NUMERIC(5, 4) NOT NULL,
     - `overall_precision` NUMERIC(5, 4) NOT NULL,
     - `overall_recall` NUMERIC(5, 4) NOT NULL,
     - `overall_f1` NUMERIC(5, 4) NOT NULL,
     - `accuracy_regression` BOOLEAN NOT NULL DEFAULT FALSE,
     - `metrics` JSONB NOT NULL, -- Detailed breakdown per field
     - `created_at` TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   - And indices are added to support fast retrieval:
     - `idx_eval_postings_split` on `eval_postings(split)`
     - `idx_evaluation_runs_timestamp` on `evaluation_runs(run_timestamp DESC)`

2. **20 Ground-Truth Postings are Seeded Into the Database**
   - When the migration runs, it seeds exactly 20 ground-truth samples (10 'train' and 10 'held_out') into the `eval_postings` table.
   - The seeded postings match the exact data specified in the **Ground-Truth Evaluation Dataset** section of this story file.
   - No placeholders, empty fields, or syntax errors exist in the seeded data.

3. **Evaluator Service Calculates Metrics with Standard Math Formulas**
   - Given a service module `backend/services/evaluator.py`
   - When triggering an evaluation run on a target split (default: `'held_out'`)
   - Then it processes each posting in the split by sending its `raw_text_excerpt` to the extraction client (reusing `backend/llm/client.py` and `prompts/extraction_v1.md` or a specified version)
   - And it calculates Precision, Recall, and F1 score for each of the 6 fields on each sample:
     - **For List Fields (`skills`, `tech_stack`):**
       - Let $E$ be the set of expected values, $A$ be the set of actual (extracted) values.
       - If both $E$ and $A$ are empty: Precision = 1.0, Recall = 1.0, F1 = 1.0.
       - If one is empty and the other is not: Precision = 0.0, Recall = 0.0, F1 = 0.0.
       - Otherwise:
         - Precision = $|E \cap A| / |A|$
         - Recall = $|E \cap A| / |E|$
         - F1 = $2 \cdot (\text{Precision} \cdot \text{Recall}) / (\text{Precision} + \text{Recall})$ (or 0.0 if sum is 0.0)
     - **For Categorical Fields (`seniority`, `remote_policy`, `role_archetype`):**
       - Precision = Recall = F1 = 1.0 if the cleaned actual value matches the expected value, else 0.0.
     - **For Struct Fields (`salary_band`):**
       - Precision = Recall = F1 = 1.0 if all fields match: `kind` matches, and if `kind` is `disclosed`, then `currency`, `min_amount`, `max_amount`, and `period` all match exactly, else 0.0.
   - And it averages the metrics across all evaluated samples in the split to yield field-level Precision, Recall, and F1.
   - And it computes the `overall_f1` (referred to as overall accuracy) as the simple average of the 6 field-level F1 scores.

4. **Regression Detection Compares Overall F1 against the Last Run**
   - Given the current evaluation run's computed overall F1 score/accuracy
   - When comparison logic runs
   - Then it queries the `evaluation_runs` table for the most recent run (ordered by `run_timestamp` DESC)
   - And if the prior run's `overall_f1` minus the current run's `overall_f1` is strictly greater than `0.03` (representing a drop of more than 3 percentage points), it sets `accuracy_regression = TRUE`.
   - And if no prior run exists or the delta is $\le 0.03$, it sets `accuracy_regression = FALSE`.

5. **Run Summaries are Saved to Database and Repo History**
   - Given a successful evaluation run
   - When finishing the execution
   - Then the evaluator saves the run metrics, timestamps, schema/prompt versions, regression status, and detailed metrics object to the `evaluation_runs` database table.
   - And it commits a structured JSON file to `_bmad-output/implementation-artifacts/run-summary-YYYY-WW.json` containing:
     - `run_timestamp` (ISO UTC string)
     - `prompt_version`
     - `schema_version`
     - `overall_metrics`: `{"precision": ..., "recall": ..., "f1": ...}`
     - `accuracy_regression` (boolean)
     - `field_metrics`: a dictionary of `{field_name: {"precision": ..., "recall": ..., "f1": ...}}` for the 6 fields
     - `detailed_diffs`: a list of sample-level comparisons containing `eval_id`, expected schema dict, actual schema dict, matching status per field, and mismatched fields highlighted.

6. **Hermes Health Boundary is Reused**
   - Given the evaluation execution starts
   - When checking the environment
   - Then it calls `check_hermes_proxy_health()` from `backend/llm/hermes.py` before doing any work
   - And if the proxy is unreachable, it aborts, logs the connection error via structlog, and raises `HermesProxyConnectionError`.

7. **Evaluation Script Provides a CLI Interface**
   - Given a CLI entrypoint `backend/scripts/run_evaluation.py`
   - When executing the script: `python -m backend.scripts.run_evaluation`
   - Then it runs the evaluator, outputs a formatted ASCII table comparing expected vs. actual extraction results, prints computed precision/recall/F1 metrics per field, outputs the overall F1 and regression status, and exits non-zero if a regression is detected or Hermes is offline.
   - And the script supports `--dry-run` which skips calling the LLM/Hermes proxy entirely, generating mock extraction results (matching expected or slightly perturbed) to verify metrics math, regression comparisons, DB persistence, and summary-file output.

8. **Tests Verify Math, Regression, Mocking, and Boundary Compliance**
   - Given backend tests run via pytest
   - When running tests in `backend/tests/services/test_evaluator.py` and `backend/tests/scripts/test_run_evaluation.py`
   - Then tests assert the correctness of precision, recall, and F1 calculations using manual arrays of mock expected/actual pairs (including list overlaps, exact matches, mismatched categories, disclosed vs undisclosed salaries).
   - And tests verify regression detection flags are set correctly across mock runs.
   - And tests assert that no database mutation occurs when Hermes health check fails.
   - And tests mock httpx requests to the Hermes proxy to ensure tests run deterministically and fast without real LLM dependencies.

---

## Ground-Truth Evaluation Dataset

The following 20 ground-truth samples must be inserted into the `eval_postings` table by the database migration:

### Training Set (`split = 'train'`)

```json
[
  {
    "eval_id": "eval-001",
    "split": "train",
    "job_url": "https://www.workatastartup.com/jobs/cognitiveflow-ai-app-engineer",
    "source_slug": "yc_waas",
    "title": "AI Application Engineer",
    "company": "CognitiveFlow",
    "raw_text_excerpt": "Tech stack: FastAPI, React, pgvector, RAG, Claude 3.5 Sonnet. Location: San Francisco office.",
    "expected_skills": ["FastAPI", "React", "pgvector", "RAG", "Claude 3.5 Sonnet"],
    "expected_seniority": "unknown",
    "expected_tech_stack": ["FastAPI", "React", "pgvector", "Claude 3.5 Sonnet"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "llm_app_engineer",
    "annotation_notes": "Seeded from YC WaaS mock posting; location is SF onsite."
  },
  {
    "eval_id": "eval-002",
    "split": "train",
    "job_url": "https://www.workatastartup.com/jobs/sentientlabs-agent-systems-architect",
    "source_slug": "yc_waas",
    "title": "Agent Systems Architect",
    "company": "SentientLabs",
    "raw_text_excerpt": "We are seeking a Senior Agent Systems Architect to design autonomous workflows. Tech stack: LangGraph, Python, Vector DBs, Multi-Agent Systems. This is a fully remote role.",
    "expected_skills": ["LangGraph", "Python", "Vector DBs", "Multi-Agent Systems", "autonomous workflows"],
    "expected_seniority": "senior",
    "expected_tech_stack": ["LangGraph", "Python", "Vector DBs"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "remote",
    "expected_role_archetype": "agent_engineer",
    "annotation_notes": "Architect title and Senior prefix imply senior. Fully remote."
  },
  {
    "eval_id": "eval-003",
    "split": "train",
    "job_url": "https://www.workatastartup.com/jobs/neuralscale-ml-platform-developer",
    "source_slug": "yc_waas",
    "title": "ML Platform Developer",
    "company": "NeuralScale",
    "raw_text_excerpt": "Tech stack: PyTorch, CUDA, Docker, Kubernetes, Triton Inference Server. Requirements: 3+ years experience. Onsite role in Bengaluru, India.",
    "expected_skills": ["PyTorch", "CUDA", "Docker", "Kubernetes", "Triton Inference Server"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["PyTorch", "CUDA", "Docker", "Kubernetes", "Triton Inference Server"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "ml_platform_engineer",
    "annotation_notes": "3+ years experience maps to mid. Location is Bengaluru onsite."
  },
  {
    "eval_id": "eval-004",
    "split": "train",
    "job_url": "https://jobs.lever.co/sarvam/ai-product-engineer",
    "source_slug": "lever",
    "title": "AI Product Engineer",
    "company": "Sarvam AI",
    "raw_text_excerpt": "Sarvam AI is looking for an AI Product Engineer to build Indian language LLM applications. Tech stack: Python, Streamlit, PostgreSQL, RAG. Requirements: 2+ years of experience. Onsite role in Bengaluru. Salary: INR 1,500,000 - 2,500,000 per year.",
    "expected_skills": ["Python", "Streamlit", "PostgreSQL", "RAG", "LLM applications"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["Python", "Streamlit", "PostgreSQL"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "INR",
      "min_amount": 1500000,
      "max_amount": 2500000,
      "period": "year"
    },
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "ai_product_engineer",
    "annotation_notes": "2+ years experience maps to mid. Salary disclosed in INR yearly."
  },
  {
    "eval_id": "eval-005",
    "split": "train",
    "job_url": "https://jobs.greenhouse.io/perplexity/senior-research-engineer",
    "source_slug": "greenhouse",
    "title": "Senior Research Engineer (Search)",
    "company": "Perplexity",
    "raw_text_excerpt": "Perplexity is hiring a Senior Research Engineer. You will work on web search optimization and model pretraining. Stack: PyTorch, JAX, Python. 5+ years of experience. Hybrid policy (SF office).",
    "expected_skills": ["PyTorch", "JAX", "Python", "web search optimization", "model pretraining"],
    "expected_seniority": "senior",
    "expected_tech_stack": ["PyTorch", "JAX", "Python"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "hybrid",
    "expected_role_archetype": "research_engineer",
    "annotation_notes": "Senior title and 5+ years experience. Hybrid policy SF."
  },
  {
    "eval_id": "eval-006",
    "split": "train",
    "job_url": "https://ashbyhq.com/llamaindex/data-engineer",
    "source_slug": "ashby",
    "title": "Senior Data & AI Engineer",
    "company": "LlamaIndex",
    "raw_text_excerpt": "LlamaIndex is seeking a Senior Data & AI Engineer to build scalable data connectors. Requirements: Apache Spark, PostgreSQL, Python, LlamaIndex framework. Salary range: USD 140,000 - 180,000 yearly. Remote (US/Canada).",
    "expected_skills": ["Apache Spark", "PostgreSQL", "Python", "LlamaIndex", "data connectors"],
    "expected_seniority": "senior",
    "expected_tech_stack": ["Apache Spark", "PostgreSQL", "Python", "LlamaIndex"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "USD",
      "min_amount": 140000,
      "max_amount": 180000,
      "period": "year"
    },
    "expected_remote_policy": "remote",
    "expected_role_archetype": "data_ai_engineer",
    "annotation_notes": "Senior data role. Disclosed salary range USD. Remote."
  },
  {
    "eval_id": "eval-007",
    "split": "train",
    "job_url": "https://jobs.lever.co/cohere/staff-ml-platform",
    "source_slug": "lever",
    "title": "Staff ML Platform Engineer",
    "company": "Cohere",
    "raw_text_excerpt": "Staff ML Platform Engineer. We need a staff level platform expert. Core tech: Kubernetes, Ray, Go, GCP, Terraform. Seniority: Staff. Remote policy: flexible.",
    "expected_skills": ["Kubernetes", "Ray", "Go", "GCP", "Terraform"],
    "expected_seniority": "staff_plus",
    "expected_tech_stack": ["Kubernetes", "Ray", "Go", "Terraform"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "flexible",
    "expected_role_archetype": "ml_platform_engineer",
    "annotation_notes": "Staff title maps to staff_plus. Remote policy is flexible."
  },
  {
    "eval_id": "eval-008",
    "split": "train",
    "job_url": "https://jobs.greenhouse.io/anthropic/llm-app-engineer",
    "source_slug": "greenhouse",
    "title": "LLM Application Developer",
    "company": "Anthropic",
    "raw_text_excerpt": "Build LLM application tooling with TypeScript, Node.js, and Anthropic API. Onsite (SF). USD 160,000 - 220,000 per year.",
    "expected_skills": ["TypeScript", "Node.js", "Anthropic API", "LLM application tooling"],
    "expected_seniority": "unknown",
    "expected_tech_stack": ["TypeScript", "Node.js"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "USD",
      "min_amount": 160000,
      "max_amount": 220000,
      "period": "year"
    },
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "llm_app_engineer",
    "annotation_notes": "No seniority mentioned. Salary range USD. SF onsite."
  },
  {
    "eval_id": "eval-009",
    "split": "train",
    "job_url": "https://jobs.greenhouse.io/pinecone/support-engineer",
    "source_slug": "greenhouse",
    "title": "AI Developer Relations Engineer",
    "company": "Pinecone",
    "raw_text_excerpt": "Join us as an AI Developer Relations Engineer. Assist clients building LLM apps. Tech stack: Python, Pinecone, Vector Databases, RAG, OpenAI APIs. Remote. USD 120,000 - 150,000.",
    "expected_skills": ["Python", "Pinecone", "Vector Databases", "RAG", "OpenAI APIs", "Developer Relations"],
    "expected_seniority": "unknown",
    "expected_tech_stack": ["Python", "Pinecone"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "USD",
      "min_amount": 120000,
      "max_amount": 150000,
      "period": "year"
    },
    "expected_remote_policy": "remote",
    "expected_role_archetype": "ai_product_engineer",
    "annotation_notes": "DevRel helping customers build. Salary range USD. Remote."
  },
  {
    "eval_id": "eval-010",
    "split": "train",
    "job_url": "https://jobs.lever.co/vllm/core-maintainer",
    "source_slug": "lever",
    "title": "Core vLLM Engineer",
    "company": "vLLM",
    "raw_text_excerpt": "Core engineer for vLLM library. Optimization of attention kernels, CUDA development, PyTorch, Triton. Remote (Flexible). 3+ years experience.",
    "expected_skills": ["vLLM", "attention kernels", "CUDA", "PyTorch", "Triton"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["vLLM", "CUDA", "PyTorch", "Triton"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "flexible",
    "expected_role_archetype": "research_engineer",
    "annotation_notes": "3+ years maps to mid. Core kernel optimizations align with research_engineer."
  }
]
```

### Held-Out Set (`split = 'held_out'`)

```json
[
  {
    "eval_id": "eval-011",
    "split": "held_out",
    "job_url": "https://www.workatastartup.com/jobs/promptperfect-ai-dev",
    "source_slug": "yc_waas",
    "title": "Junior AI Engineer",
    "company": "PromptPerfect",
    "raw_text_excerpt": "Looking for a Junior AI Engineer. Technical skills: Python, Prompt Engineering, LangChain, OpenAI API. Onsite (Bhopal, India). Salary: INR 40,000 - 60,000 per month.",
    "expected_skills": ["Python", "Prompt Engineering", "LangChain", "OpenAI API"],
    "expected_seniority": "entry",
    "expected_tech_stack": ["Python", "LangChain"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "INR",
      "min_amount": 40000,
      "max_amount": 60000,
      "period": "month"
    },
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "llm_app_engineer",
    "annotation_notes": "Junior title implies entry level. Monthly INR salary."
  },
  {
    "eval_id": "eval-012",
    "split": "held_out",
    "job_url": "https://jobs.lever.co/haptik/nlp-engineer",
    "source_slug": "lever",
    "title": "NLP & Conversational AI Engineer",
    "company": "Haptik",
    "raw_text_excerpt": "Haptik is hiring an NLP Engineer. Tech stack: Python, Rasa, BERT, PyTorch. Requirements: 3-5 years of experience. Hybrid policy in Mumbai.",
    "expected_skills": ["NLP", "Conversational AI", "Python", "Rasa", "BERT", "PyTorch"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["Python", "Rasa", "PyTorch"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "hybrid",
    "expected_role_archetype": "ai_product_engineer",
    "annotation_notes": "3-5 years experience maps to mid. Hybrid policy Mumbai."
  },
  {
    "eval_id": "eval-013",
    "split": "held_out",
    "job_url": "https://jobs.greenhouse.io/replit/agent-architect",
    "source_slug": "greenhouse",
    "title": "Lead Agent Engineer",
    "company": "Replit",
    "raw_text_excerpt": "Replit is looking for a Lead Agent Engineer to design autonomous coding agents. Tech: LangGraph, AutoGen, Python, TypeScript, Node.js. Remote policy is flexible.",
    "expected_skills": ["autonomous coding agents", "LangGraph", "AutoGen", "Python", "TypeScript", "Node.js"],
    "expected_seniority": "senior",
    "expected_tech_stack": ["LangGraph", "AutoGen", "Python", "TypeScript", "Node.js"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "flexible",
    "expected_role_archetype": "agent_engineer",
    "annotation_notes": "Lead role maps to senior. Autonomous coding agents."
  },
  {
    "eval_id": "eval-014",
    "split": "held_out",
    "job_url": "https://ashbyhq.com/scale/mlops-lead",
    "source_slug": "ashby",
    "title": "Staff MLOps / ML Platform Engineer",
    "company": "Scale AI",
    "raw_text_excerpt": "Staff ML Platform Engineer. Tech stack: Kubernetes, Kubeflow, PyTorch, Python, AWS. 7+ years of experience. Onsite in San Francisco.",
    "expected_skills": ["MLOps", "Kubernetes", "Kubeflow", "PyTorch", "Python", "AWS"],
    "expected_seniority": "staff_plus",
    "expected_tech_stack": ["Kubernetes", "Kubeflow", "PyTorch", "Python"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "ml_platform_engineer",
    "annotation_notes": "Staff title and 7+ years maps to staff_plus. SF onsite."
  },
  {
    "eval_id": "eval-015",
    "split": "held_out",
    "job_url": "https://jobs.lever.co/observeai/data-engineer",
    "source_slug": "lever",
    "title": "AI Data Pipeline Engineer",
    "company": "Observe.ai",
    "raw_text_excerpt": "Observe.ai is seeking a Data Pipeline Engineer. Tech: Apache Kafka, PostgreSQL, Python, dbt, Spark. Experience: 4+ years. Fully remote role. Salary: USD 130,000 - 160,000 per year.",
    "expected_skills": ["Apache Kafka", "PostgreSQL", "Python", "dbt", "Spark", "data pipeline"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["Apache Kafka", "PostgreSQL", "Python", "dbt", "Spark"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "USD",
      "min_amount": 130000,
      "max_amount": 160000,
      "period": "year"
    },
    "expected_remote_policy": "remote",
    "expected_role_archetype": "data_ai_engineer",
    "annotation_notes": "4+ years maps to mid. Salary disclosed USD. Remote."
  },
  {
    "eval_id": "eval-016",
    "split": "held_out",
    "job_url": "https://jobs.greenhouse.io/cohere/research-fellow",
    "source_slug": "greenhouse",
    "title": "Research Engineer (LLM Alignment)",
    "company": "Cohere",
    "raw_text_excerpt": "Research alignment algorithms. Core stack: RLHF, DPO, PyTorch, JAX, Python. 2+ years of experience. Hybrid policy in Toronto.",
    "expected_skills": ["LLM Alignment", "RLHF", "DPO", "PyTorch", "JAX", "Python"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["PyTorch", "JAX", "Python"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "hybrid",
    "expected_role_archetype": "research_engineer",
    "annotation_notes": "Research engineering on alignment. Hybrid Toronto."
  },
  {
    "eval_id": "eval-017",
    "split": "held_out",
    "job_url": "https://jobs.greenhouse.io/langchain/founding-engineer",
    "source_slug": "greenhouse",
    "title": "Founding LLM Tooling Developer",
    "company": "LangChain",
    "raw_text_excerpt": "Build next-gen LLM orchestration tooling. Tech: TypeScript, Python, FastAPI, React. Remote. USD 150,000 - 200,000 per year.",
    "expected_skills": ["LLM orchestration tooling", "TypeScript", "Python", "FastAPI", "React"],
    "expected_seniority": "unknown",
    "expected_tech_stack": ["TypeScript", "Python", "FastAPI", "React"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "USD",
      "min_amount": 150000,
      "max_amount": 200000,
      "period": "year"
    },
    "expected_remote_policy": "remote",
    "expected_role_archetype": "llm_app_engineer",
    "annotation_notes": "Founding developer with no seniority prefix. Remote."
  },
  {
    "eval_id": "eval-018",
    "split": "held_out",
    "job_url": "https://jobs.lever.co/sarvam/agent-builder",
    "source_slug": "lever",
    "title": "AI Agents Engineer",
    "company": "Sarvam AI",
    "raw_text_excerpt": "Sarvam AI is hiring an AI Agents Engineer. Requirements: Python, CrewAI, LangChain, Vector Databases. Onsite role in Bengaluru.",
    "expected_skills": ["Python", "CrewAI", "LangChain", "Vector Databases"],
    "expected_seniority": "unknown",
    "expected_tech_stack": ["Python", "CrewAI", "LangChain"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "onsite",
    "expected_role_archetype": "agent_engineer",
    "annotation_notes": "AI Agents engineer. Onsite Bengaluru."
  },
  {
    "eval_id": "eval-019",
    "split": "held_out",
    "job_url": "https://ashbyhq.com/huggingface/mlops",
    "source_slug": "ashby",
    "title": "Senior MLOps Platform Specialist",
    "company": "Hugging Face",
    "raw_text_excerpt": "MLOps Platform Specialist. Stack: Kubernetes, Docker, Python, Hugging Face Spaces. 5+ years experience. Fully remote. USD 180,000 yearly.",
    "expected_skills": ["MLOps", "Kubernetes", "Docker", "Python", "Hugging Face Spaces"],
    "expected_seniority": "senior",
    "expected_tech_stack": ["Kubernetes", "Docker", "Python"],
    "expected_salary_band": {
      "kind": "disclosed",
      "currency": "USD",
      "min_amount": 180000,
      "max_amount": 180000,
      "period": "year"
    },
    "expected_remote_policy": "remote",
    "expected_role_archetype": "ml_platform_engineer",
    "annotation_notes": "Senior MLOps specialist. Flat rate salary range. Remote."
  },
  {
    "eval_id": "eval-020",
    "split": "held_out",
    "job_url": "https://jobs.greenhouse.io/perplexity/data-analyst-ai",
    "source_slug": "greenhouse",
    "title": "AI Data Analytics Engineer",
    "company": "Perplexity",
    "raw_text_excerpt": "Extract and transform analytical data for our AI engine. Stack: Python, SQL, Snowflake, dbt. 3+ years experience. Hybrid SF role.",
    "expected_skills": ["Python", "SQL", "Snowflake", "dbt", "data analytics"],
    "expected_seniority": "mid",
    "expected_tech_stack": ["Python", "SQL", "Snowflake", "dbt"],
    "expected_salary_band": {"kind": "not_disclosed"},
    "expected_remote_policy": "hybrid",
    "expected_role_archetype": "data_ai_engineer",
    "annotation_notes": "3+ years maps to mid. Hybrid SF."
  }
]
```

---

## Tasks / Subtasks

- [x] **Task 1: Add DB Migration and Seeding (AC: 1, 2)**
  - [x] Create migration file `backend/db/migrations/V008__add_evals.sql`.
  - [x] Define the tables `eval_postings` and `evaluation_runs` with the correct column data types, constraints, defaults, and indices.
  - [x] Add the CHECK constraints to enforce enums for `split`, `expected_seniority`, `expected_remote_policy`, and `expected_role_archetype`.
  - [x] Seed all 20 postings listed in this file into the `eval_postings` table. Ensure lists and bands are parsed into valid JSONB.

- [x] **Task 2: Build Evaluator Service Core (AC: 3, 4, 6)**
  - [x] Create `backend/services/evaluator.py`.
  - [x] Implement a method `run_evaluation(conn, split: str = 'held_out', prompt_version: str = 'extraction_v1')` that loads the ground-truth data from the database.
  - [x] Integrate a proxy health check: call `check_hermes_proxy_health()` at the start and raise `HermesProxyConnectionError` on failure.
  - [x] For each ground truth posting:
    - [x] Perform structured LLM extraction on the raw text using the async extraction client in `backend/llm/client.py` and the versioned prompt.
    - [x] Calculate precision, recall, and F1 for the 6 parameters using the specified mathematical formulas.
    - [x] Compute overall F1 score/accuracy as the average of the 6 parameter F1 scores.
  - [x] Implement regression comparison logic: load the most recent run from `evaluation_runs`, and if the F1 score has dropped by $> 0.03$ compared to that prior run, set `accuracy_regression = True`.

- [x] **Task 3: Implement CLI Runner Script (AC: 5, 7)**
  - [x] Create script entrypoint `backend/scripts/run_evaluation.py`.
  - [x] Set up argument parsing to support options like `--split`, `--prompt-version`, and `--dry-run`.
  - [x] In `--dry-run` mode, generate mock/stub extraction objects (perfectly matching expected values, or with slight perturbations to test metrics) instead of calling the live Hermes proxy.
  - [x] Print a formatted terminal ASCII table displaying expected vs actual extractions side-by-side.
  - [x] Output computed metrics per field and the overall F1 and regression status to stdout.
  - [x] Save the execution run summary to the database `evaluation_runs` table.
  - [x] Write a structured JSON artifact to `_bmad-output/implementation-artifacts/run-summary-YYYY-WW.json` containing the detailed run statistics and the detailed mismatches list.
  - [x] Exit with a non-zero status code if Hermes is offline, or if an accuracy regression is detected.

- [x] **Task 4: Add Mathematical and Regression Tests (AC: 8)**
  - [x] Create test files `backend/tests/services/test_evaluator.py` and `backend/tests/scripts/test_run_evaluation.py`.
  - [x] Test the list scoring metrics using static mock data to check boundary conditions (fully identical, partial overlap, completely disjoint, both empty sets).
  - [x] Test the categorical scalar scoring logic for all enums and struct fields (salary band kind/period/amount checks).
  - [x] Mock the HTTPX network calls to the Hermes proxy to guarantee unit tests execute quickly and reliably without requiring local proxy dependencies.
  - [x] Validate regression detection flags are correctly updated in the DB when accuracy levels decrease between runs.
  - [x] Verify that no tables are written to or modified if the Hermes proxy is offline.

### Review Findings

- [x] [Review][Patch] Move summary artifact writing into the evaluator service so direct service runs satisfy AC5 [backend/services/evaluator.py:305]
- [x] [Review][Patch] Add a boundary test asserting Hermes health failure does not open a database cursor or mutate state [backend/tests/services/test_evaluator.py:115]
- [x] [Review][Patch] Add a deterministic non-dry-run Hermes/httpx success-path test for extraction validation and persistence [backend/tests/services/test_evaluator.py:45]
- [x] [Review][Patch] Make CLI table/status output strictly ASCII as required by AC7 [backend/scripts/run_evaluation.py:67]
- [x] [Review][Patch] Ensure specified prompt versions are reflected in the Hermes extraction payload metadata, not only the loaded prompt text [backend/llm/client.py:163]

---

## Dev Notes

### Existing Code to Reuse

- `backend/llm/client.py`
  - Re-use structured extraction functions and schemas.
  - Re-use error redaction logic (`redact_extraction_error`) when recording extraction errors.
- `backend/llm/hermes.py`
  - Re-use `check_hermes_proxy_health()` and related health client error classes.
- `backend/db/connection.py`
  - Re-use the existing database connection checking fixture or psycopg connection helper.
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - Update status of story 4-2 to `ready-for-dev`.

### Hard Requirements

- **No ORM:** All SQL commands must remain raw SQL run through psycopg connections.
- **Sequential Migration:** The migration must be strictly sequential. Use `V008__add_evals.sql`. Do not overwrite or modify existing migrations.
- **Accuracy Regression Threshold:** The regression threshold is hardcoded to $0.03$ (3 percentage points drop) on `overall_f1`.
- **Token Efficiency:** Redact any large raw text snippets, raw response payloads, or security tokens from log outputs.
- **No Frontend UI:** Do not build any frontend pages, components, or routers in this story. The React dashboard integration `/evals` is fully owned by Story 4.3.

### Architecture Compliance

- Database schemas belong in `backend/db/migrations/`.
- Evaluator calculations and helper services belong in `backend/services/evaluator.py`.
- Execution scripts belong in `backend/scripts/run_evaluation.py`.
- Tests belong in `backend/tests/services/test_evaluator.py` and `backend/tests/scripts/test_run_evaluation.py`.
- Snake_case must be maintained across all JSON payloads, python functions, database tables, and database columns.

### Previous Story Intelligence

- Story 4.1 established the LLM extraction client and extended `jobs` in place using the JSONB schema.
- We must make sure prompt examples do not tune against the held-out evaluation subset to prevent model leakage.
- We must catch validation errors early during extraction evaluation and map them cleanly to standard metric mismatches (e.g. F1 = 0.0).

---

## Verification Plan

### Automated Tests
- Execute unit and integration tests using pytest:
  ```bash
  python -m pytest backend/tests/services/test_evaluator.py backend/tests/scripts/test_run_evaluation.py
  ```
- Run the code compilation verification script:
  ```bash
  python -m compileall backend/services/evaluator.py backend/scripts/run_evaluation.py
  ```

### Manual Verification
- Run a dry-run evaluation to ensure mock calculations, database logging, and summary JSON artifact outputs function as expected:
  ```bash
  python -m backend.scripts.run_evaluation --dry-run
  ```
- Verify the generated `_bmad-output/implementation-artifacts/run-summary-YYYY-WW.json` artifact contains correctly calculated scores and matching properties.
- Check the local database contents of `evaluation_runs` and `eval_postings` to confirm schema attributes and seeded rows match constraints.

### References

- [Epics: Story 4.2](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#L440)
- [PRD: Labeled Evaluation Dataset Management](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/prd.md#L705)
- [Architecture: Evaluation Harness](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/architecture.md#L514)
- [Jobs Extraction Migration](file:///home/darko/Code/be-an-ai-engineer/backend/db/migrations/V007__add_job_extraction_fields.sql)
- [Extraction Client](file:///home/darko/Code/be-an-ai-engineer/backend/llm/client.py)
- [Extraction Schemas](file:///home/darko/Code/be-an-ai-engineer/backend/llm/schemas.py)
- [Hermes Proxy Health Client](file:///home/darko/Code/be-an-ai-engineer/backend/llm/hermes.py)
- [Eval Set Rubric](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/eval-set-rubric.md)
- [Eval Set Seed CSV](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/eval-set-seed.csv)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Completion Notes List

- Created database migration `V008__add_evals.sql` to define evaluation schemas and seed 20 ground-truth postings.
- Developed `backend/services/evaluator.py` to calculate precision, recall, and F1 metrics for list, categorical, and salary band fields.
- Developed CLI script `backend/scripts/run_evaluation.py` to support `--dry-run` with side-by-side ASCII comparison output and weekly JSON summary report generation.
- Created `test_evaluator.py` and `test_run_evaluation.py` to verify metric formulas, mock dry-runs, and regression check assertions.

### File List

- `backend/db/migrations/V008__add_evals.sql`
- `backend/services/evaluator.py`
- `backend/scripts/run_evaluation.py`
- `backend/tests/services/test_evaluator.py`
- `backend/tests/scripts/test_run_evaluation.py`
- `_bmad-output/implementation-artifacts/4-2-labeled-eval-set-management-and-accuracy-audits.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
