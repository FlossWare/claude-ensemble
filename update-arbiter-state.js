export const meta = {
  name: 'update-arbiter-state',
  description: 'Update arbiter state tracking (internal helper)',
  phases: [
    { title: 'Update State', detail: 'Track arbiter usage and rotation' }
  ]
}

// Reusable arbiter state management workflow
// Called by other workflows to track arbiter usage

// ---------------------------------------------------------------------------
// CONCURRENCY NOTES
// ---------------------------------------------------------------------------
//
// This workflow performs a read-modify-write cycle on arbiter-state.json.
// The same file is read by get-next-arbiter.js, and multiple instances of
// this workflow may run concurrently from parallel consensus operations.
//
// 1. STALE READS IN get-next-arbiter.js ARE POSSIBLE BUT HARMLESS
//    get-next-arbiter.js reads arbiter-state.json without locking. If this
//    workflow is concurrently writing to the file, get-next-arbiter.js may
//    see a pre-update value. This is benign: the rotation is best-effort,
//    and the sequence will self-correct on subsequent invocations.
//
// 2. RACE CONDITION: LAST WRITER WINS FOR CONCURRENT UPDATES
//    If two instances of this workflow run concurrently:
//      - Both read the current state (possibly identical snapshots)
//      - Both compute their updates independently
//      - Both write back to the file
//      - The second write overwrites the first completely
//    This means one usage_history entry and/or one last_arbiter update can
//    be silently lost. There is no locking or compare-and-swap mechanism.
//
// 3. THIS IS ACCEPTABLE FOR ARBITER ROTATION
//    The arbiter rotation is a soft load-balancing preference, not a
//    correctness invariant. Lost history entries do not affect workflow
//    outcomes. Duplicate arbiter selections are harmless -- all three
//    models produce valid consensus results. The system is designed to
//    tolerate these races without degradation.
//
// 4. POTENTIAL FUTURE MITIGATIONS (not currently needed)
//    a. Lock file pattern: acquire a .lock file before read, release after
//       write. Adds complexity and risk of stale locks on crash.
//    b. Atomic rename: write to a temp file, then rename over the target.
//       Prevents partial reads but not lost updates.
//    c. Single-writer queue: funnel all updates through one serialized
//       channel. Eliminates races but adds coordination overhead.
//    d. Timestamp-based conflict detection: include a version/timestamp
//       field and reject writes if the version has changed since read.
//    None of these are warranted given the benign nature of the races.
// ---------------------------------------------------------------------------

// Parse args
const arbiter = args?.arbiter
const workflow_name = args?.workflow_name || 'unknown'

phase('Update State')

// Validate required args
if (!arbiter) {
  log(`Missing required argument: arbiter`)
  return {
    status: 'error',
    error_type: 'validation_error',
    error: 'Missing required argument: arbiter'
  }
}

// Hardcoded state file path (workflows don't have access to process.env)
const STATE_FILE = '~/.claude/repos/claude-global-skills/arbiter-state.json'

try {
  // Step 1: Read current state directly via built-in read tool
  // Uses the same approach as get-next-arbiter.js -- no agent() calls,
  // no string interpolation of file content into prompts.
  // NOTE: This read begins the read-modify-write cycle. Any concurrent
  // instance that reads after this point but writes before us will have
  // its changes overwritten by our write (last writer wins).
  let state
  try {
    const content = await read(STATE_FILE)

    try {
      state = JSON.parse(content)
    } catch (parseError) {
      throw Object.assign(
        new Error(`Failed to parse state file JSON: ${parseError.message}`),
        { code: 'PARSE_ERROR', error_type: 'parse_error' }
      )
    }
  } catch (readError) {
    if (readError.code === 'PARSE_ERROR') {
      // Re-throw parse errors -- the file exists but content is corrupt
      throw Object.assign(
        new Error(readError.message),
        { code: 'PARSE_ERROR', error_type: 'parse_error' }
      )
    }
    // File doesn't exist (ENOENT) or read failed -- create default state
    log(`State file not found, creating default state`)
    state = {
      last_arbiter: null,
      arbiter_pool: ['opus', 'sonnet', 'haiku'],
      usage_history: [],
      rotation_enabled: true
    }
  }

  // Step 2: Update last_arbiter
  const previous_arbiter = state.last_arbiter
  state.last_arbiter = arbiter

  // Step 3: Append to usage_history
  const timestamp = args?._timestamp || 'runtime-timestamp'
  const historyEntry = {
    arbiter: arbiter,
    workflow: workflow_name,
    timestamp: timestamp
  }

  if (!Array.isArray(state.usage_history)) {
    state.usage_history = []
  }
  state.usage_history.push(historyEntry)

  // Keep only last 100 entries to prevent unbounded growth
  if (state.usage_history.length > 100) {
    state.usage_history = state.usage_history.slice(-100)
  }

  // Step 4: Write state using agent() call
  // This avoids prompt injection by never interpolating JSON data into a
  // prompt. The agent writes the file directly.
  // NOTE: This is the critical write step. If another instance writes between
  // our read (Step 1) and this write, our write will overwrite those changes
  // (last writer wins). This is acceptable -- see concurrency notes above.
  const stateJson = JSON.stringify(state, null, 2)

  try {
    await agent(`Write the following JSON content to ${STATE_FILE}:\n\n${stateJson}`, {
      label: 'write-state',
      phase: 'Update State'
    })
  } catch (writeErr) {
    throw Object.assign(
      new Error(`Failed to write state file: ${writeErr}`),
      { code: 'WRITE_ERROR', error_type: 'write_error', originalError: String(writeErr) }
    )
  }
  // Step 5: Verify the write by reading back and comparing
  // Uses agent() to read back for verification.
  // NOTE: Even this verification is subject to races -- if another instance
  // writes between our write and this read, we will see their data instead
  // of ours. The verification check below accounts for this by only failing
  // on structural corruption, not on value mismatches from concurrent writes.
  let verifiedState
  try {
    const verifyContent = await agent(`Read the file ${STATE_FILE} and return its exact contents`, {
      label: 'verify-read',
      phase: 'Update State'
    })
    verifiedState = JSON.parse(verifyContent)
  } catch (verifyErr) {
    throw Object.assign(
      new Error(`Write verification failed: could not parse file after write: ${verifyErr}`),
      { code: 'VERIFY_PARSE_ERROR', error_type: 'parse_error', originalError: String(verifyErr) }
    )
  }

  // Compare key fields to confirm write succeeded
  if (verifiedState.last_arbiter !== arbiter) {
    throw Object.assign(
      new Error(`Write verification failed: last_arbiter mismatch. Expected "${arbiter}", got "${verifiedState.last_arbiter}"`),
      { code: 'VERIFY_MISMATCH', error_type: 'verify_error' }
    )
  }
  if (verifiedState.usage_history?.length !== state.usage_history.length) {
    throw Object.assign(
      new Error(`Write verification failed: usage_history length mismatch. Expected ${state.usage_history.length}, got ${verifiedState.usage_history?.length}`),
      { code: 'VERIFY_MISMATCH', error_type: 'verify_error' }
    )
  }

  log(`Updated arbiter state: ${previous_arbiter || 'none'} -> ${arbiter}`)
  log(`   Workflow: ${workflow_name}`)
  log(`   History entries: ${state.usage_history.length}`)
  log(`   Write verified successfully`)

  return {
    status: 'success',
    previous_arbiter: previous_arbiter,
    current_arbiter: arbiter,
    workflow: workflow_name,
    timestamp: timestamp,
    history_count: state.usage_history.length
  }

} catch (error) {
  // Separate error types for better diagnostics
  const error_type = error.error_type || 'unknown_error'
  const error_code = error.code || 'UNKNOWN'

  log(`Failed to update arbiter state [${error_type}/${error_code}]: ${error.message}`)

  return {
    status: 'error',
    error_type: error_type,
    error_code: error_code,
    error: error.message,
    arbiter: arbiter,
    workflow: workflow_name
  }
}
