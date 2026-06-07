export const meta = {
  name: 'code-test',
  description: 'Comprehensive application testing with impact analysis: build verification, UI validation, integration tests, open issue verification',
  phases: [
    { title: 'Detect App Type', detail: 'Identify application type and test strategy' },
    { title: 'Build Application', detail: 'Compile/build before testing (fail fast)' },
    { title: 'Fetch Open Issues', detail: 'Get open issues to validate against' },
    { title: 'Generate Test Plans', detail: 'Multiple AIs propose test strategies' },
    { title: 'Select Best Plan', detail: 'Choose optimal test plan via consensus' },
    { title: 'Execute Tests', detail: 'Run automated tests, UI checks, integration tests' },
    { title: 'Validate Issues', detail: 'Check if open issues are reproducible' },
    { title: 'Impact Analysis', detail: 'Assess severity of test failures' },
    { title: 'Multi-Model Review', detail: 'Verify test results with multiple AIs' },
    { title: 'User Confirmation', detail: 'User decides which failures to report' },
    { title: 'Create Issues', detail: 'Create issues for approved test failures' },
  ],
}

// Configuration
const AUTONOMOUS = args?.autonomous === true  // INTERACTIVE by default (use code-test-auto for autonomous)
const MAX_ISSUES_TO_TEST = args?.maxIssues || 10
const CONFIDENCE_THRESHOLD = 70
const MIN_MODELS = args?.minModels || 3  // Minimum models needed for consensus
const MAX_MODELS = args?.maxModels || Infinity  // Maximum models to use

log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE (prompts before creating issues)'}`)
if (!AUTONOMOUS) {
  log(`💡 Use code-test-auto for fully autonomous mode (auto-creates issues)`)
}

// ============================================================================
// DYNAMIC MODEL DISCOVERY
// ============================================================================

log('🔍 Discovering available AI models...')

// Known models to try (in preference order)
const KNOWN_MODELS = [
  // Claude models (built-in)
  'opus', 'sonnet', 'haiku',
  // Gemini models
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
const arbiterModel = ARBITER_PREFERENCE.find(m => availableModels.includes(m)) || availableModels[0]

log(`⚖️  Arbiter: ${arbiterModel}`)
log(`🤖 Workers: ${availableModels.join(', ')}`)

// ============================================================================
// ISSUE OPERATIONS (inlined from shared/issue-operations.js)
// ============================================================================

async function detectPlatform() {
  const result = await agent(`Detect platform (GitHub or GitLab).

Execute:
if git remote -v | grep -q 'github.com'; then
  echo "github"
elif git remote -v | grep -q 'gitlab'; then
  echo "gitlab"
else
  echo "unknown"
fi`, {
    label: 'Detect Platform',
    schema: {
      type: 'object',
      properties: { platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] } }
    }
  })
  return {
    platform: result.platform,
    isGitHub: result.platform === 'github',
    isGitLab: result.platform === 'gitlab'
  }
}

async function fetchOpenIssues(platform, limit = 100) {
  const isGitLab = platform === 'gitlab'
  const fetchCmd = isGitLab
    ? `glab issue list --state opened --per-page ${limit} --json number,title,labels,body`
    : `gh issue list --state open --limit ${limit} --json number,title,labels,body`

  const result = await agent(`Fetch open issues from ${platform}.

Execute:
${fetchCmd}

Return list.`, {
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

  return result.issues || []
}

async function createIssue(platform, title, body, labels = []) {
  const isGitLab = platform === 'gitlab'
  let createCmd = isGitLab
    ? `glab issue create --title "${title}" --description "${body}"`
    : `gh issue create --title "${title}" --body "${body}"`

  if (labels.length > 0) {
    if (isGitLab) {
      createCmd += ` --label "${labels.join(',')}"`
    } else {
      labels.forEach(l => { createCmd += ` --label "${l}"` })
    }
  }

  const result = await agent(`Create issue.

Execute:
${createCmd}

Return issue number and URL.`, {
    label: 'Create Issue',
    schema: {
      type: 'object',
      properties: {
        issue_number: { type: 'number' },
        issue_url: { type: 'string' }
      }
    }
  })

  return result
}

async function commentOnIssue(platform, issueNumber, comment) {
  const isGitLab = platform === 'gitlab'
  const commentCmd = isGitLab
    ? `glab issue note ${issueNumber} -m "${comment}"`
    : `gh issue comment ${issueNumber} --body "${comment}"`

  await agent(`Add comment to issue #${issueNumber}.

Execute:
${commentCmd}`, {
    label: `Comment on #${issueNumber}`
  })

  return true
}

// ============================================================================
// CHUNKING UTILITIES (inlined from shared/chunking-utils.js)
// ============================================================================

function chunkArray(items, chunkSize = 10) {
  const chunks = []
  for (let i = 0; i < items.length; i += chunkSize) {
    chunks.push(items.slice(i, i + chunkSize))
  }
  return chunks
}

function calculateOptimalChunkSize(totalItems, estimatedTimePerItem, targetChunkTime = 120) {
  const itemsPerChunk = Math.max(1, Math.floor(targetChunkTime / estimatedTimePerItem))
  const cappedSize = Math.min(Math.max(itemsPerChunk, 1), 20)
  if (totalItems <= cappedSize) return totalItems
  return cappedSize
}

// ============================================================================
// CLUSTERING UTILITIES (inlined from shared/clustering-utils.js)
// ============================================================================

async function clusterRejectionReasons(rejections) {
  if (!rejections || rejections.length === 0) return { clusters: [], total: 0 }

  const reasonList = rejections.map(r => `- "${r.reason}" (${r.model}, ${r.count} times)`).join('\n')

  try {
    return await agent(`Cluster these rejection reasons into semantic groups:

${reasonList}

Group similar reasons and identify common themes.
Return clustered patterns.`, {
      label: 'Cluster Rejections',
      schema: {
        type: 'object',
        properties: {
          clusters: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                name: { type: 'string' },
                theme: { type: 'string' },
                reasons: { type: 'array' },
                total_count: { type: 'number' }
              }
            }
          },
          insights: { type: 'array', items: { type: 'string' } }
        }
      }
    })
  } catch (error) {
    // Non-critical - return empty if clustering fails
    return { clusters: [], insights: [] }
  }
}

// ============================================================================
// LEARNING SYSTEM (inlined from shared/learning-system.js)
// ============================================================================

async function captureDecision(decision) {
  const learningEntry = {
    // timestamp: new Date().toISOString(),  // Disabled - Date() not allowed in workflows
    workflow: decision.workflow,
    task_type: decision.task_type,
    worker_models: decision.worker_models,
    selected_model: decision.worker_models[decision.selected_index],
    selected_index: decision.selected_index,
    arbiter_model: decision.arbiter_model,
    why_accepted: decision.why_accepted,
    rejection_reasons: decision.rejection_reasons || {},
    consensus_score: decision.consensus_score,
    worker_confidences: decision.worker_proposals?.map(p => p?.confidence || 0) || []
  }

  const learningDir = `${'/home/sfloess'}/.claude/learning`
  const learningFile = `${learningDir}/decisions.jsonl`

  try {
    await agent(`Store learning entry.

mkdir -p "${learningDir}"
echo '${JSON.stringify(learningEntry).replace(/'/g, "'\\''")}' >> "${learningFile}"

echo "Captured learning entry"`, {
      label: 'Capture Learning'
    })
  } catch (error) {
    // Non-critical - don't fail workflow if learning capture fails
    log(`⚠️  Learning capture failed (non-critical): ${error.message}`)
  }

  return learningEntry
}

async function getWorkerFeedback(context) {
  const learningFile = `${'/home/sfloess'}/.claude/learning/decisions.jsonl`

  try {
    const result = await agent(`Query learning database for worker feedback.

Check if file exists and read it:
if [ -f "${learningFile}" ]; then
  # Count how often this model was selected for this task type
  grep '"workflow":"${context.workflow}"' "${learningFile}" | \\
    grep '"task_type":"${context.task_type}"' | \\
    tail -50 | \\
    grep -c '"selected_model":"${context.worker_model}"' || echo "0"
else
  echo "0"
fi

Return the count and generate feedback if > 0.`, {
      label: 'Get Worker Feedback',
      schema: {
        type: 'object',
        properties: {
          selection_count: { type: 'number' },
          total_decisions: { type: 'number' },
          feedback: { type: 'string' }
        }
      }
    })

    if (result.selection_count > 0) {
      const percentage = Math.round((result.selection_count / (result.total_decisions || 1)) * 100)
      return `\n\n**Historical Performance:**\nYour model (${context.worker_model}) was selected ${result.selection_count}/${result.total_decisions} times (${percentage}%) for ${context.task_type} tasks. ${percentage > 50 ? 'Keep up the strong proposals!' : 'Consider more comprehensive approaches to increase selection rate.'}\n`
    }
  } catch (error) {
    // Non-critical - return empty feedback
  }

  return ''
}

async function getArbiterFeedback(context) {
  const learningFile = `${'/home/sfloess'}/.claude/learning/decisions.jsonl`

  try {
    const result = await agent(`Query learning database for arbiter feedback.

if [ -f "${learningFile}" ]; then
  # Get selection frequencies for each worker model
  echo "Selection patterns for ${context.task_type}:"
  ${context.worker_models.map(model => `
  echo -n "${model}: "
  grep '"workflow":"${context.workflow}"' "${learningFile}" | \\
    grep '"task_type":"${context.task_type}"' | \\
    tail -50 | \\
    grep -c '"selected_model":"${model}"' || echo "0"
  `).join('\n  ')}
else
  echo "No historical data"
fi

Return selection frequencies and generate feedback.`, {
      label: 'Get Arbiter Feedback',
      schema: {
        type: 'object',
        properties: {
          model_frequencies: { type: 'object' },
          feedback: { type: 'string' }
        }
      }
    })

    if (result.model_frequencies) {
      let feedback = `\n\n**Historical Selection Patterns:**\n`
      Object.entries(result.model_frequencies).forEach(([model, count]) => {
        feedback += `- ${model}: selected ${count} times\n`
      })
      feedback += `\nConsider proposal quality over historical frequency, but use patterns to inform your decision.\n`
      return feedback
    }
  } catch (error) {
    // Non-critical
  }

  return ''
}

// Detect platform
log('📍 Detecting platform...')
const platformDetect = await detectPlatform()
const { platform, isGitHub, isGitLab } = platformDetect

log(`✅ Platform: ${platform}`)

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
log(`   Build Command: ${appDetection.build_command || 'none'}`)

// PHASE 2: Build Application
phase('Build Application')

// Skip build for libraries (no build needed) or if no build command
if (appDetection.app_type === 'library' || !appDetection.build_command || appDetection.build_command === 'none') {
  log('ℹ️  Skipping build phase (library or no build command)')
} else {
  log(`🔨 Building application with: ${appDetection.build_command}`)

  const buildResult = await agent(`Build the application to prepare for testing.

Execute build command: ${appDetection.build_command}

Application context:
- Type: ${appDetection.app_type}
- Framework: ${appDetection.framework || 'unknown'}
- Build command: ${appDetection.build_command}

Execute the build and report:
1. Did it succeed? (exit code 0)
2. Build time (approximate)
3. Any warnings or errors
4. Output artifacts (if applicable)

If build fails:
- Capture the full error message
- Identify the root cause
- Suggest fixes

Return structured build result.`, {
    label: 'Build App',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['success', 'failure', 'warning'] },
        build_time_seconds: { type: 'number' },
        errors: { type: 'array', items: { type: 'string' } },
        warnings: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array', items: { type: 'string' } },
        root_cause: { type: 'string' },
        suggested_fixes: { type: 'array', items: { type: 'string' } }
      },
      required: ['status']
    }
  })

  if (buildResult.status === 'failure') {
    log(`❌ Build failed!`)
    log(`   Root cause: ${buildResult.root_cause || 'Unknown'}`)
    if (buildResult.errors && buildResult.errors.length > 0) {
      log(`   Errors:`)
      buildResult.errors.slice(0, 3).forEach(err => log(`     - ${err}`))
    }
    if (buildResult.suggested_fixes && buildResult.suggested_fixes.length > 0) {
      log(`   Suggested fixes:`)
      buildResult.suggested_fixes.forEach(fix => log(`     - ${fix}`))
    }

    // Stop testing if build fails
    return {
      status: 'build_failed',
      app_type: appDetection.app_type,
      build_command: appDetection.build_command,
      build_result: buildResult,
      message: 'Cannot run tests - build failed. Fix build errors first.'
    }
  }

  log(`✅ Build successful in ${buildResult.build_time_seconds || 'unknown'}s`)
  if (buildResult.warnings && buildResult.warnings.length > 0) {
    log(`   ⚠️  ${buildResult.warnings.length} warnings`)
  }
}

// PHASE 3: Fetch Open Issues
phase('Fetch Open Issues')

log(`📋 Fetching open issues to validate...`)

const issuesList = await fetchOpenIssues(platform, MAX_ISSUES_TO_TEST)

log(`✅ Found ${issuesList.length} open issues to validate`)

// Wrap in same structure for compatibility
const openIssues = { issues: issuesList }

// PHASE 4: Generate Test Plans
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

// Get learning feedback for workers
log('📚 Fetching historical learning data...')
const workerFeedbacks = await Promise.all(
  availableModels.map(model =>
    getWorkerFeedback({ workflow: 'code-test', task_type: 'test_plan', worker_model: model })
  )
)

log(`🔄 Generating test plans in parallel from ${availableModels.length} models (${availableModels.join(', ')})...`)

const testPlans = await parallel(
  availableModels.map((model, idx) =>
    () => agent(testPlanPrompt + (workerFeedbacks[idx] || ''), {
      label: `${model} Plan`,
      schema: testPlanSchema,
      model
    })
  )
)

const validPlans = testPlans.filter(Boolean)

if (validPlans.length === 0) {
  log('❌ No valid test plans generated')
  return { status: 'error', message: 'Failed to generate test plans' }
}

log(`✅ Generated ${validPlans.length} test plans`)

// PHASE 5: Select Best Test Plan
phase('Select Best')

// Get arbiter feedback from learning
log('📚 Getting arbiter feedback from past decisions...')
const arbiterFeedback = await getArbiterFeedback({
  workflow: 'code-test',
  task_type: 'test_plan',
  worker_models: availableModels
})

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
- **rejection_reasons** - Object mapping model names to why they were rejected
- **consensus_score** - Overall confidence (0-100)` + arbiterFeedback

const decision = await agent(arbiterPrompt, {
  label: `${arbiterModel} Arbiter`,
  model: arbiterModel,
  schema: {
    type: 'object',
    properties: {
      selected_index: { type: 'number', minimum: 0, maximum: validPlans.length - 1 },
      reasoning: { type: 'string' },
      rejection_reasons: { type: 'object' },
      consensus_score: { type: 'number', minimum: 0, maximum: 100 }
    },
    required: ['selected_index', 'reasoning']
  }
})

// Capture this decision for learning
log('📚 Capturing decision for future learning...')
await captureDecision({
  workflow: 'code-test',
  task_type: 'test_plan',
  worker_models: availableModels,
  worker_proposals: validPlans,
  arbiter_model: arbiterModel,
  selected_index: decision.selected_index,
  why_accepted: decision.reasoning,
  rejection_reasons: decision.rejection_reasons || {},
  consensus_score: decision.consensus_score || 0
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

// PHASE 6: Execute Tests
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

// PHASE 7: Validate Open Issues
phase('Validate Issues')

const issuesToValidate = (openIssues.issues || []).slice(0, MAX_ISSUES_TO_TEST)
log(`🔍 Validating ${issuesToValidate.length} open issues...`)

// Calculate optimal chunk size (estimate 15 seconds per issue validation)
const issueChunkSize = calculateOptimalChunkSize(issuesToValidate.length, 15, 120)
const issueChunks = chunkArray(issuesToValidate, issueChunkSize)

log(`📦 Processing in ${issueChunks.length} chunks of ~${issueChunkSize} issues each`)

const issueValidations = []

for (const [chunkIndex, chunk] of issueChunks.entries()) {
  log(`📝 Chunk ${chunkIndex + 1}/${issueChunks.length}: Validating ${chunk.length} issues...`)

  const chunkValidations = await pipeline(
    chunk,

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

  issueValidations.push(...chunkValidations.filter(Boolean))

  // Log chunk progress
  const reproduced = chunkValidations.filter(v => v?.is_reproducible).length
  log(`  ✅ Chunk ${chunkIndex + 1} complete: ${reproduced}/${chunk.length} reproduced`)
}

const issuesReproduced = issueValidations.filter(v => v.is_reproducible).length
const issuesFixed = issueValidations.filter(v => !v.still_exists).length

log(`✅ All chunks complete: ${issuesReproduced} reproduced, ${issuesFixed} appear fixed`)
log(`   Total validated: ${issueValidations.length} issues`)

// PHASE 8: Multi-Model Review
phase('Multi-Model Review')

log('⚖️ Consolidating findings with arbiter consensus...')

// Cluster rejection reasons if we have learning data
if (decision.rejection_reasons && Object.keys(decision.rejection_reasons).length > 0) {
  log('🔍 Clustering rejection patterns for insights...')

  const rejections = Object.entries(decision.rejection_reasons).map(([model, reason]) => ({
    model,
    reason,
    count: 1
  }))

  const clusters = await clusterRejectionReasons(rejections)

  if (clusters.clusters && clusters.clusters.length > 0) {
    log(`📊 Identified ${clusters.clusters.length} rejection pattern clusters:`)
    clusters.clusters.forEach(c => {
      log(`   - ${c.name}: ${c.total_count} instances`)
    })

    if (clusters.insights && clusters.insights.length > 0) {
      log(`💡 Insights: ${clusters.insights.join(', ')}`)
    }
  }
}

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

// PHASE 8.5: Impact Analysis
phase('Impact Analysis')

log('🎯 Analyzing impact of test failures...')

// Analyze impact of each failure
for (const finding of allFindings) {
  // Calculate impact score based on severity and type
  finding.impact_score = finding.severity === 'critical' ? 100 :
                        finding.severity === 'high' ? 75 :
                        finding.severity === 'medium' ? 50 : 25

  // Boost score for UI failures (user-facing)
  if (finding.type?.includes('ui') || finding.type?.includes('UI')) {
    finding.impact_score += 15
  }

  // Boost score for reproduced existing issues (confirmed bugs)
  if (finding.type === 'reproduced_issue') {
    finding.impact_score += 10
  }

  // Simple risk assessment
  finding.risk_level = finding.impact_score >= 90 ? 'critical' :
                       finding.impact_score >= 70 ? 'high' :
                       finding.impact_score >= 40 ? 'medium' : 'low'
}

// Sort by impact score (highest first)
allFindings.sort((a, b) => (b.impact_score || 0) - (a.impact_score || 0))

log(`✅ Impact analysis complete`)
log(`   Highest impact: ${allFindings[0]?.description?.slice(0, 50)} (score: ${allFindings[0]?.impact_score || 0})`)

// PHASE 8.75: User Confirmation (if not autonomous)
phase('User Confirmation')

let approvedFindings = allFindings

if (!AUTONOMOUS && allFindings.length > 0) {
  log('')
  log('═'.repeat(60))
  log('📋 TEST FAILURES SUMMARY')
  log('═'.repeat(60))
  log(`Total failures: ${allFindings.length}`)
  log('')

  // Group by severity
  const bySeverity = {
    critical: allFindings.filter(f => f.severity === 'critical').length,
    high: allFindings.filter(f => f.severity === 'high').length,
    medium: allFindings.filter(f => f.severity === 'medium').length,
    low: allFindings.filter(f => f.severity === 'low').length
  }

  // Group by type
  const byType = {
    reproduced: allFindings.filter(f => f.type === 'reproduced_issue').length,
    new_failures: allFindings.length - allFindings.filter(f => f.type === 'reproduced_issue').length
  }

  log(`By Severity:`)
  log(`  🚨 Critical: ${bySeverity.critical}`)
  log(`  ⚠️  High: ${bySeverity.high}`)
  log(`  📋 Medium: ${bySeverity.medium}`)
  log(`  ℹ️  Low: ${bySeverity.low}`)
  log('')
  log(`By Type:`)
  log(`  ✅ Reproduced existing issues: ${byType.reproduced}`)
  log(`  🆕 New test failures: ${byType.new_failures}`)
  log('')

  // Show top 5 failures
  log(`Top Failures (by impact):`)
  allFindings.slice(0, 5).forEach((f, idx) => {
    const icon = f.severity === 'critical' ? '🚨' :
                 f.severity === 'high' ? '⚠️' :
                 f.severity === 'medium' ? '📋' : 'ℹ️'
    const typeLabel = f.type === 'reproduced_issue' ? '[REPRODUCED]' : '[NEW]'
    log(`${icon} ${idx + 1}. ${typeLabel} ${f.description?.slice(0, 50)}...`)
    log(`   Impact: ${f.impact_score}/100, Confidence: ${f.confidence}%`)
  })
  log('═'.repeat(60))
  log('')

  // ASK USER: Create issues for these failures?
  const userDecision = await agent(`Review test failures and decide which to report as issues.

Found ${allFindings.length} test failures:
- Critical: ${bySeverity.critical}
- High: ${bySeverity.high}
- Medium: ${bySeverity.medium}
- Low: ${bySeverity.low}

Types:
- Reproduced existing issues: ${byType.reproduced}
- New test failures: ${byType.new_failures}

Should we create/update issues for these failures?

Options:
- ALL: Create issues for all failures
- HIGH_ONLY: Create issues only for critical and high severity
- CRITICAL_ONLY: Create issues only for critical severity
- REPRODUCED_ONLY: Only update existing issues that were reproduced
- NONE: Don't create any issues

Return your decision.`, {
    label: 'User Decision',
    schema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['ALL', 'HIGH_ONLY', 'CRITICAL_ONLY', 'REPRODUCED_ONLY', 'NONE']
        },
        reasoning: { type: 'string' }
      },
      required: ['action']
    }
  })

  log(`\n👤 User Decision: ${userDecision.action}`)
  if (userDecision.reasoning) {
    log(`   Reasoning: ${userDecision.reasoning}`)
  }

  // Filter findings based on user decision
  if (userDecision.action === 'NONE') {
    approvedFindings = []
    log(`ℹ️  Skipping issue creation (user chose NONE)`)
  } else if (userDecision.action === 'CRITICAL_ONLY') {
    approvedFindings = allFindings.filter(f => f.severity === 'critical')
    log(`ℹ️  Creating issues for ${approvedFindings.length} critical failures only`)
  } else if (userDecision.action === 'HIGH_ONLY') {
    approvedFindings = allFindings.filter(f => f.severity === 'critical' || f.severity === 'high')
    log(`ℹ️  Creating issues for ${approvedFindings.length} critical/high failures only`)
  } else if (userDecision.action === 'REPRODUCED_ONLY') {
    approvedFindings = allFindings.filter(f => f.type === 'reproduced_issue')
    log(`ℹ️  Updating ${approvedFindings.length} reproduced existing issues only`)
  } else {
    log(`ℹ️  Creating/updating issues for all ${approvedFindings.length} failures`)
  }
}

// PHASE 9: Create Issues (for approved findings)
phase('Create Issues')

if (args?.['create-issues'] !== false && approvedFindings.length > 0) {
  log(`📝 Creating/updating issues for ${approvedFindings.length} findings...`)

  const reportedIssues = await pipeline(
    approvedFindings, // Use approved findings (filtered by user decision)

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

        return commentOnIssue(platform, finding.issue_number, commentBody).then(() => ({
          issue_number: finding.issue_number
        }))
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

        const labels = ['bug', 'test-failure']
        if (finding.severity) labels.push(finding.severity)

        return createIssue(platform, issueTitle, issueBody, labels)
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
