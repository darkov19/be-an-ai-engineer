-- Migration V005: Add automated ATS source discovery registry
CREATE TABLE IF NOT EXISTS source_discovery_runs (
    id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    validated_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    source_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    rejection_reasons JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage_gaps JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    execution_time_seconds NUMERIC(10, 2) NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS job_source_candidates (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES source_discovery_runs(id),
    raw_url TEXT NOT NULL,
    normalized_url TEXT,
    company_hint TEXT,
    detected_ats VARCHAR(50),
    detected_slug VARCHAR(255),
    discovery_method VARCHAR(100) NOT NULL,
    validation_status VARCHAR(50) NOT NULL DEFAULT 'candidate',
    rejection_reason TEXT,
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_sources (
    id SERIAL PRIMARY KEY,
    company TEXT,
    ats VARCHAR(50) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    source_url TEXT NOT NULL,
    discovery_method VARCHAR(100) NOT NULL,
    validation_status VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT false,
    job_count INTEGER NOT NULL DEFAULT 0,
    usable_job_count INTEGER NOT NULL DEFAULT 0,
    last_validated_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ats, slug)
);

CREATE INDEX IF NOT EXISTS idx_job_source_candidates_detected_ats ON job_source_candidates(detected_ats);
CREATE INDEX IF NOT EXISTS idx_job_source_candidates_detected_slug ON job_source_candidates(detected_slug);
CREATE INDEX IF NOT EXISTS idx_job_source_candidates_validation_status ON job_source_candidates(validation_status);

CREATE INDEX IF NOT EXISTS idx_job_sources_ats ON job_sources(ats);
CREATE INDEX IF NOT EXISTS idx_job_sources_slug ON job_sources(slug);
CREATE INDEX IF NOT EXISTS idx_job_sources_validation_status ON job_sources(validation_status);
CREATE INDEX IF NOT EXISTS idx_job_sources_active ON job_sources(active);
CREATE INDEX IF NOT EXISTS idx_job_sources_last_validated_at ON job_sources(last_validated_at);
