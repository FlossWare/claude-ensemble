export const meta = {
  name: 'code-test-auto',
  description: 'Autonomous testing bot - auto-creates issues for all test failures',
  whenToUse: 'When you want fully automated comprehensive testing without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Setup', detail: 'Detect app type and test strategy' },
    { title: 'Fetch Open Issues', detail: 'Get issues to validate' },
    { title: 'Generate Test Plans', detail: 'Multi-AI test strategies' },
    { title: 'Execute Tests', detail: 'Run comprehensive test suite' },
    { title: 'Validate Issues', detail: 'Check if issues reproduce' },
    { title: 'Multi-Model Verification', detail: 'Verify failures', model: 'opus' },
    { title: 'Impact Analysis', detail: 'Assess severity of failures' },
    { title: 'Create Issues', detail: 'Auto-create for verified failures' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===



// ============================================================================
// INLINE DEPENDENCIES
// ============================================================================

// Inlined from shared/platform-detector.js
async function detectPlatform(agent) {
  const result = await _agent(`Detect the repository platform and return details.

Execute these commands:
git remote get-url origin
which gh
which glab

Based on the remote URL and available CLIs, determine:
- Platform (github, gitlab, or bitbucket)
- CLI tool available (gh, glab, or bb)
- Repository owner/name

Return structured data.`, {
    label: 'Detect Platform',
    schema: {
      type: 'object',
      properties: {
        platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket', 'unknown'] },
        cli: { type: 'string', enum: ['gh', 'glab', 'bb', 'none'] },
        remote_url: { type: 'string' },
        repo_owner: { type: 'string' },
        repo_name: { type: 'string' },
      },
      required: ['platform', 'cli', 'remote_url'],
    }
  })

  return result
}

async function detectAppType(agent) {
  return await _agent(`Detect application type.

Check for:
- package.json (Node.js)
- requirements.txt (Python)
- pom.xml (Java)
- go.mod (Go)
- UI frameworks (React, Vue, Angular)
- Test frameworks

Return app type and test strategy.`, {
    label: 'Detect App Type',
    schema: {
      type: 'object',
      properties: {
        app_type: { type: 'string' },
        language: { type: 'string' },
        frameworks: { type: 'array', items: { type: 'string' } },
        has_ui: { type: 'boolean' },
        test_frameworks: { type: 'array', items: { type: 'string' } },
        recommended_tests: { type: 'array', items: { type: 'string' } }
      }
    }
  })
}

async function multiModelTestPlans(agent, appInfo, workers) {
  log(`🤖 ${workers.length} models creating test plans...`)

  const testPlanPrompt = `Create a comprehensive test plan for this application:

App Type: ${appInfo.app_type}
Language: ${appInfo.language}
Frameworks: ${appInfo.frameworks?.join(', ') || 'none'}
Has UI: ${appInfo.has_ui}
Existing Test Frameworks: ${appInfo.test_frameworks?.join(', ') || 'none'}

Create test plan covering:
1. Unit tests (if applicable)
2. Integration tests
3. UI tests (if has UI)
4. API tests (if applicable)
5. Edge cases
6. Performance tests

Return comprehensive test strategy.`

  const plans = await Promise.all(workers.map(model =>
    agent(testPlanPrompt, {
      label: `Test Plan (${model})`,
      model,
      phase: 'Generate Test Plans',
      schema: {
        type: 'object',
        properties: {
          test_categories: { type: 'array', items: { type: 'string' } },
          test_cases: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                name: { type: 'string' },
                category: { type: 'string' },
                description: { type: 'string' },
                expected_result: { type: 'string' }
              }
            }
          },
          priority_order: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'number' }
        }
      }
    }).catch(() => null)
  ))

  return plans.filter(Boolean)
}

async function arbiterSelectTestPlan(agent, plans, arbiterModel) {
  const planSummary = plans.map((p, idx) =>
    `Plan ${idx + 1}: ${p.test_categories?.length || 0} categories, ${p.test_cases?.length || 0} test cases, ${p.confidence}% confidence`
  ).join('\n')

  return await _agent(`Select best test plan:

${planSummary}

Choose the most comprehensive and appropriate plan.`, {
    label: 'Select Test Plan',
    model: arbiterModel || 'fable',
    schema: {
      type: 'object',
      properties: {
        selected_index: { type: 'number' },
        reasoning: { type: 'string' }
      }
    }
  })
}

async function executeTests(agent, testPlan) {
  log(`  🚀 Running ${Math.min(20, testPlan.test_cases?.length || 0)} tests in parallel...`)

  const results = await parallel((testPlan.test_cases || []).slice(0, 20).map(testCase => () =>
    agent(`Execute test: ${testCase.name}

Category: ${testCase.category}
Description: ${testCase.description}
Expected: ${testCase.expected_result}

Run this test and return results.`, {
      label: `Test: ${testCase.name}`,
      schema: {
        type: 'object',
        properties: {
          passed: { type: 'boolean' },
          actual_result: { type: 'string' },
          error_message: { type: 'string' },
          severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
          reproducible: { type: 'boolean' }
        }
      }
    }).then(result => ({
      ...testCase,
      ...result,
      test_name: testCase.name
    }))
  ))

  results.filter(Boolean).forEach(r => {
    const icon = r.passed ? '✅' : '❌'
    log(`  ${icon} ${r.test_name}`)
  })

  return results.filter(Boolean)
}

async function multiModelVerifyFailure(agent, failure, workers) {
  const verifyPrompt = `Verify this test failure is a real bug:

Test: ${failure.test_name}
Expected: ${failure.expected_result}
Actual: ${failure.actual_result}
Error: ${failure.error_message || 'none'}

Verify:
1. Is this a real bug or test issue?
2. What's the actual severity?
3. Is it reproducible?
4. Your confidence (0-100)

Return verification.`

  const verifications = await Promise.all(workers.map(model =>
    agent(verifyPrompt, {
      label: `Verify (${model})`,
      model,
      schema: {
        type: 'object',
        properties: {
          is_real_bug: { type: 'boolean' },
          severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
          reproducible: { type: 'boolean' },
          confidence: { type: 'number' },
          reasoning: { type: 'string' }
        }
      }
    }).catch(() => null)
  ))

  return verifications.filter(Boolean)
}

async function arbiterConsensus(agent, failure, verifications, arbiterModel) {
  const summary = verifications.map((v, idx) =>
    `Model ${idx + 1}: ${v.is_real_bug ? 'REAL BUG' : 'FALSE POSITIVE'} (${v.severity}, ${v.confidence}% confidence)`
  ).join('\n')

  return await _agent(`Make consensus decision on test failure:

Test: ${failure.test_name}

Verifications:
${summary}

Decide if this is a real bug worth creating an issue for.`, {
    label: 'Arbiter Consensus',
    model: arbiterModel || 'fable',
    schema: {
      type: 'object',
      properties: {
        is_real_bug: { type: 'boolean' },
        final_severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
        create_issue: { type: 'boolean' },
        reasoning: { type: 'string' },
        consensus_score: { type: 'number' }
      }
    }
  })
}

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  workers: [
    'fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini',
    // Gemini (via MCP/Google AI API)
    // 'grok',                   // Grok (via xAI API) - uncomment when configured
    // 'ollama/llama3',          // Ollama (local) - uncomment when running
    // 'gpt-4',                  // OpenAI (via MCP) - uncomment when configured
  ],
  arbiterModel: 'fable',

  // Auto-create issue criteria
  autoCreate: {
    minConsensus: 70,                 // 70%+ agreement required
    minConfidence: 75,                // 75%+ confidence
    minSeverity: 'medium',            // At least medium severity
    realBugRequired: true,            // Must be verified as real bug
    mustBeReproducible: true,         // Must be reproducible
  },

  // Test scope
  maxTestCases: 20,                   // Max test cases to run
  maxIssues: 10,                      // Max issues to validate
}

const maxTests = args?.maxTests || CONFIG.maxTestCases
const maxIssues = args?.maxIssues || CONFIG.maxIssues

log('')
log('═'.repeat(60))
log('🧪 AUTONOMOUS APPLICATION TESTING')
log('═'.repeat(60))
log(`Workers: ${CONFIG.workers.join(', ')}`)
log(`Arbiter: ${CONFIG.arbiterModel}`)
log(`Scope: ${maxTests} test cases, ${maxIssues} issues to validate`)
log(`Auto-Create: Consensus ≥ ${CONFIG.autoCreate.minConsensus}%, Real bugs only`)
log('═'.repeat(60))
log('')

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// PHASE 1: Setup
phase('Setup')

log('🔧 Detecting platform...')
const platform = await detectPlatform(agent)
log(`✅ Platform: ${platform.platform}`)

log('🔍 Detecting app type...')
const appInfo = await detectAppType(agent)
log(`✅ App: ${appInfo.app_type} (${appInfo.language})`)
log(`   Has UI: ${appInfo.has_ui}`)
log(`   Frameworks: ${appInfo.frameworks?.join(', ') || 'none'}`)

// PHASE 2: Fetch Open Issues
phase('Fetch Open Issues')

log('📋 Fetching open issues...')

const issueListCmd = platform.platform === 'gitlab'
  ? `glab issue list --state opened --per-page ${maxIssues} --json number,title,description`
  : `gh issue list --state open --limit ${maxIssues} --json number,title,body`

const openIssues = await _agent(`List open issues.

Execute:
${issueListCmd}

Return issue list.`, {
  label: 'Open Issues',
  schema: {
    type: 'object',
    properties: {
      issues: { type: 'array' },
      total: { type: 'number' }
    }
  }
})

log(`📊 ${openIssues.total || 0} open issues`)

// PHASE 3: Generate Test Plans
phase('Generate Test Plans')

log('📝 Generating test plans...')
const testPlans = await multiModelTestPlans(agent, appInfo, CONFIG.workers)
log(`✅ ${testPlans.length} test plans generated`)

const planDecision = await arbiterSelectTestPlan(agent, testPlans, CONFIG.arbiterModel)
const selectedPlan = testPlans[planDecision.selected_index]

log(`✅ Selected plan ${planDecision.selected_index + 1}`)
log(`   Test cases: ${selectedPlan.test_cases?.length || 0}`)

// PHASE 4: Execute Tests
phase('Execute Tests')

log('🧪 Running tests...')
const testResults = await executeTests(agent, selectedPlan)

const failures = testResults.filter(t => !t.passed)
const passes = testResults.filter(t => t.passed)

log(`✅ Tests complete`)
log(`   Passed: ${passes.length}`)
log(`   Failed: ${failures.length}`)

// PHASE 5: Validate Issues
phase('Validate Issues')

log('🔍 Validating open issues...')
log('🚀 Validating issues in parallel...')

const issueValidations = await parallel((openIssues.issues || []).slice(0, CONFIG.maxIssues).map(issue => () =>
  agent(`Validate if issue #${issue.number} is reproducible.

Title: ${issue.title}
Description: ${issue.body || issue.description || 'No description'}

Try to reproduce this issue.
Return validation result.`, {
    label: `Validate #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        reproducible: { type: 'boolean' },
        still_valid: { type: 'boolean' },
        notes: { type: 'string' }
      }
    }
  }).then(validation => ({
    issue_number: issue.number,
    title: issue.title,
    ...validation
  }))
))

issueValidations.filter(Boolean).forEach(validation => {
  const icon = validation.reproducible ? '✅' : !validation.still_valid ? 'ℹ️' : '❌'
  const status = validation.reproducible ? 'Reproduced' : !validation.still_valid ? 'No longer valid' : 'Could not reproduce'
  log(`  ${icon} Issue #${validation.issue_number}: ${status}`)
})

log(`✅ Issue validation complete`)

// PHASE 6: Multi-Model Verification
phase('Multi-Model Verification')

log('🤖 Verifying failures with multiple AIs...')
log('🚀 Verifying failures in parallel...')

const verifiedFailures = (await parallel(failures.map(failure => async () => {
  const verifications = await multiModelVerifyFailure(agent, failure, CONFIG.workers)
  const consensus = await arbiterConsensus(agent, failure, verifications, CONFIG.arbiterModel)

  if (consensus.create_issue && consensus.is_real_bug && consensus.consensus_score >= CONFIG.autoCreate.minConsensus) {
    return {
      ...failure,
      verified: true,
      final_severity: consensus.final_severity,
      consensus_score: consensus.consensus_score,
      reasoning: consensus.reasoning
    }
  }
  return null
}))).filter(Boolean)

verifiedFailures.forEach(failure => {
  log(`  ✅ ${failure.test_name} - VERIFIED (${failure.consensus_score}% consensus)`)
})

log(`✅ ${verifiedFailures.length} failures verified`)

// PHASE 7: Impact Analysis
phase('Impact Analysis')

log('🎯 Analyzing impact of verified failures...')

for (const failure of verifiedFailures) {
  // Base impact score from severity
  failure.impact_score = failure.final_severity === 'critical' ? 100 :
                         failure.final_severity === 'high' ? 75 :
                         failure.final_severity === 'medium' ? 50 : 25

  // Boost score for UI failures (user-facing)
  if (failure.category?.toLowerCase().includes('ui') ||
      failure.test_name?.toLowerCase().includes('ui')) {
    failure.impact_score += 15
    log(`  Boosted UI failure: ${failure.test_name} (+15)`)
  }

  // Boost score for security/auth failures
  if (failure.category?.toLowerCase().includes('security') ||
      failure.category?.toLowerCase().includes('auth') ||
      failure.test_name?.toLowerCase().includes('auth')) {
    failure.impact_score += 20
    log(`  Boosted security failure: ${failure.test_name} (+20)`)
  }

  // Boost score for highly reproducible failures
  if (failure.reproducible) {
    failure.impact_score += 10
  }

  // Cap at 100
  failure.impact_score = Math.min(100, failure.impact_score)

  // Determine risk level
  failure.risk_level = failure.impact_score >= 90 ? 'critical' :
                       failure.impact_score >= 70 ? 'high' :
                       failure.impact_score >= 40 ? 'medium' : 'low'
}

// Sort by impact score (highest first)
verifiedFailures.sort((a, b) => b.impact_score - a.impact_score)

log(`✅ Impact analysis complete`)
log(`   ${verifiedFailures.length} failures prioritized`)
if (verifiedFailures.length > 0) {
  log(`   Highest impact: ${verifiedFailures[0].test_name} (score: ${verifiedFailures[0].impact_score})`)

  // Show breakdown by impact level
  const impactBreakdown = {
    critical: verifiedFailures.filter(f => f.risk_level === 'critical').length,
    high: verifiedFailures.filter(f => f.risk_level === 'high').length,
    medium: verifiedFailures.filter(f => f.risk_level === 'medium').length,
    low: verifiedFailures.filter(f => f.risk_level === 'low').length
  }

  log(`   By impact level:`)
  log(`     🚨 Critical impact: ${impactBreakdown.critical}`)
  log(`     ⚠️  High impact: ${impactBreakdown.high}`)
  log(`     📋 Medium impact: ${impactBreakdown.medium}`)
  log(`     ℹ️  Low impact: ${impactBreakdown.low}`)
}

// PHASE 8: Create Issues
phase('Create Issues')

log('📝 Creating issues for verified failures...')

const createdIssues = []

for (const failure of verifiedFailures) {
  const severityLabel = failure.final_severity === 'critical' ? '🚨 CRITICAL' :
                        failure.final_severity === 'high' ? '⚠️ HIGH' :
                        failure.final_severity === 'medium' ? '📋 MEDIUM' : 'ℹ️ LOW'

  const issueTitle = `${severityLabel}: Test failure - ${failure.test_name}`
  const issueBody = `## Test Failure: ${failure.test_name}

**Severity**: ${failure.final_severity}
**Category**: ${failure.category}
**Consensus**: ${failure.consensus_score}%

### Test Details
**Expected**: ${failure.expected_result}
**Actual**: ${failure.actual_result}
${failure.error_message ? `**Error**: ${failure.error_message}` : ''}

### AI Verification
${failure.reasoning}

**Impact**: ${failure.impact_score}/100
**Reproducible**: ${failure.reproducible ? 'Yes' : 'No'}

### How to Reproduce
${failure.description}

---

*Auto-created by code-test-auto*
*Verified by ${CONFIG.workers.length} AI models*`

  const createCmd = platform.platform === 'gitlab'
    ? `glab issue create --title "${issueTitle}" --description "${issueBody.replace(/"/g, '\\"')}" --label "bug,test-failure,auto-created,${failure.final_severity}"`
    : `gh issue create --title "${issueTitle}" --body "${issueBody.replace(/"/g, '\\"')}" --label "bug,test-failure,auto-created,${failure.final_severity}"`

  const created = await _agent(`Create issue.

Execute:
${createCmd}

Return issue number.`, {
    label: 'Create Issue',
    schema: {
      type: 'object',
      properties: {
        number: { type: 'number' },
        url: { type: 'string' }
      }
    }
  })

  createdIssues.push({
    number: created.number,
    title: issueTitle,
    severity: failure.final_severity,
    test_name: failure.test_name
  })

  log(`  ✅ Created issue #${created.number}`)
}

log(`✅ ${createdIssues.length} issues created`)

// ============================================================================
// SUMMARY
// ============================================================================

log('')
log('═'.repeat(60))
log('📊 TESTING SUMMARY')
log('═'.repeat(60))
log(`Tests run: ${testResults.length}`)
log(`Passed: ${passes.length}`)
log(`Failed: ${failures.length}`)
log(`Verified failures: ${verifiedFailures.length}`)
log(`Issues created: ${createdIssues.length}`)
log('')

const bySeverity = {
  critical: createdIssues.filter(i => i.severity === 'critical').length,
  high: createdIssues.filter(i => i.severity === 'high').length,
  medium: createdIssues.filter(i => i.severity === 'medium').length,
  low: createdIssues.filter(i => i.severity === 'low').length
}

log(`By Severity:`)
log(`  🚨 Critical: ${bySeverity.critical}`)
log(`  ⚠️  High: ${bySeverity.high}`)
log(`  📋 Medium: ${bySeverity.medium}`)
log(`  ℹ️  Low: ${bySeverity.low}`)
log('')

log(`Issue Validations:`)
log(`  Reproducible: ${issueValidations.filter(v => v.reproducible).length}`)
log(`  Not reproducible: ${issueValidations.filter(v => !v.reproducible && v.still_valid).length}`)
log(`  No longer valid: ${issueValidations.filter(v => !v.still_valid).length}`)
log('')

createdIssues.forEach(i => {
  const icon = i.severity === 'critical' ? '🚨' :
               i.severity === 'high' ? '⚠️' :
               i.severity === 'medium' ? '📋' : 'ℹ️'
  log(`${icon} #${i.number}: ${i.title}`)
})

log('═'.repeat(60))
log('')

const result = {
  status: 'success',
  tests_run: testResults.length,
  tests_passed: passes.length,
  tests_failed: failures.length,
  pass_rate: testResults.length > 0 ? Math.round((passes.length / testResults.length) * 100) : 0,
  verified_failures: verifiedFailures.length,
  issues_created: createdIssues.length,
  issue_validations: issueValidations.length,
  issues_reproducible: issueValidations.filter(v => v.reproducible).length,
  by_severity: bySeverity,
  created_issues: createdIssues
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-test',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result

}
