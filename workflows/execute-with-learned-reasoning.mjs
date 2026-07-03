export const meta = {
  name: 'execute-with-learned-reasoning',
  description: 'Execute task using learned reasoning patterns',
  phases: [
    { title: 'Retrieve Pattern', detail: 'Find similar learned patterns' },
    { title: 'Apply Pattern', detail: 'Execute task with pattern guidance' },
    { title: 'Record Results', detail: 'Update pattern success metrics' }
  ]
}

/**
 * HOW THIS WORKS:
 *
 * 1. User provides task
 * 2. System searches for similar learned patterns
 * 3. If pattern found: Build enhanced prompt with reasoning steps
 * 4. Execute task with best model (Thompson Sampling)
 * 5. Record whether pattern helped
 * 6. Pattern success rate improves over time
 *
 * ITERATION-FRIENDLY:
 * - Falls back gracefully if no pattern found
 * - Records metrics for all executions
 * - Easy to A/B test (with vs without patterns)
 */

const task = args?.task
const taskType = args?.task_type || 'general'

if (!task) {
  return {
    error: 'Missing required arg: task',
    usage: 'Workflow({scriptPath: "...", args: {task: "...", task_type: "..."}  })'
  }
}

log(`Executing task with learned reasoning: ${taskType}`)
log(`Task: ${task.substring(0, 100)}...`)
log('')

// Phase 1: Retrieve Pattern
phase('Retrieve Pattern')

log('Searching for learned patterns...')

const patternSearch = await agent(`Search for learned reasoning patterns for this task.

Task: ${task}
Task Type: ${taskType}

Instructions:
1. Query PostgreSQL for similar patterns:

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 -c "
import sys
sys.path.insert(0, 'tools')
from reasoning_learner import OrchestratorReasoningLearner

learner = OrchestratorReasoningLearner()
patterns = learner.get_patterns_for_task(
    task='${task.replace(/'/g, "\\'")}',
    task_type='${taskType}',
    limit=3
)

if patterns:
    print('FOUND_PATTERNS=True')
    for p in patterns:
        print(f'PATTERN_ID={p[\"id\"]}')
        print(f'SUCCESS_RATE={p[\"success_rate\"]:.2%}')
        print(f'STEPS={len(p[\"reasoning_steps\"])}')
else:
    print('FOUND_PATTERNS=False')

learner.close()
"

2. Parse results

Return JSON with:
{
  "found": true/false,
  "patterns": [
    {
      "id": (number),
      "success_rate": (number),
      "step_count": (number),
      "reasoning_steps": [...],
      "example": "..."
    }
  ],
  "best_pattern_id": (number or null)
}`, {
  label: 'search-patterns',
  phase: 'Retrieve Pattern',
  schema: {
    type: 'object',
    properties: {
      found: { type: 'boolean' },
      patterns: { type: 'array' },
      best_pattern_id: { type: 'number' }
    },
    required: ['found']
  }
})

if (!patternSearch.found || !patternSearch.patterns || patternSearch.patterns.length === 0) {
  log('⚠️  No learned patterns found - executing without guidance')

  // Execute without pattern (fallback)
  const fallbackResult = await agent(task, {
    label: 'execute-no-pattern',
    phase: 'Apply Pattern'
  })

  return {
    pattern_used: false,
    result: fallbackResult,
    verdict: '⚠️  Executed without learned pattern (none available)'
  }
}

const bestPattern = patternSearch.patterns[0]
log(`✓ Found ${patternSearch.patterns.length} learned pattern(s)`)
log(`  Using pattern #${bestPattern.id} (${(bestPattern.success_rate*100).toFixed(0)}% success rate)`)
log(`  Pattern has ${bestPattern.step_count} reasoning steps`)
log('')

// Phase 2: Apply Pattern
phase('Apply Pattern')

log('Building enhanced prompt with learned reasoning...')

const enhancedPrompt = `Task: ${task}

This task is similar to: ${taskType}

Use this proven reasoning pattern (success rate: ${(bestPattern.success_rate*100).toFixed(0)}%):
${bestPattern.reasoning_steps.map((step, i) => `${i+1}. ${step}`).join('\n')}

Example similar task:
${bestPattern.example || '(see above)'}

Now solve the given task following the same reasoning pattern. Be explicit about each step.`

log('Executing task with pattern guidance...')

const executionStart = Date.now()

const result = await agent(enhancedPrompt, {
  label: 'execute-with-pattern',
  phase: 'Apply Pattern'
})

const executionTime = Date.now() - executionStart

log(`✓ Task completed in ${executionTime}ms`)
log('')

// Phase 3: Record Results
phase('Record Results')

log('Recording pattern usage metrics...')

// Evaluate quality (simple heuristic - can improve)
const qualityScore = result ? 0.8 : 0.3  // Placeholder - ideally get from user feedback

const recordResult = await agent(`Record pattern usage to PostgreSQL.

Pattern Used: ${bestPattern.id}
Task: ${task}
Execution Time: ${executionTime}ms
Quality Score: ${qualityScore}
Success: ${result ? 'true' : 'false'}

Instructions:
1. Update pattern usage statistics:

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 -c "
import sys
import hashlib
sys.path.insert(0, 'tools')
from reasoning_learner import OrchestratorReasoningLearner

learner = OrchestratorReasoningLearner()

task_hash = hashlib.sha256('${task.replace(/'/g, "\\'")}'.encode()).hexdigest()

learner.record_pattern_usage(
    pattern_id=${bestPattern.id},
    task_hash=task_hash,
    model='orchestrator',
    success=${result ? 'True' : 'False'},
    execution_time_ms=${executionTime},
    quality_score=${qualityScore},
    feedback={'workflow': 'execute-with-learned-reasoning'}
)

stats = learner.get_statistics()
print(f'TOTAL_USAGE={stats[\"total_usage_count\"]}')
print(f'AVG_SUCCESS={stats[\"avg_success_rate\"]:.2%}')

learner.close()
"

2. Return stats

Return JSON with:
{
  "recorded": true/false,
  "total_usage": (number),
  "avg_success_rate": (number)
}`, {
  label: 'record-usage',
  phase: 'Record Results',
  schema: {
    type: 'object',
    properties: {
      recorded: { type: 'boolean' },
      total_usage: { type: 'number' },
      avg_success_rate: { type: 'number' }
    },
    required: ['recorded']
  }
})

if (recordResult.recorded) {
  log(`✓ Pattern usage recorded`)
  log(`  Total pattern usage: ${recordResult.total_usage}`)
  log(`  System-wide avg success: ${(recordResult.avg_success_rate*100).toFixed(0)}%`)
}

// Return comprehensive results
return {
  pattern_used: true,
  pattern_id: bestPattern.id,
  result: result,
  execution_metrics: {
    execution_time_ms: executionTime,
    quality_score: qualityScore,
    pattern_success_rate: bestPattern.success_rate
  },
  system_stats: {
    total_usage: recordResult.total_usage,
    avg_success_rate: recordResult.avg_success_rate
  },
  verdict: `✅ Executed with pattern #${bestPattern.id} (${(bestPattern.success_rate*100).toFixed(0)}% historical success)`
}
