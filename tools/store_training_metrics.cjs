#!/usr/bin/env node
/**
 * Store Training Metrics to PostgreSQL
 *
 * Stores training results and validation data from all ML systems to PostgreSQL
 * learning database on aio-01:5433.
 */

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

const trainingResults = [
  {
    "system_name": "Thompson Sampling (Contextual Bandit)",
    "status": "SUCCESS",
    "metrics": {
      "training_records": 449,
      "test_records": 113,
      "test_accuracy": 0.071,
      "avg_training_reward": 0.772,
      "num_models_learned": 9,
      "context_features": 10,
      "algorithm": "LinUCB",
      "alpha": 0.3,
      "baseline_success_rate": 0.422,
      "expected_success_rate_min": 0.507,
      "expected_success_rate_max": 0.549,
      "expected_improvement_min": 0.2,
      "expected_improvement_max": 0.3,
      "top_models": [
        "poolside/laguna-xs.2:free (0.095)",
        "sonnet (0.092)",
        "haiku (0.089)",
        "opus (0.089)",
        "command-r7b-12-2024 (0.087)"
      ],
      "training_duration_seconds": 2.5,
      "model_size_kb": 47
    }
  },
  {
    "files_created": [],
    "metrics": {
      "initial_coverage": {
        "profiled_models": 21,
        "total_models": 252,
        "coverage_pct": 8.3
      },
      "final_coverage": {
        "profiled_models": 30,
        "total_models": 252,
        "coverage_pct": 11.9
      },
      "improvement": {
        "models_profiled": 9,
        "coverage_gain_pct": 3.6,
        "improvement_rate": "43% increase"
      },
      "task_coverage": {
        "code_generation": 14,
        "code_review": 15,
        "research": 14,
        "math_reasoning": 14,
        "general_qa": 12
      },
      "exploration_stats": {
        "exploration_rate": 0.3,
        "total_trials": 20,
        "exploration_picks": 9,
        "exploitation_picks": 11,
        "exploration_pct": 45
      },
      "quality_metrics": {
        "avg_confidence": 0.73,
        "avg_latency_ms": 1735,
        "avg_tests_per_model": 1.9,
        "max_tests_per_model": 5
      },
      "top_performers": {
        "groq/llama-3.3-70b-versatile": {
          "research_score": 0.844,
          "avg_latency_ms": 1563,
          "tests": 5
        },
        "nousresearch/hermes-3-llama-3.1-405b:free": {
          "math_reasoning_score": 0.854,
          "avg_latency_ms": 2267,
          "tests": 4
        },
        "cohere/north-mini-code:free": {
          "code_generation_score": 0.815,
          "avg_latency_ms": 2064,
          "tests": 2
        }
      },
      "newly_profiled_models": [
        "gemini-flash-lite-latest",
        "google/lyria-3-pro-preview",
        "gemini-pro-latest",
        "google/lyria-3-clip-preview",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview-customtools",
        "gemini-3.1-flash-lite"
      ],
      "algorithm": "Epsilon-greedy exploration with 30% exploration rate",
      "training_duration_seconds": 3,
      "database": "PostgreSQL learning.model_capabilities on aio-01:5433"
    },
    "system_name": "Auto-Profiler (Epsilon-Greedy Exploration)",
    "status": "SUCCESS"
  },
  {
    "system_name": "Prompt Optimizer",
    "status": "CREATED_AND_RAN",
    "metrics": {
      "training_samples": 15485,
      "patterns_discovered": 259,
      "models_optimized": 3,
      "training_duration_seconds": 183,
      "algorithm": "Pattern Mining + CMA-ES",
      "cma_es_generations": 30,
      "model_correlations": {
        "claude-sonnet-4-5": 0.185,
        "claude-haiku-4-5": 0.184,
        "claude-opus-4-6": 0.167
      },
      "best_correlation": 0.185,
      "avg_confidence_top_pattern": 0.85,
      "min_samples_threshold": 10,
      "feature_dimensions": 10,
      "population_size_cma_es": 20
    }
  },
  {
    "system_name": "Novelty Detector",
    "status": "CREATED_AND_RAN",
    "metrics": {
      "algorithm": "Isolation Forest",
      "training_samples": 108,
      "test_samples": 27,
      "total_samples": 135,
      "overall_accuracy": 0.593,
      "novel_detection_rate": 0.583,
      "familiar_accuracy": 0.6,
      "roc_auc_score": 0.667,
      "contamination": 0.426,
      "model_size_kb": 863,
      "training_time_seconds": 2,
      "n_estimators": 100,
      "feature_dimensions": 7,
      "expected_improvement": "10-15% better exploration/exploitation balance"
    }
  },
  {
    "system_name": "Complexity Estimator",
    "status": "CREATED_AND_RAN",
    "metrics": {
      "duration_predictor": {
        "test_r2": 0.853,
        "mae_ms": 5866,
        "rmse_ms": 12438,
        "cv_r2_mean": 0.783,
        "cv_r2_std": 0.155
      },
      "confidence_predictor": {
        "test_r2": 0.874,
        "mae": 0.046,
        "rmse": 0.055,
        "cv_r2_mean": 0.829,
        "cv_r2_std": 0.017
      },
      "training": {
        "n_train": 400,
        "n_test": 100,
        "n_features": 21,
        "data_source": "synthetic_500_samples"
      },
      "algorithm": "Random Forest Regression (100 trees, depth 10-15)"
    }
  }
];

const validationResults = [
  {
    "system_name": "Thompson Sampling (Contextual Bandit)",
    "validation_status": "PASS",
    "ready_for_production": true,
    "test_results": [
      "✓ Model file saved correctly (6.1 KB at learning/contextual_bandit_v2.json)",
      "✓ Model structure valid (9 models, 10 features, alpha=0.3)",
      "✓ LinUCB matrices correctly sized (9x10x10 A matrix, 9x10 b vector)",
      "✓ Prediction capability working on sample tasks",
      "✓ Task-specific recommendations functional",
      "✓ Performance improvement: 42.2% baseline → 50.7%-54.9% expected (20-30% gain)",
      "✓ Model rankings learned"
    ]
  },
  {
    "system_name": "Auto-Profiler (Epsilon-Greedy Exploration)",
    "validation_status": "PASS",
    "ready_for_production": true,
    "test_results": [
      "✅ Database integrity: 37 models stored in learning.model_capabilities",
      "✅ Coverage trajectory: 8.3%→11.9%→14.7% (continuous improvement)",
      "✅ Real-time profiling works",
      "✅ Quality metrics consistent: avg 0.73 confidence across all task types",
      "✅ System ready for integration"
    ]
  },
  {
    "system_name": "Prompt Optimizer (Pattern Mining + CMA-ES)",
    "validation_status": "FAIL",
    "ready_for_production": false,
    "test_results": [
      "✓ Model file saved: /tmp/prompt_optimization_results.json (92KB)",
      "✓ Pattern discovery: 259 patterns with confidence ≥0.60",
      "✗ Correlation too low: 0.185 best (expected 0.5+)",
      "✗ Wrong dataset: Trained on 15,485 agent executions instead of 914 workflow.worker_results"
    ]
  },
  {
    "system_name": "Novelty Detector (Isolation Forest)",
    "validation_status": "PASS",
    "ready_for_production": true,
    "test_results": [
      "✓ Model file saved correctly: 863KB",
      "✓ Model loads and predicts successfully",
      "✓ All integration checks passed"
    ]
  },
  {
    "system_name": "Complexity Estimator",
    "validation_status": "PASS",
    "ready_for_production": true,
    "test_results": [
      "✅ Model files saved",
      "✅ CLI tool works",
      "✅ Python integration working",
      "✅ JavaScript integration ready",
      "✅ Cross-validation stability"
    ]
  }
];

async function storeTrainingMetrics() {
  const client = await pool.connect();
  let recordsInserted = 0;
  const tablesUpdated = new Set();
  const errors = [];

  try {
    // Create workflow execution for this training batch (separate transaction)
    const workflowId = 'training-batch-' + Date.now();
    const execResult = await client.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
       RETURNING id`,
      [
        workflowId,
        'ml-systems-training',
        'Train 5 ML systems: Thompson Sampling, Auto-Profiler, Prompt Optimizer, Novelty Detector, Complexity Estimator',
        5,
        (2.5 + 3 + 183 + 2 + 400) * 1000, // Total training time in ms
        'success',
        JSON.stringify({
          systems_trained: 5,
          systems_passed: 4,
          systems_failed: 1
        })
      ]
    );
    const workflowExecutionId = execResult.rows[0].id;
    recordsInserted++;
    tablesUpdated.add('workflow.executions');

    // Store each training result as a worker result
    for (const training of trainingResults) {
      try {
        await client.query(
          `INSERT INTO workflow.worker_results
           (workflow_execution_id, worker_id, model, task_assigned, result, confidence,
            duration_ms, input_tokens, output_tokens, cost_usd, outcome, metadata, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())`,
          [
            workflowExecutionId,
            training.system_name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
            training.metrics.algorithm || 'unknown',
            `Train ${training.system_name}`,
            training.output || JSON.stringify(training.metrics),
            training.status === 'SUCCESS' ? 0.9 : 0.5,
            (training.metrics.training_duration_seconds || training.metrics.training_time_seconds || 0) * 1000,
            training.metrics.training_samples || training.metrics.training_records || 0,
            0, // output tokens not applicable
            0, // cost not tracked
            training.status === 'SUCCESS' ? 'success' : 'failed',
            JSON.stringify(training.metrics)
          ]
        );
        recordsInserted++;
        tablesUpdated.add('workflow.worker_results');
      } catch (err) {
        errors.push(`Worker result for ${training.system_name}: ${err.message}`);
      }
    }

    // Store learnings from successful trainings
    for (const validation of validationResults) {
      if (validation.ready_for_production) {
        const training = trainingResults.find(t => t.system_name === validation.system_name);
        if (!training) continue;

        const description = `${training.system_name} training completed successfully`;
        const actionableInsight = validation.test_results.filter(r => r.startsWith('✓') || r.startsWith('✅')).join('\n');

        try {
          await client.query(
            `INSERT INTO workflow.learnings
             (workflow_execution_id, learning_type, description, actionable_insight, importance, metadata, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [
              workflowExecutionId,
              'pattern',
              description,
              actionableInsight,
              0.9,
              JSON.stringify({
                system: training.system_name,
                algorithm: training.metrics.algorithm,
                ready_for_production: true,
                validation_status: validation.validation_status
              })
            ]
          );
          recordsInserted++;
          tablesUpdated.add('workflow.learnings');
        } catch (err) {
          errors.push(`Learning for ${validation.system_name}: ${err.message}`);
        }
      }
    }

    // Store Thompson Sampling bandit model
    const thompsonSampling = trainingResults.find(t => t.system_name.includes('Thompson Sampling'));
    if (thompsonSampling && thompsonSampling.status === 'SUCCESS') {
      try {
        await client.query(
          `INSERT INTO learning.bandit_models
           (model_name, model_type, num_strategies, context_dim, alpha, training_records, accuracy, model_path, trained_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
           ON CONFLICT (model_name) DO UPDATE SET
             training_records = EXCLUDED.training_records,
             accuracy = EXCLUDED.accuracy,
             trained_at = NOW()`,
          [
            'contextual_bandit_v2',
            'LinUCB',
            thompsonSampling.metrics.num_models_learned,
            thompsonSampling.metrics.context_features,
            thompsonSampling.metrics.alpha,
            thompsonSampling.metrics.training_records,
            thompsonSampling.metrics.test_accuracy,
            '~/.claude/learning/contextual_bandit_v2.json'
          ]
        );
        recordsInserted++;
        tablesUpdated.add('learning.bandit_models');
      } catch (err) {
        errors.push(`Bandit model: ${err.message}`);
      }
    }

    return {
      records_inserted: recordsInserted,
      tables_updated: Array.from(tablesUpdated),
      storage_status: errors.length === 0 ? 'SUCCESS' : 'PARTIAL',
      summary: `Stored ${recordsInserted} records across ${tablesUpdated.size} tables. ${errors.length > 0 ? 'Errors: ' + errors.join('; ') : 'All systems stored successfully.'}`
    };

  } catch (err) {
    errors.push(`Fatal error: ${err.message}`);
    return {
      records_inserted: recordsInserted,
      tables_updated: Array.from(tablesUpdated),
      storage_status: 'FAILED',
      summary: `Storage failed: ${err.message}. Partial records: ${recordsInserted}`
    };
  } finally {
    client.release();
  }
}

// Run and output JSON
storeTrainingMetrics()
  .then(result => {
    console.log(JSON.stringify(result, null, 2));
    process.exit(0);
  })
  .catch(err => {
    console.error(JSON.stringify({
      records_inserted: 0,
      tables_updated: [],
      storage_status: 'FAILED',
      summary: `Database storage failed: ${err.message}`
    }, null, 2));
    process.exit(1);
  })
  .finally(() => {
    pool.end();
  });
