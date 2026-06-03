-- Migration 014: SARO Data Framework — Evaluation Runs tracking table
--
-- Tracks every execution of the saro-data-framework TestRunner so that
-- evaluation history is visible in the main app dashboard and API.
--
-- Status values: running | completed | partial | failed
-- Triggered by:  api | schedule | ci | manual
--
-- Safe to re-run: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
-- Applied automatically by apply_pending_migrations() on startup.

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    -- How the run was started
    triggered_by            VARCHAR(50)  NOT NULL DEFAULT 'api',
    triggered_by_user_id    UUID         REFERENCES users(id) ON DELETE SET NULL,
    -- Comma-separated dataset names, or "all"
    datasets_requested      TEXT         NOT NULL DEFAULT 'all',
    started_at              TIMESTAMPTZ  NOT NULL,
    completed_at            TIMESTAMPTZ,
    -- running | completed | partial | failed
    status                  VARCHAR(20)  NOT NULL DEFAULT 'running',
    -- Aggregate counts from RunSummary
    datasets_attempted      INTEGER      NOT NULL DEFAULT 0,
    datasets_passed         INTEGER      NOT NULL DEFAULT 0,
    datasets_skipped        INTEGER      NOT NULL DEFAULT 0,
    datasets_failed         INTEGER      NOT NULL DEFAULT 0,
    total_samples_uploaded  INTEGER      NOT NULL DEFAULT 0,
    overall_passed          BOOLEAN,
    elapsed_seconds         DOUBLE PRECISION,
    -- Full RunSummary.as_dict() — queryable for per-dataset / per-rule breakdown
    run_summary_json        JSONB,
    -- SARO API URL the run was targeting
    api_url                 VARCHAR(500) NOT NULL DEFAULT '',
    -- Set if the run itself errored (not individual dataset failures)
    error_message           TEXT,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT eval_runs_status_check
        CHECK (status IN ('running', 'completed', 'partial', 'failed')),
    CONSTRAINT eval_runs_triggered_by_check
        CHECK (triggered_by IN ('api', 'schedule', 'ci', 'manual'))
);

-- Index: latest runs first (default dashboard query)
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_started_at
    ON evaluation_runs (started_at DESC);

-- Index: filter by status (e.g. show only completed runs)
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status
    ON evaluation_runs (status);

-- Index: filter by trigger type (e.g. all CI runs)
CREATE INDEX IF NOT EXISTS ix_evaluation_runs_triggered_by
    ON evaluation_runs (triggered_by);

COMMENT ON TABLE evaluation_runs IS
    'Tracks every SARO Data Framework TestRunner execution. '
    'Full per-dataset results stored in run_summary_json. '
    'Populated by POST /api/v1/evaluations/trigger and the weekly CI cron.';
