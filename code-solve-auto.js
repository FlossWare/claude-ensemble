export const meta = {
  name: 'code-solve-auto',
  description: 'Autonomous issue solver - auto-resolves all open issues with impact analysis',
  whenToUse: 'When you want fully automated issue resolution without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Discover Issues', detail: 'Find open issues needing resolution' },
    { title: 'Fetch Issue', detail: 'Get issue details' },
    { title: 'Impact Analysis', detail: 'Analyze impact before solving' },
    { title: 'Multi-Model Solutions', detail: 'AIs propose fixes', model: 'opus' },
    { title: 'Arbiter Decision', detail: 'Select best solution' },
    { title: 'Apply Fix', detail: 'Apply in isolated worktree' },
    { title: 'Verify Fix', detail: 'Ensure fix works' },
    { title: 'Auto-Decision', detail: 'Commit or discard' },
  ],
}

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
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
    await fetch(`${FLEET_DISPATCHER}/complete`, {
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
    const result = await _agent(prompt, opts);
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

async function syncWithRemote(agent, options = {}) {
  const { branch = 'main' } = options

  const result = await _agent(`Sync with remote repository.

Execute these commands:
git fetch origin
git rebase origin/${branch}

Return the status of the sync operation.
If there are conflicts, list them.`, {
    label: 'Sync with Remote',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['success', 'conflicts', 'failed', 'up_to_date'] },
        message: { type: 'string' },
        conflicts: { type: 'array', items: { type: 'string' } },
        branch: { type: 'string' },
      },
      required: ['status'],
    }
  })

  return result
}

async function fetchIssue(agent, platform, issueNumber) {
  const cli = platform.cli

  const result = await _agent(`Fetch issue details.

Platform: ${platform.platform}
Issue Number: ${issueNumber}

Execute:
${cli} issue view ${issueNumber} --json title,body,labels,state,author,url

Parse and return the issue details.`, {
    label: `Fetch Issue #${issueNumber}`,
    schema: {
      type: 'object',
      properties: {
        number: { type: 'number' },
        title: { type: 'string' },
        body: { type: 'string' },
        state: { type: 'string' },
        author: { type: 'string' },
        url: { type: 'string' },
        labels: { type: 'array', items: { type: 'string' } },
      },
      required: ['number', 'title', 'body', 'state'],
    }
  })

  return result
}

async function analyzeImpactBeforeFix(agent, issueTitle, issueBody) {
  const result = await _agent(`Analyze impact of fixing this issue BEFORE implementing.

Issue: ${issueTitle}
Description: ${issueBody}

Predict:
1. Which files will likely be modified?
2. Will this require API changes or breaking changes?
3. What's the risk level of this fix?
4. Are there dependencies on this code?
5. What tests will be needed?

Return impact prediction.`, {
    label: 'Pre-Fix Impact Analysis',
    schema: {
      type: 'object',
      properties: {
        likely_files: { type: 'array', items: { type: 'string' } },
        breaking_changes_likely: { type: 'boolean' },
        risk_level: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
        dependencies_affected: { type: 'number' },
        tests_needed: { type: 'array', items: { type: 'string' } },
        concerns: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
}

async function multiModelSolve(agent, prompt, workers) {
  log(`🤖 ${workers.length} models proposing solutions...`)

  const solutions = await Promise.all(workers.map(model =>
    agent(prompt, {
      label: `Solution (${model})`,
      model,
      phase: 'Multi-Model Solutions',
      schema: {
        type: 'object',
        properties: {
          approach: { type: 'string' },
          files_to_change: { type: 'array', items: { type: 'string' } },
          changes_summary: { type: 'string' },
          breaking_changes: { type: 'boolean' },
          test_plan: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 100 },
          estimated_risk: { type: 'string', enum: ['low', 'medium', 'high'] }
        }
      }
    }).catch(err => {
      log(`⚠️ ${model} failed: ${err.message}`)
      return null
    })
  ))

  return solutions.filter(Boolean)
}

async function arbiterSelectBest(agent, issueTitle, solutions, arbiterModel) {
  const solutionSummary = solutions.map((s, idx) =>
    `Solution ${idx + 1}: ${s.approach} (confidence: ${s.confidence}%, risk: ${s.estimated_risk}, breaking: ${s.breaking_changes})`
  ).join('\n')

  const result = await _agent(`Select the best solution for: "${issueTitle}"

Solutions proposed:
${solutionSummary}

Choose the best solution considering:
- Confidence level
- Risk level
- Breaking changes (avoid if possible)
- Code quality
- Test coverage

Return your decision.`, {
    label: 'Arbiter Decision',
    model: arbiterModel || 'fable',
    phase: 'Arbiter Decision',
    schema: {
      type: 'object',
      properties: {
        selected_index: { type: 'number' },
        reasoning: { type: 'string' },
        concerns: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'number' }
      }
    }
  })

  return result
}

async function applyFix(agent, issue, solution) {
  const result = await _agent(`Apply fix for issue #${issue.number}: "${issue.title}"

Approach: ${solution.approach}
Files to change: ${solution.files_to_change.join(', ')}
Changes: ${solution.changes_summary}

Implement the fix according to the plan.
Return list of files modified and summary of changes.`, {
    label: `Apply Fix #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        files_modified: { type: 'array', items: { type: 'string' } },
        changes_applied: { type: 'string' },
        success: { type: 'boolean' }
      }
    }
  })

  return result
}

async function verifyFix(agent, issue, fixResult) {
  const result = await _agent(`Verify that the fix for issue #${issue.number} actually works.

Files modified: ${fixResult.files_modified.join(', ')}
Changes: ${fixResult.changes_applied}

Verify:
1. Does the code compile/run?
2. Are there any obvious errors?
3. Does it address the issue?
4. Are there side effects?

Return verification results.`, {
    label: `Verify Fix #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        compiles: { type: 'boolean' },
        addresses_issue: { type: 'boolean' },
        side_effects: { type: 'array', items: { type: 'string' } },
        verification_passed: { type: 'boolean' },
        issues_found: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
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

  // AUTO-COMMIT CRITERIA
  autoCommit: {
    minConfidence: 85,                // 85%+ confidence required
    maxRiskLevel: 'medium',           // Max medium risk
    noBreakingChanges: true,          // No breaking changes allowed
    mustCompile: true,                // Must compile/run
    mustAddressIssue: true,           // Must fix the actual issue
  },

  // AUTO-REJECT CRITERIA
  autoReject: {
    hasBreakingChanges: true,         // Reject if breaking
    highRisk: true,                   // Reject if high risk
    lowConfidence: 70,                // Reject if confidence < 70
    doesNotCompile: true,             // Reject if doesn't compile
    doesNotAddressIssue: true,        // Reject if doesn't fix issue
  },

  maxIssuesPerRun: 10,                // Max 10 issues per run
}

const maxIssues = args?.max || args?.['--max'] || CONFIG.maxIssuesPerRun
const minConfidence = args?.confidence || args?.['--confidence'] || CONFIG.autoCommit.minConfidence

log('')
log('═'.repeat(60))
log('🤖 AUTONOMOUS ISSUE SOLVER')
log('═'.repeat(60))
log(`Workers: ${CONFIG.workers.join(', ')}`)
log(`Arbiter: ${CONFIG.arbiterModel}`)
log(`Auto-Commit: Confidence ≥ ${minConfidence}%, No breaking changes`)
log(`Auto-Reject: Breaking changes, High risk, Doesn't compile`)
log(`Max Issues/run: ${maxIssues}`)
log('═'.repeat(60))
log('')

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// PHASE 1: Setup
phase('Setup')

log('🔧 Detecting platform...')
const platform = await detectPlatform(agent)
log(`✅ Platform: ${platform.platform} (${platform.cli})`)

log('🔄 Syncing with remote...')
const syncResult = await syncWithRemote(agent)
if (syncResult.status === 'conflicts') {
  log(`❌ Conflicts detected - cannot proceed`)
  return { status: 'conflicts', message: 'Resolve conflicts first' }
}
log(`✅ Synced`)

// PHASE 2: Discover Issues
phase('Discover Issues')

log('📋 Finding open issues...')

const issueListCmd = platform.platform === 'gitlab'
  ? `glab issue list --state opened --per-page 100 --json number,title,labels`
  : `gh issue list --state open --json number,title,labels --limit 100`

const issueListResult = await _agent(`List all open issues.

Execute:
${issueListCmd}

Return list of open issues.`, {
  label: 'List Issues',
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
            labels: { type: 'array' }
          }
        }
      },
      total: { type: 'number' }
    }
  }
})

const openIssues = issueListResult.issues || []

log(`📊 Found ${openIssues.length} open issues`)

if (openIssues.length === 0) {
  log('✅ No open issues - all done!')
  return {
    status: 'complete',
    message: 'No open issues',
    issues_resolved: 0
  }
}

const issuesToSolve = openIssues.slice(0, maxIssues)
log(`🎯 Solving ${issuesToSolve.length} issues this run`)
log('')

// ============================================================================
// SOLVE SINGLE ISSUE IN ISOLATED WORKTREE
// ============================================================================

const solveSingleIssue = async (issueRef, platform, minConfidence) => {
  const issueNum = issueRef.number
  const worktreePath = `.claude/worktrees/issue-${issueNum}`
  const worktreeBranch = `fix/issue-${issueNum}`

  log('')
  log('═'.repeat(60))
  log(`🐛 Issue #${issueNum} (isolated worktree)`)
  log('═'.repeat(60))

  // Create isolated worktree
  log(`📁 Creating worktree: ${worktreePath}`)

  try {
    await _agent(`Create git worktree for issue #${issueNum}.

Execute:
mkdir -p .claude/worktrees
git worktree add ${worktreePath} -b ${worktreeBranch} 2>/dev/null || git worktree add ${worktreePath} ${worktreeBranch}

Create isolated worktree.`, {
      label: `Create Worktree #${issueNum}`
    })

    log(`✅ Worktree created at ${worktreePath}`)

    // PHASE 3: Fetch Issue
    phase('Fetch Issue')

    log(`📥 Fetching issue #${issueNum}...`)
    const issue = await fetchIssue(agent, platform, issueNum)
    log(`✅ "${issue.title}"`)

  // PHASE 4: Impact Analysis
  phase('Impact Analysis')

  log('🎯 Analyzing impact before solving...')
  const preImpact = await analyzeImpactBeforeFix(agent, issue.title, issue.body || issue.description || '')

  log(`✅ Predicted impact:`)
  log(`   Risk: ${preImpact.risk_level}`)
  log(`   Breaking changes likely: ${preImpact.breaking_changes_likely ? 'YES' : 'NO'}`)
  log(`   Files affected: ~${preImpact.likely_files?.length || 0}`)

  // PHASE 5: Multi-Model Solutions
  phase('Multi-Model Solutions')

  const solvePrompt = `Propose a solution for this issue:

**Issue #${issueNum}**: ${issue.title}
**Description**: ${issue.body || issue.description || 'No description'}

**Predicted Impact**:
- Risk: ${preImpact.risk_level}
- Likely files: ${preImpact.likely_files?.join(', ') || 'unknown'}
- Breaking changes likely: ${preImpact.breaking_changes_likely}

Propose:
1. Your approach to fix this
2. Which files to change
3. Summary of changes
4. Whether it introduces breaking changes
5. Test plan
6. Your confidence (0-100)
7. Estimated risk (low/medium/high)

Be specific and actionable.`

  const solutions = await multiModelSolve(agent, solvePrompt, CONFIG.workers)

  log(`✅ ${solutions.length} solutions proposed`)

  // PHASE 6: Arbiter Decision
  phase('Arbiter Decision')

  log('⚖️ Arbiter selecting best solution...')
  const decision = await arbiterSelectBest(agent, issue.title, solutions, CONFIG.arbiterModel)

  const selectedSolution = solutions[decision.selected_index]

  log(`✅ Selected solution ${decision.selected_index + 1}`)
  log(`   Approach: ${selectedSolution.approach}`)
  log(`   Confidence: ${decision.confidence}%`)

  // PHASE 7: Apply Fix (in worktree)
  phase('Apply Fix')

  log('🔧 Applying fix in worktree...')
  const fixResult = await _agent(`Apply fix for issue #${issueNum} in worktree.

Execute all commands in worktree:
cd ${worktreePath} && <your commands here>

Approach: ${selectedSolution.approach}
Files to change: ${selectedSolution.files_to_change.join(', ')}
Changes: ${selectedSolution.changes_summary}

Implement the fix. Return files modified and summary.`, {
    label: `Apply Fix #${issueNum}`,
    schema: {
      type: 'object',
      properties: {
        files_modified: { type: 'array', items: { type: 'string' } },
        changes_applied: { type: 'string' },
        success: { type: 'boolean' }
      }
    }
  })

  log(`✅ Fix applied`)
  log(`   Files modified: ${fixResult.files_modified?.length || 0}`)

  // PHASE 8: Verify Fix (in worktree)
  phase('Verify Fix')

  log('🧪 Verifying fix in worktree...')
  const verification = await _agent(`Verify fix for issue #${issueNum} in worktree.

Execute all commands in worktree:
cd ${worktreePath} && <your commands here>

Files modified: ${fixResult.files_modified?.join(', ')}
Changes: ${fixResult.changes_applied}

Verify: compiles, addresses issue, no side effects.`, {
    label: `Verify Fix #${issueNum}`,
    schema: {
      type: 'object',
      properties: {
        compiles: { type: 'boolean' },
        addresses_issue: { type: 'boolean' },
        side_effects: { type: 'array', items: { type: 'string' } },
        verification_passed: { type: 'boolean' },
        issues_found: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  log(`✅ Verification ${verification.verification_passed ? 'PASSED' : 'FAILED'}`)
  log(`   Compiles: ${verification.compiles}`)
  log(`   Addresses issue: ${verification.addresses_issue}`)
  log(`   Side effects: ${verification.side_effects?.length || 0}`)

  // PHASE 9: Auto-Decision
  phase('Auto-Decision')

  log('🤖 Determining auto-action...')

  let autoAction = 'DISCARD' // Default: discard if uncertain
  let reasoning = ''

  // AUTO-REJECT criteria
  if (selectedSolution.breaking_changes) {
    autoAction = 'DISCARD'
    reasoning = `Breaking changes introduced`
  } else if (selectedSolution.estimated_risk === 'high') {
    autoAction = 'DISCARD'
    reasoning = `High risk solution`
  } else if (!verification.compiles) {
    autoAction = 'DISCARD'
    reasoning = `Fix doesn't compile`
  } else if (!verification.addresses_issue) {
    autoAction = 'DISCARD'
    reasoning = `Fix doesn't address the issue`
  } else if (decision.confidence < CONFIG.autoReject.lowConfidence) {
    autoAction = 'DISCARD'
    reasoning = `Low confidence (${decision.confidence}%)`
  }
  // AUTO-COMMIT criteria
  else if (
    decision.confidence >= minConfidence &&
    selectedSolution.estimated_risk !== 'high' &&
    !selectedSolution.breaking_changes &&
    verification.compiles &&
    verification.addresses_issue &&
    verification.verification_passed
  ) {
    autoAction = 'COMMIT'
    reasoning = `High confidence (${decision.confidence}%), ${selectedSolution.estimated_risk} risk, verified`
  }

  log(`🎯 Auto-Action: ${autoAction}`)
  log(`   Reasoning: ${reasoning}`)

  if (autoAction === 'COMMIT') {
    log('📝 Committing fix in worktree...')

    const commitCmd = `cd ${worktreePath} && git add ${fixResult.files_modified.join(' ')} && git commit -m "Fix #${issueNum}: ${issue.title}\n\n${selectedSolution.changes_summary}\n\nAuto-fixed by code-solve-auto\nConfidence: ${decision.confidence}%\nRisk: ${selectedSolution.estimated_risk}"`

    await _agent(`Commit the fix in worktree.

Execute:
${commitCmd}

Commit the changes.`, {
      label: `Commit Fix #${issueNum}`
    })

    log(`✅ Fix committed in worktree`)

    // Squash merge worktree branch to main
    log('📤 Squash merging to main...')

    const squashMsg = `fix: resolve issue #${issueNum} - ${issue.title}

${selectedSolution.approach}

Auto-fixed by code-solve-auto
Confidence: ${decision.confidence}%
Risk: ${selectedSolution.estimated_risk}

Fixes #${issueNum}`

    await _agent(`Squash merge worktree branch to main.

Execute:
git checkout main
git merge --squash ${worktreeBranch}
git commit -m "${squashMsg.replace(/"/g, '\\"')}"
git push origin main`, {
      label: 'Squash Merge'
    })

    log(`✅ Squash merged to main`)

    // Close issue
    const closeCmd = platform.platform === 'gitlab'
      ? `glab issue close ${issueNum} --comment "✅ Auto-resolved by code-solve-auto\n\nSolution: ${selectedSolution.approach}\nConfidence: ${decision.confidence}%\nRisk: ${selectedSolution.estimated_risk}\nFiles modified: ${fixResult.files_modified.join(', ')}"`
      : `gh issue close ${issueNum} --comment "✅ Auto-resolved by code-solve-auto\n\nSolution: ${selectedSolution.approach}\nConfidence: ${decision.confidence}%\nRisk: ${selectedSolution.estimated_risk}\nFiles modified: ${fixResult.files_modified.join(', ')}"`

    await _agent(`Close issue #${issueNum}.

Execute:
${closeCmd}

Close the issue with resolution comment.`, {
      label: `Close Issue #${issueNum}`
    })

    log(`✅ Issue #${issueNum} closed`)

  } else {
    log('🗑️  Discarding fix (no cleanup needed - worktree will be removed)...')

    // Comment on issue why we couldn't auto-fix
    const commentCmd = platform.platform === 'gitlab'
      ? `glab issue comment ${issueNum} --message "⚠️ Auto-fix attempted but discarded\n\nReason: ${reasoning}\nProposed solution: ${selectedSolution.approach}\nConfidence: ${decision.confidence}%\n\nManual intervention needed."`
      : `gh issue comment ${issueNum} --body "⚠️ Auto-fix attempted but discarded\n\nReason: ${reasoning}\nProposed solution: ${selectedSolution.approach}\nConfidence: ${decision.confidence}%\n\nManual intervention needed."`

    await _agent(`Comment on issue #${issueNum}.

Execute:
${commentCmd}

Add comment explaining why auto-fix was discarded.`, {
      label: `Comment Issue #${issueNum}`
    })

    log(`✅ Comment added to issue`)
  }

  return {
    issue_number: issueNum,
    title: issue.title,
    action: autoAction,
    reasoning,
    confidence: decision.confidence,
    risk: selectedSolution.estimated_risk,
    files_modified: fixResult.files_modified?.length || 0,
    resolved: autoAction === 'COMMIT'
  }

  } finally {
    // Clean up worktree
    log(`🧹 Cleaning up worktree ${worktreePath}...`)

    await _agent(`Remove worktree.

Execute:
git worktree remove ${worktreePath} --force 2>/dev/null || rm -rf ${worktreePath}
git branch -D ${worktreeBranch} 2>/dev/null || true

Remove the isolated worktree and branch.`, {
      label: `Cleanup Worktree #${issueNum}`
    })

    log(`✅ Worktree cleaned up`)
  }
}

// ============================================================================
// SOLVE ALL ISSUES IN PARALLEL (each in isolated worktree)
// ============================================================================

log('')
log('🚀 Solving issues in parallel using worktree isolation...')
log('')

const results = await parallel(issuesToSolve.map(issueRef => () =>
  solveSingleIssue(issueRef, platform, minConfidence)
))

const validResults = results.filter(Boolean)

// ============================================================================
// SUMMARY
// ============================================================================

log('')
log('═'.repeat(60))
log('📊 AUTONOMOUS SOLVE SUMMARY')
log('═'.repeat(60))
log(`Total issues processed: ${validResults.length}/${issuesToSolve.length}`)
log(`Auto-resolved: ${validResults.filter(r => r.resolved).length}`)
log(`Discarded: ${validResults.filter(r => !r.resolved).length}`)
log(`Failed: ${results.length - validResults.length}`)
log('')

validResults.forEach(r => {
  const icon = r.resolved ? '✅' : '⚠️'
  log(`${icon} Issue #${r.issue_number}: ${r.title}`)
  log(`   Action: ${r.action}, Confidence: ${r.confidence}%, Risk: ${r.risk}`)
})

log('═'.repeat(60))
log('')

if (openIssues.length > maxIssues) {
  log(`ℹ️  ${openIssues.length - maxIssues} more issues remain - run again to continue`)
} else {
  log(`✅ All issues processed!`)
}

const result = {
  status: 'success',
  issues_processed: validResults.length,
  resolved: validResults.filter(r => r.resolved).length,
  discarded: validResults.filter(r => !r.resolved).length,
  failed: results.length - validResults.length,
  remaining: Math.max(0, openIssues.length - maxIssues),
  success_rate: validResults.length > 0 ? Math.round((validResults.filter(r => r.resolved).length / validResults.length) * 100) : 0,
  parallel_worktrees: true,
  results: validResults
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-solve',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
