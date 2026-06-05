/**
 * Work Coordinator Pattern - Reusable coordinator for distributing work to parallel workers
 *
 * IMPORTANT: This module depends on workflow runtime globals (log, agent, parallel).
 * It is designed to be imported ONLY within workflow scripts (.js files using scriptPath).
 * Do NOT import in non-workflow contexts (unit tests, CLI tools, standalone scripts).
 *
 * Solves the TOCTOU race condition problem by centralizing work item fetching and claiming.
 * One coordinator fetches and claims all work, then distributes to parallel workers.
 *
 * @example
 * // Simple usage
 * const results = await coordinateWork({
 *   fetchWork: async () => {
 *     const issues = await agent(`gh issue list --state open`)
 *     return issues.map(i => ({ id: i.number, data: i }))
 *   },
 *   claimWork: async (item) => {
 *     await agent(`gh issue edit ${item.id} --add-label "in-progress"`)
 *     return true
 *   },
 *   processWork: async (item) => {
 *     return await solveSingleIssue(item.id)
 *   }
 * })
 *
 * @example
 * // With filtering and validation
 * const results = await coordinateWork({
 *   fetchWork: async () => fetchAllIssues(),
 *   filterWork: (item) => !item.labels.includes('wontfix'),
 *   claimWork: async (item) => atomicClaim(item.id),
 *   processWork: async (item) => processIssue(item),
 *   maxWorkers: 10,
 *   onProgress: (completed, total) => log(`${completed}/${total} done`)
 * })
 */

/**
 * Coordinate parallel work distribution with centralized fetching and claiming
 *
 * @param {Object} config Configuration object
 * @param {Function} config.fetchWork Async function that returns array of work items
 * @param {Function} [config.filterWork] Optional sync function to filter work items (item => boolean)
 * @param {Function} config.claimWork Async function to claim a work item, returns boolean (true=claimed, false=already claimed)
 * @param {Function} config.processWork Async function to process a claimed work item
 * @param {number} [config.maxWorkers] Max parallel workers (default: Infinity, let pipeline handle it)
 * @param {Function} [config.onProgress] Optional progress callback (completed, total) => void
 * @param {Function} [config.onSkip] Optional skip callback (item, reason) => void
 * @param {boolean} [config.failFast] Stop on first error (default: false, continue processing)
 * @returns {Promise<Array>} Results array with status for each item
 */
export async function coordinateWork({
  fetchWork,
  filterWork = null,
  claimWork,
  processWork,
  maxWorkers = Infinity,
  onProgress = null,
  onSkip = null,
  failFast = false
}) {
  // Validation
  if (typeof fetchWork !== 'function') {
    throw new Error('fetchWork must be a function')
  }
  if (typeof claimWork !== 'function') {
    throw new Error('claimWork must be a function')
  }
  if (typeof processWork !== 'function') {
    throw new Error('processWork must be a function')
  }

  // Phase 1: Fetch all work items (centralized, happens once)
  log('📥 Coordinator: Fetching work items...')
  const allWork = await fetchWork()

  if (!Array.isArray(allWork)) {
    throw new Error('fetchWork must return an array')
  }

  log(`✅ Coordinator: Found ${allWork.length} work items`)

  // Phase 2: Filter work items (optional)
  const filteredWork = filterWork ? allWork.filter(filterWork) : allWork

  if (filteredWork.length < allWork.length) {
    const filtered = allWork.length - filteredWork.length
    log(`🔍 Coordinator: Filtered out ${filtered} items (${filteredWork.length} remaining)`)
  }

  if (filteredWork.length === 0) {
    log('✅ Coordinator: No work items to process')
    return {
      status: 'success',
      total: 0,
      successful: 0,
      skipped: 0,
      failed: 0,
      results: []
    }
  }

  log(`🚀 Coordinator: Starting ${filteredWork.length} workers...`)

  // Phase 3: Process items in parallel with atomic claiming
  // Note: parallel() handles concurrency limits internally, no need to slice
  let completed = 0
  const results = await parallel(
    filteredWork.map((item, idx) => async () => {
      try {
        // Atomic claim
        const claimed = await claimWork(item)

        if (!claimed) {
          // Already claimed by another process
          const skip = { status: 'skipped', item, reason: 'Already claimed' }
          if (onSkip) onSkip(item, 'Already claimed')
          completed++
          if (onProgress) onProgress(completed, filteredWork.length)
          return skip
        }

        // Successfully claimed - process it
        const result = await processWork(item)
        completed++
        if (onProgress) onProgress(completed, filteredWork.length)

        return { status: 'success', item, result }
      } catch (error) {
        completed++
        if (onProgress) onProgress(completed, filteredWork.length)

        const errorResult = { status: 'error', item, error: error.message }

        if (failFast) {
          throw error
        }

        return errorResult
      }
    })
  )

  // Phase 4: Summarize results (single pass for efficiency)
  const counts = results.reduce((acc, r) => {
    if (r?.status === 'success') acc.successful++
    else if (r?.status === 'skipped') acc.skipped++
    else if (r?.status === 'error') acc.failed++
    return acc
  }, { successful: 0, skipped: 0, failed: 0 })

  const { successful, skipped, failed } = counts

  log(`✅ Coordinator: Complete - ${successful} successful, ${skipped} skipped, ${failed} failed`)

  return {
    status: 'success',
    total: filteredWork.length,
    successful,
    skipped,
    failed,
    results
  }
}

/**
 * Batch work coordinator - processes work in batches to limit concurrency
 * Useful when you have many items but want to limit parallel execution
 *
 * @example
 * const results = await coordinateBatchWork({
 *   fetchWork: async () => fetchAllIssues(),
 *   claimWork: async (item) => claimIssue(item.id),
 *   processWork: async (item) => processIssue(item),
 *   batchSize: 10, // Process 10 at a time
 *   delayBetweenBatches: 5000 // 5 second delay between batches
 * })
 */
export async function coordinateBatchWork({
  fetchWork,
  filterWork = null,
  claimWork,
  processWork,
  batchSize = 10,
  delayBetweenBatches = 0,
  onProgress = null,
  onSkip = null,
  failFast = false
}) {
  // Fetch and filter
  const allWork = await fetchWork()
  const filteredWork = filterWork ? allWork.filter(filterWork) : allWork

  log(`🚀 Coordinator: Processing ${filteredWork.length} items in batches of ${batchSize}`)

  const allResults = []
  let completed = 0

  // Process in batches
  for (let i = 0; i < filteredWork.length; i += batchSize) {
    const batch = filteredWork.slice(i, i + batchSize)
    const batchNum = Math.floor(i / batchSize) + 1
    const totalBatches = Math.ceil(filteredWork.length / batchSize)

    log(`📦 Coordinator: Processing batch ${batchNum}/${totalBatches} (${batch.length} items)`)

    const batchResults = await coordinateWork({
      fetchWork: async () => batch,
      claimWork,
      processWork,
      onProgress: (batchCompleted, batchTotal) => {
        completed = i + batchCompleted
        if (onProgress) onProgress(completed, filteredWork.length)
      },
      onSkip,
      failFast
    })

    allResults.push(...batchResults.results)

    // Delay between batches if specified
    if (delayBetweenBatches > 0 && i + batchSize < filteredWork.length) {
      log(`⏳ Coordinator: Waiting ${delayBetweenBatches}ms before next batch...`)
      await new Promise(resolve => setTimeout(resolve, delayBetweenBatches))
    }
  }

  // Single pass for efficiency
  const counts = allResults.reduce((acc, r) => {
    if (r?.status === 'success') acc.successful++
    else if (r?.status === 'skipped') acc.skipped++
    else if (r?.status === 'error') acc.failed++
    return acc
  }, { successful: 0, skipped: 0, failed: 0 })

  const { successful, skipped, failed } = counts

  return {
    status: 'success',
    total: filteredWork.length,
    successful,
    skipped,
    failed,
    results: allResults
  }
}

/**
 * Simple helper to create a claim function for GitLab/GitHub issues
 *
 * @example
 * const claimIssue = createIssueClaimer({
 *   platform: 'gitlab',
 *   label: 'in-progress'
 * })
 *
 * const claimed = await claimIssue({ id: 123 })
 */
export function createIssueClaimer({ platform, label = 'in-progress' }) {
  return async (item) => {
    const issueId = item.id || item.number

    // Use structured output to avoid string parsing bugs
    const result = await agent(`Atomically claim issue #${issueId} with label "${label}".

Execute:
${platform === 'gitlab'
  ? `if glab issue view ${issueId} --json labels 2>/dev/null | jq -e '.labels[]? | select(.name == "${label}")' >/dev/null 2>&1; then echo '{"claimed":false,"alreadyClaimed":true}'; else glab issue update ${issueId} --add-label "${label}" 2>/dev/null && echo '{"claimed":true,"alreadyClaimed":false}' || echo '{"claimed":false,"alreadyClaimed":false}'; fi`
  : `if gh issue view ${issueId} --json labels --jq '.labels[]? | select(.name == "${label}")' 2>/dev/null | grep -q .; then echo '{"claimed":false,"alreadyClaimed":true}'; else gh issue edit ${issueId} --add-label "${label}" 2>/dev/null && echo '{"claimed":true,"alreadyClaimed":false}' || echo '{"claimed":false,"alreadyClaimed":false}'; fi`
}

Return the JSON output.`, {
      label: `Claim #${issueId}`,
      schema: {
        type: 'object',
        properties: {
          claimed: { type: 'boolean' },
          alreadyClaimed: { type: 'boolean' }
        },
        required: ['claimed', 'alreadyClaimed']
      }
    })

    return result?.claimed === true
  }
}
