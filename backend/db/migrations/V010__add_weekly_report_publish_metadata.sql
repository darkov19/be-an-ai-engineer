-- Migration V010: Add weekly report publish metadata and static snapshot fields
ALTER TABLE weekly_reports
    ADD COLUMN IF NOT EXISTS report_slug TEXT,
    ADD COLUMN IF NOT EXISTS report_path TEXT,
    ADD COLUMN IF NOT EXISTS og_image_path TEXT,
    ADD COLUMN IF NOT EXISTS commit_sha TEXT,
    ADD COLUMN IF NOT EXISTS deployment_url TEXT,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS experience_distribution JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS profile_fit_deltas JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS coverage_diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS accountability_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS profile_freshness JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_weekly_reports_run_date ON weekly_reports(run_date);
