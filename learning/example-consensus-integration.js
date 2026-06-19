/**
 * Example: Integrating Workflow Storage into AI Consensus Workflows
 *
 * This shows how to add automatic workflow logging to existing consensus patterns
 */

const { logWorkflowExecution } = require('./workflow-hook');

/**
 * Example: AI Consensus Weighted Pattern
 * (Simplified version showing integration points)
 */
async function aiConsensusWeighted(prompt, options = {}) {
  const startTime = Date.now();
  const workers = [];
  let arbiter = null;
  let outcome = 'success';

  try {
    // 1. Execute worker models in parallel
    const models = options.models || ['opus', 'sonnet', 'haiku'];

    for (const model of models) {
      const workerStart = Date.now();

      // Simulate worker execution
      const response = await callModel(model, prompt);

      workers.push({
        model,
        response: response.text,
        confidence: response.confidence,
        quality_score: response.quality_score,
        input_tokens: response.usage.input_tokens,
        output_tokens: response.usage.output_tokens,
        cost_usd: calculateCost(model, response.usage),
        duration_ms: Date.now() - workerStart,
        metadata: { temperature: response.temperature }
      });
    }

    // 2. Execute arbiter to synthesize consensus
    const arbiterStart = Date.now();
    const arbiterResponse = await callArbiter(prompt, workers);

    arbiter = {
      model: 'opus',
      response: arbiterResponse.text,
      confidence: arbiterResponse.confidence,
      votes: arbiterResponse.worker_weights,
      reasoning: arbiterResponse.reasoning,
      input_tokens: arbiterResponse.usage.input_tokens,
      output_tokens: arbiterResponse.usage.output_tokens,
      cost_usd: calculateCost('opus', arbiterResponse.usage),
      duration_ms: Date.now() - arbiterStart
    };

    // 3. Calculate total metrics
    const totalCost = workers.reduce((sum, w) => sum + w.cost_usd, 0) + arbiter.cost_usd;
    const duration = Date.now() - startTime;

    // 4. LOG TO DATABASE (this is the integration point)
    await logWorkflowExecution({
      workflow_type: 'consensus-weighted',
      prompt,
      workers,
      arbiter,
      duration_ms: duration,
      total_cost_usd: totalCost,
      outcome: 'success',
      metadata: {
        num_workers: workers.length,
        arbiter_model: arbiter.model,
        session_id: options.sessionId
      }
    });

    return arbiter.response;

  } catch (error) {
    outcome = 'error';

    // Still log the execution even on failure
    if (workers.length > 0 || arbiter) {
      await logWorkflowExecution({
        workflow_type: 'consensus-weighted',
        prompt,
        workers,
        arbiter: arbiter || { model: 'none', response: '', confidence: 0, votes: {} },
        duration_ms: Date.now() - startTime,
        total_cost_usd: workers.reduce((sum, w) => sum + w.cost_usd, 0),
        outcome: 'error',
        metadata: { error: error.message }
      });
    }

    throw error;
  }
}

/**
 * Example: AI Consensus Debate Pattern
 */
async function aiConsensusDebate(prompt, options = {}) {
  const startTime = Date.now();
  const workers = [];
  let arbiter = null;

  try {
    // 1. Initial proposals
    const proposalWorkers = await generateProposals(prompt);
    workers.push(...proposalWorkers);

    // 2. Rebuttals
    const rebuttalWorkers = await generateRebuttals(proposalWorkers);
    workers.push(...rebuttalWorkers);

    // 3. Arbiter judges
    const arbiterStart = Date.now();
    const arbiterResponse = await judgeDebate(prompt, workers);

    arbiter = {
      model: 'opus',
      response: arbiterResponse.text,
      confidence: arbiterResponse.confidence,
      votes: arbiterResponse.scores,
      reasoning: arbiterResponse.verdict,
      input_tokens: arbiterResponse.usage.input_tokens,
      output_tokens: arbiterResponse.usage.output_tokens,
      cost_usd: calculateCost('opus', arbiterResponse.usage),
      duration_ms: Date.now() - arbiterStart
    };

    // 4. LOG TO DATABASE
    await logWorkflowExecution({
      workflow_type: 'consensus-debate',
      prompt,
      workers,
      arbiter,
      duration_ms: Date.now() - startTime,
      total_cost_usd: workers.reduce((sum, w) => sum + w.cost_usd, 0) + arbiter.cost_usd,
      outcome: 'success',
      metadata: {
        num_rounds: 2,
        debate_format: 'adversarial'
      }
    });

    return arbiter.response;

  } catch (error) {
    // Log failed execution
    await logWorkflowExecution({
      workflow_type: 'consensus-debate',
      prompt,
      workers,
      arbiter: arbiter || { model: 'none', response: '', confidence: 0, votes: {} },
      duration_ms: Date.now() - startTime,
      total_cost_usd: workers.reduce((sum, w) => sum + w.cost_usd, 0),
      outcome: 'error',
      metadata: { error: error.message }
    });

    throw error;
  }
}

/**
 * Integration Checklist:
 *
 * For ANY consensus workflow, add these steps:
 *
 * 1. Import the hook:
 *    const { logWorkflowExecution } = require('~/.claude/learning/workflow-hook');
 *
 * 2. Track timing:
 *    const startTime = Date.now();
 *
 * 3. Collect worker data:
 *    - Store each worker result with: model, response, confidence, tokens, cost, duration
 *
 * 4. Collect arbiter data:
 *    - Store arbiter: model, response, confidence, votes, reasoning, tokens, cost, duration
 *
 * 5. Call the hook at the end:
 *    await logWorkflowExecution({
 *      workflow_type: 'your-workflow-name',
 *      prompt,
 *      workers,
 *      arbiter,
 *      duration_ms: Date.now() - startTime,
 *      total_cost_usd: totalCost,
 *      outcome: 'success|failed|error',
 *      metadata: { ... }
 *    });
 *
 * That's it! The hook handles:
 * - Database insertion
 * - Embedding generation
 * - Index updates
 * - Materialized view refresh
 */

// Stub functions (replace with actual implementations)
async function callModel(model, prompt) {
  return {
    text: `Response from ${model}`,
    confidence: 0.85,
    quality_score: 0.80,
    temperature: 0.7,
    usage: { input_tokens: 100, output_tokens: 200 }
  };
}

async function callArbiter(prompt, workers) {
  return {
    text: 'Synthesized consensus response',
    confidence: 0.90,
    worker_weights: { opus: 0.4, sonnet: 0.35, haiku: 0.25 },
    reasoning: 'Weighted by confidence and quality scores',
    usage: { input_tokens: 500, output_tokens: 300 }
  };
}

function calculateCost(model, usage) {
  const rates = {
    opus: { input: 15 / 1e6, output: 75 / 1e6 },
    sonnet: { input: 3 / 1e6, output: 15 / 1e6 },
    haiku: { input: 0.25 / 1e6, output: 1.25 / 1e6 }
  };
  const rate = rates[model] || rates.haiku;
  return usage.input_tokens * rate.input + usage.output_tokens * rate.output;
}

async function generateProposals(prompt) {
  return [
    { model: 'opus', response: 'Proposal 1', confidence: 0.9, quality_score: 0.85, input_tokens: 100, output_tokens: 200, cost_usd: 0.01, duration_ms: 1000 },
    { model: 'sonnet', response: 'Proposal 2', confidence: 0.85, quality_score: 0.80, input_tokens: 100, output_tokens: 180, cost_usd: 0.005, duration_ms: 800 }
  ];
}

async function generateRebuttals(proposals) {
  return [
    { model: 'haiku', response: 'Rebuttal to Proposal 1', confidence: 0.75, quality_score: 0.70, input_tokens: 150, output_tokens: 120, cost_usd: 0.002, duration_ms: 600 }
  ];
}

async function judgeDebate(prompt, workers) {
  return {
    text: 'Final verdict',
    confidence: 0.92,
    scores: { proposal1: 0.8, proposal2: 0.7 },
    verdict: 'Proposal 1 is stronger',
    usage: { input_tokens: 600, output_tokens: 250 }
  };
}

module.exports = {
  aiConsensusWeighted,
  aiConsensusDebate
};
