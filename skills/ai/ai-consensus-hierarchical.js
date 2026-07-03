export const meta = {
  name: 'ai-consensus-hierarchical',
  description: 'Hierarchical multi-AI consensus - specialized sub-teams with sub-arbiters feed a meta-arbiter for cross-domain synthesis',
  whenToUse: 'When a task spans multiple domains (e.g. security + architecture + testing) and benefits from specialized sub-team analysis before cross-domain synthesis',
  phases: [
    { title: 'Classify', detail: 'Analyze task to identify domains and form sub-teams' },
    { title: 'Sub-Teams', detail: 'Level 1: Specialized workers execute in parallel sub-teams' },
    { title: 'Sub-Arbiters', detail: 'Level 1: Each sub-team arbiter synthesizes its team result' },
    { title: 'Meta-Arbiter', detail: 'Level 2: Meta-arbiter synthesizes across all sub-team results' },
    { title: 'Update State', detail: 'Record arbiter usage and feedback' },
  ],
}

// Rate limiting (fail-open)
let _rlm_mod = null;
try { const m = await import('./shared/rate-limit-manager.cjs'); _rlm_mod = m.default || m; } catch (_e) { /* rate limiting unavailable */ }
async function _rlFetch(provider, url, options) {
  if (_rlm_mod) { try { await _rlm_mod.checkRateLimit(provider); } catch (_e) { /* fail open */ } }
  const start = Date.now();
  try {
    const response = await fetch(url, options);
    if (_rlm_mod) { _rlm_mod.recordRequest(provider, response.ok, { url, duration_ms: Date.now() - start }).catch(() => {}); }
    return response;
  } catch (error) {
    if (_rlm_mod) { _rlm_mod.recordRequest(provider, false, { url, error: error.message, duration_ms: Date.now() - start }).catch(() => {}); }
    throw error;
  }
}

export default async function({ args, phase, log, agent, parallel }) {

// ============================================================================
// USAGE:
//
// const result = await workflow('ai-consensus-hierarchical', {
//   task: 'Review this service for production readiness',
//   context: '<code + architecture docs>',
//   schema: { type: 'object', properties: { ... } },
//   arbiter_instructions: 'Synthesize the cross-domain analysis into a unified readiness assessment',
//
//   // Sub-team configuration (optional -- auto-detected from task if omitted)
//   sub_teams: [
//     { domain: 'security',     models: ['opus', 'sonnet'] },
//     { domain: 'architecture', models: ['opus', 'haiku'] },
//     { domain: 'testing',      models: ['sonnet', 'haiku'] },
//   ],
//
//   meta_arbiter_model: 'opus',     // optional, defaults to 'opus'
//   budget: 'medium',               // optional, passed to task-router for auto-detection
//   min_sub_teams: 2,               // optional, minimum sub-teams (default: 2)
//   max_sub_teams: 5,               // optional, maximum sub-teams (default: 5)
// })
// ============================================================================

// ============================================================================
// MODEL SPECIALIZATION CONFIG (mirrors ai-task-router.js)
// ============================================================================

const MODEL_SPECIALIZATIONS = {
  // fable removed per Issue #197 (API 403 errors)
  opus: {
    id: 'opus',
    tier: 'flagship',
    specializations: ['security', 'architecture', 'logic', 'synthesis', 'complex-reasoning', 'code-review', 'reasoning', 'analysis'],
    quality: 1.0,
  },
  sonnet: {
    id: 'sonnet',
    tier: 'mid',
    specializations: ['code-review', 'refactoring', 'documentation', 'testing', 'general'],
    quality: 0.85,
  },
  haiku: {
    id: 'haiku',
    tier: 'fast',
    specializations: ['formatting', 'classification', 'extraction', 'simple-qa', 'summarization'],
    quality: 0.65,
  },
  'gpt-4o': {
    id: 'gpt-4o',
    tier: 'mid',
    specializations: ['general', 'code-review', 'reasoning', 'multimodal'],
    quality: 0.80,
  },
  gemini: {
    id: 'gemini',
    tier: 'mid',
    specializations: ['general', 'summarization', 'extraction', 'multimodal'],
    quality: 0.75,
  },
}

// Domain keywords used when auto-detecting sub-teams from task text
const DOMAIN_KEYWORDS = {
  security:       ['security', 'vulnerability', 'CVE', 'injection', 'XSS', 'auth', 'CSRF', 'SSRF', 'encrypt', 'permission', 'access control'],
  architecture:   ['architecture', 'design', 'pattern', 'microservice', 'scalability', 'system design', 'coupling', 'cohesion', 'API'],
  'code-review':  ['review', 'code review', 'bug', 'defect', 'correctness', 'lint', 'code quality'],
  testing:        ['test', 'spec', 'coverage', 'unit test', 'integration test', 'e2e', 'QA', 'regression'],
  performance:    ['performance', 'optimize', 'latency', 'throughput', 'bottleneck', 'profiling', 'memory', 'CPU'],
  documentation:  ['document', 'readme', 'jsdoc', 'docstring', 'comment', 'explain', 'onboarding'],
  refactoring:    ['refactor', 'simplify', 'clean', 'extract', 'rename', 'reorganize', 'technical debt'],
  logic:          ['logic', 'algorithm', 'concurrent', 'race condition', 'distributed', 'state machine'],
}

// ============================================================================
// LOAD EXTERNAL MODEL CONFIG (if present)
// ============================================================================

function loadModelConfig() {
  try {
    const fs = require('fs')
    const configPath = '~/.claude/repos/claude-global-skills/model-config.json'
    const raw = fs.readFileSync(configPath, 'utf-8')
    const external = JSON.parse(raw)
    const merged = { ...MODEL_SPECIALIZATIONS }
    if (external.models) {
      for (const [id, overrides] of Object.entries(external.models)) {
        merged[id] = { ...(merged[id] || {}), ...overrides, id }
      }
    }
    return merged
  } catch (_err) {
    return MODEL_SPECIALIZATIONS
  }
}

// ============================================================================
// HELPERS
// ============================================================================

function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 50
  return Math.max(0, Math.min(100, value))
}

/**
 * Auto-detect which domains a task touches by keyword matching.
 * Returns an array of { domain, score } sorted by relevance.
 */
function detectDomains(taskText, contextText) {
  const combined = `${taskText} ${contextText}`.toLowerCase()
  const scored = []

  for (const [domain, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
    let score = 0
    for (const kw of keywords) {
      if (combined.includes(kw.toLowerCase())) {
        score += 1
      }
    }
    if (score > 0) {
      scored.push({ domain, score })
    }
  }

  scored.sort((a, b) => b.score - a.score)
  return scored
}

/**
 * Select the best models for a given domain based on specialization overlap.
 * Returns up to `count` model IDs, prioritizing models whose specializations
 * include the domain. Falls back to quality-sorted if no specialization match.
 */
function selectModelsForDomain(domain, modelConfig, count = 2, excludeModels = []) {
  const allModels = Object.values(modelConfig).filter(m => !excludeModels.includes(m.id))

  const scored = allModels.map(model => {
    let score = 0
    // Direct specialization match
    if (model.specializations && model.specializations.includes(domain)) {
      score += 50
    }
    // Quality bonus
    score += (model.quality || 0.5) * 30
    // Tier bonus for complex domains
    if (model.tier === 'flagship') score += 10
    return { model: model.id, score }
  })

  scored.sort((a, b) => b.score - a.score)
  return scored.slice(0, count).map(s => s.model)
}

/**
 * Build sub-team configurations automatically from detected domains.
 */
function buildSubTeams(detectedDomains, modelConfig, minTeams, maxTeams) {
  // Clamp the number of sub-teams
  const teamCount = Math.min(maxTeams, Math.max(minTeams, detectedDomains.length))
  const domains = detectedDomains.slice(0, teamCount)

  // If we detected fewer domains than minTeams, pad with 'general'
  while (domains.length < minTeams) {
    domains.push({ domain: 'general', score: 0 })
  }

  return domains.map(d => ({
    domain: d.domain,
    models: selectModelsForDomain(d.domain, modelConfig, 2),
    relevance_score: d.score,
  }))
}

// ============================================================================
// INPUT PARSING
// ============================================================================

const task = args.task || (typeof args === 'string' ? args : null)
const context = args.context || ''
const userSubTeams = args.sub_teams || args.subTeams || null
const metaArbiterModel = args.meta_arbiter_model || args.metaArbiterModel || 'opus'
const budget = args.budget || 'medium'
const minSubTeams = args.min_sub_teams || args.minSubTeams || 2
const maxSubTeams = args.max_sub_teams || args.maxSubTeams || 5
const userSchema = args.schema || {
  type: 'object',
  properties: {
    answer: { type: 'string', description: 'Your answer to the task' },
  },
  required: ['answer'],
}
const arbiterInstructions = args.arbiter_instructions || args.arbiterInstructions ||
  'Synthesize the sub-team analyses into a unified, cross-domain answer. Highlight where sub-teams agree, where they conflict, and any gaps.'

if (!task) {
  log('ERROR: No task provided')
  log('Usage: workflow("ai-consensus-hierarchical", { task: "...", context: "..." })')
  log('')
  log('Options:')
  log('  task                  - The question or task (required)')
  log('  context               - Additional context for workers')
  log('  schema                - JSON Schema for the answer portion')
  log('  arbiter_instructions  - Custom instructions for the meta-arbiter')
  log('  sub_teams             - Array of { domain, models } for manual team config')
  log('  meta_arbiter_model    - Model for Level 2 meta-arbiter (default: opus)')
  log('  budget                - Budget tier for task-router when auto-detecting (default: medium)')
  log('  min_sub_teams         - Minimum sub-teams to form (default: 2)')
  log('  max_sub_teams         - Maximum sub-teams to form (default: 5)')
  return { error: 'No task provided' }
}

// ============================================================================
// WORKER SCHEMA
// ============================================================================

const workerSchema = {
  type: 'object',
  properties: {
    answer: userSchema,
    confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Your confidence in this answer (0-100). Be calibrated.',
    },
    reasoning: {
      type: 'string',
      description: 'Why you chose this answer and your confidence level.',
    },
    domain_insights: {
      type: 'array',
      items: { type: 'string' },
      description: 'Key domain-specific insights from your analysis.',
    },
    caveats: {
      type: 'array',
      items: { type: 'string' },
      description: 'Caveats or limitations of your analysis.',
    },
  },
  required: ['answer', 'confidence', 'reasoning'],
}

const subArbiterSchema = {
  type: 'object',
  properties: {
    synthesized_answer: userSchema,
    domain: { type: 'string', description: 'The domain this sub-team analyzed' },
    overall_confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Confidence in the sub-team synthesis (0-100)',
    },
    winning_worker: { type: 'string', description: 'Which worker in this sub-team produced the best answer' },
    why_selected: { type: 'string', description: 'Why this worker was selected or how answers were combined' },
    key_findings: {
      type: 'array',
      items: { type: 'string' },
      description: 'Key findings from this domain analysis',
    },
    agreements: {
      type: 'array',
      items: { type: 'string' },
      description: 'Points where sub-team workers agreed',
    },
    disagreements: {
      type: 'array',
      items: { type: 'string' },
      description: 'Points where sub-team workers disagreed',
    },
  },
  required: ['synthesized_answer', 'domain', 'overall_confidence', 'key_findings'],
}

const metaArbiterSchema = {
  type: 'object',
  properties: {
    final_answer: userSchema,
    overall_confidence: {
      type: 'number',
      minimum: 0,
      maximum: 100,
      description: 'Confidence in the cross-domain synthesis (0-100)',
    },
    synthesis_notes: {
      type: 'string',
      description: 'How you combined the sub-team results into a unified answer',
    },
    cross_domain_insights: {
      type: 'array',
      items: { type: 'string' },
      description: 'Insights that emerged from combining multiple domain analyses',
    },
    cross_domain_conflicts: {
      type: 'array',
      items: { type: 'string' },
      description: 'Conflicts or tensions between domain-specific findings',
    },
    domain_rankings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          domain: { type: 'string' },
          contribution_weight: { type: 'number', description: 'How much this domain contributed (0-100)' },
          assessment: { type: 'string', description: 'Brief assessment of this sub-team analysis quality' },
        },
      },
      description: 'Ranking of sub-team contributions to the final answer',
    },
    coverage_gaps: {
      type: 'array',
      items: { type: 'string' },
      description: 'Domains or aspects not covered by any sub-team',
    },
  },
  required: ['final_answer', 'overall_confidence', 'synthesis_notes', 'cross_domain_insights'],
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

log('='.repeat(60))
log('HIERARCHICAL MULTI-AI CONSENSUS')
log('='.repeat(60))
log(`Task: ${task}`)
log(`Meta-arbiter: ${metaArbiterModel}`)
log('')

// ============================================================================
// PHASE 1: CLASSIFY -- Determine sub-teams
// ============================================================================

phase('Classify')

const modelConfig = loadModelConfig()
let subTeams

if (userSubTeams && userSubTeams.length > 0) {
  // User-specified sub-teams
  subTeams = userSubTeams.map(t => ({
    domain: t.domain,
    models: t.models || selectModelsForDomain(t.domain, modelConfig, 2),
    relevance_score: null,
  }))
  log(`Using ${subTeams.length} user-specified sub-teams`)
} else {
  // Auto-detect domains from task + context
  const detectedDomains = detectDomains(task, context)

  if (detectedDomains.length === 0) {
    // No clear domain signals -- create a general sub-team split by model tier
    log('No domain signals detected, forming general sub-teams by model tier')
    subTeams = [
      { domain: 'flagship-analysis', models: ['opus', 'sonnet'], relevance_score: 0 },
      { domain: 'mid-tier-analysis', models: ['sonnet', 'gpt-4o', 'gemini'], relevance_score: 0 },
      { domain: 'fast-analysis', models: ['haiku'], relevance_score: 0 },
    ]
  } else {
    subTeams = buildSubTeams(detectedDomains, modelConfig, minSubTeams, maxSubTeams)
    log(`Auto-detected ${detectedDomains.length} domains, formed ${subTeams.length} sub-teams`)
  }
}

// Log sub-team configuration
log('')
log('Sub-team configuration:')
subTeams.forEach((team, i) => {
  log(`  Team ${i + 1} [${team.domain}]: ${team.models.join(', ')}${team.relevance_score !== null ? ` (relevance: ${team.relevance_score})` : ''}`)
})
log('')

// ============================================================================
// PHASE 2: LEVEL 1 -- Sub-team workers execute in parallel
// ============================================================================

phase('Sub-Teams')

log(`Level 1: ${subTeams.length} sub-teams executing workers in parallel...`)

// Build all worker tasks grouped by sub-team
const subTeamWorkerTasks = subTeams.map((team, teamIndex) => {
  return team.models.map(model => {
    const workerPrompt = `You are ${model.toUpperCase()}, a specialist in the "${team.domain}" domain.
You are part of a specialized sub-team focused on ${team.domain} analysis.

TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}

DOMAIN FOCUS: ${team.domain}
Analyze this task specifically through the lens of ${team.domain}. Provide domain-specific insights
that a generalist might miss. Focus on ${team.domain}-related concerns, best practices, and potential issues.

INSTRUCTIONS:
1. Provide your best domain-specific answer.
2. Rate your confidence (0-100) -- be calibrated.
3. List domain-specific insights that emerged from your specialized perspective.
4. Note any caveats or limitations.

Return structured data per schema.`

    return {
      teamIndex,
      domain: team.domain,
      model,
      task: () => {
        try {
          return agent(workerPrompt, {
            label: `L1-${team.domain}-${model}-worker`,
            model,
            schema: workerSchema,
          })
        } catch (err) {
          log(`  WARNING: Worker ${model} (${team.domain}) threw: ${err.message || err}`)
          return null
        }
      },
    }
  })
})

// Flatten and execute all sub-team workers in parallel
const allWorkerDescriptors = subTeamWorkerTasks.flat()
const allWorkerResults = await parallel(allWorkerDescriptors.map(d => d.task))

// Re-group results by sub-team
const subTeamResults = subTeams.map((team, teamIndex) => {
  const teamDescriptors = allWorkerDescriptors.filter(d => d.teamIndex === teamIndex)
  const teamResults = teamDescriptors.map((d, i) => {
    const globalIndex = allWorkerDescriptors.indexOf(d)
    const result = allWorkerResults[globalIndex]
    if (!result) return null
    return {
      model: d.model,
      domain: d.domain,
      answer: result.answer || null,
      confidence: clampConfidence(result.confidence),
      reasoning: result.reasoning || '',
      domain_insights: result.domain_insights || [],
      caveats: result.caveats || [],
    }
  }).filter(Boolean)

  return {
    domain: team.domain,
    models: team.models,
    workers: teamResults,
    workerCount: teamResults.length,
  }
})

// Log per-team worker results
subTeamResults.forEach(team => {
  log(`  [${team.domain}]: ${team.workerCount}/${team.models.length} workers completed`)
  team.workers.forEach(w => {
    log(`    ${w.model}: confidence=${w.confidence}%`)
  })
})

// Check if we have at least one team with results
const teamsWithResults = subTeamResults.filter(t => t.workerCount > 0)
if (teamsWithResults.length === 0) {
  log('ERROR: All sub-team workers failed')
  return {
    status: 'error',
    error: 'All sub-team workers failed to produce results',
    sub_teams_attempted: subTeams.length,
  }
}

log('')

// ============================================================================
// PHASE 3: LEVEL 1 -- Sub-arbiter synthesis per team
// ============================================================================

phase('Sub-Arbiters')

log(`Level 1: ${teamsWithResults.length} sub-arbiters synthesizing...`)

// Select sub-arbiter models -- use the highest-tier model NOT in the worker set
// to avoid self-judging, or fall back to the best available model
function selectSubArbiter(team) {
  const tierOrder = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'cerebras-120b']
  // Prefer a model not already used as worker in this team
  for (const candidate of tierOrder) {
    if (!team.models.includes(candidate)) {
      return candidate
    }
  }
  // All models used -- default to fable
  return 'fable'
}

const subArbiterTasks = teamsWithResults.map(team => {
  const subArbiterModel = selectSubArbiter(team)

  const subArbiterPrompt = `[SUB-ARBITER - ${team.domain.toUpperCase()} DOMAIN]
You are synthesizing ${team.workerCount} worker responses from the "${team.domain}" sub-team.

ORIGINAL TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}

DOMAIN: ${team.domain}

WORKER RESPONSES:
${team.workers.map(w => `
--- ${w.model.toUpperCase()} (Confidence: ${w.confidence}%) ---
Answer: ${JSON.stringify(w.answer, null, 2)}
Reasoning: ${w.reasoning}
Domain Insights: ${(w.domain_insights || []).length > 0 ? w.domain_insights.join('; ') : 'None'}
Caveats: ${(w.caveats || []).length > 0 ? w.caveats.join('; ') : 'None'}
`).join('\n')}

INSTRUCTIONS:
1. Synthesize the best domain-specific answer from the workers.
2. Identify key findings unique to this domain perspective.
3. Note where workers agreed and disagreed.
4. Rate your overall confidence in the sub-team synthesis.
5. Focus specifically on ${team.domain} aspects -- the meta-arbiter will handle cross-domain integration.`

  return () => {
    try {
      return agent(subArbiterPrompt, {
        label: `L1-${team.domain}-sub-arbiter`,
        model: subArbiterModel,
        schema: subArbiterSchema,
      }).then(result => ({
        ...result,
        _subArbiterModel: subArbiterModel,
        _teamDomain: team.domain,
        _teamWorkers: team.workers,
      }))
    } catch (err) {
      log(`  WARNING: Sub-arbiter for ${team.domain} threw: ${err.message || err}`)
      return null
    }
  }
})

const subArbiterResults = await parallel(subArbiterTasks)

// Process sub-arbiter results
const level1Results = subArbiterResults.map((result, i) => {
  if (!result) return null
  const team = teamsWithResults[i]
  return {
    domain: result._teamDomain || result.domain || team.domain,
    sub_arbiter_model: result._subArbiterModel,
    synthesized_answer: result.synthesized_answer,
    confidence: clampConfidence(result.overall_confidence),
    winning_worker: result.winning_worker || null,
    why_selected: result.why_selected || '',
    key_findings: result.key_findings || [],
    agreements: result.agreements || [],
    disagreements: result.disagreements || [],
    workers: (result._teamWorkers || team.workers).map(w => ({
      model: w.model,
      confidence: w.confidence,
      reasoning: w.reasoning,
    })),
  }
}).filter(Boolean)

log(`${level1Results.length}/${teamsWithResults.length} sub-arbiters completed`)
level1Results.forEach(r => {
  log(`  [${r.domain}] confidence=${r.confidence}% (sub-arbiter: ${r.sub_arbiter_model})`)
  if (r.key_findings.length > 0) {
    log(`    Key findings: ${r.key_findings.slice(0, 2).join('; ')}${r.key_findings.length > 2 ? '...' : ''}`)
  }
})

if (level1Results.length === 0) {
  log('ERROR: All sub-arbiters failed')
  return {
    status: 'error',
    error: 'All sub-arbiters failed to produce results',
    sub_teams_attempted: teamsWithResults.length,
  }
}

log('')

// ============================================================================
// PHASE 4: LEVEL 2 -- Meta-arbiter cross-domain synthesis
// ============================================================================

phase('Meta-Arbiter')

log(`Level 2: Meta-arbiter (${metaArbiterModel}) synthesizing across ${level1Results.length} domains...`)

const metaArbiterPrompt = `[META-ARBITER - CROSS-DOMAIN SYNTHESIS]
You are the meta-arbiter in a hierarchical consensus process. Multiple specialized sub-teams have
independently analyzed different domain aspects of the same task. Your job is to synthesize their
findings into a unified, cross-domain answer.

ORIGINAL TASK: ${task}

${context ? `CONTEXT:\n${context}\n` : ''}

SUB-TEAM RESULTS (Level 1 synthesis, one per domain):
${level1Results.map(r => `
=== DOMAIN: ${r.domain.toUpperCase()} (Confidence: ${r.confidence}%) ===
Sub-Arbiter: ${r.sub_arbiter_model}
${r.winning_worker ? `Best Worker: ${r.winning_worker}` : ''}

Synthesized Answer:
${JSON.stringify(r.synthesized_answer, null, 2)}

Key Findings:
${r.key_findings.map((f, i) => `  ${i + 1}. ${f}`).join('\n')}

${r.agreements.length > 0 ? `Agreements: ${r.agreements.join('; ')}` : ''}
${r.disagreements.length > 0 ? `Disagreements: ${r.disagreements.join('; ')}` : ''}

Workers: ${r.workers.map(w => `${w.model}(${w.confidence}%)`).join(', ')}
`).join('\n')}

INSTRUCTIONS:
${arbiterInstructions}

SYNTHESIS GUIDELINES:
1. Integrate findings from ALL domain sub-teams into a unified answer.
2. Identify cross-domain insights that only emerge when combining perspectives.
3. Flag any conflicts between domain-specific findings and explain your resolution.
4. Rank each domain's contribution to the final answer.
5. Note any coverage gaps -- domains or aspects not analyzed by any sub-team.
6. Weight higher-confidence sub-teams more heavily, but do not ignore lower-confidence domains
   if they raise valid concerns.
7. Your confidence should reflect the quality of the cross-domain integration, not just
   the average of sub-team confidences.`

const metaResult = await agent(metaArbiterPrompt, {
  label: 'L2-meta-arbiter',
  model: metaArbiterModel,
  schema: metaArbiterSchema,
})

const finalConfidence = clampConfidence(metaResult.overall_confidence)

log(`Meta-arbiter synthesis complete`)
log(`  Overall confidence: ${finalConfidence}%`)
log(`  Cross-domain insights: ${(metaResult.cross_domain_insights || []).length}`)
log(`  Cross-domain conflicts: ${(metaResult.cross_domain_conflicts || []).length}`)
log(`  Coverage gaps: ${(metaResult.coverage_gaps || []).length}`)

if (metaResult.domain_rankings && metaResult.domain_rankings.length > 0) {
  log('  Domain contributions:')
  metaResult.domain_rankings.forEach(dr => {
    log(`    ${dr.domain}: weight=${dr.contribution_weight}% -- ${dr.assessment || ''}`)
  })
}

log('')

// ============================================================================
// PHASE 5: UPDATE STATE & FEEDBACK
// ============================================================================

phase('Update State')

// Update arbiter state for rotation tracking
await workflow('update-arbiter-state', {
  arbiter: metaArbiterModel,
  workflow_name: 'ai-consensus-hierarchical',
})

// ============================================================================
// RECORD FEEDBACK TO LEARNING SYSTEM
// ============================================================================

const executionId = `hierarchical_${args?._timestamp || 'exec'}_${Math.random().toString(36).substr(2, 9)}`

try {
  log('Recording feedback to learning system...')

  // Record feedback for each Level 1 sub-team
  for (const l1Result of level1Results) {
    for (const worker of l1Result.workers) {
      const feedbackPayload = {
        worker_id: `${worker.model}-${l1Result.domain}-worker`,
        model: worker.model,
        consensus_score: l1Result.confidence,
        confidence: worker.confidence,
        tokens_used: 0,
        cost_usd: 0.0,
        accepted: worker.model === l1Result.winning_worker,
        execution_id: executionId,
        reasoning: worker.reasoning,
        outcome: 'success',
        workflow_type: 'ai-consensus-hierarchical',
        metadata: {
          level: 1,
          domain: l1Result.domain,
          sub_arbiter: l1Result.sub_arbiter_model,
        },
      }

      try {
        const token = process.env.LEARNING_API_TOKEN
        const authHeader = token ? { 'Authorization': `Bearer ${token}` } : {}
        const response = await _rlFetch('learning-api', 'http://localhost:8000/api/learning/record-feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...authHeader,
          },
          body: JSON.stringify(feedbackPayload),
        })

        if (response.ok) {
          log(`Feedback recorded for ${worker.model} (${l1Result.domain})`)
        } else {
          log(`Failed to record feedback for ${worker.model} (${l1Result.domain}): ${response.statusText}`)
        }
      } catch (err) {
        log(`Feedback recording failed for ${worker.model} (${l1Result.domain}): ${err.message || err}`)
      }
    }
  }
} catch (err) {
  log(`Learning system unavailable: ${err.message || err}`)
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'ai-consensus-hierarchical',
    execution_data: {
      task,
      sub_teams: level1Results.map(r => ({
        domain: r.domain,
        confidence: r.confidence,
        findings_count: r.key_findings.length,
      })),
      meta_confidence: finalConfidence,
      cross_domain_insights_count: (metaResult.cross_domain_insights || []).length,
      cross_domain_conflicts_count: (metaResult.cross_domain_conflicts || []).length,
      coverage_gaps: metaResult.coverage_gaps || [],
    },
  })
} catch (err) {
  log(`WARNING: Learning extraction failed: ${err.message || err}`)
}

// ============================================================================
// FINAL OUTPUT
// ============================================================================

// Compute summary metrics
const avgSubTeamConfidence = level1Results.reduce((s, r) => s + r.confidence, 0) / level1Results.length
const totalWorkers = level1Results.reduce((s, r) => s + r.workers.length, 0)
const totalSubArbiters = level1Results.length

log('='.repeat(60))
log('HIERARCHICAL CONSENSUS RESULT')
log('='.repeat(60))
log(`  Sub-teams: ${level1Results.length}`)
log(`  Total workers: ${totalWorkers}`)
log(`  Avg sub-team confidence: ${avgSubTeamConfidence.toFixed(1)}%`)
log(`  Meta-arbiter confidence: ${finalConfidence}%`)
log(`  Cross-domain insights: ${(metaResult.cross_domain_insights || []).length}`)
log('='.repeat(60))

return {
  status: 'success',
  confidence: finalConfidence,
  result: metaResult.final_answer,
  synthesis_notes: metaResult.synthesis_notes,
  cross_domain_insights: metaResult.cross_domain_insights || [],
  cross_domain_conflicts: metaResult.cross_domain_conflicts || [],
  coverage_gaps: metaResult.coverage_gaps || [],
  domain_rankings: metaResult.domain_rankings || [],

  hierarchy: {
    level_2: {
      meta_arbiter_model: metaArbiterModel,
      confidence: finalConfidence,
    },
    level_1: level1Results.map(r => ({
      domain: r.domain,
      sub_arbiter_model: r.sub_arbiter_model,
      confidence: r.confidence,
      winning_worker: r.winning_worker,
      why_selected: r.why_selected,
      key_findings: r.key_findings,
      agreements: r.agreements,
      disagreements: r.disagreements,
      workers: r.workers,
    })),
  },

  summary: {
    sub_team_count: level1Results.length,
    total_workers: totalWorkers,
    total_sub_arbiters: totalSubArbiters,
    meta_arbiter_calls: 1,
    total_agent_calls: totalWorkers + totalSubArbiters + 1,
    avg_sub_team_confidence: parseFloat(avgSubTeamConfidence.toFixed(1)),
    domains_analyzed: level1Results.map(r => r.domain),
  },

  execution_id: executionId,
}

}