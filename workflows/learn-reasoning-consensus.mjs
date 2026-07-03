export const meta = {
  name: 'learn-reasoning-consensus',
  description: 'Learn reasoning patterns from multi-model consensus',
  phases: [
    { title: 'Parallel Reasoning', detail: '6 diverse models solve same task' },
    { title: 'Extract Consensus', detail: 'Find common reasoning patterns' },
    { title: 'Store & Validate', detail: 'Save pattern to PostgreSQL' }
  ]
}

/**
 * HOW THIS WORKS:
 *
 * 1. User provides task
 * 2. Orchestrator assigns to 6 diverse models in parallel
 * 3. Each model provides: solution + reasoning steps + confidence
 * 4. System finds consensus (what did 4+ models do similarly?)
 * 5. Stores learned pattern in PostgreSQL
 * 6. Future similar tasks use this pattern automatically
 *
 * ITERATION-FRIENDLY DESIGN:
 * - args parameter controls all behavior
 * - Easy to test different model counts
 * - Easy to adjust consensus threshold
 * - Results logged for analysis
 */

// Validate args
const task = args?.task
const taskType = args?.task_type || 'general'
const workerCount = args?.worker_count || 6
const minConsensus = args?.min_consensus || 0.66

if (!task) {
  return {
    error: 'Missing required arg: task',
    usage: 'Workflow({scriptPath: "...", args: {task: "...", task_type: "..."}  })'
  }
}

log(`Learning reasoning pattern for: ${taskType}`)
log(`Task: ${task.substring(0, 100)}...`)
log(`Workers: ${workerCount}, Min consensus: ${(minConsensus*100).toFixed(0)}%`)
log('')

// Phase 1: Parallel Reasoning
phase('Parallel Reasoning')

log(`Assigning task to ${workerCount} diverse models...`)

// Define diverse model set (can customize via args in future)
const diverseModels = [
  'opus',           // Most capable, expensive
  'sonnet',         // Balanced
  'haiku',          // Fast
  'gemini-2.0-flash-exp:free',  // Google's latest
  'deepseek-r1-distill-llama-70b',  // Reasoning specialist
  'qwen/qwen-2.5-72b-instruct'  // Code specialist
]

const workers = diverseModels.slice(0, workerCount)

const workerResults = await parallel(
  workers.map((model, idx) => () =>
    agent(`Solve this task and explain your reasoning step-by-step.

Task Type: ${taskType}
Task: ${task}

IMPORTANT: Return structured JSON with:
{
  "solution": "your complete solution",
  "reasoning_steps": [
    "step 1 description",
    "step 2 description",
    ...
  ],
  "confidence": 0.0-1.0  (how confident you are)
}

Be explicit about your reasoning process. Each step should be a clear action or decision.`, {
      label: `worker-${idx+1}:${model.substring(0, 20)}`,
      phase: 'Parallel Reasoning',
      model: model,
      schema: {
        type: 'object',
        properties: {
          solution: { type: 'string' },
          reasoning_steps: {
            type: 'array',
            items: { type: 'string' }
          },
          confidence: { type: 'number', minimum: 0, maximum: 1 }
        },
        required: ['solution', 'reasoning_steps', 'confidence']
      }
    }).then(result => ({
      model: model,
      solution: result?.solution || '',
      reasoning_steps: result?.reasoning_steps || [],
      confidence: result?.confidence || 0,
      result: result
    }))
  )
)

const validResults = workerResults.filter(Boolean)

log(`✓ ${validResults.length}/${workerCount} workers completed`)
for (const r of validResults) {
  log(`  ${r.model}: ${r.reasoning_steps.length} steps, ${(r.confidence*100).toFixed(0)}% confidence`)
}
log('')

// Phase 2: Extract Consensus
phase('Extract Consensus')

log('Analyzing reasoning patterns across models...')

const consensusExtraction = await agent(`Extract consensus reasoning pattern from multi-model results.

Task: ${task}
Task Type: ${taskType}

Worker Results (${validResults.length} models):
${JSON.stringify(validResults.map(r => ({
  model: r.model,
  steps: r.reasoning_steps,
  confidence: r.confidence
})), null, 2)}

Instructions:
1. Find reasoning steps that appear in ${Math.ceil(workerCount * minConsensus)}+ models (${(minConsensus*100).toFixed(0)}% consensus)
2. Extract common pattern (what did most models do?)
3. Identify best solution (highest confidence)
4. Calculate consensus quality

Return JSON with:
{
  "consensus_steps": ["step 1", "step 2", ...],  // Common reasoning pattern
  "consensus_score": 0.0-1.0,  // Fraction of models that agreed
  "best_solution": "...",      // Highest confidence solution
  "best_confidence": 0.0-1.0,  // Confidence of best solution
  "pattern_quality": "excellent" | "good" | "weak",
  "reasoning": "why this pattern is reliable"
}

Only extract patterns with ${(minConsensus*100).toFixed(0)}%+ consensus. Return null if no consensus.`, {
  label: 'extract-consensus',
  phase: 'Extract Consensus',
  schema: {
    type: 'object',
    properties: {
      consensus_steps: { type: 'array', items: { type: 'string' } },
      consensus_score: { type: 'number' },
      best_solution: { type: 'string' },
      best_confidence: { type: 'number' },
      pattern_quality: { type: 'string', enum: ['excellent', 'good', 'weak'] },
      reasoning: { type: 'string' }
    },
    required: ['consensus_steps', 'consensus_score', 'best_solution', 'pattern_quality']
  }
})

if (!consensusExtraction || consensusExtraction.consensus_score < minConsensus) {
  log('❌ No consensus found - models disagreed too much')
  return {
    learned: false,
    consensus_score: consensusExtraction?.consensus_score || 0,
    reason: 'Insufficient consensus across models',
    worker_results: validResults
  }
}

log(`✓ Consensus pattern found: ${consensusExtraction.consensus_steps.length} steps`)
log(`  Consensus score: ${(consensusExtraction.consensus_score*100).toFixed(0)}%`)
log(`  Pattern quality: ${consensusExtraction.pattern_quality}`)
log('')

// Phase 3: Store & Validate
phase('Store & Validate')

log('Storing learned pattern to PostgreSQL...')

const storeResult = await agent(`Store this learned reasoning pattern to PostgreSQL.

Pattern Data:
${JSON.stringify({
  task_type: taskType,
  task_description: task,
  reasoning_steps: consensusExtraction.consensus_steps,
  example_task: task,
  example_solution: consensusExtraction.best_solution,
  consensus_score: consensusExtraction.consensus_score,
  avg_confidence: consensusExtraction.best_confidence,
  metadata: {
    worker_count: validResults.length,
    models_used: validResults.map(r => r.model),
    pattern_quality: consensusExtraction.pattern_quality,
    learned_at: new Date().toISOString()
  }
}, null, 2)}

Instructions:
1. Run this Python code to store pattern:

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 -c "
import sys
sys.path.insert(0, 'tools')
from reasoning_learner import OrchestratorReasoningLearner
import json

learner = OrchestratorReasoningLearner()

# Pattern data
worker_results = ${JSON.stringify(validResults.map(r => ({
  model: r.model,
  reasoning_steps: r.reasoning_steps,
  solution: r.solution,
  confidence: r.confidence
})))}

# Learn from consensus
pattern = learner.learn_from_consensus(
    task='${task.replace(/'/g, "\\'")}',
    task_type='${taskType}',
    worker_results=worker_results,
    metadata={
        'pattern_quality': '${consensusExtraction.pattern_quality}',
        'learned_via': 'orchestrator_workflow'
    }
)

if pattern:
    print(f'PATTERN_ID={pattern[\"id\"]}')
    print(f'CONSENSUS={pattern[\"consensus_score\"]:.2%}')
    stats = learner.get_statistics()
    print(f'TOTAL_PATTERNS={stats[\"total_patterns\"]}')
else:
    print('PATTERN_ID=None')

learner.close()
"

2. Parse output and extract PATTERN_ID

Return JSON with:
{
  "stored": true/false,
  "pattern_id": (number or null),
  "total_patterns": (number - total learned so far),
  "message": "success/error message"
}`, {
  label: 'store-pattern',
  phase: 'Store & Validate',
  schema: {
    type: 'object',
    properties: {
      stored: { type: 'boolean' },
      pattern_id: { type: 'number' },
      total_patterns: { type: 'number' },
      message: { type: 'string' }
    },
    required: ['stored', 'message']
  }
})

if (storeResult.stored) {
  log(`✅ Pattern stored successfully (ID: ${storeResult.pattern_id})`)
  log(`   Total patterns learned: ${storeResult.total_patterns}`)
} else {
  log(`⚠️  Pattern storage failed: ${storeResult.message}`)
}

// Return comprehensive results
return {
  learned: storeResult.stored,
  pattern_id: storeResult.pattern_id,
  pattern: {
    task_type: taskType,
    reasoning_steps: consensusExtraction.consensus_steps,
    consensus_score: consensusExtraction.consensus_score,
    quality: consensusExtraction.pattern_quality
  },
  consensus_extraction: consensusExtraction,
  worker_results: validResults.map(r => ({
    model: r.model,
    steps_count: r.reasoning_steps.length,
    confidence: r.confidence
  })),
  statistics: {
    workers_used: validResults.length,
    consensus_score: consensusExtraction.consensus_score,
    pattern_quality: consensusExtraction.pattern_quality,
    total_patterns_learned: storeResult.total_patterns
  },
  verdict: storeResult.stored
    ? `✅ LEARNED: ${consensusExtraction.consensus_steps.length}-step pattern for ${taskType} (${(consensusExtraction.consensus_score*100).toFixed(0)}% consensus)`
    : `❌ NOT LEARNED: ${storeResult.message}`
}
