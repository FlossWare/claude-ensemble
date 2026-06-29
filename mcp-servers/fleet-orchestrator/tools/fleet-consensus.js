import { exec } from 'child_process';
import { promisify } from 'util';
import { createRequire } from 'module';
import shellescape from 'shell-escape';
import { withRetry } from '../lib/retry.js';
import { CircuitBreaker } from '../lib/circuit-breaker.js';
import { getCostTracker } from '../lib/cost-tracker.js';
import { executeOnModel } from '../../../shared/fleet-orchestrator-integrated.js';
import { getWorkflowStorage } from '../../../shared/workflow-storage-adapter.cjs';
import { getWorkers } from '../../../shared/fleet-utils.js';

const require = createRequire(import.meta.url);
const { getCredentialManager } = require('../../../shared/credential-manager.cjs');

const execAsync = promisify(exec);
const circuitBreaker = new CircuitBreaker({ threshold: 5, resetTimeout: 30000 });
const costTracker = getCostTracker();

/**
 * Map model shorthand names to API provider names for credential lookup.
 */
function mapModelToProvider(model) {
  const modelProviderMap = {
    // Anthropic
    'opus': 'anthropic',
    'sonnet': 'anthropic',
    'haiku': 'anthropic',
    'claude-opus-4': 'anthropic',
    'claude-sonnet-4.5': 'anthropic',
    'claude-haiku-4': 'anthropic',
    // OpenAI
    'gpt-4o': 'openai',
    'gpt-4-turbo': 'openai',
    'gpt-3.5-turbo': 'openai',
    // Google
    'gemini': 'google',
    'gemini-2.0-flash-exp': 'google',
    'gemini-1.5-pro': 'google',
    // Groq (free)
    'llama-3.3-70b-versatile': 'groq',
    'llama-3.1-8b-instant': 'groq',
    'mixtral-8x7b-32768': 'groq',
    // DeepInfra (free)
    'meta-llama/Meta-Llama-3.1-70B-Instruct': 'deepinfra',
    // Together (free)
    'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo': 'together',
    // Mistral (free)
    'mistral-large-latest': 'mistral',
    'mistral-small-latest': 'mistral',
    // Cohere (free)
    'command-r-plus': 'cohere',
    // AI21 (free)
    'jamba-1.5-large': 'ai21',
    'jamba-1.5-mini': 'ai21'
  };

  return modelProviderMap[model] || 'anthropic';
}

/**
 * Execute a single model query on a fleet worker.
 * Returns the model's answer along with metadata (tokens, cost, duration).
 */
async function executeModelQuery(model, question, workerPool, timeout_ms) {
  const selectedWorker = workerPool[Math.floor(Math.random() * workerPool.length)];

  // Get API credentials for the selected model's provider
  const credManager = getCredentialManager();
  const apiKey = credManager.getCredentialForProvider(mapModelToProvider(model));

  return await circuitBreaker.execute(selectedWorker, async () => {
    return await withRetry(async () => {
      const startTime = Date.now();

      // Execute on remote worker via SSH with real API call
      const nodeScript = 'const result = executeModelAPI(' + JSON.stringify(model) + ', ' + JSON.stringify(question) + '); console.log(JSON.stringify(result));';
      const remoteCmd = 'cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node -e ' + shellescape([nodeScript]);
      const cmd = 'ssh claude@' + selectedWorker + ' ' + shellescape([remoteCmd]);

      const { stdout } = await execAsync(cmd, { timeout: timeout_ms });
      const apiResult = JSON.parse(stdout);
      const duration_ms = Date.now() - startTime;

      const inputTokens = apiResult.input_tokens || 0;
      const outputTokens = apiResult.output_tokens || 0;

      // Calculate actual cost
      let costData = {
        cost_usd: apiResult.cost_usd || 0,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cost_tracking: false
      };

      if (inputTokens > 0 || outputTokens > 0) {
        try {
          const calculated = costTracker.calculateCost(model, inputTokens, outputTokens);
          costData = {
            cost_usd: calculated.total_cost_usd,
            input_tokens: calculated.input_tokens,
            output_tokens: calculated.output_tokens,
            input_cost_usd: calculated.input_cost_usd,
            output_cost_usd: calculated.output_cost_usd,
            provider: calculated.provider,
            cost_tracking: true
          };
        } catch (costError) {
          console.warn('Failed to calculate cost for model ' + model + ':', costError.message);
          costData.cost_tracking = false;
        }
      }

      return {
        model,
        worker: selectedWorker,
        answer: apiResult.output || stdout.trim(),
        confidence: apiResult.confidence || null,
        duration_ms: apiResult.duration_ms || duration_ms,
        ...costData,
        success: true,
        error: null
      };
    }, {
      maxRetries: 3,
      backoffMs: 1000,
      backoffMultiplier: 2
    });
  });
}

/**
 * Compute consensus from an array of model results.
 *
 * Strategy:
 *   1. Group answers by normalized text.
 *   2. Compute majority vote percentage.
 *   3. If confidence scores are available, compute a weighted average.
 *   4. Determine verdict based on min_confidence threshold.
 */
function computeConsensus(results, min_confidence) {
  const successfulResults = results.filter(r => r.success);
  const failedResults = results.filter(r => !r.success);

  if (successfulResults.length === 0) {
    return {
      consensus_answer: null,
      consensus_confidence: 0,
      agreement_ratio: 0,
      verdict: 'NO_QUORUM',
      reason: 'All model queries failed',
      successful_votes: 0,
      failed_votes: failedResults.length
    };
  }

  // Group answers by normalized text (trim + lowercase for comparison)
  const answerGroups = {};
  for (const r of successfulResults) {
    const normalized = (r.answer || '').trim().toLowerCase();
    if (!answerGroups[normalized]) {
      answerGroups[normalized] = {
        original_answer: r.answer,
        votes: [],
        total_confidence: 0,
        count: 0
      };
    }
    answerGroups[normalized].votes.push(r);
    answerGroups[normalized].count += 1;
    if (r.confidence !== null && r.confidence !== undefined) {
      answerGroups[normalized].total_confidence += r.confidence;
    }
  }

  // Sort groups by vote count descending, then by total confidence descending
  const sortedGroups = Object.values(answerGroups).sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return b.total_confidence - a.total_confidence;
  });

  const winningGroup = sortedGroups[0];
  const agreement_ratio = winningGroup.count / successfulResults.length;

  // Compute weighted confidence if individual confidences are available
  const hasConfidences = winningGroup.votes.some(v => v.confidence !== null && v.confidence !== undefined);
  let consensus_confidence;
  if (hasConfidences) {
    const confVotes = winningGroup.votes.filter(v => v.confidence !== null && v.confidence !== undefined);
    consensus_confidence = confVotes.reduce((sum, v) => sum + v.confidence, 0) / confVotes.length;
  } else {
    // Fall back to agreement ratio as a proxy for confidence
    consensus_confidence = agreement_ratio;
  }

  // Determine verdict
  let verdict;
  let reason;
  if (agreement_ratio === 1.0) {
    verdict = consensus_confidence >= min_confidence ? 'UNANIMOUS_ACCEPT' : 'UNANIMOUS_LOW_CONFIDENCE';
    reason = 'All models agree' + (consensus_confidence < min_confidence ? ' but confidence below threshold' : '');
  } else if (agreement_ratio >= 0.5 && consensus_confidence >= min_confidence) {
    verdict = 'MAJORITY_ACCEPT';
    reason = Math.round(agreement_ratio * 100) + '% agreement, confidence ' + consensus_confidence.toFixed(2);
  } else if (agreement_ratio >= 0.5) {
    verdict = 'MAJORITY_LOW_CONFIDENCE';
    reason = 'Majority agrees but confidence ' + consensus_confidence.toFixed(2) + ' below threshold ' + min_confidence;
  } else {
    verdict = 'NO_CONSENSUS';
    reason = 'No majority agreement (' + sortedGroups.length + ' distinct answers from ' + successfulResults.length + ' models)';
  }

  return {
    consensus_answer: winningGroup.original_answer,
    consensus_confidence: Math.round(consensus_confidence * 1000) / 1000,
    agreement_ratio: Math.round(agreement_ratio * 1000) / 1000,
    verdict,
    reason,
    successful_votes: successfulResults.length,
    failed_votes: failedResults.length,
    distinct_answers: sortedGroups.length,
    answer_distribution: sortedGroups.map(g => ({
      answer_preview: (g.original_answer || '').slice(0, 200),
      vote_count: g.count,
      models: g.votes.map(v => v.model)
    }))
  };
}

/**
 * Fleet Consensus - Execute a question on multiple models in parallel
 * and return majority-vote consensus results.
 *
 * Features:
 *   - Parallel execution across fleet workers with circuit breakers
 *   - Retry with exponential backoff per model
 *   - Cost tracking per model and aggregate
 *   - Workflow storage integration (execution + worker results + arbiter decision)
 *   - Majority voting with confidence weighting
 *   - Graceful degradation (partial failures still produce consensus)
 *
 * @param {Object} params
 * @param {string} params.question - Question or task to get consensus on
 * @param {string[]} params.models - Models to query (default: opus, sonnet, haiku)
 * @param {number} params.min_confidence - Minimum confidence for ACCEPT verdict (default: 0.7)
 * @param {number} params.timeout_ms - Per-model timeout in milliseconds (default: 120000)
 * @param {boolean} params.track_costs - Track costs in PostgreSQL (default: true)
 * @param {boolean} params.track_execution - Track execution in workflow storage (default: true)
 * @returns {Object} Consensus result with votes, costs, and verdict
 */
export async function fleetConsensus({
  question,
  models = ['opus', 'sonnet', 'haiku'],
  min_confidence = 0.7,
  timeout_ms = 120000,
  track_costs = true,
  track_execution = true
}) {
  const startTime = Date.now();

  // Get live worker list from fleet configuration
  const workers = getWorkers();
  const workerPool = workers.map(w => w.hostname);

  if (workerPool.length === 0) {
    throw new Error('No fleet workers available. Check ~/.claude/fleet.json and worker connectivity.');
  }

  // Execute question on all models in parallel
  const results = await Promise.allSettled(
    models.map(async (model) => {
      try {
        return await executeModelQuery(model, question, workerPool, timeout_ms);
      } catch (error) {
        return {
          model,
          worker: null,
          answer: null,
          confidence: null,
          duration_ms: Date.now() - startTime,
          input_tokens: 0,
          output_tokens: 0,
          cost_usd: 0,
          cost_tracking: false,
          success: false,
          error: error.message
        };
      }
    })
  );

  // Unwrap Promise.allSettled results
  const votes = results.map((r, i) => {
    if (r.status === 'fulfilled') {
      return r.value;
    }
    return {
      model: models[i],
      worker: null,
      answer: null,
      confidence: null,
      duration_ms: Date.now() - startTime,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      cost_tracking: false,
      success: false,
      error: r.reason?.message || 'Unknown error'
    };
  });

  // Compute consensus
  const consensus = computeConsensus(votes, min_confidence);

  // Aggregate costs
  const totalCost = votes.reduce((sum, v) => sum + (v.cost_usd || 0), 0);
  const totalInputTokens = votes.reduce((sum, v) => sum + (v.input_tokens || 0), 0);
  const totalOutputTokens = votes.reduce((sum, v) => sum + (v.output_tokens || 0), 0);
  const totalDuration = Date.now() - startTime;

  // Track costs in PostgreSQL
  const costEntries = [];
  if (track_costs) {
    for (const vote of votes) {
      if (vote.success && vote.cost_tracking && (vote.input_tokens > 0 || vote.output_tokens > 0)) {
        try {
          const costEntry = await costTracker.trackCost({
            model: vote.model,
            input_tokens: vote.input_tokens,
            output_tokens: vote.output_tokens,
            worker_id: vote.worker,
            task_hash: Buffer.from(question).toString('hex').slice(0, 64),
            metadata: {
              fleet_consensus: true,
              verdict: consensus.verdict,
              agreement_ratio: consensus.agreement_ratio
            }
          });
          costEntries.push({ model: vote.model, id: costEntry.id, tracked: true });
        } catch (dbError) {
          console.warn('Failed to track cost for model ' + vote.model + ':', dbError.message);
          costEntries.push({ model: vote.model, tracked: false, error: dbError.message });
        }
      }
    }
  }

  // Track execution in workflow storage
  let workflowTracking = { tracked: false };
  if (track_execution) {
    try {
      const storage = getWorkflowStorage();
      const execId = await storage.storeExecution({
        workflow_id: 'consensus-' + Date.now(),
        workflow_name: 'fleet-consensus',
        task_description: question.slice(0, 500),
        total_workers: models.length,
        total_duration_ms: totalDuration,
        outcome: consensus.verdict.includes('ACCEPT') ? 'success' : consensus.verdict === 'NO_QUORUM' ? 'error' : 'partial'
      });

      // Store each vote as a worker result
      for (const vote of votes) {
        await storage.storeWorkerResult({
          workflow_execution_id: execId,
          worker_id: vote.worker || 'unknown',
          execution_host: vote.worker || 'unknown',
          model: vote.model,
          task_assigned: question.slice(0, 100),
          result: vote.answer ? vote.answer.slice(0, 500) : '',
          confidence: vote.confidence,
          duration_ms: vote.duration_ms,
          input_tokens: vote.input_tokens || 0,
          output_tokens: vote.output_tokens || 0,
          cost_usd: vote.cost_usd || 0,
          outcome: vote.success ? 'success' : 'error',
          metadata: {
            fleet_consensus: true,
            error: vote.error || null
          }
        });
      }

      // Store consensus as arbiter decision
      await storage.storeArbiterDecision({
        workflow_execution_id: execId,
        arbiter_model: 'majority-vote',
        decision: consensus.consensus_answer ? consensus.consensus_answer.slice(0, 500) : 'no consensus',
        confidence: consensus.consensus_confidence,
        reasoning: consensus.reason,
        dissenting_views: consensus.answer_distribution
          ? consensus.answer_distribution.slice(1).map(d => d.answer_preview).join(' | ')
          : '',
        metadata: {
          verdict: consensus.verdict,
          agreement_ratio: consensus.agreement_ratio,
          distinct_answers: consensus.distinct_answers,
          min_confidence_threshold: min_confidence
        }
      });

      workflowTracking = { tracked: true, execution_id: execId };
    } catch (dbError) {
      console.warn('Failed to track consensus in workflow storage:', dbError.message);
      workflowTracking = { tracked: false, error: dbError.message };
    }
  }

  return {
    question: question.slice(0, 200),
    models_queried: models,
    ...consensus,
    votes,
    cost_summary: {
      total_cost_usd: Math.round(totalCost * 1000000) / 1000000,
      total_input_tokens: totalInputTokens,
      total_output_tokens: totalOutputTokens,
      per_model: votes.map(v => ({
        model: v.model,
        cost_usd: v.cost_usd || 0,
        input_tokens: v.input_tokens || 0,
        output_tokens: v.output_tokens || 0
      })),
      cost_entries: costEntries.length > 0 ? costEntries : undefined
    },
    timing: {
      total_duration_ms: totalDuration,
      per_model: votes.map(v => ({ model: v.model, duration_ms: v.duration_ms }))
    },
    workers_used: [...new Set(votes.filter(v => v.worker).map(v => v.worker))],
    workflow_tracking: workflowTracking
  };
}
