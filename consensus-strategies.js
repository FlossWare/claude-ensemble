// consensus-strategies.js - Additional consensus strategies for workflows
// Port of Universal AI's 5 consensus strategies to Claude Code workflows

/**
 * Consensus Strategies
 *
 * 1. rotating - Democratic: each AI judges others (most thorough)
 * 2. single - One arbiter judges all workers (fast)
 * 3. majority - Simple majority vote (no arbiter overhead)
 * 4. pairwise - Workers in pairs (balanced)
 * 5. weighted - Confidence-based voting (quality-aware)
 */

/**
 * Strategy 1: Rotating Arbiter (Democratic)
 * Each worker takes turns being the arbiter
 * Most thorough, catches most issues
 */
export async function rotatingArbiter(workers, prompt, schema) {
  log('Using rotating arbiter (democratic consensus)')

  // All workers produce solutions
  const solutions = await parallel(workers.map(w => () =>
    agent(prompt, {
      schema,
      model: w.model,
      label: `${w.name}-propose`
    })
  ))

  // Each worker judges ALL other workers
  const judgments = await parallel(workers.map((arbiter, ai) => () =>
    agent(
      `You are the arbiter. Review solutions from other workers and select the best.

Workers' Solutions:
${solutions.filter((_, si) => si !== ai).map((s, i) => `
Worker ${i + 1}: ${JSON.stringify(s)}
`).join('\n')}

Select the BEST solution. Explain why.`,
      {
        schema: {
          type: 'object',
          properties: {
            best_index: { type: 'number' },
            reasoning: { type: 'string' },
            arbiter: { type: 'string' }
          },
          required: ['best_index', 'reasoning', 'arbiter']
        },
        model: arbiter.model,
        label: `${arbiter.name}-arbiter`
      }
    )
  ))

  // Tally votes
  const votes = {}
  judgments.forEach(j => {
    votes[j.best_index] = (votes[j.best_index] || 0) + 1
  })

  // Winner is solution with most votes
  const winner = Object.entries(votes)
    .sort((a, b) => b[1] - a[1])[0]

  const winnerIndex = parseInt(winner[0])
  const voteCount = winner[1]

  log(`Consensus reached: Solution ${winnerIndex + 1} (${voteCount}/${workers.length} votes)`)

  return {
    solution: solutions[winnerIndex],
    strategy: 'rotating',
    votes: voteCount,
    total_workers: workers.length,
    all_solutions: solutions,
    all_judgments: judgments
  }
}

/**
 * Strategy 2: Single Arbiter (Fast)
 * One designated arbiter judges all workers
 * Faster, less thorough
 */
export async function singleArbiter(workers, prompt, schema, arbiterModel = 'opus') {
  log('Using single arbiter (fast consensus)')

  // Workers produce solutions
  const solutions = await parallel(workers.map(w => () =>
    agent(prompt, {
      schema,
      model: w.model,
      label: `${w.name}-propose`
    })
  ))

  // Single arbiter judges all
  const judgment = await agent(
    `You are the arbiter. Review ALL solutions and select the best.

Workers' Solutions:
${solutions.map((s, i) => `
Worker ${i + 1} (${workers[i].name}): ${JSON.stringify(s)}
`).join('\n')}

Select the BEST solution. Explain your reasoning.`,
    {
      schema: {
        type: 'object',
        properties: {
          best_index: { type: 'number' },
          reasoning: { type: 'string' },
          quality_scores: {
            type: 'array',
            items: { type: 'number' }
          }
        },
        required: ['best_index', 'reasoning']
      },
      model: arbiterModel,
      label: 'arbiter'
    }
  )

  log(`Arbiter selected: Solution ${judgment.best_index + 1}`)

  return {
    solution: solutions[judgment.best_index],
    strategy: 'single',
    arbiter_model: arbiterModel,
    reasoning: judgment.reasoning,
    all_solutions: solutions
  }
}

/**
 * Strategy 3: Majority Vote (No Arbiter)
 * Simple majority vote, no arbiter overhead
 * Fastest, works when solutions are similar
 */
export async function majorityVote(workers, prompt, schema) {
  log('Using majority vote (no arbiter)')

  // All workers produce solutions
  const solutions = await parallel(workers.map(w => () =>
    agent(prompt, {
      schema,
      model: w.model,
      label: `${w.name}-vote`
    })
  ))

  // Group identical solutions
  const groups = {}
  solutions.forEach((sol, i) => {
    const key = JSON.stringify(sol)
    if (!groups[key]) {
      groups[key] = { solution: sol, count: 0, workers: [] }
    }
    groups[key].count++
    groups[key].workers.push(workers[i].name)
  })

  // Winner is most common solution
  const winner = Object.values(groups)
    .sort((a, b) => b.count - a.count)[0]

  const majority = winner.count / workers.length

  log(`Majority reached: ${winner.count}/${workers.length} workers (${(majority * 100).toFixed(0)}%)`)

  return {
    solution: winner.solution,
    strategy: 'majority',
    votes: winner.count,
    total_workers: workers.length,
    agreement_rate: majority,
    agreeing_workers: winner.workers,
    all_solutions: solutions
  }
}

/**
 * Strategy 4: Pairwise Comparison (Balanced)
 * Workers compete in pairs, winners advance
 * Tournament-style, balanced thoroughness/speed
 */
export async function pairwiseComparison(workers, prompt, schema) {
  log('Using pairwise comparison (tournament)')

  // All workers produce solutions
  const solutions = await parallel(workers.map(w => () =>
    agent(prompt, {
      schema,
      model: w.model,
      label: `${w.name}-compete`
    })
  ))

  // Pair up solutions for comparison
  let remaining = solutions.map((s, i) => ({ solution: s, worker: workers[i] }))
  let round = 1

  while (remaining.length > 1) {
    log(`  Round ${round}: ${remaining.length} solutions`)

    const pairs = []
    for (let i = 0; i < remaining.length; i += 2) {
      if (i + 1 < remaining.length) {
        pairs.push([remaining[i], remaining[i + 1]])
      } else {
        // Odd one out advances automatically
        pairs.push([remaining[i]])
      }
    }

    // Judge each pair
    const winners = await parallel(pairs.map(pair => () => {
      if (pair.length === 1) {
        return pair[0] // Bye - advances automatically
      }

      return agent(
        `Compare these two solutions and select the better one.

Solution A (${pair[0].worker.name}):
${JSON.stringify(pair[0].solution)}

Solution B (${pair[1].worker.name}):
${JSON.stringify(pair[1].solution)}

Which is better? A or B?`,
        {
          schema: {
            type: 'object',
            properties: {
              winner: { type: 'string', enum: ['A', 'B'] },
              reasoning: { type: 'string' }
            },
            required: ['winner', 'reasoning']
          },
          model: 'opus',
          label: `round${round}-judge`
        }
      ).then(result => {
        return result.winner === 'A' ? pair[0] : pair[1]
      })
    }))

    remaining = winners
    round++
  }

  const winner = remaining[0]

  log(`Tournament winner: ${winner.worker.name} (${round - 1} rounds)`)

  return {
    solution: winner.solution,
    strategy: 'pairwise',
    winner_worker: winner.worker.name,
    rounds: round - 1,
    all_solutions: solutions
  }
}

/**
 * Strategy 5: Weighted Voting (Quality-Aware)
 * Workers vote with confidence weights
 * Prioritizes high-confidence solutions
 */
export async function weightedVoting(workers, prompt, schema) {
  log('Using weighted voting (confidence-based)')

  // Workers produce solutions with confidence scores
  const WEIGHTED_SCHEMA = {
    type: 'object',
    properties: {
      ...schema.properties,
      confidence: {
        type: 'number',
        minimum: 0,
        maximum: 1,
        description: 'Your confidence in this solution (0.0-1.0)'
      },
      reasoning: {
        type: 'string',
        description: 'Why you chose this solution'
      }
    },
    required: [...(schema.required || []), 'confidence']
  }

  const solutions = await parallel(workers.map(w => () =>
    agent(
      `${prompt}\n\nIMPORTANT: Include your confidence level (0.0-1.0) in the solution.`,
      {
        schema: WEIGHTED_SCHEMA,
        model: w.model,
        label: `${w.name}-weighted`
      }
    )
  ))

  // Group by solution (excluding confidence/reasoning)
  const groups = {}
  solutions.forEach((sol, i) => {
    const { confidence, reasoning, ...actualSolution } = sol
    const key = JSON.stringify(actualSolution)

    if (!groups[key]) {
      groups[key] = {
        solution: actualSolution,
        total_weight: 0,
        workers: []
      }
    }

    groups[key].total_weight += confidence
    groups[key].workers.push({
      name: workers[i].name,
      confidence
    })
  })

  // Winner is solution with highest total weight
  const winner = Object.values(groups)
    .sort((a, b) => b.total_weight - a.total_weight)[0]

  const totalPossibleWeight = workers.length
  const weightedAgreement = winner.total_weight / totalPossibleWeight

  log(`Weighted consensus: ${winner.total_weight.toFixed(2)}/${totalPossibleWeight} total confidence (${(weightedAgreement * 100).toFixed(0)}%)`)

  return {
    solution: winner.solution,
    strategy: 'weighted',
    total_weight: winner.total_weight,
    max_possible_weight: totalPossibleWeight,
    agreement_rate: weightedAgreement,
    contributing_workers: winner.workers,
    all_solutions: solutions
  }
}

/**
 * Auto-select best strategy based on context
 */
export async function autoSelectStrategy(workers, prompt, schema, context = {}) {
  const {
    critical = false,    // Is this critical? (use thorough)
    fast = false,        // Need fast result? (use simple)
    diverse = false      // Expect diverse solutions? (use pairwise)
  } = context

  if (critical) {
    log('Auto-selected: rotating arbiter (critical task)')
    return rotatingArbiter(workers, prompt, schema)
  }

  if (fast) {
    log('Auto-selected: majority vote (fast result needed)')
    return majorityVote(workers, prompt, schema)
  }

  if (diverse) {
    log('Auto-selected: pairwise comparison (diverse solutions expected)')
    return pairwiseComparison(workers, prompt, schema)
  }

  // Default: rotating arbiter (maximum quality)
  log('Auto-selected: rotating arbiter (maximum quality)')
  return rotatingArbiter(workers, prompt, schema)
}

// Export all strategies
export default {
  rotating: rotatingArbiter,
  single: singleArbiter,
  majority: majorityVote,
  pairwise: pairwiseComparison,
  weighted: weightedVoting,
  auto: autoSelectStrategy
}
