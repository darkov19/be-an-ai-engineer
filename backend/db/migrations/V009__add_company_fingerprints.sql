-- Migration V009: Add company fingerprints table for precomputed insights
CREATE TABLE IF NOT EXISTS company_fingerprints (
    id SERIAL PRIMARY KEY,
    company_slug VARCHAR(255) UNIQUE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    role_archetypes JSONB NOT NULL,
    top_technologies JSONB NOT NULL,
    llm_observation TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_company_fingerprints_slug ON company_fingerprints(company_slug);

-- Drop trigger if it exists and recreate it to keep updated_at in sync
DROP TRIGGER IF EXISTS trg_company_fingerprints_updated_at ON company_fingerprints;
CREATE TRIGGER trg_company_fingerprints_updated_at
BEFORE UPDATE ON company_fingerprints
FOR EACH ROW
EXECUTE FUNCTION set_jobs_updated_at();
