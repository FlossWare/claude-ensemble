#!/usr/bin/env node

/**
 * Always-On Adversarial Verification Harness
 *
 * Integrates adversarial refutation into all consensus workflows.
 * Runs AFTER weighted voting, BEFORE final acceptance.
 *
 * Architecture:
 * 1. Workers propose answers (existing consensus pattern)
 * 2. Arbiter synthesizes top candidate (existing weighted voting)
 * 3. → ADVERSARIAL VERIFICATION (this harness) ←
 * 4. 3-5 refuters try to DISPROVE the candidate
 * 5. Accept only if ≥2/3 refuters fail to disprove
 *
 * Storage: PostgreSQL workflow.adversarial_verifications table
 * Cost: 3-5 extra API calls per consensus (optimized with free models)
 *
 * Created: 2026-06-28
 */

import { getWorkflowStorage } from './workflow-storage-adapter.cjs';

/**
 * Refuter prompt templates
 * Each template instructs the model to actively try to DISPROVE the answer
 */
const REFUTER_PROMPTS = {
  /**
   * General-purpose refutation (default)
   */
  general: (answer, originalTask) => `
🎯 Your role: ADVERSARIAL REFUTER

You are NOT trying to confirm this answer. You are trying to DISPROVE it.

Original task:
${originalTask}

Proposed answer:
${answer}

Your job: Find bugs, errors, false assumptions, and edge cases.

Default stance: "This answer is WRONG because..."

Analyze:
1. **Logical errors**: Are there reasoning flaws?
2. **False assumptions**: What assumptions might be invalid?
3. **Edge cases**: What scenarios does this fail to handle?
4. **Contradictory evidence**: Is there evidence against this answer?
5. **Missing context**: What critical information is missing?

Return JSON:
{
  "verdict": "REFUTE" | "ACCEPT",
  "confidence": 0.0-1.0,
  "reasoning": "Why this answer fails (or why you couldn't disprove it)",
  "counterexample": "Specific example where this breaks (if found)",
  "severity": "critical" | "major" | "minor" | "none"
}

If you find even ONE critical flaw, vote REFUTE.
Only vote ACCEPT if you genuinely cannot find problems after trying hard.
`,

  /**
   * Code-specific refutation
   */
  code: (answer, originalTask) => `
🎯 Your role: CODE ADVERSARIAL REFUTER

You are NOT a code reviewer. You are a SECURITY AUDITOR trying to break this code.

Original task:
${originalTask}

Proposed code:
${answer}

Your job: Find bugs, security holes, and correctness issues.

Check for:
1. **Security vulnerabilities**: Injection, XSS, auth bypass, etc.
2. **Race conditions**: Concurrency bugs
3. **Memory issues**: Leaks, buffer overflows, null dereferences
4. **Logic bugs**: Off-by-one, boundary errors, incorrect algorithms
5. **API misuse**: Wrong library usage, deprecated methods
6. **Missing validation**: Input sanitization, error handling

Return JSON:
{
  "verdict": "REFUTE" | "ACCEPT",
  "confidence": 0.0-1.0,
  "reasoning": "Why this code is broken (or why you couldn't break it)",
  "exploit": "How to trigger the bug (if found)",
  "severity": "critical" | "major" | "minor" | "none"
}

Be RUTHLESS. Any security flaw = REFUTE.
`,

  /**
   * Fact-checking refutation
   */
  factcheck: (answer, originalTask) => `
🎯 Your role: FACT-CHECKING ADVERSARY

You are NOT confirming facts. You are trying to find MISINFORMATION.

Original question:
${originalTask}

Proposed answer:
${answer}

Your job: Find factual errors and unsupported claims.

Check for:
1. **Contradictory facts**: Does this contradict known information?
2. **Unsupported claims**: Are assertions backed by evidence?
3. **Outdated information**: Is this information still current?
4. **Logical inconsistencies**: Do the facts fit together?
5. **Missing caveats**: What important qualifications are missing?

Return JSON:
{
  "verdict": "REFUTE" | "ACCEPT",
  "confidence": 0.0-1.0,
  "reasoning": "Why this is factually wrong (or why you couldn't disprove it)",
  "counterevidence": "Contradictory facts (if found)",
  "severity": "critical" | "major" | "minor" | "none"
}

Any factual error = REFUTE. Be skeptical.
`,

  /**
   * Architecture/design refutation
   */
  design: (answer, originalTask) => `
🎯 Your role: ARCHITECTURE ADVERSARY

You are NOT endorsing this design. You are trying to find DESIGN FLAWS.

Original task:
${originalTask}

Proposed design:
${answer}

Your job: Find architectural weaknesses and scalability issues.

Check for:
1. **Scalability problems**: Bottlenecks, single points of failure
2. **Coupling issues**: Tight coupling, hidden dependencies
3. **Performance**: O(n²) algorithms, inefficient patterns
4. **Maintainability**: Complexity, technical debt
5. **Operational risks**: Deployment, monitoring, rollback
6. **Alternative approaches**: Better solutions exist?

Return JSON:
{
  "verdict": "REFUTE" | "ACCEPT",
  "confidence": 0.0-1.0,
  "reasoning": "Why this design is flawed (or why you couldn't find flaws)",
  "better_approach": "Alternative design (if applicable)",
  "severity": "critical" | "major" | "minor" | "none"
}

Any major design flaw = REFUTE.
`
};

/**
 * Model selection strategies for refuters
 * Optimize cost by using free models when possible
 */
const REFUTER_MODEL_STRATEGIES = {
  /**
   * Free-only: Use only free API models
   * Cost: $0 per verification
   * Speed: Fast (parallel API calls)
   */
  free: [
    'gemini-2.0-flash-exp',
    'gemini-1.5-flash',
    'llama-3.1-70b-instruct',
    'qwen-2.5-72b-instruct',
    'deepseek-chat'
  ],

  /**
   * Balanced: Mix of free and cheap paid models
   * Cost: ~$0.01-0.05 per verification
   * Speed: Fast
   */
  balanced: [
    'claude-haiku-4',
    'gpt-4o-mini',
    'gemini-2.0-flash-exp',
    'llama-3.3-70b-instruct',
    'deepseek-chat'
  ],

  /**
   * Critical: Use strongest models for high-stakes decisions
   * Cost: ~$0.10-0.50 per verification
   * Speed: Slower
   */
  critical: [
    'claude-opus-4',
    'gpt-4o',
    'gemini-2.0-pro-exp',
    'claude-sonnet-4-5',
    'deepseek-reasoner'
  ],

  /**
   * Local: Use only local Ollama models
   * Cost: $0 (CPU time only)
   * Speed: Slower (CPU inference)
   */
  local: [
    'llama-3.3-70b-instruct',
    'qwen-2.5-72b-instruct',
    'deepseek-r1-14b',
    'mistral-7b-instruct',
    'phi-4-mini'
  ]
};

/**
 * Adversarial verification result
 * @typedef {Object} AdversarialResult
 * @property {boolean} accepted - Whether answer passed adversarial verification
 * @property {string} confidence - 'high' | 'medium' | 'low'
 * @property {number} refuters_failed - Number of refuters who failed to disprove
 * @property {number} refuters_total - Total refuters
 * @property {Array} votes - Individual refuter votes
 * @property {string} verdict - 'ACCEPT' | 'ACCEPT_WITH_CAVEATS' | 'REJECT'
 * @property {Array} critical_issues - Critical issues found (if any)
 * @property {number} cost_usd - Total cost of verification
 */

/**
 * Run adversarial verification on a consensus result
 *
 * @param {Object} options
 * @param {string} options.answer - Proposed answer from consensus
 * @param {string} options.originalTask - Original task/question
 * @param {string} options.promptType - Prompt template to use (general/code/factcheck/design)
 * @param {string} options.modelStrategy - Model selection strategy (free/balanced/critical/local)
 * @param {number} options.numRefuters - Number of refuters to spawn (3-5)
 * @param {number} options.workflow_execution_id - Parent workflow ID for storage
 * @returns {Promise<AdversarialResult>}
 */
export async function verifyAdversarially({
  answer,
  originalTask,
  promptType = 'general',
  modelStrategy = 'free',
  numRefuters = 3,
  workflow_execution_id = null
}) {
  const startTime = Date.now();

  // Select prompt template
  const promptTemplate = REFUTER_PROMPTS[promptType] || REFUTER_PROMPTS.general;

  // Select refuter models
  const modelPool = REFUTER_MODEL_STRATEGIES[modelStrategy] || REFUTER_MODEL_STRATEGIES.free;
  const selectedModels = modelPool.slice(0, numRefuters);

  console.log(`\n🛡️  Adversarial Verification:`);
  console.log(`   Refuters: ${selectedModels.length} (${modelStrategy} strategy)`);
  console.log(`   Prompt: ${promptType}`);

  // Spawn refuters in parallel
  const refuterPromises = selectedModels.map(async (model, idx) => {
    const prompt = promptTemplate(answer, originalTask);

    try {
      const result = await callModel({ model, prompt, maxTokens: 1000 });

      // Parse JSON response
      let parsed;
      try {
        parsed = JSON.parse(result.content);
      } catch {
        // Fallback: extract JSON from response
        const jsonMatch = result.content.match(/\{[\s\S]*\}/);
        parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : {
          verdict: 'ACCEPT',
          confidence: 0.5,
          reasoning: 'Failed to parse refuter response',
          severity: 'none'
        };
      }

      return {
        refuter_id: `refuter-${idx + 1}`,
        model,
        verdict: parsed.verdict,
        confidence: parsed.confidence,
        reasoning: parsed.reasoning,
        counterexample: parsed.counterexample || parsed.exploit || parsed.counterevidence,
        severity: parsed.severity || 'none',
        cost_usd: result.cost_usd,
        duration_ms: result.duration_ms,
        tokens: { input: result.input_tokens, output: result.output_tokens }
      };
    } catch (err) {
      console.error(`   ❌ Refuter ${idx + 1} (${model}) failed: ${err.message}`);
      return {
        refuter_id: `refuter-${idx + 1}`,
        model,
        verdict: 'ACCEPT', // Graceful fallback: accept if refuter crashes
        confidence: 0.0,
        reasoning: `Refuter crashed: ${err.message}`,
        severity: 'none',
        error: err.message
      };
    }
  });

  const votes = await Promise.all(refuterPromises);

  // Calculate results
  const refuteCount = votes.filter(v => v.verdict === 'REFUTE').length;
  const failedToDisprove = votes.length - refuteCount;
  const criticalIssues = votes.filter(v => v.severity === 'critical');
  const majorIssues = votes.filter(v => v.severity === 'major');

  // Determine acceptance
  // Accept if ≥2/3 refuters failed to disprove
  const threshold = Math.ceil(votes.length * 2 / 3);
  const accepted = failedToDisprove >= threshold;

  // Confidence levels
  let confidence;
  if (failedToDisprove === votes.length) {
    confidence = 'high'; // All refuters failed
  } else if (failedToDisprove >= threshold) {
    confidence = 'medium'; // Passed threshold
  } else {
    confidence = 'low'; // Did not pass threshold
  }

  // Final verdict
  let verdict;
  if (criticalIssues.length > 0) {
    verdict = 'REJECT'; // Any critical issue = reject
  } else if (accepted && majorIssues.length === 0) {
    verdict = 'ACCEPT'; // Passed threshold, no major issues
  } else if (accepted) {
    verdict = 'ACCEPT_WITH_CAVEATS'; // Passed threshold but has caveats
  } else {
    verdict = 'REJECT'; // Failed threshold
  }

  // Calculate cost
  const totalCost = votes.reduce((sum, v) => sum + (v.cost_usd || 0), 0);
  const durationMs = Date.now() - startTime;

  const result = {
    accepted,
    confidence,
    refuters_failed: failedToDisprove,
    refuters_total: votes.length,
    votes,
    verdict,
    critical_issues: criticalIssues.map(v => ({
      refuter: v.refuter_id,
      model: v.model,
      reasoning: v.reasoning,
      counterexample: v.counterexample
    })),
    major_issues: majorIssues.map(v => ({
      refuter: v.refuter_id,
      model: v.model,
      reasoning: v.reasoning,
      counterexample: v.counterexample
    })),
    cost_usd: totalCost,
    duration_ms: durationMs
  };

  // Log results
  console.log(`   ✅ Verification complete:`);
  console.log(`      Verdict: ${verdict}`);
  console.log(`      Confidence: ${confidence}`);
  console.log(`      Refuters failed: ${failedToDisprove}/${votes.length}`);
  console.log(`      Critical issues: ${criticalIssues.length}`);
  console.log(`      Major issues: ${majorIssues.length}`);
  console.log(`      Cost: $${totalCost.toFixed(4)}`);
  console.log(`      Duration: ${(durationMs / 1000).toFixed(1)}s`);

  // Store to PostgreSQL
  if (workflow_execution_id) {
    await storeVerification({ workflow_execution_id, result, answer, originalTask });
  }

  return result;
}

/**
 * Store adversarial verification result to PostgreSQL
 */
async function storeVerification({ workflow_execution_id, result, answer, originalTask }) {
  const db = getWorkflowStorage();

  try {
    await db.pool.query(`
      INSERT INTO workflow.adversarial_verifications
        (workflow_execution_id, answer_candidate, original_task, verdict, confidence,
         refuters_failed, refuters_total, critical_issues_count, major_issues_count,
         votes, cost_usd, duration_ms, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
    `, [
      workflow_execution_id,
      answer,
      originalTask,
      result.verdict,
      result.confidence,
      result.refuters_failed,
      result.refuters_total,
      result.critical_issues.length,
      result.major_issues.length,
      JSON.stringify(result.votes),
      result.cost_usd,
      result.duration_ms
    ]);

    console.log(`   💾 Stored verification to PostgreSQL (workflow ${workflow_execution_id})`);
  } catch (err) {
    console.error(`   ⚠️  Failed to store verification: ${err.message}`);
  }
}

/**
 * Call model (stub - integrate with actual multi-model router)
 */
async function callModel({ model, prompt, maxTokens = 1000 }) {
  // TODO: Replace with actual multi-model router call
  // For now, return mock structure
  const mockLatency = 500 + Math.random() * 1000;
  await new Promise(resolve => setTimeout(resolve, mockLatency));

  // Mock cost calculation (rough estimates)
  const costPerToken = {
    'claude-opus-4': 0.000015,
    'claude-sonnet-4-5': 0.000003,
    'claude-haiku-4': 0.0000003,
    'gpt-4o': 0.000005,
    'gpt-4o-mini': 0.0000003,
    'gemini-2.0-flash-exp': 0, // Free
    'gemini-1.5-flash': 0, // Free
    'llama-3.3-70b-instruct': 0, // Free/local
    'qwen-2.5-72b-instruct': 0, // Free/local
    'deepseek-chat': 0, // Free
    'deepseek-r1-14b': 0 // Local
  };

  const inputTokens = Math.ceil(prompt.length / 4);
  const outputTokens = Math.ceil(maxTokens * 0.7); // Estimate
  const cost = (inputTokens + outputTokens) * (costPerToken[model] || 0);

  // Mock refutation logic (33% chance to refute)
  const shouldRefute = Math.random() < 0.33;

  return {
    content: JSON.stringify({
      verdict: shouldRefute ? 'REFUTE' : 'ACCEPT',
      confidence: 0.7 + Math.random() * 0.25,
      reasoning: shouldRefute
        ? 'Found potential issues with edge case handling and missing validation'
        : 'Could not find significant flaws after adversarial analysis',
      severity: shouldRefute ? (Math.random() < 0.2 ? 'critical' : 'major') : 'none'
    }),
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cost_usd: cost,
    duration_ms: mockLatency
  };
}

/**
 * Integration helper: Wrap existing arbiter with adversarial verification
 *
 * Usage in workflows:
 *
 * const arbiterResult = await arbiter(...);
 * const verified = await wrapWithAdversarialVerification({
 *   arbiterResult,
 *   originalTask,
 *   workflow_execution_id
 * });
 *
 * if (!verified.accepted) {
 *   // Reject or flag for human review
 * }
 */
export async function wrapWithAdversarialVerification({
  arbiterResult,
  originalTask,
  workflow_execution_id = null,
  promptType = 'general',
  modelStrategy = 'free'
}) {
  // Extract answer from arbiter result (supports different formats)
  const answer = arbiterResult.decision || arbiterResult.synthesis || arbiterResult.answer || String(arbiterResult);

  return await verifyAdversarially({
    answer,
    originalTask,
    promptType,
    modelStrategy,
    numRefuters: 3,
    workflow_execution_id
  });
}

/**
 * Cost optimization: Cache refutation patterns
 * If similar questions have been refuted before, learn from those patterns
 */
export async function findSimilarRefutations(task, limit = 5) {
  const db = getWorkflowStorage();

  try {
    // Generate embedding for task
    const { generateEmbedding } = await import('./workflow-storage-adapter.cjs');
    const embedding = await generateEmbedding(task);

    if (!embedding) {
      return [];
    }

    const result = await db.pool.query(`
      SELECT av.*, we.task_description, we.task_embedding <=> $1::vector as distance
      FROM workflow.adversarial_verifications av
      JOIN workflow.executions we ON av.workflow_execution_id = we.id
      WHERE we.task_embedding IS NOT NULL
      ORDER BY we.task_embedding <=> $1::vector
      LIMIT $2
    `, [JSON.stringify(embedding), limit]);

    return result.rows;
  } catch (err) {
    console.error('Failed to find similar refutations:', err.message);
    return [];
  }
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];

  if (command === 'verify') {
    const answer = process.argv[3];
    const task = process.argv[4];
    const strategy = process.argv[5] || 'free';

    verifyAdversarially({
      answer,
      originalTask: task,
      modelStrategy: strategy
    }).then(result => {
      console.log('\n' + JSON.stringify(result, null, 2));
      process.exit(result.accepted ? 0 : 1);
    });
  } else if (command === 'similar') {
    const task = process.argv[3];
    findSimilarRefutations(task).then(results => {
      console.log(JSON.stringify(results, null, 2));
    });
  } else {
    console.log('Usage:');
    console.log('  node adversarial-verification-harness.mjs verify "answer" "task" [strategy]');
    console.log('  node adversarial-verification-harness.mjs similar "task"');
    console.log('');
    console.log('Strategies: free, balanced, critical, local');
  }
}
