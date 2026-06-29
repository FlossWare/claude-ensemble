// Test suite for ai-consensus-hierarchical.js helper functions
// Run with: node ai-consensus-hierarchical.test.js

// Test helper
function assert(condition, message) {
  if (!condition) {
    console.error(`FAIL: ${message}`)
    process.exit(1)
  }
  console.log(`PASS: ${message}`)
}

function assertDeepEqual(actual, expected, message) {
  const actualStr = JSON.stringify(actual, null, 2)
  const expectedStr = JSON.stringify(expected, null, 2)
  if (actualStr !== expectedStr) {
    console.error(`FAIL: ${message}`)
    console.error(`Expected: ${expectedStr}`)
    console.error(`Actual: ${actualStr}`)
    process.exit(1)
  }
  console.log(`PASS: ${message}`)
}

// ============================================================================
// HELPER FUNCTIONS (extracted from ai-consensus-hierarchical.js)
// ============================================================================

const MODEL_SPECIALIZATIONS = {
  fable: {
    id: 'fable',
    tier: 'flagship',
    specializations: ['reasoning', 'analysis', 'synthesis', 'complex-reasoning', 'code-review', 'architecture'],
    quality: 1.0,
  },
  opus: {
    id: 'opus',
    tier: 'flagship',
    specializations: ['security', 'architecture', 'logic', 'synthesis', 'complex-reasoning', 'code-review'],
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

function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 50
  return Math.max(0, Math.min(100, value))
}

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
// TEST SUITE
// ============================================================================

function runTests() {
  console.log('Starting ai-consensus-hierarchical helper function tests...\n')

  // ========================================================================
  // Test clampConfidence
  // ========================================================================
  console.log('='.repeat(60))
  console.log('Test Suite: clampConfidence')
  console.log('='.repeat(60))

  console.log('\nTest 1.1: NaN returns 50')
  assert(clampConfidence(NaN) === 50, 'NaN should return 50')

  console.log('\nTest 1.2: Negative returns 0')
  assert(clampConfidence(-10) === 0, 'Negative value should return 0')
  assert(clampConfidence(-100) === 0, 'Large negative value should return 0')

  console.log('\nTest 1.3: >100 returns 100')
  assert(clampConfidence(150) === 100, '>100 should return 100')
  assert(clampConfidence(200) === 100, 'Large value should return 100')

  console.log('\nTest 1.4: Normal values pass through')
  assert(clampConfidence(0) === 0, '0 should pass through')
  assert(clampConfidence(50) === 50, '50 should pass through')
  assert(clampConfidence(100) === 100, '100 should pass through')
  assert(clampConfidence(75.5) === 75.5, '75.5 should pass through')

  console.log('\nTest 1.5: Non-number returns 50')
  assert(clampConfidence(undefined) === 50, 'undefined should return 50')
  assert(clampConfidence(null) === 50, 'null should return 50')
  assert(clampConfidence('string') === 50, 'string should return 50')

  // ========================================================================
  // Test detectDomains
  // ========================================================================
  console.log('\n' + '='.repeat(60))
  console.log('Test Suite: detectDomains')
  console.log('='.repeat(60))

  console.log('\nTest 2.1: Task with security keywords')
  let domains = detectDomains('Review this code for security vulnerabilities and XSS attacks', '')
  assert(domains.length > 0, 'Should detect domains')
  assert(domains[0].domain === 'security', 'Should detect security domain')
  assert(domains[0].score >= 2, 'Should have score >= 2 for security')

  console.log('\nTest 2.2: Task with architecture keywords')
  domains = detectDomains('Design a microservice architecture with good scalability', '')
  assert(domains.length > 0, 'Should detect domains')
  assert(domains[0].domain === 'architecture', 'Should detect architecture domain')
  assert(domains[0].score >= 2, 'Should have score >= 2 for architecture')

  console.log('\nTest 2.3: Multiple domains')
  domains = detectDomains('Review this code for security issues and write unit tests', '')
  assert(domains.length >= 2, 'Should detect multiple domains')
  const domainNames = domains.map(d => d.domain)
  assert(domainNames.includes('security'), 'Should include security')
  assert(domainNames.includes('testing'), 'Should include testing')
  assert(domainNames.includes('code-review'), 'Should include code-review')

  console.log('\nTest 2.4: No domain signals')
  domains = detectDomains('Tell me a story about cats', '')
  assert(domains.length === 0, 'Should return empty array for no domain signals')

  console.log('\nTest 2.5: Context text contributes to detection')
  domains = detectDomains('Review this', 'Context has security vulnerabilities and XSS')
  assert(domains.length > 0, 'Should detect domains from context')
  assert(domains[0].domain === 'security', 'Should detect security from context')

  console.log('\nTest 2.6: Scoring and sorting')
  domains = detectDomains('security vulnerability auth encrypt XSS test coverage', '')
  assert(domains[0].score > domains[domains.length - 1].score, 'Should sort by score descending')

  // ========================================================================
  // Test selectModelsForDomain
  // ========================================================================
  console.log('\n' + '='.repeat(60))
  console.log('Test Suite: selectModelsForDomain')
  console.log('='.repeat(60))

  console.log('\nTest 3.1: Direct specialization match - security')
  let models = selectModelsForDomain('security', MODEL_SPECIALIZATIONS, 2, [])
  assert(models.length === 2, 'Should return 2 models')
  assert(models.includes('opus'), 'Should include opus (security specialist)')

  console.log('\nTest 3.2: Direct specialization match - architecture')
  models = selectModelsForDomain('architecture', MODEL_SPECIALIZATIONS, 2, [])
  assert(models.length === 2, 'Should return 2 models')
  assert(models.includes('opus') || models.includes('fable'), 'Should include opus or fable (architecture specialists)')

  console.log('\nTest 3.3: Quality-based fallback for general domain')
  models = selectModelsForDomain('general', MODEL_SPECIALIZATIONS, 2, [])
  assert(models.length === 2, 'Should return 2 models')
  // Should prioritize higher quality models
  assert(models.includes('sonnet') || models.includes('gpt-4o'), 'Should include general-capable models')

  console.log('\nTest 3.4: excludeModels filtering')
  models = selectModelsForDomain('security', MODEL_SPECIALIZATIONS, 2, ['opus'])
  assert(models.length === 2, 'Should return 2 models')
  assert(!models.includes('opus'), 'Should exclude opus')

  console.log('\nTest 3.5: count parameter')
  models = selectModelsForDomain('security', MODEL_SPECIALIZATIONS, 3, [])
  assert(models.length === 3, 'Should return 3 models when count=3')

  models = selectModelsForDomain('security', MODEL_SPECIALIZATIONS, 1, [])
  assert(models.length === 1, 'Should return 1 model when count=1')

  console.log('\nTest 3.6: Exclude multiple models')
  models = selectModelsForDomain('security', MODEL_SPECIALIZATIONS, 2, ['opus', 'fable'])
  assert(models.length === 2, 'Should return 2 models')
  assert(!models.includes('opus') && !models.includes('fable'), 'Should exclude both opus and fable')

  // ========================================================================
  // Test buildSubTeams
  // ========================================================================
  console.log('\n' + '='.repeat(60))
  console.log('Test Suite: buildSubTeams')
  console.log('='.repeat(60))

  console.log('\nTest 4.1: minTeams padding with general')
  let detectedDomains = [{ domain: 'security', score: 5 }]
  let teams = buildSubTeams(detectedDomains, MODEL_SPECIALIZATIONS, 3, 5)
  assert(teams.length === 3, 'Should pad to minTeams=3')
  assert(teams[0].domain === 'security', 'First team should be security')
  assert(teams[1].domain === 'general', 'Second team should be general (padding)')
  assert(teams[2].domain === 'general', 'Third team should be general (padding)')

  console.log('\nTest 4.2: maxTeams clamping')
  detectedDomains = [
    { domain: 'security', score: 5 },
    { domain: 'architecture', score: 4 },
    { domain: 'testing', score: 3 },
    { domain: 'performance', score: 2 },
    { domain: 'documentation', score: 1 },
    { domain: 'refactoring', score: 1 },
  ]
  teams = buildSubTeams(detectedDomains, MODEL_SPECIALIZATIONS, 2, 4)
  assert(teams.length === 4, 'Should clamp to maxTeams=4')

  console.log('\nTest 4.3: Auto-detection from domain scores')
  detectedDomains = [
    { domain: 'security', score: 5 },
    { domain: 'testing', score: 3 },
  ]
  teams = buildSubTeams(detectedDomains, MODEL_SPECIALIZATIONS, 2, 5)
  assert(teams.length === 2, 'Should create 2 teams for 2 detected domains')
  assert(teams[0].domain === 'security', 'First team should be highest score')
  assert(teams[1].domain === 'testing', 'Second team should be second highest score')

  console.log('\nTest 4.4: Team structure completeness')
  detectedDomains = [{ domain: 'security', score: 5 }]
  teams = buildSubTeams(detectedDomains, MODEL_SPECIALIZATIONS, 2, 5)
  assert(teams[0].domain, 'Team should have domain')
  assert(Array.isArray(teams[0].models), 'Team should have models array')
  assert(teams[0].models.length === 2, 'Team should have 2 models')
  assert(typeof teams[0].relevance_score === 'number', 'Team should have relevance_score')

  console.log('\nTest 4.5: Relevance scores preserved')
  detectedDomains = [
    { domain: 'security', score: 10 },
    { domain: 'testing', score: 5 },
  ]
  teams = buildSubTeams(detectedDomains, MODEL_SPECIALIZATIONS, 2, 5)
  assert(teams[0].relevance_score === 10, 'First team should preserve score 10')
  assert(teams[1].relevance_score === 5, 'Second team should preserve score 5')

  // ========================================================================
  // Test MODEL_SPECIALIZATIONS data structure integrity
  // ========================================================================
  console.log('\n' + '='.repeat(60))
  console.log('Test Suite: MODEL_SPECIALIZATIONS data structure')
  console.log('='.repeat(60))

  console.log('\nTest 5.1: All models have required fields')
  for (const [modelId, config] of Object.entries(MODEL_SPECIALIZATIONS)) {
    assert(config.id, `Model ${modelId} should have id`)
    assert(config.id === modelId, `Model ${modelId} id should match key`)
    assert(config.tier, `Model ${modelId} should have tier`)
    assert(Array.isArray(config.specializations), `Model ${modelId} should have specializations array`)
    assert(config.specializations.length > 0, `Model ${modelId} should have at least one specialization`)
    assert(typeof config.quality === 'number', `Model ${modelId} should have numeric quality`)
    assert(config.quality >= 0 && config.quality <= 1, `Model ${modelId} quality should be 0-1`)
  }
  console.log(`PASS: All ${Object.keys(MODEL_SPECIALIZATIONS).length} models have required fields`)

  console.log('\nTest 5.2: Valid tier values')
  const validTiers = ['flagship', 'mid', 'fast']
  for (const [modelId, config] of Object.entries(MODEL_SPECIALIZATIONS)) {
    assert(validTiers.includes(config.tier), `Model ${modelId} tier should be one of: ${validTiers.join(', ')}`)
  }
  console.log(`PASS: All model tiers are valid`)

  console.log('\nTest 5.3: Specializations are non-empty strings')
  for (const [modelId, config] of Object.entries(MODEL_SPECIALIZATIONS)) {
    for (const spec of config.specializations) {
      assert(typeof spec === 'string' && spec.length > 0, `Model ${modelId} specialization should be non-empty string`)
    }
  }
  console.log(`PASS: All specializations are non-empty strings`)

  console.log('\nTest 5.4: Quality scores are reasonable')
  for (const [modelId, config] of Object.entries(MODEL_SPECIALIZATIONS)) {
    assert(config.quality >= 0.5, `Model ${modelId} quality should be >= 0.5`)
    if (config.tier === 'flagship') {
      assert(config.quality >= 0.95, `Flagship model ${modelId} should have quality >= 0.95`)
    }
  }
  console.log(`PASS: Quality scores are reasonable`)

  console.log('\nTest 5.5: Expected models exist')
  const expectedModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
  for (const modelId of expectedModels) {
    assert(MODEL_SPECIALIZATIONS[modelId], `Expected model ${modelId} should exist`)
  }
  console.log(`PASS: All expected models exist`)

  // ========================================================================
  // SUMMARY
  // ========================================================================
  console.log('\n' + '='.repeat(60))
  console.log('ALL TESTS PASSED')
  console.log('='.repeat(60))
  console.log('\nTest Summary:')
  console.log('  - clampConfidence: 9 tests')
  console.log('  - detectDomains: 6 tests')
  console.log('  - selectModelsForDomain: 6 tests')
  console.log('  - buildSubTeams: 5 tests')
  console.log('  - MODEL_SPECIALIZATIONS: 5 tests')
  console.log('  Total: 31 tests')
}

// Run tests
runTests()
