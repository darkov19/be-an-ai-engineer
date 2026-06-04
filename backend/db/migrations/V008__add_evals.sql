-- Migration V008: Add evaluation tables and seed 20 ground-truth postings

CREATE TABLE IF NOT EXISTS eval_postings (
    eval_id VARCHAR(50) PRIMARY KEY,
    split VARCHAR(20) NOT NULL,
    job_url TEXT NOT NULL,
    source_slug VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    raw_text_excerpt TEXT NOT NULL,
    expected_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_seniority VARCHAR(50) NOT NULL,
    expected_tech_stack JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_salary_band JSONB NOT NULL DEFAULT '{"kind": "not_disclosed"}'::jsonb,
    expected_remote_policy VARCHAR(50) NOT NULL,
    expected_role_archetype VARCHAR(100) NOT NULL,
    annotation_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT eval_postings_split_check
        CHECK (split IN ('train', 'held_out')),
    CONSTRAINT eval_postings_seniority_check
        CHECK (expected_seniority IN ('entry', 'mid', 'senior', 'staff_plus', 'unknown')),
    CONSTRAINT eval_postings_remote_policy_check
        CHECK (expected_remote_policy IN ('remote', 'hybrid', 'onsite', 'flexible', 'unknown')),
    CONSTRAINT eval_postings_role_archetype_check
        CHECK (expected_role_archetype IN (
            'llm_app_engineer',
            'ai_product_engineer',
            'agent_engineer',
            'ml_platform_engineer',
            'data_ai_engineer',
            'research_engineer',
            'unknown'
        ))
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    prompt_version VARCHAR(100) NOT NULL,
    extraction_schema_version VARCHAR(50) NOT NULL,
    overall_accuracy NUMERIC(5, 4) NOT NULL,
    overall_precision NUMERIC(5, 4) NOT NULL,
    overall_recall NUMERIC(5, 4) NOT NULL,
    overall_f1 NUMERIC(5, 4) NOT NULL,
    accuracy_regression BOOLEAN NOT NULL DEFAULT FALSE,
    metrics JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eval_postings_split ON eval_postings(split);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_timestamp ON evaluation_runs(run_timestamp DESC);

CREATE OR REPLACE FUNCTION set_eval_postings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_eval_postings_updated_at ON eval_postings;
CREATE TRIGGER trg_eval_postings_updated_at
BEFORE UPDATE ON eval_postings
FOR EACH ROW
EXECUTE FUNCTION set_eval_postings_updated_at();

-- Seed 20 ground-truth postings (10 train, 10 held_out)
INSERT INTO eval_postings (
    eval_id, split, job_url, source_slug, title, company, raw_text_excerpt,
    expected_skills, expected_seniority, expected_tech_stack, expected_salary_band,
    expected_remote_policy, expected_role_archetype, annotation_notes
) VALUES
('eval-001', 'train', 'https://www.workatastartup.com/jobs/cognitiveflow-ai-app-engineer', 'yc_waas', 'AI Application Engineer', 'CognitiveFlow', 'Tech stack: FastAPI, React, pgvector, RAG, Claude 3.5 Sonnet. Location: San Francisco office.', '["FastAPI", "React", "pgvector", "RAG", "Claude 3.5 Sonnet"]'::jsonb, 'unknown', '["FastAPI", "React", "pgvector", "Claude 3.5 Sonnet"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'onsite', 'llm_app_engineer', 'Seeded from YC WaaS mock posting; location is SF onsite.'),
('eval-002', 'train', 'https://www.workatastartup.com/jobs/sentientlabs-agent-systems-architect', 'yc_waas', 'Agent Systems Architect', 'SentientLabs', 'We are seeking a Senior Agent Systems Architect to design autonomous workflows. Tech stack: LangGraph, Python, Vector DBs, Multi-Agent Systems. This is a fully remote role.', '["LangGraph", "Python", "Vector DBs", "Multi-Agent Systems", "autonomous workflows"]'::jsonb, 'senior', '["LangGraph", "Python", "Vector DBs"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'remote', 'agent_engineer', 'Architect title and Senior prefix imply senior. Fully remote.'),
('eval-003', 'train', 'https://www.workatastartup.com/jobs/neuralscale-ml-platform-developer', 'yc_waas', 'ML Platform Developer', 'NeuralScale', 'Tech stack: PyTorch, CUDA, Docker, Kubernetes, Triton Inference Server. Requirements: 3+ years experience. Onsite role in Bengaluru, India.', '["PyTorch", "CUDA", "Docker", "Kubernetes", "Triton Inference Server"]'::jsonb, 'mid', '["PyTorch", "CUDA", "Docker", "Kubernetes", "Triton Inference Server"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'onsite', 'ml_platform_engineer', '3+ years experience maps to mid. Location is Bengaluru onsite.'),
('eval-004', 'train', 'https://jobs.lever.co/sarvam/ai-product-engineer', 'lever', 'AI Product Engineer', 'Sarvam AI', 'Sarvam AI is looking for an AI Product Engineer to build Indian language LLM applications. Tech stack: Python, Streamlit, PostgreSQL, RAG. Requirements: 2+ years of experience. Onsite role in Bengaluru. Salary: INR 1,500,000 - 2,500,000 per year.', '["Python", "Streamlit", "PostgreSQL", "RAG", "LLM applications"]'::jsonb, 'mid', '["Python", "Streamlit", "PostgreSQL"]'::jsonb, '{"kind": "disclosed", "currency": "INR", "min_amount": 1500000, "max_amount": 2500000, "period": "year"}'::jsonb, 'onsite', 'ai_product_engineer', '2+ years experience maps to mid. Salary disclosed in INR yearly.'),
('eval-005', 'train', 'https://jobs.greenhouse.io/perplexity/senior-research-engineer', 'greenhouse', 'Senior Research Engineer (Search)', 'Perplexity', 'Perplexity is hiring a Senior Research Engineer. You will work on web search optimization and model pretraining. Stack: PyTorch, JAX, Python. 5+ years of experience. Hybrid policy (SF office).', '["PyTorch", "JAX", "Python", "web search optimization", "model pretraining"]'::jsonb, 'senior', '["PyTorch", "JAX", "Python"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'hybrid', 'research_engineer', 'Senior title and 5+ years experience. Hybrid policy SF.'),
('eval-006', 'train', 'https://ashbyhq.com/llamaindex/data-engineer', 'ashby', 'Senior Data & AI Engineer', 'LlamaIndex', 'LlamaIndex is seeking a Senior Data & AI Engineer to build scalable data connectors. Requirements: Apache Spark, PostgreSQL, Python, LlamaIndex framework. Salary range: USD 140,000 - 180,000 yearly. Remote (US/Canada).', '["Apache Spark", "PostgreSQL", "Python", "LlamaIndex", "data connectors"]'::jsonb, 'senior', '["Apache Spark", "PostgreSQL", "Python", "LlamaIndex"]'::jsonb, '{"kind": "disclosed", "currency": "USD", "min_amount": 140000, "max_amount": 180000, "period": "year"}'::jsonb, 'remote', 'data_ai_engineer', 'Senior data role. Disclosed salary range USD. Remote.'),
('eval-007', 'train', 'https://jobs.lever.co/cohere/staff-ml-platform', 'lever', 'Staff ML Platform Engineer', 'Cohere', 'Staff ML Platform Engineer. We need a staff level platform expert. Core tech: Kubernetes, Ray, Go, GCP, Terraform. Seniority: Staff. Remote policy: flexible.', '["Kubernetes", "Ray", "Go", "GCP", "Terraform"]'::jsonb, 'staff_plus', '["Kubernetes", "Ray", "Go", "Terraform"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'flexible', 'ml_platform_engineer', 'Staff title maps to staff_plus. Remote policy is flexible.'),
('eval-008', 'train', 'https://jobs.greenhouse.io/anthropic/llm-app-engineer', 'greenhouse', 'LLM Application Developer', 'Anthropic', 'Build LLM application tooling with TypeScript, Node.js, and Anthropic API. Onsite (SF). USD 160,000 - 220,000 per year.', '["TypeScript", "Node.js", "Anthropic API", "LLM application tooling"]'::jsonb, 'unknown', '["TypeScript", "Node.js"]'::jsonb, '{"kind": "disclosed", "currency": "USD", "min_amount": 160000, "max_amount": 220000, "period": "year"}'::jsonb, 'onsite', 'llm_app_engineer', 'No seniority mentioned. Salary range USD. SF onsite.'),
('eval-009', 'train', 'https://jobs.greenhouse.io/pinecone/support-engineer', 'greenhouse', 'AI Developer Relations Engineer', 'Pinecone', 'Join us as an AI Developer Relations Engineer. Assist clients building LLM apps. Tech stack: Python, Pinecone, Vector Databases, RAG, OpenAI APIs. Remote. USD 120,000 - 150,000.', '["Python", "Pinecone", "Vector Databases", "RAG", "OpenAI APIs", "Developer Relations"]'::jsonb, 'unknown', '["Python", "Pinecone"]'::jsonb, '{"kind": "disclosed", "currency": "USD", "min_amount": 120000, "max_amount": 150000, "period": "year"}'::jsonb, 'remote', 'ai_product_engineer', 'DevRel helping customers build. Salary range USD. Remote.'),
('eval-010', 'train', 'https://jobs.lever.co/vllm/core-maintainer', 'lever', 'Core vLLM Engineer', 'vLLM', 'Core engineer for vLLM library. Optimization of attention kernels, CUDA development, PyTorch, Triton. Remote (Flexible). 3+ years experience.', '["vLLM", "attention kernels", "CUDA", "PyTorch", "Triton"]'::jsonb, 'mid', '["vLLM", "CUDA", "PyTorch", "Triton"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'flexible', 'research_engineer', '3+ years maps to mid. Core kernel optimizations align with research_engineer.'),
('eval-011', 'held_out', 'https://www.workatastartup.com/jobs/promptperfect-ai-dev', 'yc_waas', 'Junior AI Engineer', 'PromptPerfect', 'Looking for a Junior AI Engineer. Technical skills: Python, Prompt Engineering, LangChain, OpenAI API. Onsite (Bhopal, India). Salary: INR 40,000 - 60,000 per month.', '["Python", "Prompt Engineering", "LangChain", "OpenAI API"]'::jsonb, 'entry', '["Python", "LangChain"]'::jsonb, '{"kind": "disclosed", "currency": "INR", "min_amount": 40000, "max_amount": 60000, "period": "month"}'::jsonb, 'onsite', 'llm_app_engineer', 'Junior title implies entry level. Monthly INR salary.'),
('eval-012', 'held_out', 'https://jobs.lever.co/haptik/nlp-engineer', 'lever', 'NLP & Conversational AI Engineer', 'Haptik', 'Haptik is hiring an NLP Engineer. Tech stack: Python, Rasa, BERT, PyTorch. Requirements: 3-5 years of experience. Hybrid policy in Mumbai.', '["NLP", "Conversational AI", "Python", "Rasa", "BERT", "PyTorch"]'::jsonb, 'mid', '["Python", "Rasa", "PyTorch"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'hybrid', 'ai_product_engineer', '3-5 years experience maps to mid. Hybrid policy Mumbai.'),
('eval-013', 'held_out', 'https://jobs.greenhouse.io/replit/agent-architect', 'greenhouse', 'Lead Agent Engineer', 'Replit', 'Replit is looking for a Lead Agent Engineer to design autonomous coding agents. Tech: LangGraph, AutoGen, Python, TypeScript, Node.js. Remote policy is flexible.', '["autonomous coding agents", "LangGraph", "AutoGen", "Python", "TypeScript", "Node.js"]'::jsonb, 'senior', '["LangGraph", "AutoGen", "Python", "TypeScript", "Node.js"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'flexible', 'agent_engineer', 'Lead role maps to senior. Autonomous coding agents.'),
('eval-014', 'held_out', 'https://ashbyhq.com/scale/mlops-lead', 'ashby', 'Staff MLOps / ML Platform Engineer', 'Scale AI', 'Staff ML Platform Engineer. Tech stack: Kubernetes, Kubeflow, PyTorch, Python, AWS. 7+ years of experience. Onsite in San Francisco.', '["MLOps", "Kubernetes", "Kubeflow", "PyTorch", "Python", "AWS"]'::jsonb, 'staff_plus', '["Kubernetes", "Kubeflow", "PyTorch", "Python"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'onsite', 'ml_platform_engineer', 'Staff title and 7+ years maps to staff_plus. SF onsite.'),
('eval-015', 'held_out', 'https://jobs.lever.co/observeai/data-engineer', 'lever', 'AI Data Pipeline Engineer', 'Observe.ai', 'Observe.ai is seeking a Data Pipeline Engineer. Tech: Apache Kafka, PostgreSQL, Python, dbt, Spark. Experience: 4+ years. Fully remote role. Salary: USD 130,000 - 160,000 per year.', '["Apache Kafka", "PostgreSQL", "Python", "dbt", "Spark", "data pipeline"]'::jsonb, 'mid', '["Apache Kafka", "PostgreSQL", "Python", "dbt", "Spark"]'::jsonb, '{"kind": "disclosed", "currency": "USD", "min_amount": 130000, "max_amount": 160000, "period": "year"}'::jsonb, 'remote', 'data_ai_engineer', '4+ years maps to mid. Salary disclosed USD. Remote.'),
('eval-016', 'held_out', 'https://jobs.greenhouse.io/cohere/research-fellow', 'greenhouse', 'Research Engineer (LLM Alignment)', 'Cohere', 'Research alignment algorithms. Core stack: RLHF, DPO, PyTorch, JAX, Python. 2+ years of experience. Hybrid policy in Toronto.', '["LLM Alignment", "RLHF", "DPO", "PyTorch", "JAX", "Python"]'::jsonb, 'mid', '["PyTorch", "JAX", "Python"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'hybrid', 'research_engineer', 'Research engineering on alignment. Hybrid Toronto.'),
('eval-017', 'held_out', 'https://jobs.greenhouse.io/langchain/founding-engineer', 'greenhouse', 'Founding LLM Tooling Developer', 'LangChain', 'Build next-gen LLM orchestration tooling. Tech: TypeScript, Python, FastAPI, React. Remote. USD 150,000 - 200,000 per year.', '["LLM orchestration tooling", "TypeScript", "Python", "FastAPI", "React"]'::jsonb, 'unknown', '["TypeScript", "Python", "FastAPI", "React"]'::jsonb, '{"kind": "disclosed", "currency": "USD", "min_amount": 150000, "max_amount": 200000, "period": "year"}'::jsonb, 'remote', 'llm_app_engineer', 'Founding developer with no seniority prefix. Remote.'),
('eval-018', 'held_out', 'https://jobs.lever.co/sarvam/agent-builder', 'lever', 'AI Agents Engineer', 'Sarvam AI', 'Sarvam AI is hiring an AI Agents Engineer. Requirements: Python, CrewAI, LangChain, Vector Databases. Onsite role in Bengaluru.', '["Python", "CrewAI", "LangChain", "Vector Databases"]'::jsonb, 'unknown', '["Python", "CrewAI", "LangChain"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'onsite', 'agent_engineer', 'AI Agents engineer. Onsite Bengaluru.'),
('eval-019', 'held_out', 'https://ashbyhq.com/huggingface/mlops', 'ashby', 'Senior MLOps Platform Specialist', 'Hugging Face', 'MLOps Platform Specialist. Stack: Kubernetes, Docker, Python, Hugging Face Spaces. 5+ years experience. Fully remote. USD 180,000 yearly.', '["MLOps", "Kubernetes", "Docker", "Python", "Hugging Face Spaces"]'::jsonb, 'senior', '["Kubernetes", "Docker", "Python"]'::jsonb, '{"kind": "disclosed", "currency": "USD", "min_amount": 180000, "max_amount": 180000, "period": "year"}'::jsonb, 'remote', 'ml_platform_engineer', 'Senior MLOps specialist. Flat rate salary range. Remote.'),
('eval-020', 'held_out', 'https://jobs.greenhouse.io/perplexity/data-analyst-ai', 'greenhouse', 'AI Data Analytics Engineer', 'Perplexity', 'Extract and transform analytical data for our AI engine. Stack: Python, SQL, Snowflake, dbt. 3+ years experience. Hybrid SF role.', '["Python", "SQL", "Snowflake", "dbt", "data analytics"]'::jsonb, 'mid', '["Python", "SQL", "Snowflake", "dbt"]'::jsonb, '{"kind": "not_disclosed"}'::jsonb, 'hybrid', 'data_ai_engineer', '3+ years maps to mid. Hybrid SF.')
ON CONFLICT (eval_id) DO NOTHING;
