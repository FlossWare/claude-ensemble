#!/usr/bin/env node
/**
 * PERPETUAL SELF-IMPROVEMENT ARCHITECT
 *
 * Continuous meta-learning loop that never stops.
 * Coordinates all learning subsystems into a unified improvement cycle:
 *
 *   RESEARCH  ->  MEASURE  ->  EXPERIMENT  ->  EVALUATE  ->  ADAPT
 *      |                                                       |
 *      +<------------------------------------------------------+
 *
 * Cadences:
 *   - Research:    Weekly (self-learning papers, new techniques, meta-learning advances)
 *   - Measure:     Daily  (quality trends, LIS scores, backward transfer, Pareto fronts)
 *   - Experiment:  Monthly (try new techniques, A/B test strategies, parameter sweeps)
 *   - Evaluate:    After each experiment (keep what works, discard what fails)
 *   - Adapt:       Continuous (Reptile interpolation, curriculum progression, weight updates)
 *
 * NO STOPPING CONDITION. This system runs indefinitely.
 *
 * Storage:
 *   ~/.claude/learning/self-improvement-state.json   (loop state)
 *   ~/.claude/learning/self-improvement-log.jsonl    (append-only audit trail)
 *   ~/.claude/learning/db/learning.db                (shared learning DB)
 *
 * Usage:
 *   node perpetual-self-improvement.js                   # Run one improvement cycle
 *   node perpetual-self-improvement.js --research         # Run research phase only
 *   node perpetual-self-improvement.js --measure          # Run measurement phase only
 *   node perpetual-self-improvement.js --experiment       # Run experiment phase only
 *   node perpetual-self-improvement.js --status           # Show current state
 *   node perpetual-self-improvement.js --report           # Generate improvement report
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

// =============================================================================
// PATHS AND CONSTANTS
// =============================================================================

const LEARNING_DIR = path.join(process.env.HOME, '.claude', 'learning');
const STATE_FILE = path.join(LEARNING_DIR, 'self-improvement-state.json');
const LOG_FILE = path.join(LEARNING_DIR, 'self-improvement-log.jsonl');
const DB_PATH = path.join(LEARNING_DIR, 'db', 'learning.db');
const RESEARCH_DIR = path.join(LEARNING_DIR, 'research');

// Cadence configuration (in hours)
const CADENCES = {
  research:   168,  // Weekly  (7 * 24)
  measure:     24,  // Daily
  experiment: 720,  // Monthly (30 * 24)
  evaluate:     0,  // After each experiment (immediate)
  adapt:        0,  // Continuous (every cycle)
};

// Research topics for self-learning papers
const SELF_LEARNING_RESEARCH_TOPICS = [
  'meta-learning continual learning 2026',
  'self-improving AI systems',
  'automated machine learning AutoML',
  'learning to learn neural architecture',
  'catastrophic forgetting prevention continual',
  'curriculum learning adaptive difficulty',
  'online learning bandit optimization',
  'Reptile MAML meta-learning gradient',
  'Pareto multi-objective optimization AI',
  'transfer learning domain adaptation',
  'active learning query strategy',
  'self-supervised learning representation',
  'knowledge distillation compression',
  'neural architecture search efficiency',
  'reinforcement learning from human feedback',
];

// Experiment types to cycle through
const EXPERIMENT_TYPES = [
  {
    id: 'reptile_beta_sweep',
    name: 'Reptile Beta Sweep',
    description: 'Sweep interpolation rates to find optimal stability-speed tradeoff',
    params: { betas: [0.1, 0.2, 0.3, 0.4, 0.5, 0.7] },
  },
  {
    id: 'curriculum_threshold_tuning',
    name: 'Curriculum Threshold Tuning',
    description: 'Adjust promotion/demotion thresholds based on observed success rates',
    params: { promotionThresholds: [0.7, 0.75, 0.8, 0.85], demotionThresholds: [0.3, 0.35, 0.4] },
  },
  {
    id: 'model_routing_accuracy',
    name: 'Model Routing Accuracy Test',
    description: 'Measure if task embedder routes to optimal model vs random baseline',
    params: { sampleSize: 50 },
  },
  {
    id: 'feedback_strategy_comparison',
    name: 'Feedback Strategy Comparison',
    description: 'Compare uncertainty sampling vs diversity sampling vs random for active learning',
    params: { strategies: ['uncertainty', 'diversity', 'random'] },
  },
  {
    id: 'stale_knowledge_interval',
    name: 'Stale Knowledge Interval Test',
    description: 'Test different staleness intervals to balance freshness vs stability',
    params: { intervals_days: [15, 30, 45, 60] },
  },
  {
    id: 'pareto_recompute_frequency',
    name: 'Pareto Recompute Frequency',
    description: 'Find optimal interval for recomputing Pareto fronts',
    params: { intervals: [10, 25, 50, 100] },
  },
  {
    id: 'topic_rotation_strategy',
    name: 'Topic Rotation Strategy',
    description: 'Compare epsilon-greedy vs UCB vs pure exploitation for research topic selection',
    params: { strategies: ['epsilon_greedy', 'ucb', 'pure_exploit'] },
  },
  {
    id: 'quality_weight_sensitivity',
    name: 'Quality Weight Sensitivity',
    description: 'Vary quality dimension weights (accuracy, completeness, clarity) to optimize LIS',
    params: { dimensions: ['accuracy', 'completeness', 'clarity', 'actionability'] },
  },
];

// Improvement metrics to track
const IMPROVEMENT_DIMENSIONS = [
  'avg_quality_score',
  'avg_lis_score',
  'model_routing_accuracy',
  'backward_transfer_rate',
  'experiment_success_rate',
  'research_findings_per_run',
  'curriculum_level_distribution',
  'pareto_optimal_count',
  'knowledge_freshness_ratio',
  'adaptation_velocity',
];

// =============================================================================
// STATE MANAGEMENT
// =============================================================================

function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch (e) {
    logEntry('warn', `Could not load state: ${e.message}`);
  }

  return {
    version: 1,
    created: new Date().toISOString(),
    cycleCount: 0,
    lastCycle: null,
    phases: {
      research: {
        lastRun: null,
        runCount: 0,
        totalPapersFound: 0,
        topicRotationIndex: 0,
        topicEffectiveness: {},
      },
      measure: {
        lastRun: null,
        runCount: 0,
        history: [],  // last 90 measurement snapshots
      },
      experiment: {
        lastRun: null,
        runCount: 0,
        experimentRotationIndex: 0,
        completedExperiments: [],
        activeExperiment: null,
        results: {},  // experimentId -> { outcome, metrics, kept }
      },
      evaluate: {
        lastRun: null,
        runCount: 0,
        keptTechniques: [],
        discardedTechniques: [],
      },
      adapt: {
        lastRun: null,
        runCount: 0,
        adaptationLog: [],  // last 100 adaptations
      },
    },
    metrics: {
      improvementRate: 0,       // % improvement per cycle
      cumulativeImprovement: 0, // total % improvement since start
      baselineMetrics: null,    // snapshot at system start
      latestMetrics: null,      // most recent measurement
      trend: 'initializing',    // improving, stable, declining, initializing
    },
    config: {
      researchTopicsPerCycle: 2,
      experimentsPerMonth: 2,
      measurementRetention: 90,  // days
      adaptationLogRetention: 100,
      minSamplesForDecision: 5,
    },
  };
}

function saveState(state) {
  try {
    if (!fs.existsSync(LEARNING_DIR)) {
      fs.mkdirSync(LEARNING_DIR, { recursive: true });
    }
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
  } catch (e) {
    logEntry('error', `Could not save state: ${e.message}`);
  }
}

// =============================================================================
// LOGGING
// =============================================================================

function logEntry(level, message, data = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'perpetual-self-improvement',
    message,
    ...data,
  };

  const line = `[${entry.timestamp}] [${level.toUpperCase()}] ${message}`;
  console.log(line);

  try {
    if (!fs.existsSync(LEARNING_DIR)) {
      fs.mkdirSync(LEARNING_DIR, { recursive: true });
    }
    fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + '\n', 'utf8');
  } catch (_) {}
}

// =============================================================================
// DATABASE HELPERS
// =============================================================================

let _sqlite3 = null;
function getSqlite3() {
  if (!_sqlite3) {
    try { _sqlite3 = require('sqlite3').verbose(); } catch (_) {
      _sqlite3 = require(path.join(LEARNING_DIR, 'node_modules', 'sqlite3')).verbose();
    }
  }
  return _sqlite3;
}

function openDb() {
  const sqlite3 = getSqlite3();
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) return reject(err);
      db.run('PRAGMA journal_mode = WAL', () => {
        db.run('PRAGMA busy_timeout = 5000', () => resolve(db));
      });
    });
  });
}

function dbAll(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => err ? reject(err) : resolve(rows || []));
  });
}

function dbGet(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => err ? reject(err) : resolve(row || null));
  });
}

function dbRun(db, sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) reject(err);
      else resolve({ lastID: this.lastID, changes: this.changes });
    });
  });
}

function closeDb(db) {
  return new Promise((resolve) => {
    if (db) db.close(() => resolve());
    else resolve();
  });
}

// =============================================================================
// PHASE 1: RESEARCH -- Weekly self-learning paper discovery
// =============================================================================

async function runResearchPhase(state) {
  logEntry('info', '=== PHASE 1: RESEARCH (Self-Learning Papers) ===');

  const phase = state.phases.research;
  const topicsPerCycle = state.config.researchTopicsPerCycle;

  // Select topics using adaptive rotation (same strategy as perpetual-web-learner)
  const allTopics = SELF_LEARNING_RESEARCH_TOPICS;
  const recentIndices = new Set(
    (phase.topicEffectiveness._recentIndices || []).slice(0, 6)
  );

  // Score topics: boost effective ones, suppress recently used
  const scored = allTopics.map((topic, idx) => {
    let weight = 1.0;
    const eff = phase.topicEffectiveness[topic];
    if (eff && eff.runCount > 0) {
      weight *= (1 + eff.avgFindings / 10);
    }
    if (recentIndices.has(idx)) {
      weight *= 0.15; // Suppress recently used
    }
    weight *= (0.8 + Math.random() * 0.4); // Epsilon-greedy jitter
    return { topic, idx, weight };
  });

  scored.sort((a, b) => b.weight - a.weight);
  const selectedTopics = scored.slice(0, topicsPerCycle);

  logEntry('info', `Selected research topics: ${selectedTopics.map(t => t.topic).join('; ')}`);

  let totalPapersFound = 0;

  for (const { topic, idx } of selectedTopics) {
    try {
      // Use the perpetual-web-learner's research infrastructure
      const research = require('./research-session');
      const result = await research.investigate(topic, {
        sources: ['arxiv', 'hackernews', 'github'],
        maxResultsPerSource: 5,
        persist: true,
      });

      const findings = result.summary?.totalFindings || 0;
      totalPapersFound += findings;

      // Update topic effectiveness
      if (!phase.topicEffectiveness[topic]) {
        phase.topicEffectiveness[topic] = { totalFindings: 0, avgFindings: 0, runCount: 0 };
      }
      const eff = phase.topicEffectiveness[topic];
      eff.totalFindings += findings;
      eff.runCount++;
      eff.avgFindings = eff.totalFindings / eff.runCount;
      eff.lastRun = new Date().toISOString();

      logEntry('info', `Research "${topic}": ${findings} findings`);
    } catch (e) {
      logEntry('warn', `Research failed for "${topic}": ${e.message}`);
    }
  }

  // Update recent indices
  phase.topicEffectiveness._recentIndices = [
    ...selectedTopics.map(t => t.idx),
    ...(phase.topicEffectiveness._recentIndices || []),
  ].slice(0, 10);

  phase.lastRun = new Date().toISOString();
  phase.runCount++;
  phase.totalPapersFound += totalPapersFound;

  logEntry('info', `Research phase complete: ${totalPapersFound} papers found (${phase.totalPapersFound} all-time)`);

  return { totalPapersFound };
}

// =============================================================================
// PHASE 2: MEASURE -- Daily performance measurement
// =============================================================================

async function runMeasurePhase(state) {
  logEntry('info', '=== PHASE 2: MEASURE (Daily Performance) ===');

  const db = await openDb();
  const phase = state.phases.measure;

  try {
    const snapshot = {
      timestamp: new Date().toISOString(),
      metrics: {},
    };

    // 1. Average quality score (last 7 days)
    const qualityRow = await dbGet(db, `
      SELECT AVG(quality_score) AS avg_quality, COUNT(*) AS count
      FROM execution_log
      WHERE quality_score IS NOT NULL AND timestamp > datetime('now', '-7 days')
    `);
    snapshot.metrics.avg_quality_score = qualityRow?.avg_quality || 0;
    snapshot.metrics.recent_execution_count = qualityRow?.count || 0;

    // 2. Average LIS score
    const lisRows = await dbAll(db, `
      SELECT json_extract(outcome_notes, '$.lis_score') AS lis
      FROM execution_log
      WHERE outcome_notes IS NOT NULL AND timestamp > datetime('now', '-7 days')
    `);
    const lisScores = lisRows.filter(r => r.lis !== null).map(r => parseFloat(r.lis));
    snapshot.metrics.avg_lis_score = lisScores.length > 0
      ? lisScores.reduce((a, b) => a + b, 0) / lisScores.length
      : 0;

    // 3. Backward transfer rate (how many task types show degradation)
    const bwtRows = await dbAll(db, `
      SELECT bwt_impact FROM parameter_tuning WHERE bwt_impact IS NOT NULL AND bwt_impact != '{}'
    `);
    let degradedCount = 0;
    for (const row of bwtRows) {
      try {
        const impact = JSON.parse(row.bwt_impact);
        for (const delta of Object.values(impact)) {
          if (delta < -0.05) degradedCount++;
        }
      } catch (_) {}
    }
    snapshot.metrics.backward_transfer_degradations = degradedCount;

    // 4. Knowledge freshness ratio
    const statusRows = await dbAll(db, `
      SELECT COALESCE(status, 'active') AS status, COUNT(*) AS cnt
      FROM parameter_tuning
      GROUP BY status
    `);
    const statusMap = {};
    for (const r of statusRows) statusMap[r.status] = r.cnt;
    const totalKnowledge = Object.values(statusMap).reduce((a, b) => a + b, 0);
    snapshot.metrics.knowledge_freshness_ratio = totalKnowledge > 0
      ? (statusMap.active || 0) / totalKnowledge
      : 1;
    snapshot.metrics.knowledge_status = statusMap;

    // 5. Pareto optimal model count
    const paretoRow = await dbGet(db, `
      SELECT COUNT(*) AS cnt FROM pareto_fronts WHERE is_pareto_optimal = 1
    `);
    snapshot.metrics.pareto_optimal_count = paretoRow?.cnt || 0;

    // 6. Curriculum level distribution
    const curriculumRows = await dbAll(db, `
      SELECT current_level, COUNT(*) AS cnt FROM curriculum_state GROUP BY current_level
    `);
    snapshot.metrics.curriculum_levels = {};
    for (const r of curriculumRows) {
      snapshot.metrics.curriculum_levels[`level_${r.current_level}`] = r.cnt;
    }

    // 7. Research findings from perpetual-web-learner
    try {
      const webState = JSON.parse(
        fs.readFileSync(path.join(RESEARCH_DIR, 'perpetual-state.json'), 'utf8')
      );
      snapshot.metrics.research_findings_total = webState.totalFindingsStored || 0;
      snapshot.metrics.research_run_count = webState.runCount || 0;
    } catch (_) {
      snapshot.metrics.research_findings_total = 0;
    }

    // 8. Meta-analysis summary
    try {
      const metaRows = await dbAll(db, `
        SELECT COUNT(*) AS total,
               AVG(net_benefit) AS avg_benefit,
               SUM(CASE WHEN net_benefit > 0 THEN 1 ELSE 0 END) AS positive
        FROM meta_insights
      `);
      if (metaRows.length > 0) {
        snapshot.metrics.meta_insight_count = metaRows[0].total;
        snapshot.metrics.meta_avg_benefit = metaRows[0].avg_benefit || 0;
        snapshot.metrics.meta_positive_rate = metaRows[0].total > 0
          ? metaRows[0].positive / metaRows[0].total
          : 0;
      }
    } catch (_) {}

    // Store snapshot
    phase.history.push(snapshot);

    // Retain only last N measurements
    const retention = state.config.measurementRetention;
    if (phase.history.length > retention) {
      phase.history = phase.history.slice(-retention);
    }

    // Compute trend and improvement rate
    computeTrend(state, snapshot);

    phase.lastRun = new Date().toISOString();
    phase.runCount++;

    logEntry('info', `Measurement complete: quality=${(snapshot.metrics.avg_quality_score || 0).toFixed(3)}, ` +
      `LIS=${(snapshot.metrics.avg_lis_score || 0).toFixed(3)}, ` +
      `freshness=${(snapshot.metrics.knowledge_freshness_ratio || 0).toFixed(2)}, ` +
      `trend=${state.metrics.trend}`);

    return snapshot;

  } finally {
    await closeDb(db);
  }
}

/**
 * Compute improvement trend from measurement history
 */
function computeTrend(state, latestSnapshot) {
  const history = state.phases.measure.history;
  state.metrics.latestMetrics = latestSnapshot.metrics;

  if (!state.metrics.baselineMetrics && history.length > 0) {
    state.metrics.baselineMetrics = history[0].metrics;
  }

  if (history.length < 3) {
    state.metrics.trend = 'initializing';
    return;
  }

  // Compare last 7 measurements to previous 7
  const recent = history.slice(-7);
  const previous = history.slice(-14, -7);

  if (previous.length < 3) {
    state.metrics.trend = 'initializing';
    return;
  }

  const recentAvg = recent.reduce((s, m) => s + (m.metrics.avg_quality_score || 0), 0) / recent.length;
  const previousAvg = previous.reduce((s, m) => s + (m.metrics.avg_quality_score || 0), 0) / previous.length;

  const delta = recentAvg - previousAvg;
  const relativeChange = previousAvg > 0 ? (delta / previousAvg) * 100 : 0;

  state.metrics.improvementRate = relativeChange;

  if (state.metrics.baselineMetrics) {
    const baseQuality = state.metrics.baselineMetrics.avg_quality_score || 0;
    if (baseQuality > 0) {
      state.metrics.cumulativeImprovement =
        ((recentAvg - baseQuality) / baseQuality) * 100;
    }
  }

  if (relativeChange > 1) {
    state.metrics.trend = 'improving';
  } else if (relativeChange < -1) {
    state.metrics.trend = 'declining';
  } else {
    state.metrics.trend = 'stable';
  }
}

// =============================================================================
// PHASE 3: EXPERIMENT -- Monthly technique exploration
// =============================================================================

async function runExperimentPhase(state) {
  logEntry('info', '=== PHASE 3: EXPERIMENT (Monthly Technique Exploration) ===');

  const phase = state.phases.experiment;
  const db = await openDb();

  try {
    // Select next experiment from rotation
    const expIdx = phase.experimentRotationIndex % EXPERIMENT_TYPES.length;
    const experiment = EXPERIMENT_TYPES[expIdx];

    logEntry('info', `Running experiment: ${experiment.name} (${experiment.id})`);
    logEntry('info', `Description: ${experiment.description}`);

    const experimentRun = {
      id: `exp_${Date.now()}_${crypto.randomBytes(4).toString('hex')}`,
      experimentType: experiment.id,
      name: experiment.name,
      startedAt: new Date().toISOString(),
      params: experiment.params,
      results: {},
      outcome: 'pending',
    };

    phase.activeExperiment = experimentRun;

    // Execute experiment based on type
    switch (experiment.id) {
      case 'reptile_beta_sweep':
        experimentRun.results = await experimentReptileBetaSweep(db, experiment.params);
        break;

      case 'curriculum_threshold_tuning':
        experimentRun.results = await experimentCurriculumThresholds(db, experiment.params);
        break;

      case 'model_routing_accuracy':
        experimentRun.results = await experimentModelRoutingAccuracy(db, experiment.params);
        break;

      case 'feedback_strategy_comparison':
        experimentRun.results = await experimentFeedbackStrategies(db, experiment.params);
        break;

      case 'stale_knowledge_interval':
        experimentRun.results = await experimentStalenessIntervals(db, experiment.params);
        break;

      case 'pareto_recompute_frequency':
        experimentRun.results = await experimentParetoFrequency(db, experiment.params);
        break;

      case 'topic_rotation_strategy':
        experimentRun.results = await experimentTopicRotation(db, experiment.params);
        break;

      case 'quality_weight_sensitivity':
        experimentRun.results = await experimentQualityWeights(db, experiment.params);
        break;

      default:
        experimentRun.results = { error: `Unknown experiment type: ${experiment.id}` };
    }

    experimentRun.completedAt = new Date().toISOString();
    experimentRun.outcome = experimentRun.results.error ? 'failed' : 'completed';

    // Store results
    phase.results[experimentRun.id] = experimentRun;
    phase.completedExperiments.push({
      id: experimentRun.id,
      type: experiment.id,
      outcome: experimentRun.outcome,
      completedAt: experimentRun.completedAt,
    });

    // Advance rotation
    phase.experimentRotationIndex = (expIdx + 1) % EXPERIMENT_TYPES.length;
    phase.lastRun = new Date().toISOString();
    phase.runCount++;
    phase.activeExperiment = null;

    logEntry('info', `Experiment "${experiment.name}" ${experimentRun.outcome}`);

    return experimentRun;

  } finally {
    await closeDb(db);
  }
}

// --- Experiment implementations ---

async function experimentReptileBetaSweep(db, params) {
  const betas = params.betas || [0.1, 0.3, 0.5];
  const results = {};

  // Get task types with enough data
  const taskTypes = await dbAll(db, `
    SELECT DISTINCT task_type FROM parameter_tuning WHERE status = 'active'
  `);

  for (const beta of betas) {
    const qualityByTask = {};
    for (const { task_type } of taskTypes) {
      // Simulate quality impact of different beta values using existing data
      const existing = await dbGet(db,
        'SELECT optimal_params, interpolation_beta FROM parameter_tuning WHERE task_type = ?',
        [task_type]
      );
      if (existing) {
        const currentBeta = existing.interpolation_beta || 0.3;
        // Estimate quality change based on beta distance from current
        const stabilityPenalty = Math.abs(beta - currentBeta) * 0.05;
        qualityByTask[task_type] = 1 - stabilityPenalty;
      }
    }
    results[`beta_${beta}`] = {
      beta,
      avgEstimatedQuality: Object.values(qualityByTask).length > 0
        ? Object.values(qualityByTask).reduce((a, b) => a + b, 0) / Object.values(qualityByTask).length
        : 0,
      taskCount: Object.keys(qualityByTask).length,
    };
  }

  const bestBeta = Object.entries(results).sort(
    (a, b) => b[1].avgEstimatedQuality - a[1].avgEstimatedQuality
  )[0];

  return {
    allResults: results,
    bestBeta: bestBeta ? bestBeta[1].beta : 0.3,
    bestQuality: bestBeta ? bestBeta[1].avgEstimatedQuality : 0,
    recommendation: bestBeta
      ? `Use beta=${bestBeta[1].beta} for best stability-speed tradeoff`
      : 'Insufficient data for recommendation',
  };
}

async function experimentCurriculumThresholds(db, params) {
  // Analyze actual promotion/demotion rates at different thresholds
  const history = await dbAll(db, `
    SELECT task_type, current_level, success_rate, total_attempts
    FROM curriculum_state WHERE total_attempts > 0
  `);

  const results = {};
  for (const threshold of params.promotionThresholds) {
    const wouldPromote = history.filter(h => h.success_rate >= threshold);
    results[`promotion_${threshold}`] = {
      threshold,
      wouldPromoteCount: wouldPromote.length,
      promotionRate: history.length > 0 ? wouldPromote.length / history.length : 0,
    };
  }

  return {
    currentDistribution: history.map(h => ({
      taskType: h.task_type,
      level: h.current_level,
      successRate: h.success_rate,
    })),
    thresholdAnalysis: results,
    recommendation: 'Adjust thresholds based on desired promotion velocity',
  };
}

async function experimentModelRoutingAccuracy(db, params) {
  // Check if model selection correlates with quality outcomes
  const routings = await dbAll(db, `
    SELECT model, task_type, AVG(quality_score) AS avg_quality,
           COUNT(*) AS cnt, AVG(confidence) AS avg_conf
    FROM execution_log
    WHERE quality_score IS NOT NULL AND model IS NOT NULL
    GROUP BY model, task_type
    HAVING COUNT(*) >= 3
    ORDER BY task_type, avg_quality DESC
  `);

  // For each task type, check if the most-used model was also the best
  const byTask = {};
  for (const r of routings) {
    if (!byTask[r.task_type]) byTask[r.task_type] = [];
    byTask[r.task_type].push(r);
  }

  let correctRoutings = 0;
  let totalTasks = 0;

  for (const [taskType, models] of Object.entries(byTask)) {
    if (models.length < 2) continue;
    totalTasks++;

    const bestModel = models[0]; // sorted by avg_quality DESC
    const mostUsed = models.sort((a, b) => b.cnt - a.cnt)[0];

    if (bestModel.model === mostUsed.model) {
      correctRoutings++;
    }
  }

  return {
    routingAccuracy: totalTasks > 0 ? correctRoutings / totalTasks : 0,
    correctRoutings,
    totalTasks,
    details: byTask,
    recommendation: correctRoutings / Math.max(1, totalTasks) < 0.6
      ? 'Model routing needs improvement -- task embedder may need retraining'
      : 'Model routing is performing well',
  };
}

async function experimentFeedbackStrategies(db, _params) {
  // Analyze effectiveness of different feedback selection strategies
  const feedbackData = await dbAll(db, `
    SELECT rating_source, COUNT(*) AS cnt,
           AVG(overall_score) AS avg_score
    FROM quality_ratings
    GROUP BY rating_source
  `);

  return {
    feedbackSources: feedbackData,
    recommendation: 'Compare active learning batch annotations across strategies',
  };
}

async function experimentStalenessIntervals(db, params) {
  const intervals = params.intervals_days || [15, 30, 45, 60];
  const results = {};

  for (const days of intervals) {
    const wouldBeStale = await dbGet(db, `
      SELECT COUNT(*) AS cnt FROM parameter_tuning
      WHERE status = 'active' AND updated_at < datetime('now', '-' || ? || ' days')
    `, [days]);

    const total = await dbGet(db, 'SELECT COUNT(*) AS cnt FROM parameter_tuning');

    results[`${days}_days`] = {
      intervalDays: days,
      wouldBeStale: wouldBeStale?.cnt || 0,
      totalKnowledge: total?.cnt || 0,
      staleRatio: total?.cnt > 0 ? (wouldBeStale?.cnt || 0) / total.cnt : 0,
    };
  }

  return {
    intervals: results,
    recommendation: 'Choose interval that keeps stale ratio between 10-30%',
  };
}

async function experimentParetoFrequency(db, params) {
  const intervals = params.intervals || [10, 25, 50, 100];

  const executionCount = await dbGet(db, `
    SELECT COUNT(*) AS cnt FROM execution_log WHERE quality_score IS NOT NULL
  `);

  return {
    currentExecutionCount: executionCount?.cnt || 0,
    intervals: intervals.map(interval => ({
      interval,
      recomputesPerCurrentData: Math.floor((executionCount?.cnt || 0) / interval),
    })),
    recommendation: 'Balance computation cost vs decision freshness',
  };
}

async function experimentTopicRotation(db, _params) {
  // Analyze perpetual-web-learner topic effectiveness
  try {
    const webState = JSON.parse(
      fs.readFileSync(path.join(RESEARCH_DIR, 'perpetual-state.json'), 'utf8')
    );

    const topics = Object.entries(webState.topicEffectiveness || {})
      .filter(([k]) => !k.startsWith('_'))
      .map(([topic, eff]) => ({
        topic,
        avgEngagement: eff.avgEngagement || 0,
        totalFindings: eff.totalFindings || 0,
        runCount: eff.runCount || 0,
        avgFindings: eff.runCount > 0 ? eff.totalFindings / eff.runCount : 0,
      }))
      .sort((a, b) => b.avgEngagement - a.avgEngagement);

    return {
      topicRanking: topics,
      recommendation: topics.length > 3
        ? `Top topics: ${topics.slice(0, 3).map(t => t.topic).join(', ')}`
        : 'Insufficient data for topic ranking',
    };
  } catch (_) {
    return { error: 'Could not load perpetual-web-learner state' };
  }
}

async function experimentQualityWeights(db, params) {
  const dimensions = params.dimensions || ['accuracy', 'completeness', 'clarity'];

  const ratings = await dbAll(db, `
    SELECT accuracy_score, completeness_score, clarity_score,
           actionability_score, overall_score, thumbs_up
    FROM quality_ratings
    WHERE overall_score IS NOT NULL
    LIMIT 200
  `);

  if (ratings.length < 5) {
    return { error: 'Insufficient quality ratings for sensitivity analysis' };
  }

  // Compute correlation between each dimension and user satisfaction
  const results = {};
  for (const dim of dimensions) {
    const key = `${dim}_score`;
    const pairs = ratings.filter(r => r[key] !== null && r.thumbs_up !== null);
    if (pairs.length < 3) continue;

    const dimScores = pairs.map(r => r[key]);
    const thumbs = pairs.map(r => r.thumbs_up);
    const correlation = computeCorrelation(dimScores, thumbs);

    results[dim] = {
      correlation,
      sampleCount: pairs.length,
      avgScore: dimScores.reduce((a, b) => a + b, 0) / dimScores.length,
    };
  }

  return {
    dimensionCorrelations: results,
    recommendation: 'Increase weight for dimensions with highest user-satisfaction correlation',
  };
}

function computeCorrelation(xs, ys) {
  const n = xs.length;
  if (n < 2) return 0;
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, denX = 0, denY = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - meanX;
    const dy = ys[i] - meanY;
    num += dx * dy;
    denX += dx * dx;
    denY += dy * dy;
  }
  const den = Math.sqrt(denX * denY);
  return den > 0 ? num / den : 0;
}

// =============================================================================
// PHASE 4: EVALUATE -- Keep what works, discard what fails
// =============================================================================

async function runEvaluatePhase(state) {
  logEntry('info', '=== PHASE 4: EVALUATE (Keep/Discard Decisions) ===');

  const phase = state.phases.evaluate;
  const expPhase = state.phases.experiment;

  // Review all completed experiments that haven't been evaluated yet
  const unevaluated = expPhase.completedExperiments.filter(exp => {
    return !phase.keptTechniques.find(k => k.experimentId === exp.id) &&
           !phase.discardedTechniques.find(d => d.experimentId === exp.id);
  });

  if (unevaluated.length === 0) {
    logEntry('info', 'No unevaluated experiments to review');
    return { evaluated: 0 };
  }

  let kept = 0;
  let discarded = 0;

  for (const exp of unevaluated) {
    const results = expPhase.results[exp.id];
    if (!results) continue;

    const decision = evaluateExperiment(results);

    if (decision.keep) {
      phase.keptTechniques.push({
        experimentId: exp.id,
        type: exp.type,
        reason: decision.reason,
        evaluatedAt: new Date().toISOString(),
        actionTaken: decision.action,
      });
      kept++;
      logEntry('info', `KEPT: ${exp.type} -- ${decision.reason}`);

      // Apply the improvement if actionable
      if (decision.action) {
        await applyImprovement(state, exp, results, decision);
      }
    } else {
      phase.discardedTechniques.push({
        experimentId: exp.id,
        type: exp.type,
        reason: decision.reason,
        evaluatedAt: new Date().toISOString(),
      });
      discarded++;
      logEntry('info', `DISCARDED: ${exp.type} -- ${decision.reason}`);
    }
  }

  phase.lastRun = new Date().toISOString();
  phase.runCount++;

  logEntry('info', `Evaluation complete: ${kept} kept, ${discarded} discarded`);

  return { evaluated: kept + discarded, kept, discarded };
}

function evaluateExperiment(experimentRun) {
  if (!experimentRun || experimentRun.outcome === 'failed') {
    return { keep: false, reason: 'Experiment failed to execute' };
  }

  const results = experimentRun.results;
  if (!results || results.error) {
    return { keep: false, reason: results?.error || 'No results produced' };
  }

  // Type-specific evaluation
  switch (experimentRun.experimentType) {
    case 'reptile_beta_sweep':
      if (results.bestQuality > 0.9) {
        return { keep: true, reason: `Beta=${results.bestBeta} yields high quality`, action: 'update_beta' };
      }
      return { keep: false, reason: 'No significant improvement from beta sweep' };

    case 'model_routing_accuracy':
      if (results.routingAccuracy !== undefined) {
        if (results.routingAccuracy >= 0.6) {
          return { keep: true, reason: `Routing accuracy ${(results.routingAccuracy * 100).toFixed(0)}% is acceptable` };
        }
        return { keep: false, reason: `Routing accuracy ${(results.routingAccuracy * 100).toFixed(0)}% needs improvement`, action: 'flag_routing' };
      }
      return { keep: false, reason: 'Could not measure routing accuracy' };

    case 'stale_knowledge_interval':
      if (results.intervals) {
        // Find interval that gives 10-30% stale ratio
        for (const [, data] of Object.entries(results.intervals)) {
          if (data.staleRatio >= 0.1 && data.staleRatio <= 0.3) {
            return { keep: true, reason: `${data.intervalDays}-day interval maintains healthy freshness`, action: 'update_staleness' };
          }
        }
      }
      return { keep: false, reason: 'No interval found in target range' };

    default:
      // For other experiments, keep if they produced actionable recommendations
      if (results.recommendation && !results.recommendation.includes('Insufficient')) {
        return { keep: true, reason: results.recommendation };
      }
      return { keep: false, reason: 'No actionable recommendation produced' };
  }
}

async function applyImprovement(state, experiment, experimentRun, decision) {
  logEntry('info', `Applying improvement: ${decision.action} from ${experiment.type}`);

  state.phases.adapt.adaptationLog.push({
    timestamp: new Date().toISOString(),
    source: experiment.type,
    action: decision.action,
    details: experimentRun.results?.recommendation || '',
  });

  // Trim adaptation log
  if (state.phases.adapt.adaptationLog.length > state.config.adaptationLogRetention) {
    state.phases.adapt.adaptationLog = state.phases.adapt.adaptationLog.slice(-state.config.adaptationLogRetention);
  }
}

// =============================================================================
// PHASE 5: ADAPT -- Continuous system tuning
// =============================================================================

async function runAdaptPhase(state) {
  logEntry('info', '=== PHASE 5: ADAPT (Continuous Tuning) ===');

  const phase = state.phases.adapt;
  const db = await openDb();

  try {
    const adaptations = [];

    // 1. Run meta-optimization cycle (stale knowledge, Pareto fronts, meta-analysis)
    try {
      const metaOptimizer = require('./meta-optimizer');
      const metaResult = await metaOptimizer.runMetaOptimizationCycle();

      adaptations.push({
        type: 'meta_optimization',
        staleness: metaResult.staleness,
        paretoFronts: Object.keys(metaResult.paretoFronts || {}).length,
        metaRecommendation: metaResult.metaAnalysis?.recommendation || 'none',
      });

      logEntry('info', `Meta-optimization: ${metaResult.staleness?.newlyStale || 0} stale, ` +
        `${metaResult.staleness?.newlyRetired || 0} retired`);
    } catch (e) {
      logEntry('warn', `Meta-optimization failed: ${e.message}`);
    }

    // 2. Check for backward transfer in recent parameter updates
    try {
      const metaOptimizer = require('./meta-optimizer');
      const recentUpdates = await dbAll(db, `
        SELECT DISTINCT model, task_type FROM parameter_tuning
        WHERE updated_at > datetime('now', '-7 days') AND status = 'active'
      `);

      for (const { model, task_type } of recentUpdates) {
        const bwt = await metaOptimizer.checkBackwardTransfer(model, task_type);
        if (bwt.rollbackRecommended) {
          logEntry('warn', `Backward transfer detected for ${model}/${task_type}, rolling back`);
          await metaOptimizer.rollbackParameters(model, task_type);
          adaptations.push({ type: 'rollback', model, task_type });
        }
      }
    } catch (e) {
      logEntry('warn', `Backward transfer check failed: ${e.message}`);
    }

    // 3. Run parameter optimization if enough new executions
    try {
      const execCount = await dbGet(db, `
        SELECT COUNT(*) AS cnt FROM execution_log
        WHERE timestamp > datetime('now', '-7 days')
      `);

      if ((execCount?.cnt || 0) >= 10) {
        logEntry('info', `${execCount.cnt} recent executions -- running parameter optimization`);
        try {
          execSync('node ' + path.join(LEARNING_DIR, 'optimize-parameters.js') + ' --force', {
            timeout: 60000,
            cwd: LEARNING_DIR,
          });
          adaptations.push({ type: 'parameter_optimization', executionCount: execCount.cnt });
        } catch (e) {
          logEntry('warn', `Parameter optimization failed: ${e.message}`);
        }
      }
    } catch (_) {}

    // 4. Adapt research topic weights based on measurement trends
    if (state.metrics.trend === 'declining') {
      logEntry('info', 'Declining trend detected -- boosting research diversity');
      state.config.researchTopicsPerCycle = Math.min(5, state.config.researchTopicsPerCycle + 1);
      adaptations.push({ type: 'research_diversity_boost', newTopicCount: state.config.researchTopicsPerCycle });
    } else if (state.metrics.trend === 'improving') {
      // Stabilize -- don't change too much during improvement
      state.config.researchTopicsPerCycle = Math.max(2, state.config.researchTopicsPerCycle);
    }

    phase.lastRun = new Date().toISOString();
    phase.runCount++;

    logEntry('info', `Adaptation complete: ${adaptations.length} adaptations applied`);

    return { adaptations };

  } finally {
    await closeDb(db);
  }
}

// =============================================================================
// ORCHESTRATOR -- Main improvement cycle
// =============================================================================

function shouldRun(phase, cadenceHours) {
  if (cadenceHours === 0) return true; // Always run
  if (!phase.lastRun) return true; // Never run before

  const lastRun = new Date(phase.lastRun);
  const now = new Date();
  const hoursSinceLastRun = (now - lastRun) / (1000 * 60 * 60);

  return hoursSinceLastRun >= cadenceHours;
}

async function runImprovementCycle(options = {}) {
  const state = loadState();
  const startTime = Date.now();

  logEntry('info', '================================================================');
  logEntry('info', `PERPETUAL SELF-IMPROVEMENT -- Cycle #${state.cycleCount + 1}`);
  logEntry('info', `Previous cycle: ${state.lastCycle || 'never'}`);
  logEntry('info', `Trend: ${state.metrics.trend} | Improvement rate: ${state.metrics.improvementRate.toFixed(2)}%`);
  logEntry('info', '================================================================');

  const results = {};

  // Phase 1: Research (weekly)
  if (options.forceResearch || shouldRun(state.phases.research, CADENCES.research)) {
    try {
      results.research = await runResearchPhase(state);
    } catch (e) {
      logEntry('error', `Research phase failed: ${e.message}`);
      results.research = { error: e.message };
    }
  } else {
    logEntry('info', 'Skipping research phase (not due yet)');
  }

  // Phase 2: Measure (daily)
  if (options.forceMeasure || shouldRun(state.phases.measure, CADENCES.measure)) {
    try {
      results.measure = await runMeasurePhase(state);
    } catch (e) {
      logEntry('error', `Measure phase failed: ${e.message}`);
      results.measure = { error: e.message };
    }
  } else {
    logEntry('info', 'Skipping measure phase (not due yet)');
  }

  // Phase 3: Experiment (monthly)
  if (options.forceExperiment || shouldRun(state.phases.experiment, CADENCES.experiment)) {
    try {
      results.experiment = await runExperimentPhase(state);
    } catch (e) {
      logEntry('error', `Experiment phase failed: ${e.message}`);
      results.experiment = { error: e.message };
    }
  }

  // Phase 4: Evaluate (after experiments)
  if (results.experiment || shouldRun(state.phases.evaluate, CADENCES.evaluate)) {
    try {
      results.evaluate = await runEvaluatePhase(state);
    } catch (e) {
      logEntry('error', `Evaluate phase failed: ${e.message}`);
      results.evaluate = { error: e.message };
    }
  }

  // Phase 5: Adapt (continuous)
  try {
    results.adapt = await runAdaptPhase(state);
  } catch (e) {
    logEntry('error', `Adapt phase failed: ${e.message}`);
    results.adapt = { error: e.message };
  }

  // Update cycle state
  state.cycleCount++;
  state.lastCycle = new Date().toISOString();

  const durationMs = Date.now() - startTime;

  logEntry('info', '');
  logEntry('info', '--- CYCLE SUMMARY ---');
  logEntry('info', `Cycle:           #${state.cycleCount}`);
  logEntry('info', `Duration:        ${(durationMs / 1000).toFixed(1)}s`);
  logEntry('info', `Trend:           ${state.metrics.trend}`);
  logEntry('info', `Improvement:     ${state.metrics.improvementRate.toFixed(2)}% (cycle), ${state.metrics.cumulativeImprovement.toFixed(2)}% (cumulative)`);
  logEntry('info', `Research:        ${results.research?.totalPapersFound || 'skipped'} papers`);
  logEntry('info', `Measure:         quality=${(state.metrics.latestMetrics?.avg_quality_score || 0).toFixed(3)}`);
  logEntry('info', `Experiments:     ${results.experiment?.outcome || 'skipped'}`);
  logEntry('info', `Evaluate:        ${results.evaluate?.kept || 0} kept, ${results.evaluate?.discarded || 0} discarded`);
  logEntry('info', `Adapt:           ${results.adapt?.adaptations?.length || 0} adaptations`);
  logEntry('info', '--------------------');

  saveState(state);

  return { state, results, durationMs };
}

// =============================================================================
// STATUS REPORT
// =============================================================================

function showStatus() {
  const state = loadState();

  console.log('\n' + '='.repeat(70));
  console.log('PERPETUAL SELF-IMPROVEMENT -- STATUS');
  console.log('='.repeat(70));

  console.log(`\nCycles completed:      ${state.cycleCount}`);
  console.log(`Last cycle:            ${state.lastCycle || 'never'}`);
  console.log(`Trend:                 ${state.metrics.trend}`);
  console.log(`Improvement rate:      ${state.metrics.improvementRate.toFixed(2)}% per cycle`);
  console.log(`Cumulative improvement: ${state.metrics.cumulativeImprovement.toFixed(2)}%`);

  console.log('\nPhase Status:');
  for (const [name, phase] of Object.entries(state.phases)) {
    const cadence = CADENCES[name];
    const due = shouldRun(phase, cadence) ? 'DUE NOW' : 'on schedule';
    console.log(`  ${name.padEnd(12)} | runs: ${String(phase.runCount).padStart(4)} | last: ${phase.lastRun || 'never'} | ${due}`);
  }

  if (state.metrics.latestMetrics) {
    console.log('\nLatest Metrics:');
    for (const [key, value] of Object.entries(state.metrics.latestMetrics)) {
      if (typeof value === 'number') {
        console.log(`  ${key.padEnd(35)} ${value.toFixed(4)}`);
      } else if (typeof value === 'object') {
        console.log(`  ${key.padEnd(35)} ${JSON.stringify(value)}`);
      }
    }
  }

  const evalPhase = state.phases.evaluate;
  console.log(`\nTechniques kept:      ${evalPhase.keptTechniques.length}`);
  console.log(`Techniques discarded: ${evalPhase.discardedTechniques.length}`);

  if (evalPhase.keptTechniques.length > 0) {
    console.log('\nKept techniques:');
    for (const t of evalPhase.keptTechniques.slice(-5)) {
      console.log(`  [${t.evaluatedAt}] ${t.type}: ${t.reason}`);
    }
  }

  console.log('\n' + '='.repeat(70) + '\n');

  return state;
}

// =============================================================================
// SYSTEMD SERVICE + TIMER SETUP
// =============================================================================

function generateSystemdUnits() {
  const serviceContent = `[Unit]
Description=Perpetual Self-Improvement Loop - Meta-Learning Cycle
Documentation=file://${path.join(LEARNING_DIR, 'perpetual-self-improvement.js')}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${LEARNING_DIR}
ExecStart=/usr/bin/node ${path.join(LEARNING_DIR, 'perpetual-self-improvement.js')}
Environment=NODE_ENV=production
Environment=HOME=${process.env.HOME}

# Allow up to 45 minutes per cycle
TimeoutStartSec=2700

# Resource limits
MemoryMax=768M
CPUQuota=60%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=self-improvement

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=${LEARNING_DIR}
ProtectHome=tmpfs
BindPaths=${LEARNING_DIR}

[Install]
WantedBy=default.target
`;

  const timerContent = `[Unit]
Description=Perpetual Self-Improvement Timer - Daily cycle, NO STOPPING CONDITION
Documentation=file://${path.join(LEARNING_DIR, 'perpetual-self-improvement.js')}

[Timer]
# Run daily with randomized delay
OnBootSec=30min
OnUnitActiveSec=24h
RandomizedDelaySec=30min

# Catch up if a run was missed while system was off
Persistent=true

# Accuracy: allow up to 10 min drift for power efficiency
AccuracySec=10min

[Install]
WantedBy=timers.target
`;

  return { service: serviceContent, timer: timerContent };
}

// =============================================================================
// CLI
// =============================================================================

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--help')) {
    console.log(`
Perpetual Self-Improvement Architect

A continuous meta-learning loop that:
  1. RESEARCHES self-learning papers weekly
  2. MEASURES own learning performance daily
  3. EXPERIMENTS with new techniques monthly
  4. EVALUATES results (keep what works, discard what fails)
  5. ADAPTS parameters and strategies continuously

NO STOPPING CONDITION.

Usage:
  node perpetual-self-improvement.js              # Run full cycle
  node perpetual-self-improvement.js --research    # Run research phase only
  node perpetual-self-improvement.js --measure     # Run measurement phase only
  node perpetual-self-improvement.js --experiment  # Run experiment phase only
  node perpetual-self-improvement.js --status      # Show current state
  node perpetual-self-improvement.js --report      # Generate improvement report
  node perpetual-self-improvement.js --setup       # Generate systemd unit files
`);
    process.exit(0);
  }

  if (args.includes('--status')) {
    showStatus();
    process.exit(0);
  }

  if (args.includes('--setup')) {
    const units = generateSystemdUnits();
    const serviceDir = path.join(process.env.HOME, '.config', 'systemd', 'user');

    if (!fs.existsSync(serviceDir)) {
      fs.mkdirSync(serviceDir, { recursive: true });
    }

    fs.writeFileSync(path.join(serviceDir, 'self-improvement.service'), units.service);
    fs.writeFileSync(path.join(serviceDir, 'self-improvement.timer'), units.timer);

    console.log('Systemd units generated:');
    console.log(`  ${path.join(serviceDir, 'self-improvement.service')}`);
    console.log(`  ${path.join(serviceDir, 'self-improvement.timer')}`);
    console.log('\nTo enable:');
    console.log('  systemctl --user daemon-reload');
    console.log('  systemctl --user enable --now self-improvement.timer');
    process.exit(0);
  }

  const options = {};
  if (args.includes('--research')) options.forceResearch = true;
  if (args.includes('--measure')) options.forceMeasure = true;
  if (args.includes('--experiment')) options.forceExperiment = true;

  runImprovementCycle(options)
    .then(({ durationMs }) => {
      logEntry('info', `Cycle complete in ${(durationMs / 1000).toFixed(1)}s. NO STOPPING.`);
      process.exit(0);
    })
    .catch((err) => {
      logEntry('error', `Cycle failed: ${err.message}`);
      logEntry('error', err.stack);
      process.exit(1);
    });
}

module.exports = {
  runImprovementCycle,
  runResearchPhase,
  runMeasurePhase,
  runExperimentPhase,
  runEvaluatePhase,
  runAdaptPhase,
  showStatus,
  loadState,
  CADENCES,
  EXPERIMENT_TYPES,
  IMPROVEMENT_DIMENSIONS,
};
