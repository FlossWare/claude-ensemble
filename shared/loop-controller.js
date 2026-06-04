// Loop Controller for Continuous/Iterative Workflows
// Used by: code-improve loop, code-solve loop, pr-review loop

export async function loopMode(iterationFn, options = {}) {
  const {
    maxIterations = Infinity,
    convergenceCheck = null,
    interval = 0, // 0 = no delay between iterations
    onIterationStart = null,
    onIterationEnd = null,
    onConvergence = null,
    stopCondition = null,
  } = options

  let iteration = 0
  let lastResult = null
  const results = []

  log(`🔄 Starting loop mode (max ${maxIterations === Infinity ? '∞' : maxIterations} iterations)`)

  while (iteration < maxIterations) {
    iteration++

    // Iteration start callback
    if (onIterationStart) {
      await onIterationStart(iteration, lastResult)
    }

    log(`\n═══ Iteration ${iteration}/${maxIterations === Infinity ? '∞' : maxIterations} ═══`)

    // Run the iteration
    const result = await iterationFn(iteration, lastResult)
    results.push(result)

    // Iteration end callback
    if (onIterationEnd) {
      await onIterationEnd(iteration, result, lastResult)
    }

    // Check for convergence
    if (convergenceCheck && convergenceCheck(result, lastResult)) {
      log(`✅ Converged at iteration ${iteration} - stopping loop`)
      if (onConvergence) {
        await onConvergence(result, iteration)
      }
      return {
        status: 'converged',
        iterations: iteration,
        results,
        finalResult: result
      }
    }

    // Check custom stop condition
    if (stopCondition && stopCondition(result, iteration)) {
      log(`🛑 Stop condition met at iteration ${iteration}`)
      return {
        status: 'stopped',
        iterations: iteration,
        results,
        finalResult: result
      }
    }

    lastResult = result

    // Delay between iterations (if specified)
    if (iteration < maxIterations && interval > 0) {
      log(`⏸️  Waiting ${interval}ms before next iteration...`)
      await sleep(interval)
    }
  }

  log(`🏁 Completed ${iteration} iterations (max reached)`)
  return {
    status: 'max_iterations',
    iterations: iteration,
    results,
    finalResult: lastResult
  }
}

export async function continuousMonitor(checkFn, actionFn, options = {}) {
  const {
    interval = 300000, // 5 minutes default
    maxRuns = Infinity,
    stopOnNoWork = false,
  } = options

  let runs = 0

  log(`👀 Starting continuous monitoring (checking every ${interval}ms)`)

  while (runs < maxRuns) {
    runs++

    log(`\n🔍 Check ${runs}/${maxRuns === Infinity ? '∞' : maxRuns}`)

    // Check for work
    const workItems = await checkFn(runs)

    if (!workItems || workItems.length === 0) {
      log('ℹ️  No work items found')

      if (stopOnNoWork) {
        log('✅ No work - stopping monitor')
        return {
          status: 'no_work',
          runs,
          totalProcessed: 0
        }
      }

      log(`⏸️  Waiting ${interval}ms...`)
      await sleep(interval)
      continue
    }

    log(`📋 Found ${workItems.length} work items`)

    // Process work
    const results = await actionFn(workItems, runs)

    log(`✅ Processed ${results.length} items`)

    // Delay before next check
    if (runs < maxRuns) {
      log(`⏸️  Waiting ${interval}ms before next check...`)
      await sleep(interval)
    }
  }

  log(`🏁 Continuous monitoring stopped (${runs} runs)`)
  return {
    status: 'max_runs',
    runs
  }
}

export function iterativeImprovement(qualityScoreFn, options = {}) {
  const {
    targetScore = 95,
    maxIterations = 10,
    tolerance = 2,
  } = options

  return {
    convergenceCheck: (current, previous) => {
      if (!previous) return false

      const currentQuality = qualityScoreFn(current)
      const previousQuality = qualityScoreFn(previous)

      // Converged if:
      // 1. Target score reached
      if (currentQuality.score >= targetScore) {
        return true
      }

      // 2. No more improvements (within tolerance)
      const improvement = currentQuality.score - previousQuality.score
      if (Math.abs(improvement) <= tolerance && currentQuality.critical_count === 0) {
        return true
      }

      return false
    },

    stopCondition: (result, iteration) => {
      const quality = qualityScoreFn(result)

      // Stop if perfect score
      if (quality.score === 100) {
        return true
      }

      // Stop if max iterations
      if (iteration >= maxIterations) {
        return true
      }

      return false
    },

    onIterationEnd: (iteration, result, previous) => {
      const quality = qualityScoreFn(result)
      const previousQuality = previous ? qualityScoreFn(previous) : null

      log(`\n📊 Iteration ${iteration} Quality:`)
      log(`   Score: ${quality.score}/100 ${previousQuality ? `(${quality.score > previousQuality.score ? '+' : ''}${quality.score - previousQuality.score})` : ''}`)
      log(`   Critical: ${quality.critical_count}`)
      log(`   High: ${quality.high_count}`)
      log(`   Medium: ${quality.medium_count}`)
      log(`   Low: ${quality.low_count}`)

      if (quality.score >= targetScore) {
        log(`   ✅ Target score (${targetScore}) reached!`)
      }
    }
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
