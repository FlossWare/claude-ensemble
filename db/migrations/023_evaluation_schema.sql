-- Migration: 023_evaluation_schema.sql
-- Created: 2026-06-28
-- Purpose: Create evaluation schema for benchmark dataset and result tracking

-- Create evaluation schema
CREATE SCHEMA IF NOT EXISTS evaluation;

-- Table for benchmark questions with ground truth
CREATE TABLE evaluation.benchmarks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    ground_truth JSONB NOT NULL,
    difficulty VARCHAR(20) NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for benchmarks table
CREATE INDEX idx_benchmarks_task_type ON evaluation.benchmarks(task_type);
CREATE INDEX idx_benchmarks_difficulty ON evaluation.benchmarks(difficulty);
CREATE INDEX idx_benchmarks_category ON evaluation.benchmarks(category);

-- Table for storing evaluation results
CREATE TABLE evaluation.results (
    id SERIAL PRIMARY KEY,
    benchmark_id INTEGER NOT NULL REFERENCES evaluation.benchmarks(id) ON DELETE CASCADE,
    model VARCHAR(100) NOT NULL,
    worker_id VARCHAR(100),
    answer TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0.0 AND confidence <= 1.0),
    correctness_score FLOAT CHECK (correctness_score >= 0.0 AND correctness_score <= 1.0),
    robustness_score FLOAT CHECK (robustness_score >= 0.0 AND robustness_score <= 1.0),
    generalization_score FLOAT CHECK (generalization_score >= 0.0 AND generalization_score <= 1.0),
    bias_resistance_score FLOAT CHECK (bias_resistance_score >= 0.0 AND bias_resistance_score <= 1.0),
    reproducibility_score FLOAT CHECK (reproducibility_score >= 0.0 AND reproducibility_score <= 1.0),
    overall_score FLOAT,
    evaluation_notes JSONB,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10, 6),
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for results table
CREATE INDEX idx_results_benchmark_id ON evaluation.results(benchmark_id);
CREATE INDEX idx_results_model ON evaluation.results(model);
CREATE INDEX idx_results_worker_id ON evaluation.results(worker_id);
CREATE INDEX idx_results_created_at ON evaluation.results(created_at);

-- Materialized view for benchmark statistics
CREATE MATERIALIZED VIEW evaluation.benchmark_stats AS
WITH difficulty_counts AS (
    SELECT
        task_type,
        COUNT(*) as total_questions,
        COUNT(CASE WHEN difficulty = 'easy' THEN 1 END) as easy_count,
        COUNT(CASE WHEN difficulty = 'medium' THEN 1 END) as medium_count,
        COUNT(CASE WHEN difficulty = 'hard' THEN 1 END) as hard_count,
        ROUND(AVG(CASE WHEN difficulty = 'easy' THEN 1 ELSE 0 END)::NUMERIC * 100, 2) as easy_percent,
        ROUND(AVG(CASE WHEN difficulty = 'medium' THEN 1 ELSE 0 END)::NUMERIC * 100, 2) as medium_percent,
        ROUND(AVG(CASE WHEN difficulty = 'hard' THEN 1 ELSE 0 END)::NUMERIC * 100, 2) as hard_percent
    FROM evaluation.benchmarks
    GROUP BY task_type
)
SELECT
    task_type,
    total_questions,
    easy_count,
    medium_count,
    hard_count,
    easy_percent,
    medium_percent,
    hard_percent,
    ROUND((easy_count + (medium_count * 2) + (hard_count * 3))::NUMERIC / total_questions, 2) as avg_difficulty
FROM difficulty_counts
ORDER BY task_type;

-- Materialized view for model performance
CREATE MATERIALIZED VIEW evaluation.model_performance AS
SELECT
    model,
    COUNT(*) as evaluations,
    ROUND(AVG(correctness_score)::NUMERIC, 3) as avg_correctness,
    ROUND(AVG(robustness_score)::NUMERIC, 3) as avg_robustness,
    ROUND(AVG(generalization_score)::NUMERIC, 3) as avg_generalization,
    ROUND(AVG(bias_resistance_score)::NUMERIC, 3) as avg_bias_resistance,
    ROUND(AVG(reproducibility_score)::NUMERIC, 3) as avg_reproducibility,
    ROUND(AVG(overall_score)::NUMERIC, 3) as avg_overall,
    ROUND(AVG(confidence)::NUMERIC, 3) as avg_confidence,
    ROUND(AVG(CAST(execution_time_ms AS FLOAT))::NUMERIC, 1) as avg_execution_ms,
    ROUND(SUM(cost_usd)::NUMERIC, 6) as total_cost_usd
FROM evaluation.results
GROUP BY model
ORDER BY avg_overall DESC;

-- Materialized view for task type performance by model
CREATE MATERIALIZED VIEW evaluation.task_model_performance AS
SELECT
    b.task_type,
    r.model,
    COUNT(*) as evaluations,
    ROUND(AVG(r.correctness_score)::NUMERIC, 3) as avg_correctness,
    ROUND(AVG(r.overall_score)::NUMERIC, 3) as avg_overall,
    ROUND(AVG(CAST(r.execution_time_ms AS FLOAT))::NUMERIC, 1) as avg_execution_ms
FROM evaluation.results r
JOIN evaluation.benchmarks b ON r.benchmark_id = b.id
GROUP BY b.task_type, r.model
ORDER BY b.task_type, r.model;

-- Create indexes for common queries
CREATE INDEX idx_results_benchmark_model ON evaluation.results(benchmark_id, model);
CREATE INDEX idx_results_overall_score ON evaluation.results(overall_score DESC);

-- Unique indexes on materialized views (required for REFRESH MATERIALIZED VIEW CONCURRENTLY)
CREATE UNIQUE INDEX idx_benchmark_stats_unique ON evaluation.benchmark_stats(task_type);
CREATE UNIQUE INDEX idx_model_performance_unique ON evaluation.model_performance(model);
CREATE UNIQUE INDEX idx_task_model_performance_unique ON evaluation.task_model_performance(task_type, model);

-- Create function to refresh all materialized views
CREATE OR REPLACE FUNCTION evaluation.refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.benchmark_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.model_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.task_model_performance;
END;
$$ LANGUAGE plpgsql;

-- Create function to calculate overall score from dimension scores
CREATE OR REPLACE FUNCTION evaluation.calculate_overall_score(
    correctness FLOAT,
    robustness FLOAT,
    generalization FLOAT,
    bias_resistance FLOAT,
    reproducibility FLOAT
)
RETURNS FLOAT AS $$
BEGIN
    RETURN ROUND(
        (correctness * 0.35 + robustness * 0.20 + generalization * 0.20 + bias_resistance * 0.15 + reproducibility * 0.10)::NUMERIC,
        3
    )::FLOAT;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to update overall_score on results table
CREATE OR REPLACE FUNCTION evaluation.update_result_overall_score()
RETURNS TRIGGER AS $$
BEGIN
    NEW.overall_score := evaluation.calculate_overall_score(
        NEW.correctness_score,
        NEW.robustness_score,
        NEW.generalization_score,
        NEW.bias_resistance_score,
        NEW.reproducibility_score
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_overall_score
BEFORE INSERT OR UPDATE ON evaluation.results
FOR EACH ROW
EXECUTE FUNCTION evaluation.update_result_overall_score();

-- Grant permissions
ALTER SCHEMA evaluation OWNER TO postgres;
GRANT USAGE ON SCHEMA evaluation TO PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA evaluation TO PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA evaluation TO PUBLIC;

-- Add comments for documentation
COMMENT ON SCHEMA evaluation IS 'Evaluation and benchmarking schema for multi-AI model assessment';
COMMENT ON TABLE evaluation.benchmarks IS 'Benchmark questions with ground truth answers across 7 task types (1000 total)';
COMMENT ON TABLE evaluation.results IS 'Evaluation results from models attempting benchmark questions';
COMMENT ON COLUMN evaluation.results.correctness_score IS 'Score 0-1 for answer correctness (35% weight)';
COMMENT ON COLUMN evaluation.results.robustness_score IS 'Score 0-1 for answer robustness (20% weight)';
COMMENT ON COLUMN evaluation.results.generalization_score IS 'Score 0-1 for answer generalization (20% weight)';
COMMENT ON COLUMN evaluation.results.bias_resistance_score IS 'Score 0-1 for resistance to bias (15% weight)';
COMMENT ON COLUMN evaluation.results.reproducibility_score IS 'Score 0-1 for reproducibility (10% weight)';
