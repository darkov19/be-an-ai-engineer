-- Migration V006: Add company discovery signals and canonical resolver diagnostics
CREATE TABLE IF NOT EXISTS company_discovery_runs (
    id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    provider_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolved_count INTEGER NOT NULL DEFAULT 0,
    unresolved_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    rejection_reasons JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    execution_time_seconds NUMERIC(10, 2) NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS company_signals (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES company_discovery_runs(id),
    provider VARCHAR(100) NOT NULL,
    company_name TEXT,
    company_domain TEXT,
    normalized_domain TEXT,
    careers_url TEXT,
    direct_ats_url TEXT,
    evidence_url TEXT NOT NULL,
    confidence NUMERIC(5, 2),
    category_hints JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'candidate',
    resolved_ats VARCHAR(50),
    resolved_slug VARCHAR(255),
    resolved_source_url TEXT,
    json_ld_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    rejection_reason TEXT,
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT company_signals_status_check CHECK (status IN ('candidate', 'resolved', 'rejected', 'unresolved', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_company_signals_provider ON company_signals(provider);
CREATE INDEX IF NOT EXISTS idx_company_signals_normalized_domain ON company_signals(normalized_domain);
CREATE INDEX IF NOT EXISTS idx_company_signals_status ON company_signals(status);
CREATE INDEX IF NOT EXISTS idx_company_signals_confidence ON company_signals(confidence);
CREATE INDEX IF NOT EXISTS idx_company_signals_last_seen_at ON company_signals(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_company_signals_resolved_at ON company_signals(resolved_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_signals_provider_evidence_unique
    ON company_signals(provider, evidence_url, normalized_domain, direct_ats_url) NULLS NOT DISTINCT;
