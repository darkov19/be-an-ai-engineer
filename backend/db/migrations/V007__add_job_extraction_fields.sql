-- Migration V007: Add structured LLM extraction fields to jobs
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(100),
    ADD COLUMN IF NOT EXISTS extraction_schema_version VARCHAR(50),
    ADD COLUMN IF NOT EXISTS skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS seniority VARCHAR(50),
    ADD COLUMN IF NOT EXISTS tech_stack JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS salary_band JSONB NOT NULL DEFAULT '{"kind": "not_disclosed"}'::jsonb,
    ADD COLUMN IF NOT EXISTS remote_policy VARCHAR(50),
    ADD COLUMN IF NOT EXISTS role_archetype VARCHAR(100),
    ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS extraction_error TEXT,
    ADD COLUMN IF NOT EXISTS extraction_run_id VARCHAR(100);

ALTER TABLE jobs
    DROP CONSTRAINT IF EXISTS jobs_extraction_status_check,
    ADD CONSTRAINT jobs_extraction_status_check
        CHECK (extraction_status IN ('pending', 'extracted', 'failed', 'retryable_error'));

ALTER TABLE jobs
    DROP CONSTRAINT IF EXISTS jobs_seniority_check,
    ADD CONSTRAINT jobs_seniority_check
        CHECK (
            seniority IS NULL
            OR seniority IN ('entry', 'mid', 'senior', 'staff_plus', 'unknown')
        );

ALTER TABLE jobs
    DROP CONSTRAINT IF EXISTS jobs_remote_policy_check,
    ADD CONSTRAINT jobs_remote_policy_check
        CHECK (
            remote_policy IS NULL
            OR remote_policy IN ('remote', 'hybrid', 'onsite', 'flexible', 'unknown')
        );

ALTER TABLE jobs
    DROP CONSTRAINT IF EXISTS jobs_role_archetype_check,
    ADD CONSTRAINT jobs_role_archetype_check
        CHECK (
            role_archetype IS NULL
            OR role_archetype IN (
                'llm_app_engineer',
                'ai_product_engineer',
                'agent_engineer',
                'ml_platform_engineer',
                'data_ai_engineer',
                'research_engineer',
                'unknown'
            )
        );

CREATE INDEX IF NOT EXISTS idx_jobs_extracted_at ON jobs(extracted_at);
CREATE INDEX IF NOT EXISTS idx_jobs_extraction_status ON jobs(extraction_status);
CREATE INDEX IF NOT EXISTS idx_jobs_extraction_unextracted_retryable
    ON jobs(source_slug, status, extraction_status, extracted_at)
    WHERE extracted_at IS NULL OR extraction_status IN ('pending', 'retryable_error');
CREATE INDEX IF NOT EXISTS idx_jobs_prompt_schema_version
    ON jobs(prompt_version, extraction_schema_version);
CREATE INDEX IF NOT EXISTS idx_jobs_extraction_run_id ON jobs(extraction_run_id);

CREATE OR REPLACE FUNCTION set_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;
CREATE TRIGGER trg_jobs_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION set_jobs_updated_at();
