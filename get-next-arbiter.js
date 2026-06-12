export const meta = {
  name: 'get-next-arbiter',
  description: 'Get next arbiter model in rotation (fable → opus → sonnet → haiku → gpt-4o → gemini)',
  whenToUse: 'Internal helper for cycling through arbiter models',
  phases: [
    { title: 'Read State', detail: 'Load arbiter-state.json' },
    { title: 'Determine Next', detail: 'Calculate next arbiter in rotation' },
  ],
}

// USAGE:
// const result = await workflow('get-next-arbiter')
// Returns: { arbiter: 'sonnet', previous: 'opus' }

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
    log(`📄 Loaded arbiter state: ${JSON.stringify(arbiterState)}`)
  } catch (error) {
    // File doesn't exist or is invalid - start with null
    log(`⚠️  Could not read arbiter state (${error.message}), starting fresh`)
    arbiterState = { last_arbiter: null }
  }

  // PHASE 2: Determine next arbiter
  // NOTE: The value of lastArbiter may already be outdated by the time we use
  // it, if a concurrent workflow updated the state between our read and now.
  // The rotation will self-correct on the next invocation.
  phase('Determine Next')

  const lastArbiter = arbiterState.last_arbiter
  let nextArbiter

  // Rotation logic: fable → opus → sonnet → haiku → gpt-4o → gemini
  if (lastArbiter === 'fable') {
    nextArbiter = 'opus'
  } else if (lastArbiter === 'opus') {
    nextArbiter = 'sonnet'
  } else if (lastArbiter === 'sonnet') {
    nextArbiter = 'haiku'
  } else if (lastArbiter === 'haiku') {
    nextArbiter = 'gpt-4o'
  } else if (lastArbiter === 'gpt-4o') {
    nextArbiter = 'gemini'
  } else if (lastArbiter === 'gemini') {
    nextArbiter = 'fable'
  } else {
    // null or any other value defaults to fable
    nextArbiter = 'fable'
  }

  log(`🔄 Rotation: ${lastArbiter || 'null'} → ${nextArbiter}`)

  const result = {
    arbiter: nextArbiter,
    previous: lastArbiter
  }

  log(`✅ Next arbiter: ${nextArbiter}`)

  return result

} catch (error) {
  log(`❌ Error in get-next-arbiter: ${error.message}`)
  log(error.stack)
  return {
    error: error.message,
    arbiter: 'fable', // fallback to fable on error
    previous: null
  }
}
