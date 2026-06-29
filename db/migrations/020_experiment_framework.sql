-- Migration: Experiment tracking framework
-- Purpose: Schema for registering experiments, tracking runs, and recording verdicts
-- Author: Claude Opus 4.6
-- Date: 2026-06-28

BEGIN;

-- Create schema for experiment tracking
CREATE SCHEMA IF NOT EXISTS experiments;

-- Registry of experiments (hypotheses to test)
CREATE TABLE IF NOT EXISTS experiments.registry (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL UNIQUE,
    hypothesis      TEXT NOT NULL,
    metric          VARCHAR(255) NOT NULL,
    success_criteria TEXT NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'active', 'completed', 'abandoned')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE experiments.registry IS
'Central registry of experiments with hypotheses and success criteria';

-- Individual experiment runs (baseline vs treatment)
CREATE TABLE IF NOT EXISTS experiments.runs (
    id                  SERIAL PRIMARY KEY,
    experiment_id       INTEGER NOT NULL REFERENCES experiments.registry(id) ON DELETE CASCADE,
    baseline_config     JSONB NOT NULL DEFAULT '{}',
    treatment_config    JSONB NOT NULL DEFAULT '{}',
    result              JSONB,
    verdict             VARCHAR(50)
                        CHECK (verdict IS NULL OR verdict IN ('confirmed', 'refuted', 'inconclusive')),
    run_date            TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE experiments.runs IS
'Individual runs of an experiment comparing baseline to treatment configurations';

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_registry_status
ON experiments.registry(status);

CREATE INDEX IF NOT EXISTS idx_registry_name
ON experiments.registry(name);

CREATE INDEX IF NOT EXISTS idx_runs_experiment_id
ON experiments.runs(experiment_id);

CREATE INDEX IF NOT EXISTS idx_runs_verdict
ON experiments.runs(verdict);

CREATE INDEX IF NOT EXISTS idx_runs_run_date
ON experiments.runs(run_date DESC);

COMMIT;
