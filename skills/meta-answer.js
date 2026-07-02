#!/usr/bin/env node
/**
 * Meta-Answer Skill - Adaptive Model Selection with Thompson Sampling
 *
 * This module implements the complete meta-learning loop:
 * 1. Select model via Thompson Sampling (orchestrator)
 * 2. Execute with selected model (would spawn agent in Claude Code)
 * 3. Log execution to learning database
 * 4. Update Thompson Sampling state
 *
 * Usage from Claude Code skill system:
 *   The skill system would call this with the user's question,
 *   and this module would handle model selection, execution,
 *   and learning loop integration.
 *
 * Command-line usage (for testing):
 *   node meta-answer.js "How do I implement retry logic?"
 */

import { selectModel, recordResult, getThompsonStats } from '../orchestrator.js';
import { logExecution } from '../shared/learning-logger.js';
import { randomUUID } from 'crypto';

// ============================================================================
// CONFIGURATION
// ============================================================================

const TASK_TYPE = 'meta-answer';
const DEFAULT_QUALITY_SCORE = 0.8;
const WORKFLOW_NAME = 'meta-answer';

// ============================================================================
// META-ANSWER WORKFLOW
// ============================================================================

/**
 * Execute meta-answer workflow with Thompson Sampling model selection.
 *
 * @param {string} question - User's question
 * @param {object} options - Execution options
 * @param {number} options.qualityScore - Quality score override (default: 0.8)
 * @param {boolean} options.debug - Enable debug output
 * @returns {Promise<object>} Result with model, answer, and learning stats
 */
export async function metaAnswer(question, options = {}) {
  const {
    qualityScore = DEFAULT_QUALITY_SCORE,
    debug = false,
  } = options;

  const runId = randomUUID();
  const startTime = Date.now();

  try {
    // Step 1: Select model via Thompson Sampling
    if (debug) console.log('[meta-answer] Selecting model via Thompson Sampling...');

    const selectedModel = await selectModel(TASK_TYPE, {
      strategy: 'thompson',
      count: 1,
    });

    if (debug) {
      console.log(`[meta-answer] Selected model: ${selectedModel}`);
      const stats = getThompsonStats();
      const modelStats = stats.find(s => s.model === selectedModel);
      if (modelStats) {
        console.log(`[meta-answer] Model stats:`, {
          success_rate: modelStats.success_rate.toFixed(3),
          avg_quality: modelStats.avg_quality.toFixed(3),
          uncertainty: modelStats.uncertainty.toFixed(3),
          total: modelStats.total,
        });
      }
    }

    // Step 2: Execute with selected model
    // NOTE: In the actual Claude Code integration, this would use the Agent tool
    // to spawn an agent with the selected model. For now, we simulate the response.
    const answer = await executeWithModel(selectedModel, question, { debug });

    const endTime = Date.now();
    const durationMs = endTime - startTime;

    // Step 3: Log execution to learning database
    if (debug) console.log('[meta-answer] Logging execution to learning database...');

    const executionId = logExecution({
      run_id: runId,
      model: selectedModel,
      model_role: 'worker',
      workflow: WORKFLOW_NAME,
      task_type: TASK_TYPE,
      quality_score: qualityScore,
      confidence: 0.85, // Could be extracted from agent response
      input_tokens: estimateTokens(question),
      output_tokens: estimateTokens(answer),
      cost_usd: estimateCost(selectedModel, question, answer),
      duration_ms: durationMs,
      outcome: 'success',
      parameters: JSON.stringify({ question: question.substring(0, 100) }),
    });

    if (debug) console.log(`[meta-answer] Logged execution: id=${executionId}`);

    // Step 4: Update Thompson Sampling state
    if (debug) console.log('[meta-answer] Updating Thompson Sampling state...');

    const updatedState = recordResult(selectedModel, qualityScore);

    if (debug) {
      console.log(`[meta-answer] Thompson state updated:`, {
        alpha: updatedState.alpha,
        beta: updatedState.beta,
        total: updatedState.total,
        avg_quality: updatedState.avg_quality.toFixed(3),
      });
    }

    // Return result
    return {
      success: true,
      model: selectedModel,
      question,
      answer,
      execution: {
        id: executionId,
        run_id: runId,
        duration_ms: durationMs,
        quality_score: qualityScore,
      },
      learning: {
        alpha: updatedState.alpha,
        beta: updatedState.beta,
        success_rate: updatedState.alpha / (updatedState.alpha + updatedState.beta),
        total_executions: updatedState.total,
      },
    };
  } catch (error) {
    console.error('[meta-answer] Error:', error.message);

    // Log the failure
    logExecution({
      run_id: runId,
      model: 'unknown',
      model_role: 'worker',
      workflow: WORKFLOW_NAME,
      task_type: TASK_TYPE,
      quality_score: 0.0,
      duration_ms: Date.now() - startTime,
      outcome: 'error',
      error: error.message,
    });

    return {
      success: false,
      error: error.message,
      question,
    };
  }
}

/**
 * Execute with selected model.
 * In the actual implementation, this would spawn an agent via Claude Code's Agent tool.
 * For now, this is a placeholder that returns a simulated response.
 *
 * @param {string} model - Model to use
 * @param {string} question - Question to answer
 * @param {object} options - Execution options
 * @returns {Promise<string>} Answer
 */
async function executeWithModel(model, question, options = {}) {
  const { debug = false } = options;

  if (debug) {
    console.log(`[meta-answer] Executing with model: ${model}`);
    console.log(`[meta-answer] Question: ${question}`);
  }

  // PLACEHOLDER: In the actual Claude Code integration, this would be:
  //
  // const agent = await Agent.spawn({
  //   model: model,
  //   description: 'Meta-answer with Thompson Sampling',
  //   prompt: question,
  // });
  //
  // return agent.response;

  // For testing purposes, return a simulated response
  return `[Simulated ${model} response to: "${question.substring(0, 50)}..."]

This is a placeholder response. In the actual Claude Code integration,
this would be the real response from an agent spawned with model '${model}'.

The agent would provide a detailed, thoughtful answer to your question,
and the quality of that answer would be scored (default: ${DEFAULT_QUALITY_SCORE})
to update the Thompson Sampling state for future model selection.`;
}

/**
 * Estimate tokens for a text (rough approximation).
 */
function estimateTokens(text) {
  return Math.ceil(text.length / 4);
}

/**
 * Estimate cost for a model execution (rough approximation).
 */
function estimateCost(model, input, output) {
  const inputTokens = estimateTokens(input);
  const outputTokens = estimateTokens(output);

  // Rough pricing (per million tokens)
  const pricing = {
    opus: { input: 15.0, output: 75.0 },
    sonnet: { input: 3.0, output: 15.0 },
    haiku: { input: 0.25, output: 1.25 },
    // fable removed per Issue #197 (API 403 errors)
    'gpt-4o': { input: 5.0, output: 15.0 },
    gemini: { input: 2.0, output: 8.0 },
  };

  const rates = pricing[model] || pricing.sonnet;
  const inputCost = (inputTokens / 1_000_000) * rates.input;
  const outputCost = (outputTokens / 1_000_000) * rates.output;

  return inputCost + outputCost;
}

// ============================================================================
// CLI INTERFACE
// ============================================================================

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    console.log(`
Meta-Answer - Adaptive Model Selection with Thompson Sampling

Usage:
  node meta-answer.js <question>
  node meta-answer.js --help

Examples:
  node meta-answer.js "How do I implement retry logic?"
  node meta-answer.js "What's the best way to handle async errors?"

Options:
  --help, -h    Show this help message

This is a test interface. In production, this would be called via
Claude Code's /meta-answer skill system with full agent integration.
`);
    process.exit(0);
  }

  const question = args.join(' ');

  console.log('Meta-Answer Workflow');
  console.log('===================\n');
  console.log(`Question: ${question}\n`);

  const result = await metaAnswer(question, { debug: true });

  console.log('\n===================');
  console.log('Result\n');

  if (result.success) {
    console.log(`Model: ${result.model}`);
    console.log(`Quality Score: ${result.execution.quality_score}`);
    console.log(`Duration: ${result.execution.duration_ms}ms`);
    console.log(`\nLearning Stats:`);
    console.log(`  Alpha: ${result.learning.alpha}`);
    console.log(`  Beta: ${result.learning.beta}`);
    console.log(`  Success Rate: ${(result.learning.success_rate * 100).toFixed(1)}%`);
    console.log(`  Total Executions: ${result.learning.total_executions}`);
    console.log(`\nAnswer:\n${result.answer}`);
  } else {
    console.error(`Error: ${result.error}`);
    process.exit(1);
  }
}

// Run CLI if invoked directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

// ============================================================================
// EXPORTS
// ============================================================================

export default metaAnswer;
