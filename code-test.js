// AUTONOMOUS WORKFLOW - No user prompts or confirmations
// This workflow is designed for automated/background execution
// It must complete without user interaction
// Auto-tests application, validates UIs, checks against open issues, creates bug reports

export const meta = {
  name: 'code-test',
  description: 'Comprehensive application testing: UI validation, integration tests, open issue verification (AUTONOMOUS)',
  phases: [
    { title: 'Detect App Type', detail: 'Identify application type and test strategy' },
    { title: 'Fetch Open Issues', detail: 'Get open issues to validate against' },
    { title: 'Generate Test Plans', detail: 'Multiple AIs propose test strategies' },
    { title: 'Select Best Plan', detail: 'Choose optimal test plan via consensus' },
    { title: 'Execute Tests', detail: 'Run automated tests, UI checks, integration tests' },
    { title: 'Validate Issues', detail: 'Check if open issues are reproducible' },
    { title: 'Multi-Model Review', detail: 'Verify test results with multiple AIs' },
    { title: 'Report Results', detail: 'Create/update issues with test findings' },
  ],
}

// Configuration
const AUTONOMOUS = args?.autonomous !== false
const MAX_ISSUES_TO_TEST = args?.maxIssues || 10
const CONFIDENCE_THRESHOLD = 70
const MIN_MODELS = args?.minModels || 3  // Minimum models needed for consensus
const MAX_MODELS = args?.maxModels || Infinity  // Maximum models to use

log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

// ============================================================================
// DYNAMIC MODEL DISCOVERY
// ============================================================================

log('🔍 Discovering available AI models...')

// Known models to try (in preference order)
const KNOWN_MODELS = [
  // Claude models (built-in)
  'opus', 'sonnet', 'haiku',
  // Gemini models
  'gemini', 'gemini-pro', 'gemini-flash',
  // Grok models (xAI)
  'grok', 'grok-2', 'grok-beta',
  // Ollama models (if running locally)
  'ollama/llama3', 'ollama/llama3.1', 'ollama/mistral', 'ollama/mixtral', 'ollama/codestral',
  // OpenAI (if MCP available)
  'gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo',
]

const availableModels = []
const providersSeen = new Set()

// Quick ping test for each model
for (const modelId of KNOWN_MODELS) {
  if (availableModels.length >= MAX_MODELS) break

  try {
    // Extract provider
    const provider = modelId.includes('/') ? modelId.split('/')[0] : modelId.split('-')[0]

    // Skip duplicate providers (one model per provider for diversity)
    if (providersSeen.has(provider)) continue

    // Lightweight ping - just test if model responds
    const pingResult = await agent('Respond with only "ok"', {
      model: modelId,
      label: `Ping ${modelId}`,
      schema: {
        type: 'object',
        properties: { status: { type: 'string' } }
      }
    })

    if (pingResult) {
      availableModels.push(modelId)
      providersSeen.add(provider)
      log(`  ✅ ${modelId} available`)
    }
  } catch (error) {
    // Model not available - silently skip
  }
}

if (availableModels.length < MIN_MODELS) {
  log(`❌ Only found ${availableModels.length} models, need at least ${MIN_MODELS}`)
  return {
    status: 'error',
    message: `Insufficient models: found ${availableModels.length}, need ${MIN_MODELS}`,
    available: availableModels
  }
}

log(`✅ Model discovery complete: ${availableModels.length} models available`)
log(`   Models: ${availableModels.join(', ')}`)
log(`   Providers: ${Array.from(providersSeen).join(', ')}`)

// Select arbiter (most capable model)
const ARBITER_PREFERENCE = ['opus', 'gpt-4', 'grok-2', 'gemini-pro', 'gemini', 'sonnet', 'grok']
const arbiterModel = ARBITER_PREFERENCE.find(m => availableModels.includes(m)) || availableModels[0]

log(`⚖️  Arbiter: ${arbiterModel}`)
log(`🤖 Workers: ${availableModels.join(', ')}`)

// Detect platform (GitHub or GitLab)
log('📍 Detecting platform...')
const platformDetect = await agent(`Detect if this is a GitHub or GitLab repository.

Execute:
if git remote -v | grep -q 'github.com'; then
  echo "github"
elif git remote -v | grep -q 'gitlab'; then
  echo "gitlab"
else
  echo "unknown"
fi

Return the platform name.`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] }
    }
  }
})

const isGitLab = platformDetect.platform === 'gitlab'
const isGitHub = platformDetect.platform === 'github'

log(`✅ Platform: ${platformDetect.platform}`)

// PHASE 1: Detect Application Type
phase('Detect App Type')

log('🔍 Analyzing application structure...')

const appDetection = await agent(`Detect the application type and test strategy.

Analyze the project structure to determine:
1. Application type (web app, CLI, API, library, desktop app, mobile app)
2. Framework/stack (React, Vue, Angular, Express, Django, etc.)
3. Existing test infrastructure (Jest, Mocha, Pytest, etc.)
4. Build/run commands
5. UI presence and how to test it

Execute:
# Check package.json / setup.py / pom.xml / build.gradle / etc.
if [ -f package.json ]; then
  cat package.json | head -100
elif [ -f setup.py ]; then
  cat setup.py | head -50
elif [ -f pom.xml ]; then
  cat pom.xml | head -50
elif [ -f build.gradle ]; then
  cat build.gradle | head -50
elif [ -f Cargo.toml ]; then
  cat Cargo.toml | head -50
fi

# Check for common frameworks
find . -maxdepth 3 -type f -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" | head -20

Return structured app metadata.`, {
  label: 'Detect App Type',
  schema: {
    type: 'object',
    properties: {
      app_type: { type: 'string', enum: ['web', 'cli', 'api', 'library', 'desktop', 'mobile', 'unknown'] },
      framework: { type: 'string' },
      has_ui: { type: 'boolean' },
      test_framework: { type: 'string' },
      build_command: { type: 'string' },
      run_command: { type: 'string' },
      test_command: { type: 'string' },
      entry_points: { type: 'array', items: { type: 'string' } }
    },
    required: ['app_type', 'has_ui']
  }
})

log(`✅ Detected: ${appDetection.app_type} app (${appDetection.framework || 'unknown framework'})`)
log(`   UI: ${appDetection.has_ui ? 'Yes' : 'No'}`)
log(`   Test Framework: ${appDetection.test_framework || 'none detected'}`)

// PHASE 2: Fetch Open Issues
phase('Fetch Open Issues')

log(`📋 Fetching open issues to validate...`)

const fetchIssuesCmd = isGitLab
  ? `glab issue list --state opened --per-page ${MAX_ISSUES_TO_TEST} --json number,title,labels,body`
  : `gh issue list --state open --limit ${MAX_ISSUES_TO_TEST} --json number,title,labels,body`

const openIssues = await agent(`Get open issues to test against.

Execute:
${fetchIssuesCmd}

Return list of open issues with metadata.`, {
  label: 'Fetch Open Issues',
  schema: {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            body: { type: 'string' },
            labels: { type: 'array' }
          }
        }
      }
    }
  }
})

log(`✅ Found ${openIssues.issues?.length || 0} open issues to validate`)

// PHASE 3: Generate Test Plans
phase('Generate Test Plans')

log(`🤖 Generating test strategies from ${availableModels.length} AI models...`)

const testPlanPrompt = `Generate a comprehensive test plan for this ${appDetection.app_type} application.

**Application Details:**
- Type: ${appDetection.app_type}
- Framework: ${appDetection.framework || 'unknown'}
- Has UI: ${appDetection.has_ui}
- Test Framework: ${appDetection.test_framework || 'none'}
- Build Command: ${appDetection.build_command || 'unknown'}
- Run Command: ${appDetection.run_command || 'unknown'}

**Open Issues to Validate (${openIssues.issues?.length || 0}):**
${(openIssues.issues || []).slice(0, 5).map(i => `- #${i.number}: ${i.title}`).join('\n')}

Provide:
1. **test_strategy** - Overall approach (unit, integration, e2e, UI, etc.)
2. **test_steps** - Specific steps to execute
3. **ui_validation_steps** - How to test UI (if applicable)
4. **issue_validation_steps** - How to validate each open issue
5. **tools_needed** - Testing tools/frameworks to use
6. **confidence** - Confidence in this plan (0-100)
7. **rationale** - Why this approach works

Be specific and executable.`

const testPlanSchema = {
  type: 'object',
  properties: {
    test_strategy: { type: 'string' },
    test_steps: { type: 'array', items: { type: 'string' } },
    ui_validation_steps: { type: 'array', items: { type: 'string' } },
    issue_validation_steps: { type: 'array', items: { type: 'object' } },
    tools_needed: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    rationale: { type: 'string' }
  },
  required: ['test_strategy', 'test_steps', 'confidence']
}

log(`🔄 Generating test plans in parallel from ${availableModels.length} models (${availableModels.join(', ')})...`)

const testPlans = await parallel(
  availableModels.map(model =>
    () => agent(testPlanPrompt, { label: `${model} Plan`, schema: testPlanSchema, model })
  )
)

const validPlans = testPlans.filter(Boolean)

if (validPlans.length === 0) {
  log('❌ No valid test plans generated')
  return { status: 'error', message: 'Failed to generate test plans' }
}

log(`✅ Generated ${validPlans.length} test plans`)

// PHASE 4: Select Best Test Plan
phase('Select Best')

log(`⚖️ Selecting best test plan via ${arbiterModel} arbiter...`)

const arbiterPrompt = `Review these ${validPlans.length} proposed test plans for ${appDetection.app_type} application.

${validPlans.map((plan, i) => `
**Plan ${i + 1}**:
- Strategy: ${plan.test_strategy}
- Confidence: ${plan.confidence}%
- Steps: ${plan.test_steps?.length || 0}
- UI Steps: ${plan.ui_validation_steps?.length || 0}
- Rationale: ${plan.rationale}
`).join('\n')}

Select the BEST plan based on:
1. Completeness (covers all test types)
2. UI validation coverage
3. Issue validation strategy
4. Confidence level
5. Executability

Return:
- **selected_index** - Which plan to use (0, 1, or 2)
- **reasoning** - Why this plan is best
- **consensus_score** - Overall confidence (0-100)`

const decision = await agent(arbiterPrompt, {
  label: `${arbiterModel} Arbiter`,
  model: arbiterModel,
  schema: {
    type: 'object',
    properties: {
      selected_index: { type: 'number', minimum: 0, maximum: validPlans.length - 1 },
      reasoning: { type: 'string' },
      consensus_score: { type: 'number', minimum: 0, maximum: 100 }
    },
    required: ['selected_index', 'reasoning']
  }
})

const selectedPlan = validPlans[decision.selected_index]

log(`✅ Selected Plan #${decision.selected_index + 1}`)
log(`   Reasoning: ${decision.reasoning}`)
log(`   Consensus: ${decision.consensus_score}%`)

// Create AI attribution
const aiAttribution = createArbiterAttribution({
  workerModels: availableModels,
  workerProposals: validPlans,
  arbiterModel: arbiterModel,
  arbiterDecision: decision,
  selectedIndex: decision.selected_index
})

log(`📊 AI Attribution: ${availableModels.length} workers, 1 arbiter, ${aiAttribution.rejected_proposals.length} alternatives`)

// PHASE 5: Execute Tests
phase('Execute Tests')

log('🧪 Executing test plan...')

// Execute each test step with multiple AI reviewers
const testResults = await pipeline(
  selectedPlan.test_steps || [],

  // Stage 1: Execute test step
  (step, _, idx) => agent(`Execute test step #${idx + 1}:

${step}

Application context:
- Type: ${appDetection.app_type}
- Framework: ${appDetection.framework}
- Build: ${appDetection.build_command}
- Run: ${appDetection.run_command}

Execute the test step and report:
1. What was tested
2. Pass/fail status
3. Any errors or issues found
4. Screenshots (if UI test)
5. Confidence in result

Return structured test result.`, {
    label: `Test Step ${idx + 1}`,
    schema: {
      type: 'object',
      properties: {
        step_description: { type: 'string' },
        status: { type: 'string', enum: ['pass', 'fail', 'skip', 'error'] },
        findings: { type: 'array', items: { type: 'object' } },
        errors: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'number' }
      }
    }
  }),

  // Stage 2: Multi-model review of result (only for failures)
  (result, _, idx) => {
    if (result.status === 'pass') {
      return { ...result, reviews: [] }
    }

    // For failures, get multi-model review with rotation for diversity
    const rotation = idx % availableModels.length
    const reviewModels = [
      ...availableModels.slice(rotation),
      ...availableModels.slice(0, rotation)
    ]

    log(`🔍 Test failed - reviewing with ${reviewModels.length} models (${reviewModels.join(', ')})...`)

    return parallel(reviewModels.map((model, modelIdx) => () => {
      const prompts = [
        `Review this test failure:

Step: ${result.step_description}
Status: ${result.status}
Errors: ${result.errors?.join(', ')}

Is this a real bug or a test infrastructure issue?
Severity: critical, major, or minor?
Root cause analysis?`,
        `Analyze test failure: ${result.step_description}

Determine:
1. Is this reproducible?
2. What's the impact?
3. Is it related to any open issue?`,
        `Quick bug assessment: ${result.step_description}

Real bug or flaky test?`,
        `Comprehensive analysis: ${result.step_description}

Check for edge cases and integration issues.`
      ]

      const prompt = prompts[modelIdx % prompts.length]

      return agent(prompt, {
        label: `${model} Review`,
        model,
        schema: {
          type: 'object',
          properties: {
            is_real_bug: { type: 'boolean' },
            severity: { type: 'string' },
            root_cause: { type: 'string' },
            confidence: { type: 'number' },
            related_issue: { type: 'number' }
          }
        }
      })
    })).then(reviews => ({
      ...result,
      reviews: reviews.filter(Boolean),
      ai_consensus: {
        models: reviewModels,
        real_bug_votes: reviews.filter(Boolean).filter(r => r.is_real_bug).length,
        total_votes: reviews.filter(Boolean).length
      }
    }))
  }
)

const testsPassed = testResults.filter(Boolean).filter(r => r.status === 'pass').length
const testsFailed = testResults.filter(Boolean).filter(r => r.status === 'fail').length

log(`✅ Tests complete: ${testsPassed} passed, ${testsFailed} failed`)

// PHASE 6: Validate Open Issues
phase('Validate Issues')

log(`🔍 Validating ${openIssues.issues?.length || 0} open issues...`)

const issueValidations = await pipeline(
  (openIssues.issues || []).slice(0, MAX_ISSUES_TO_TEST),

  // Stage 1: Try to reproduce the issue
  (issue) => agent(`Validate issue #${issue.number}: "${issue.title}"

Issue description:
${issue.body || 'No description'}

Test if this issue is reproducible:
1. Follow steps in issue description
2. Try to trigger the bug
3. Document what you observe
4. Determine if bug still exists

Application context:
- Type: ${appDetection.app_type}
- Run: ${appDetection.run_command}

Return validation result.`, {
    label: `Validate #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        issue_number: { type: 'number' },
        is_reproducible: { type: 'boolean' },
        still_exists: { type: 'boolean' },
        observations: { type: 'string' },
        severity: { type: 'string' },
        confidence: { type: 'number' }
      }
    }
  }),

  // Stage 2: Multi-model consensus on validation (only for reproducible issues)
  (validation, _, idx) => {
    if (!validation.is_reproducible) {
      return { ...validation, consensus: null }
    }

    // Get consensus from all available models with rotation
    const rotation = idx % availableModels.length
    const consensusModels = [
      ...availableModels.slice(rotation),
      ...availableModels.slice(0, rotation)
    ]

    log(`🤖 Issue #${validation.issue_number} reproduced - getting ${consensusModels.length}-model consensus (${consensusModels.join(', ')})...`)

    return parallel(consensusModels.map((model, modelIdx) => () => {
      const prompts = [
        `Verify issue #${validation.issue_number} is real.

Observations: ${validation.observations}

Confirm:
1. This is a real bug (not test issue)
2. Severity assessment
3. Should it stay open or be closed?`,
        `Review validation of issue #${validation.issue_number}.

Is the issue still present? What action?`,
        `Quick check: issue #${validation.issue_number} valid?`,
        `Final verification: issue #${validation.issue_number} status?`
      ]

      const prompt = prompts[modelIdx % prompts.length]

      return agent(prompt, {
        label: `${model} Verify`,
        model,
        schema: {
          type: 'object',
          properties: {
            is_real: { type: 'boolean' },
            severity: { type: 'string' },
            action: { type: 'string', enum: ['keep-open', 'close-fixed', 'close-invalid', 'unknown'] }
          }
        }
      })
    })).then(reviews => ({
      ...validation,
      consensus: {
        models: consensusModels,
        is_real_votes: reviews.filter(Boolean).filter(r => r.is_real).length,
        total_votes: reviews.filter(Boolean).length,
        reviews: reviews.filter(Boolean)
      }
    }))
  }
)

const issuesReproduced = issueValidations.filter(Boolean).filter(v => v.is_reproducible).length
const issuesFixed = issueValidations.filter(Boolean).filter(v => !v.still_exists).length

log(`✅ Issue validation: ${issuesReproduced} reproduced, ${issuesFixed} appear fixed`)

// PHASE 7: Multi-Model Review
phase('Multi-Model Review')

log('⚖️ Consolidating findings with arbiter consensus...')

// Collect all findings
const allFindings = []

// Add test failures
testResults.filter(Boolean).forEach(result => {
  if (result.status === 'fail' && result.ai_consensus) {
    const isRealBug = result.ai_consensus.real_bug_votes >= 2
    if (isRealBug) {
      allFindings.push({
        source: 'test_execution',
        type: 'test_failure',
        description: result.step_description,
        severity: result.reviews?.[0]?.severity || 'major',
        errors: result.errors,
        confidence: result.confidence,
        ai_attribution: {
          worker_models: result.ai_consensus.models,
          consensus_votes: `${result.ai_consensus.real_bug_votes}/${result.ai_consensus.total_votes}`,
          reviews: result.reviews
        }
      })
    }
  }
})

// Add issue validations
issueValidations.filter(Boolean).forEach(validation => {
  if (validation.is_reproducible && validation.consensus) {
    const isRealBug = validation.consensus.is_real_votes >= 2
    if (isRealBug) {
      allFindings.push({
        source: 'issue_validation',
        type: 'reproduced_issue',
        issue_number: validation.issue_number,
        description: validation.observations,
        severity: validation.severity,
        confidence: validation.confidence,
        ai_attribution: {
          worker_models: validation.consensus.models,
          consensus_votes: `${validation.consensus.is_real_votes}/${validation.consensus.total_votes}`,
          reviews: validation.consensus.reviews
        }
      })
    }
  }
})

log(`✅ Consolidated ${allFindings.length} verified findings`)

// PHASE 8: Report Results
phase('Report Results')

if (args?.['create-issues'] !== false && allFindings.length > 0) {
  log(`📝 Creating/updating issues for ${allFindings.length} findings...`)

  const reportedIssues = await pipeline(
    allFindings,

    (finding) => {
      // If this is a reproduced issue, update it instead of creating new
      if (finding.type === 'reproduced_issue') {
        const commentBody = `✅ **Issue Validated by Automated Testing**

This issue was tested and confirmed to still exist.

**Validation Results:**
- Reproducible: Yes
- Severity: ${finding.severity}
- Confidence: ${finding.confidence}%

**Observations:**
${finding.description}

---

## 🤖 AI Attribution

**Multi-Model Consensus:**
- Models: ${finding.ai_attribution.worker_models.join(', ')}
- Consensus: ${finding.ai_attribution.consensus_votes} models confirmed
- Reviews: ${finding.ai_attribution.reviews.length}

${finding.ai_attribution.reviews.map((r, i) => `
**Review ${i + 1} (${finding.ai_attribution.worker_models[i]})**:
- Real Bug: ${r.is_real ? 'Yes' : 'No'}
- Severity: ${r.severity || 'N/A'}
- Action: ${r.action || 'N/A'}
`).join('\n')}

---

🤖 Validated by code-test workflow`

        const commentCmd = isGitLab
          ? `glab issue note ${finding.issue_number} -m "${commentBody}"`
          : `gh issue comment ${finding.issue_number} --body "${commentBody}"`

        return agent(`Add validation comment to issue #${finding.issue_number}.

Execute:
${commentCmd}

Return issue number.`, {
          label: `Update #${finding.issue_number}`,
          schema: {
            type: 'object',
            properties: {
              issue_number: { type: 'number' }
            }
          }
        })
      } else {
        // Create new issue for test failure
        const issueTitle = `[TEST FAILURE] ${finding.description?.slice(0, 80)}`
        const issueBody = `## Test Failure

**Type**: ${finding.type}
**Severity**: ${finding.severity}
**Confidence**: ${finding.confidence}%

### Description
${finding.description}

### Errors
${finding.errors?.join('\n') || 'None'}

---

## 🤖 AI Attribution

**Multi-Model Consensus:**
- Models: ${finding.ai_attribution.worker_models.join(', ')}
- Consensus: ${finding.ai_attribution.consensus_votes} models confirmed as real bug

${finding.ai_attribution.reviews.map((r, i) => `
**Review ${i + 1} (${finding.ai_attribution.worker_models[i]})**:
- Real Bug: ${r.is_real_bug ? 'Yes' : 'No'}
- Severity: ${r.severity || 'N/A'}
- Root Cause: ${r.root_cause || 'N/A'}
`).join('\n')}

---

🤖 Found by code-test workflow`

        const createCmd = isGitLab
          ? `glab issue create --title "${issueTitle}" --description "${issueBody}" --label bug,test-failure`
          : `gh issue create --title "${issueTitle}" --body "${issueBody}" --label bug,test-failure,${finding.severity}`

        return agent(`Create issue for test failure.

Execute:
${createCmd}

Return issue number and URL.`, {
          label: `Create Issue: ${finding.description?.slice(0, 30)}`,
          schema: {
            type: 'object',
            properties: {
              issue_url: { type: 'string' },
              issue_number: { type: 'number' }
            }
          }
        })
      }
    }
  )

  const successCount = reportedIssues.filter(Boolean).length
  log(`✅ Reported ${successCount} issues`)
} else {
  log('ℹ️  No issues to report or issue creation disabled')
}

// Final Summary
log('')
log('═'.repeat(80))
log('🧪 APPLICATION TESTING COMPLETE 🧪')
log('═'.repeat(80))
log(`App Type: ${appDetection.app_type} (${appDetection.framework || 'unknown'})`)
log(`Tests Executed: ${testResults.filter(Boolean).length}`)
log(`  Passed: ${testsPassed}`)
log(`  Failed: ${testsFailed}`)
log(`Issues Validated: ${issueValidations.filter(Boolean).length}`)
log(`  Reproduced: ${issuesReproduced}`)
log(`  Appear Fixed: ${issuesFixed}`)
log(`Total Findings: ${allFindings.length}`)
log('═'.repeat(80))

return {
  status: 'complete',
  app_type: appDetection.app_type,
  framework: appDetection.framework,
  test_summary: {
    total: testResults.filter(Boolean).length,
    passed: testsPassed,
    failed: testsFailed
  },
  issue_summary: {
    total: issueValidations.filter(Boolean).length,
    reproduced: issuesReproduced,
    fixed: issuesFixed
  },
  findings: allFindings,
  ai_attribution: aiAttribution
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function createArbiterAttribution({workerModels, workerProposals, arbiterModel, arbiterDecision, selectedIndex}) {
  const selectedWorker = workerModels[selectedIndex]
  const selectedProposal = workerProposals[selectedIndex]

  const rejectedProposals = workerProposals
    .map((proposal, idx) => ({
      model: workerModels[idx],
      proposal: proposal,
      index: idx
    }))
    .filter((_, idx) => idx !== selectedIndex)
    .map(rp => ({
      model: rp.model,
      approach: rp.proposal?.test_strategy || '',
      confidence: rp.proposal?.confidence || 0,
      reason: `Not selected by ${arbiterModel} arbiter`,
      rationale: rp.proposal?.rationale || ''
    }))

  return {
    total_models_reviewed: workerModels.length,
    worker_ai: {
      model: selectedWorker,
      confidence: selectedProposal?.confidence || 0,
      approach: selectedProposal?.test_strategy || '',
      rationale: selectedProposal?.rationale || ''
    },
    arbiter: {
      model: arbiterModel,
      decision: 'selected',
      selected_index: selectedIndex,
      reasoning: arbiterDecision?.reasoning || '',
      consensus_score: arbiterDecision?.consensus_score || 0
    },
    rejected_proposals: rejectedProposals,
    consensus: {
      models_proposed: workerModels.length,
      selected_by_arbiter: 1
    }
  }
}
