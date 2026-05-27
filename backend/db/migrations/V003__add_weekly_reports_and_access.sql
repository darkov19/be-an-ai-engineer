-- Migration V003: Add weekly reports and cockpit access logs
CREATE TABLE IF NOT EXISTS weekly_reports (
    id SERIAL PRIMARY KEY,
    run_date DATE UNIQUE NOT NULL,
    corpus_size INTEGER NOT NULL DEFAULT 0,
    per_source_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    eval_accuracy FLOAT,
    extraction_latency_ms INTEGER,
    report_html TEXT,
    geo_us_eu JSONB NOT NULL DEFAULT '{}'::jsonb,
    geo_india JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS cockpit_access_logs (
    id SERIAL PRIMARY KEY,
    accessed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weekly_reports_run_date ON weekly_reports(run_date);
