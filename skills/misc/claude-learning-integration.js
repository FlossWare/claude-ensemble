/**
 * Claude Learning Integration - Active Intelligence for Main Loop
 *
 * Makes Claude's main decision loop ACTIVELY USE the learning systems:
 * - Consults historical learnings before making decisions
 * - Searches knowledge bases (disseminator, web synthesis, PDFs)
 * - Uses Thompson Sampling for intelligent model selection
 * - Records decisions and outcomes to feed the learning loop
 * - Decides when to delegate to orchestrator for complex coordination
 *
 * This bridges the gap between "having intelligence" and "using intelligence".
 *
 * Knowledge base search uses ChromaDB vector embeddings for semantic similarity,
 * so a query like "async error handling" finds learnings titled "promise rejection
 * patterns". Falls back to substring matching when ChromaDB is unavailable.
 *
 * Usage:
 *   import { consultLearnings, selectModelIntelligently, searchKnowledgeBases,
 *            recordDecision, shouldUseOrchestrator } from './claude-learning-integration.js';
 *
 *   // Before making a decision
 *   const guidance = await consultLearnings('code-review');
 *   const model = await selectModelIntelligently('code-review', { useThompson: true });
 *   const knowledge = await searchKnowledgeBases('How to handle async patterns?');
 *
 *   // Decide coordination strategy
 *   if (shouldUseOrchestrator(task)) {
 *     // Delegate to orchestrator-brain.js
 *   }
 *
 *   // After execution
 *   await recordDecision({
 *     task_type: 'code-review',
 *     model_used: 'opus',
 *     decision: 'Use multi-AI consensus',
 *     outcome: 'success',
 *     quality_score: 0.92
 *   });
 */

import { readFileSync, existsSync, appendFileSync, writeFileSync, readdirSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import * as db from './learning/db.js';
import * as thompson from './learning/thompson-sampling.js';
import * as orchestrator from './orchestrator.js';
import * as semanticKB from './shared/semantic-knowledge-search.js';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || process.env.USERPROFILE || '/tmp';
const LEARNING_DIR = join(HOME, '.claude', 'learning');
const DISSEMINATOR_KB = join(LEARNING_DIR, 'disseminator-knowledge.jsonl');
const DISSEMINATOR_VECTORS = join(LEARNING_DIR, 'disseminator-vectors.jsonl');
const RESEARCH_DIR = join(LEARNING_DIR, 'research');
const DECISIONS_LOG = join(LEARNING_DIR, 'decisions.jsonl');
const META_LEARNINGS = join(LEARNING_DIR, 'meta-learnings.jsonl');

// Thresholds for orchestrator delegation
const ORCHESTRATOR_THRESHOLDS = {
  MIN_MODEL_COUNT: 3,           // Use orchestrator when needing 3+ models
  HIGH_COMPLEXITY_SCORE: 0.7,   // Complexity score > 0.7 -> orchestrator
  MULTI_DOMAIN: true,           // Cross-domain tasks -> orchestrator
  UNKNOWN_TASK: 0.3,            // If past success rate < 0.3 -> orchestrator
};

// Track whether semantic search has been initialized for this process
let _semanticInitialized = false;

// ============================================================================
// CONSULT LEARNINGS - What worked before?
// ============================================================================

/**
 * Consult historical learnings for guidance on a task type.
 * Returns what worked well, what failed, and recommendations.
 *
 * @param {string} taskType - Type of task (code-review, multi-model-consensus, etc.)
 * @param {Object} options - Query options
 * @param {number} options.days - Look back N days (default: 30)
 * @param {number} options.minQuality - Minimum quality score to consider (default: 0.7)
 * @returns {Promise<Object>} Learning guidance
 */
export async function consultLearnings(taskType, options = {}) {
  const { days = 30, minQuality = 0.7 } = options;

  try {
    // 1. Query database for past executions
    const recentExecutions = db.query(`
      SELECT model, strategy, quality_score, confidence, outcome,
             worker_models, arbiter_model, parameters,
             duration_ms, cost_usd, task_description
      FROM execution_log
      WHERE task_type = ?
        AND timestamp > datetime('now', '-' || ? || ' days')
        AND quality_score IS NOT NULL
      ORDER BY quality_score DESC
      LIMIT 50
    `, [taskType, days]);

    if (recentExecutions.length === 0) {
      return {
        available: false,
        task_type: taskType,
        recommendation: 'No historical data - consider using Thompson Sampling to explore',
        confidence: 0.0,
      };
    }

    // 2. Analyze what worked well
    const successful = recentExecutions.filter(e => e.quality_score >= minQuality);
    const failed = recentExecutions.filter(e => e.quality_score < 0.5);

    // 3. Extract patterns
    const bestModels = _extractBestModels(successful);
    const bestStrategies = _extractBestStrategies(successful);
    const commonFailures = _extractCommonFailures(failed);
    const optimalParams = _extractOptimalParams(successful);

    // 4. Get model performance metrics
    const modelMetrics = await orchestrator.compareModels(taskType, { days });

    // 5. Check for meta-learnings
    const metaLearnings = _loadMetaLearnings(taskType);

    // 6. Synthesize guidance
    const avgQuality = successful.reduce((sum, e) => sum + e.quality_score, 0) / successful.length;
    const avgCost = successful.reduce((sum, e) => sum + (e.cost_usd || 0), 0) / successful.length;
    const avgDuration = successful.reduce((sum, e) => sum + (e.duration_ms || 0), 0) / successful.length;

    return {
      available: true,
      task_type: taskType,
      sample_size: recentExecutions.length,
      success_rate: successful.length / recentExecutions.length,
      avg_quality: avgQuality,
      avg_cost: avgCost,
      avg_duration: avgDuration,

      best_models: bestModels.slice(0, 3),
      best_strategies: bestStrategies.slice(0, 3),
      optimal_params: optimalParams,

      common_failures: commonFailures,
      model_metrics: modelMetrics.slice(0, 5),
      meta_learnings: metaLearnings,

      recommendation: _synthesizeRecommendation(bestModels, bestStrategies, modelMetrics),
      confidence: Math.min(0.95, 0.5 + (successful.length / 100)),
    };
  } catch (err) {
    console.error(`[consultLearnings] Error: ${err.message}`);
    return {
      available: false,
      task_type: taskType,
      error: err.message,
      recommendation: 'Error consulting learnings - fallback to defaults',
      confidence: 0.0,
    };
  }
}

/**
 * Extract best-performing models from successful executions
 */
function _extractBestModels(executions) {
  const modelScores = {};

  for (const exec of executions) {
    const model = exec.model || exec.arbiter_model;
    if (!model) continue;

    if (!modelScores[model]) {
      modelScores[model] = { total: 0, count: 0, model };
    }
    modelScores[model].total += exec.quality_score;
    modelScores[model].count += 1;
  }

  return Object.values(modelScores)
    .map(m => ({ model: m.model, avg_quality: m.total / m.count, count: m.count }))
    .sort((a, b) => b.avg_quality - a.avg_quality);
}

/**
 * Extract best-performing strategies
 */
function _extractBestStrategies(executions) {
  const strategyScores = {};

  for (const exec of executions) {
    const strategy = exec.strategy || 'unknown';

    if (!strategyScores[strategy]) {
      strategyScores[strategy] = { total: 0, count: 0, strategy };
    }
    strategyScores[strategy].total += exec.quality_score;
    strategyScores[strategy].count += 1;
  }

  return Object.values(strategyScores)
    .map(s => ({ strategy: s.strategy, avg_quality: s.total / s.count, count: s.count }))
    .sort((a, b) => b.avg_quality - a.avg_quality);
}

/**
 * Extract common failure patterns
 */
function _extractCommonFailures(executions) {
  const failures = {};

  for (const exec of executions) {
    const key = `${exec.model}_${exec.strategy || 'unknown'}`;
    if (!failures[key]) {
      failures[key] = { model: exec.model, strategy: exec.strategy, count: 0, avg_score: 0 };
    }
    failures[key].count += 1;
    failures[key].avg_score += exec.quality_score;
  }

  return Object.values(failures)
    .map(f => ({ ...f, avg_score: f.avg_score / f.count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);
}

/**
 * Extract optimal parameters from successful executions
 */
function _extractOptimalParams(executions) {
  const params = {};
  let count = 0;

  for (const exec of executions) {
    if (!exec.parameters) continue;
    try {
      const p = typeof exec.parameters === 'string' ? JSON.parse(exec.parameters) : exec.parameters;
      for (const [key, value] of Object.entries(p)) {
        if (!params[key]) params[key] = [];
        params[key].push(value);
      }
      count++;
    } catch (_err) {
      // Skip malformed parameters
    }
  }

  // Calculate mode or average for each parameter
  const optimal = {};
  for (const [key, values] of Object.entries(params)) {
    if (typeof values[0] === 'number') {
      optimal[key] = values.reduce((sum, v) => sum + v, 0) / values.length;
    } else {
      // Mode for non-numeric
      const counts = {};
      for (const v of values) {
        counts[v] = (counts[v] || 0) + 1;
      }
      optimal[key] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
    }
  }

  return optimal;
}

/**
 * Load meta-learnings for task type
 */
function _loadMetaLearnings(taskType) {
  if (!existsSync(META_LEARNINGS)) return [];

  try {
    const lines = readFileSync(META_LEARNINGS, 'utf-8').trim().split('\n').filter(Boolean);
    return lines
      .map(line => {
        try {
          return JSON.parse(line);
        } catch (_err) {
          return null;
        }
      })
      .filter(ml => ml && ml.task_type === taskType)
      .slice(0, 5);
  } catch (_err) {
    return [];
  }
}

/**
 * Synthesize recommendation from analysis
 */
function _synthesizeRecommendation(bestModels, bestStrategies, modelMetrics) {
  const parts = [];

  if (bestModels.length > 0) {
    parts.push(`Use ${bestModels[0].model} (avg quality: ${bestModels[0].avg_quality.toFixed(2)})`);
  }

  if (bestStrategies.length > 0 && bestStrategies[0].strategy !== 'unknown') {
    parts.push(`with ${bestStrategies[0].strategy} strategy`);
  }

  if (modelMetrics.length >= 3) {
    parts.push(`Consider multi-AI with top 3: ${modelMetrics.slice(0, 3).map(m => m.model).join(', ')}`);
  }

  return parts.join('; ');
}

// ============================================================================
// MODEL SELECTION - Use Thompson Sampling
// ============================================================================

/**
 * Intelligently select model(s) using Thompson Sampling and historical data.
 *
 * @param {string} taskType - Type of task
 * @param {Object} options - Selection options
 * @param {boolean} options.useThompson - Use Thompson Sampling (default: true)
 * @param {number} options.count - Number of models to select (default: 1)
 * @param {string[]} options.candidates - Candidate models (default: all)
 * @returns {Promise<string|string[]>} Selected model(s)
 */
export async function selectModelIntelligently(taskType, options = {}) {
  const {
    useThompson = true,
    count = 1,
    candidates = ['opus', 'sonnet', 'haiku', 'fable', 'gpt-4o', 'gemini'],
  } = options;

  try {
    if (useThompson) {
      // Use Thompson Sampling for exploration/exploitation balance
      return await orchestrator.selectModel(taskType, {
        count,
        models: candidates,
        strategy: 'thompson',
      });
    } else {
      // Use greedy (best historical performance)
      return await orchestrator.selectModel(taskType, {
        count,
        models: candidates,
        strategy: 'greedy',
      });
    }
  } catch (err) {
    console.error(`[selectModelIntelligently] Error: ${err.message}`);
    return count === 1 ? 'sonnet' : ['opus', 'sonnet', 'haiku'];
  }
}

// ============================================================================
// KNOWLEDGE BASE SEARCH - Semantic Vector Search via ChromaDB
// ============================================================================

/**
 * Search knowledge bases for relevant information using semantic vector search.
 * Uses ChromaDB embeddings (all-mpnet-base-v2, 1024-dim, cosine distance) via
 * a Python bridge to find semantically similar content even when wording differs.
 *
 * Example: Query "async error handling" finds "promise rejection patterns"
 * Example: Query "deployment pipeline" finds "CI/CD workflow orchestration"
 *
 * Falls back to naive substring matching if ChromaDB/Python is unavailable.
 *
 * @param {string} query - Natural language search query
 * @param {Object} options - Search options
 * @param {number} options.limit - Max results per source (default: 5)
 * @param {number} options.minConfidence - Minimum confidence score (default: 0.5)
 * @param {boolean} options.autoIndex - Auto-index KBs if not yet indexed (default: true)
 * @returns {Promise<Object>} Search results from all sources
 */
export async function searchKnowledgeBases(query, options = {}) {
  const { limit = 5, minConfidence = 0.5, autoIndex = true } = options;

  const results = {
    query,
    method: 'unknown',
    disseminator: [],
    web_synthesis: [],
    total_found: 0,
  };

  try {
    // Check if ChromaDB semantic search is available
    if (semanticKB.isAvailable()) {
      // Lazily auto-index knowledge bases on first search
      if (autoIndex && !_semanticInitialized) {
        _semanticInitialized = true;
        try {
          await semanticKB.ensureIndexed();
        } catch (indexErr) {
          console.error(`[searchKnowledgeBases] Auto-indexing failed: ${indexErr.message}`);
          // Continue with search anyway -- collections may already have data
        }
      }

      // Semantic search across all knowledge bases
      const semanticResults = await semanticKB.searchAll(query, { limit, minConfidence });

      results.method = 'semantic';
      results.disseminator = semanticResults.disseminator || [];
      results.web_synthesis = semanticResults.web_synthesis || [];
      results.total_found = semanticResults.total_found || 0;

      return results;
    }

    // Fallback: ChromaDB not available, use substring matching
    console.warn('[searchKnowledgeBases] ChromaDB unavailable, falling back to substring matching');
    results.method = 'substring-fallback';

    if (existsSync(DISSEMINATOR_KB)) {
      results.disseminator = _searchDisseminatorKBSubstring(query, limit, minConfidence);
    }

    if (existsSync(RESEARCH_DIR)) {
      results.web_synthesis = _searchWebSynthesisSubstring(query, limit, minConfidence);
    }

    results.total_found = results.disseminator.length + results.web_synthesis.length;

    return results;
  } catch (err) {
    console.error(`[searchKnowledgeBases] Error: ${err.message}`);

    // Last resort fallback to substring matching
    try {
      results.method = 'substring-fallback-error';
      results.error = err.message;

      if (existsSync(DISSEMINATOR_KB)) {
        results.disseminator = _searchDisseminatorKBSubstring(query, limit, minConfidence);
      }
      if (existsSync(RESEARCH_DIR)) {
        results.web_synthesis = _searchWebSynthesisSubstring(query, limit, minConfidence);
      }
      results.total_found = results.disseminator.length + results.web_synthesis.length;
    } catch (_fallbackErr) {
      // Even fallback failed
    }

    return results;
  }
}

// ============================================================================
// KNOWLEDGE BASE INDEXING
// ============================================================================

/**
 * Index or re-index knowledge bases into ChromaDB for semantic search.
 * Call this after adding new knowledge entries to make them searchable.
 *
 * @param {Object} options - Indexing options
 * @param {boolean} options.disseminator - Index disseminator KB (default: true)
 * @param {boolean} options.webSynthesis - Index web synthesis (default: true)
 * @param {number} options.minConfidence - Skip entries below this (default: 0)
 * @returns {Promise<Object>} Indexing summary
 */
export async function indexKnowledgeBases(options = {}) {
  const { disseminator = true, webSynthesis = true, minConfidence = 0 } = options;

  if (!semanticKB.isAvailable()) {
    return {
      success: false,
      error: 'ChromaDB not available. Requires: python3 with chromadb installed (pip install chromadb)',
    };
  }

  const summary = {
    success: true,
    disseminator: null,
    web_synthesis: null,
  };

  try {
    if (disseminator) {
      summary.disseminator = await semanticKB.indexDisseminatorKB({ minConfidence });
      console.log(`[indexKnowledgeBases] Disseminator: indexed ${summary.disseminator.indexed} entries`);
    }

    if (webSynthesis) {
      summary.web_synthesis = await semanticKB.indexWebSynthesis({ minConfidence });
      console.log(`[indexKnowledgeBases] Web synthesis: indexed ${summary.web_synthesis.indexed} entries`);
    }

    _semanticInitialized = true;
    return summary;
  } catch (err) {
    console.error(`[indexKnowledgeBases] Error: ${err.message}`);
    return { success: false, error: err.message, ...summary };
  }
}

/**
 * Get statistics about the semantic search index.
 *
 * @returns {Promise<Object>} { disseminator_count, web_synthesis_count, chroma_dir }
 */
export async function getIndexStats() {
  if (!semanticKB.isAvailable()) {
    return { available: false, error: 'ChromaDB not available' };
  }

  return await semanticKB.getIndexStats();
}

// ============================================================================
// SUBSTRING FALLBACK SEARCH
// These functions are used when ChromaDB is not available. They perform
// naive case-insensitive substring matching -- the original behavior before
// semantic search was integrated.
// ============================================================================

/**
 * Substring fallback: search disseminator knowledge base.
 * Only matches when the query text appears literally in title/content/entities.
 */
function _searchDisseminatorKBSubstring(query, limit, minConfidence) {
  try {
    const lines = readFileSync(DISSEMINATOR_KB, 'utf-8').trim().split('\n').filter(Boolean);
    const queryLower = query.toLowerCase();

    const matches = [];
    for (const line of lines) {
      try {
        const item = JSON.parse(line);

        // Skip low-confidence items
        if (item.confidence && item.confidence < minConfidence) continue;

        const titleMatch = item.title?.toLowerCase().includes(queryLower);
        const contentMatch = item.content?.toLowerCase().includes(queryLower);
        const entityMatch = item.entities?.some(e => e.toLowerCase().includes(queryLower));

        if (titleMatch || contentMatch || entityMatch) {
          matches.push({
            ...item,
            relevance: (titleMatch ? 0.5 : 0) + (contentMatch ? 0.3 : 0) + (entityMatch ? 0.2 : 0),
            source: 'disseminator',
          });
        }
      } catch (_err) {
        // Skip malformed lines
      }
    }

    return matches
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, limit);
  } catch (err) {
    console.error(`[_searchDisseminatorKBSubstring] Error: ${err.message}`);
    return [];
  }
}

/**
 * Substring fallback: search web synthesis findings.
 * Only matches when the query text appears literally in title/finding/topics.
 */
function _searchWebSynthesisSubstring(query, limit, minConfidence) {
  try {
    const files = readdirSync(RESEARCH_DIR)
      .filter(f => f.startsWith('web-synthesis-') && f.endsWith('.jsonl'));

    const queryLower = query.toLowerCase();
    const matches = [];

    for (const file of files) {
      const filePath = join(RESEARCH_DIR, file);
      const lines = readFileSync(filePath, 'utf-8').trim().split('\n').filter(Boolean);

      for (const line of lines) {
        try {
          const item = JSON.parse(line);

          // Skip low-confidence items
          if (item.confidence && item.confidence < minConfidence) continue;

          const titleMatch = item.title?.toLowerCase().includes(queryLower);
          const findingMatch = item.finding?.toLowerCase().includes(queryLower);
          const topicMatch = item.topics?.some(t => t.toLowerCase().includes(queryLower));

          if (titleMatch || findingMatch || topicMatch) {
            matches.push({
              ...item,
              relevance: (titleMatch ? 0.5 : 0) + (findingMatch ? 0.3 : 0) + (topicMatch ? 0.2 : 0),
              source: 'web_synthesis',
              source_file: file,
            });
          }
        } catch (_err) {
          // Skip malformed lines
        }
      }
    }

    return matches
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, limit);
  } catch (err) {
    console.error(`[_searchWebSynthesisSubstring] Error: ${err.message}`);
    return [];
  }
}

// ============================================================================
// ORCHESTRATOR DELEGATION DECISION
// ============================================================================

/**
 * Decide whether to delegate a task to the orchestrator.
 * Uses heuristics based on task complexity, model count, and historical success.
 *
 * @param {Object} task - Task description
 * @param {string} task.type - Task type
 * @param {number} task.complexity - Complexity score (0-1)
 * @param {boolean} task.multiDomain - Whether task spans multiple domains
 * @param {number} task.modelCount - Number of models needed
 * @returns {Promise<Object>} Delegation decision
 */
export async function shouldUseOrchestrator(task) {
  const { type, complexity = 0.5, multiDomain = false, modelCount = 1 } = task;

  try {
    // Get historical success rate for this task type
    const guidance = await consultLearnings(type);
    const successRate = guidance.success_rate || 0.5;

    const reasons = [];
    let useOrchestrator = false;

    // Reason 1: High model count
    if (modelCount >= ORCHESTRATOR_THRESHOLDS.MIN_MODEL_COUNT) {
      reasons.push(`Needs ${modelCount} models (threshold: ${ORCHESTRATOR_THRESHOLDS.MIN_MODEL_COUNT})`);
      useOrchestrator = true;
    }

    // Reason 2: High complexity
    if (complexity >= ORCHESTRATOR_THRESHOLDS.HIGH_COMPLEXITY_SCORE) {
      reasons.push(`High complexity: ${complexity.toFixed(2)} (threshold: ${ORCHESTRATOR_THRESHOLDS.HIGH_COMPLEXITY_SCORE})`);
      useOrchestrator = true;
    }

    // Reason 3: Multi-domain task
    if (multiDomain && ORCHESTRATOR_THRESHOLDS.MULTI_DOMAIN) {
      reasons.push('Multi-domain task requires specialized coordination');
      useOrchestrator = true;
    }

    // Reason 4: Poor historical success rate
    if (successRate < ORCHESTRATOR_THRESHOLDS.UNKNOWN_TASK) {
      reasons.push(`Low success rate: ${(successRate * 100).toFixed(0)}% (threshold: ${ORCHESTRATOR_THRESHOLDS.UNKNOWN_TASK * 100}%)`);
      useOrchestrator = true;
    }

    return {
      use_orchestrator: useOrchestrator,
      confidence: useOrchestrator ? 0.8 : 0.6,
      reasons,
      guidance,
    };
  } catch (err) {
    console.error(`[shouldUseOrchestrator] Error: ${err.message}`);
    return {
      use_orchestrator: false,
      confidence: 0.3,
      reasons: [`Error: ${err.message}`],
    };
  }
}

// ============================================================================
// RECORD DECISION - Feed the learning loop
// ============================================================================

/**
 * Record a decision and its outcome to feed the learning loop.
 * Logs to decisions.jsonl and learning.db.
 *
 * @param {Object} decision - Decision data
 * @param {string} decision.task_type - Type of task
 * @param {string} decision.model_used - Model that was used
 * @param {string} decision.decision - What was decided
 * @param {string} decision.outcome - Outcome (success/failure/partial)
 * @param {number} decision.quality_score - Quality score (0-1)
 * @param {Object} decision.metadata - Additional metadata
 * @returns {Promise<Object>} Recording result
 */
export async function recordDecision(decision) {
  const {
    task_type,
    model_used,
    decision: decisionText,
    outcome,
    quality_score,
    metadata = {},
  } = decision;

  const record = {
    id: randomUUID(),
    timestamp: new Date().toISOString(),
    task_type,
    model_used,
    decision: decisionText,
    outcome,
    quality_score,
    metadata,
  };

  try {
    // 1. Log to decisions.jsonl
    appendFileSync(DECISIONS_LOG, JSON.stringify(record) + '\n', 'utf-8');

    // 2. Log to learning database
    db.logOrchestration({
      execution_id: record.id,
      model: model_used,
      task_type,
      outcome,
      quality_score,
      outcome_notes: decisionText,
      parameters: JSON.stringify(metadata),
    });

    // 3. Update Thompson Sampling if model was selected via Thompson
    if (metadata.selected_via_thompson) {
      thompson.updateModel(model_used, quality_score);
    }

    return {
      success: true,
      recorded_id: record.id,
      timestamp: record.timestamp,
    };
  } catch (err) {
    console.error(`[recordDecision] Error: ${err.message}`);
    return {
      success: false,
      error: err.message,
    };
  }
}

// ============================================================================
// DECISION SUMMARY - What have we learned recently?
// ============================================================================

/**
 * Get summary of recent decisions and their outcomes.
 *
 * @param {Object} options - Query options
 * @param {number} options.limit - Max decisions to return (default: 20)
 * @param {string} options.task_type - Filter by task type
 * @returns {Promise<Object>} Decision summary
 */
export async function getDecisionSummary(options = {}) {
  const { limit = 20, task_type } = options;

  try {
    if (!existsSync(DECISIONS_LOG)) {
      return { total: 0, decisions: [] };
    }

    const lines = readFileSync(DECISIONS_LOG, 'utf-8').trim().split('\n').filter(Boolean);
    const decisions = lines
      .map(line => {
        try {
          return JSON.parse(line);
        } catch (_err) {
          return null;
        }
      })
      .filter(d => d && (!task_type || d.task_type === task_type))
      .reverse()
      .slice(0, limit);

    const successCount = decisions.filter(d => d.outcome === 'success').length;
    const avgQuality = decisions.reduce((sum, d) => sum + (d.quality_score || 0), 0) / decisions.length;

    return {
      total: decisions.length,
      success_rate: successCount / decisions.length,
      avg_quality: avgQuality,
      decisions,
    };
  } catch (err) {
    console.error(`[getDecisionSummary] Error: ${err.message}`);
    return { total: 0, decisions: [], error: err.message };
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
  consultLearnings,
  selectModelIntelligently,
  searchKnowledgeBases,
  indexKnowledgeBases,
  getIndexStats,
  shouldUseOrchestrator,
  recordDecision,
  getDecisionSummary,
};
