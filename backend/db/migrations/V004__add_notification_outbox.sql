-- Migration V004: durable notification outbox for restart-safe delivery
CREATE TABLE IF NOT EXISTS notification_outbox (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(64) NOT NULL,
    run_date DATE NOT NULL,
    payload JSONB NOT NULL,
    due_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    sent_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_outbox_kind_run_date
    ON notification_outbox(kind, run_date);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_due_unsent
    ON notification_outbox(due_at)
    WHERE sent_at IS NULL;
