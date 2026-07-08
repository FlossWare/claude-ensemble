export const meta = {
  name: 'get-next-arbiter',
  description: 'Get next arbiter model in rotation, optionally task-aware via quality-first routing',
  whenToUse: 'Internal helper for cycling through arbiter models. Pass taskType arg to route by capability.',
  phases: [
    { title: 'Read State', detail: 'Load arbiter-state.json' },
    { title: 'Select Pool', detail: 'Determine model pool (task-aware or default)' },
    { title: 'Determine Next', detail: 'Calculate next arbiter in rotation' },
    { title: 'Log Usage', detail: 'Track model selection for monitoring' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// USAGE:
// const result = await workflow('get-next-arbiter')
// Returns: { arbiter: 'sonnet', previous: 'opus' }
//
// TASK-AWARE USAGE:
// const result = await workflow('get-next-arbiter', { taskType: 'code_review' })
// Returns: { arbiter: <best model for code_review>, previous: 'opus', taskType: 'code_review', pool: [...] }

// ---------------------------------------------------------------------------
// CONCURRENCY NOTES
// ---------------------------------------------------------------------------
//
// This workflow reads arbiter-state.json to determine the next arbiter in the
// rotation. The same file is written by update-arbiter-state.js, which may be
// running concurrently in a different workflow invocation.
//
// 1. STALE READS ARE POSSIBLE BUT HARMLESS
//    Between the time this workflow reads last_arbiter and the caller later
//    invokes update-arbiter-state to persist the choice, another workflow may
//    have already advanced the rotation. This means two concurrent callers
//    could read the same last_arbiter value and both select the same "next"
//    arbiter. This is benign: the rotation is best-effort, and the next cycle
//    will self-correct back to the intended round-robin sequence.
//
// 2. NO WRITES HAPPEN HERE
//    This workflow is read-only. It never modifies arbiter-state.json.
//    All mutation is performed by update-arbiter-state.js, so there is no
//    risk of this file causing write-write conflicts.
//
// 3. RACE CONDITION: LAST WRITER WINS (in update-arbiter-state.js)
//    When multiple workflows call update-arbiter-state.js concurrently, the
//    last write wins. One update's history entry may be lost. See the
//    concurrency notes in update-arbiter-state.js for details.
//
// 4. ACCEPTABLE FOR ARBITER ROTATION
//    The arbiter rotation is a soft preference, not a correctness requirement.
//    Occasional duplicate selections or skipped rotations do not affect the
//    quality of consensus results. The system tolerates these races by design.
// ---------------------------------------------------------------------------

// Default hardcoded rotation (fallback when no taskType provided)
const DEFAULT_ROTATION = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

try {
  // PHASE 1: Read arbiter-state.json
  // NOTE: This read may return stale data if update-arbiter-state.js is
  // concurrently writing to the same file. This is harmless -- see
  // concurrency notes above.
  phase('Read State')

  const stateFilePath = '~/.claude/repos/claude-global-skills/arbiter-state.json'

  let arbiterState
  try {
    const stateContent = await read(stateFilePath)
    arbiterState = JSON.parse(stateContent)
    log(`Loaded arbiter state: ${JSON.stringify(arbiterState)}`)
  } catch (error) {
    // File doesn't exist or is invalid - start with null
    log(`Could not read arbiter state (${error.message}), starting fresh`)
    arbiterState = { last_arbiter: null }
  }

  // PHASE 2: Select model pool (task-aware or default)
  phase('Select Pool')

  const taskType = args?.taskType || null
  let rotationPool = DEFAULT_ROTATION
  let poolSource = 'default_hardcoded'
  let filterReason = null

  if (taskType) {
    try {
      const { selectModelsByCapability } = require(
        '../../shared/model-capability-matrix.cjs'
      )
      const { applyRules, getFilterReason } = require(
        '../../shared/task-model-rules.js'
      )

      // Get task-aware ranked models
      const ranked = await selectModelsByCapability(taskType, { limit: 204, minScore: 0.1 })

      if (ranked && ranked.length > 0) {
        const allModels = ranked.map(entry => entry.model)

        // Apply task-specific rules (whitelist/blacklist/anthropic_only)
        const filteredModels = applyRules(allModels, taskType)
        filterReason = getFilterReason(taskType)

        // Take top 6 after filtering
        rotationPool = filteredModels.slice(0, 6)
        poolSource = 'quality_first_task_aware_filtered'

        log(`Task-aware pool for "${taskType}": [${rotationPool.join(', ')}]`)
        log(`Filter reason: ${filterReason}`)
        log(`Filtered ${allModels.length} models -> ${filteredModels.length} models (top 6 selected)`)
      } else {
        log(`No models returned for taskType "${taskType}", falling back to default rotation`)
      }
    } catch (error) {
      log(`Could not load model-capability-matrix (${error.message}), falling back to default rotation`)
    }
  } else {
    log('No taskType provided, using default rotation')
  }

  // PHASE 3: Determine next arbiter from selected pool
  phase('Determine Next')

  const lastArbiter = arbiterState.last_arbiter
  let nextArbiter

  const lastIndex = rotationPool.indexOf(lastArbiter)

  if (lastIndex === -1) {
    // lastArbiter not in this pool - start at the beginning
    nextArbiter = rotationPool[0]
  } else {
    // Advance to next model in pool, wrapping around
    nextArbiter = rotationPool[(lastIndex + 1) % rotationPool.length]
  }

  log(`Rotation (${poolSource}): ${lastArbiter || 'null'} -> ${nextArbiter}`)

  // PHASE 4: Log usage for tracking
  phase('Log Usage')

  try {
    const { logModelUsage } = require('../../shared/model-usage-tracker.cjs')
    const { getRulesForTask } = require('../../shared/task-model-rules.cjs')

    const rulesApplied = taskType ? getRulesForTask(taskType) : {}

    await logModelUsage({
      model: nextArbiter,
      taskType: taskType,
      filterReason: filterReason,
      pool: rotationPool,
      poolSource: poolSource,
      rulesApplied: rulesApplied,
      workflow: 'get-next-arbiter',
      context: args?.context || '',
    })

    log('Usage logged to monitoring.model_usage')
  } catch (trackError) {
    log(`Could not log usage (${trackError.message}), continuing anyway`)
  }

  const result = {
    arbiter: nextArbiter,
    previous: lastArbiter,
    taskType: taskType,
    poolSource: poolSource,
    pool: rotationPool,
    filterReason: filterReason,
  }

  log(`Next arbiter: ${nextArbiter}`)

  return result

} catch (error) {
  log(`Error in get-next-arbiter: ${error.message}`)
  log(error.stack)
  return {
    error: error.message,
    arbiter: DEFAULT_ROTATION[0], // fallback to first default model on error
    previous: null,
    taskType: args?.taskType || null,
    poolSource: 'error_fallback',
    pool: DEFAULT_ROTATION,
  }
}

}
