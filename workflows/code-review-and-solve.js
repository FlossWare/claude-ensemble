// AUTONOMOUS WORKFLOW - Full Code Review + Auto-Solve
// Self-contained implementation without nested workflow() calls
// Uses pipeline with inline agent calls for issue solving

export const meta = {
  name: 'code-review-and-solve',
  description: 'Complete code quality loop: review finds issues, meta-review validates, solve fixes, verify (AUTONOMOUS)',
  phases: [
    { title: 'Code Review', detail: 'Find issues across commits, files, and security' },
    { title: 'Meta-Review', detail: 'Independent panel validates review findings before fixes' },
    { title: 'Create Issues', detail: 'Create GitHub/GitLab issues for validated findings' },
    { title: 'Wait', detail: 'Allow issues to be created' },
    { title: 'Code Solve', detail: 'Auto-resolve all found issues' },
    { title: 'Verify Fixes', detail: 'Check fixes didn\'t introduce new bugs' },
    { title: 'Summary', detail: 'Report on issues found, validated, fixed, and verified' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

log('🔄 CODE REVIEW + SOLVE WORKFLOW')
log('═'.repeat(80))

// ──────────────────────────────────────────────────────────────────────────────
// MODEL SELECTION: Two completely independent panels with ZERO overlap.
//
// Review panel  → strongest code-reasoning models (find bugs)
// Meta-review   → equally-strong but DIFFERENT models (adversarially validate)
// Solve/Verify  → Claude models via native agent() (need tool use for edits)
//
// Non-Claude models are called via executeRemoteLLMTask() inside each agent.
// Claude models use native agent() model parameter directly.
// ──────────────────────────────────────────────────────────────────────────────

// REVIEW PANEL: Strong code reasoning models
// These agents read code and find bugs — need top-tier reasoning
const REVIEW_MODELS = [
  { name: 'opus',           type: 'claude' },
  { name: 'sonnet',         type: 'claude' },
  { name: 'deepseek-chat',  type: 'fleet', provider: 'deepseek' },
  { name: 'qwen/qwen3-coder:free', type: 'fleet', provider: 'openrouter' },
]

// META-REVIEW PANEL: Equally strong, ZERO overlap with review panel
// These agents challenge findings — need equal or stronger reasoning to avoid
// rubber-stamping or incorrectly rejecting valid findings
const META_REVIEW_MODELS = [
  { name: 'fable',          type: 'claude' },
  { name: 'nousresearch/hermes-3-llama-3.1-405b:free', type: 'fleet', provider: 'openrouter' },
  { name: 'nvidia/nemotron-3-ultra-550b-a55b:free',    type: 'fleet', provider: 'openrouter' },
  { name: 'qwen/qwen3-next-80b-a3b-instruct:free',    type: 'fleet', provider: 'openrouter' },
]

// Arbiters: one per phase, all different
const REVIEW_ARBITER = 'opus'     // Strongest for synthesizing review findings
const META_REVIEW_ARBITER = 'sonnet'  // Different from review arbiter
const SOLVE_ARBITER = 'fable'     // Different from both
const VERIFY_ARBITER = 'haiku'    // Different from all above

const allFindings = []
const DAYS_BACK = args?.days || 30
const MAX_COMMITS = args?.maxCommits || 5
const MAX_FILES = args?.maxFiles || 10
const CONFIDENCE_THRESHOLD = 70

log('⚙️  Configuration:')
log(`   Review window: Last ${DAYS_BACK} days`)
log(`   Max commits: ${MAX_COMMITS}`)
log(`   Max files: ${MAX_FILES}`)
log(`   Confidence threshold: ${CONFIDENCE_THRESHOLD}%`)
log(`   Max issues to create: 20`)
log(`   Review panel: ${REVIEW_MODELS.map(m => m.name).join(', ')}`)
log(`   Meta-review panel: ${META_REVIEW_MODELS.map(m => m.name).join(', ')}`)
log(`   Arbiters: Review=${REVIEW_ARBITER}, MetaReview=${META_REVIEW_ARBITER}, Solve=${SOLVE_ARBITER}, Verify=${VERIFY_ARBITER}`)
log(`   Panel overlap: ZERO (review and meta-review use completely different models)`)
log('')

// PHASE 1: Code Review
phase('Code Review')

log('🔍 Running focused code review...')
log(`   Commits: last ${DAYS_BACK} days (max ${MAX_COMMITS})`)
log(`   Files: max ${MAX_FILES}`)
log(`   Confidence threshold: ${CONFIDENCE_THRESHOLD}%`)

// 1.1: Review Recent Commits
log('📅 Analyzing recent commits...')

const commitHistory = await _agent(`Get detailed commit history for the last ${DAYS_BACK} days.

Execute:
git log --since="${DAYS_BACK} days ago" --pretty=format:"%H|%an|%ad|%s" --date=short

Return structured data about each commit.`, {
  label: 'Fetch Commit History',
  schema: {
    type: 'object',
    properties: {
      commits: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            hash: { type: 'string' },
            author: { type: 'string' },
            date: { type: 'string' },
            message: { type: 'string' },
          }
        }
      },
      total_commits: { type: 'number' }
    },
    required: ['commits', 'total_commits']
  }
})

log(`✅ Found ${commitHistory.total_commits} commits`)

// Review each commit
const commitFindings = await pipeline(
  commitHistory.commits.slice(0, MAX_COMMITS),

  // Get diff
  (commit, idx) => {
    log(`📝 [${idx + 1}/${Math.min(MAX_COMMITS, commitHistory.total_commits)}] Getting diff for ${commit.hash.slice(0, 8)}: "${commit.message.slice(0, 60)}..."`)
    return _agent(`Get the full diff for commit ${commit.hash}.

Execute:
git show ${commit.hash} --stat
git diff ${commit.hash}^..${commit.hash}

Return the files changed and diff content.`, {
      label: `Diff: ${commit.hash.slice(0, 8)}`,
      schema: {
        type: 'object',
        properties: {
          files_changed: { type: 'array', items: { type: 'string' } },
          diff: { type: 'string' },
          commit_hash: { type: 'string' }
        }
      }
    })
  },

  // Review diff - multi-model consensus: all workers review independently
  (diffData, _, idx) => {
    log(`🔍 [${idx + 1}/${Math.min(MAX_COMMITS, commitHistory.total_commits)}] Multi-AI reviewing commit ${diffData.commit_hash.slice(0, 8)}...`)

    const reviewSchema = {
      type: 'object',
      properties: {
        issues: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
              category: { type: 'string' },
              description: { type: 'string' },
              file: { type: 'string' },
              line_hint: { type: 'string' },
              confidence: { type: 'number', minimum: 0, maximum: 100 }
            }
          }
        },
        commit_hash: { type: 'string' }
      }
    }

    const reviewPrompt = `Code review of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find issues:
- Security vulnerabilities
- Logic bugs
- Performance problems
- Code quality issues

Focus on critical and major issues only.`

    // Each review model gets its own agent — Claude models use native agent(),
    // fleet models delegate to executeRemoteLLMTask() via the agent's bash access
    return parallel(REVIEW_MODELS.map(m => {
      if (m.type === 'claude') {
        return () => agent(reviewPrompt, {
          label: `${m.name} Review: ${diffData.commit_hash.slice(0, 8)}`,
          model: m.name,
          schema: reviewSchema
        })
      } else {
        // Fleet model: agent calls executeRemoteLLMTask via orchestrator API
        return () => agent(`You are a code review proxy. Call the fleet LLM API to get a review from model "${m.name}".

Execute this command to get the review:
curl -s http://aio-01:5000/secrets/OPENROUTER_API_KEY | python3 -c "import json,sys; print(json.load(sys.stdin).get('value',''))" > /tmp/.api_key_tmp 2>/dev/null

Then call:
curl -s https://openrouter.ai/api/v1/chat/completions \\
  -H "Authorization: Bearer $(cat /tmp/.api_key_tmp)" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify({
    model: m.name,
    messages: [{ role: "user", content: reviewPrompt + "\n\nReturn your response as JSON with this structure: {\"issues\": [{\"severity\": \"critical|major|minor\", \"category\": \"string\", \"description\": \"string\", \"file\": \"string\", \"line_hint\": \"string\", \"confidence\": number}], \"commit_hash\": \"" + diffData.commit_hash + "\"}" }],
    max_tokens: 4096
  }).replace(/'/g, "'\\''")}'

Parse the response JSON from the API, extract the message content, and return the structured review.
Clean up: rm -f /tmp/.api_key_tmp`, {
          label: `${m.name.split('/').pop()} Review: ${diffData.commit_hash.slice(0, 8)}`,
          schema: reviewSchema
        })
      }
    })).then(reviews => {
      const allIssues = reviews.filter(Boolean).flatMap(r => r.issues || [])
      return {
        issues: allIssues,
        commit_hash: diffData.commit_hash
      }
    })
  }
)

// Collect commit findings
let commitIssueCount = 0
commitFindings.filter(Boolean).forEach(cf => {
  cf.issues?.forEach(issue => {
    if (issue.confidence >= CONFIDENCE_THRESHOLD) {
      commitIssueCount++
      allFindings.push({
        source: 'commit_review',
        commit_hash: cf.commit_hash,
        ...issue
      })
    }
  })
})

log(`✅ Commit review complete: ${commitIssueCount} issues found (${allFindings.length} total so far)`)
log(`   Breakdown: ${commitFindings.filter(Boolean).map(cf => `${cf.commit_hash?.slice(0, 8)}: ${cf.issues?.filter(i => i.confidence >= CONFIDENCE_THRESHOLD).length || 0}`).join(', ')}`)

// 1.2: Review Source Files
log('🔍 Scanning source files...')

const sourceFiles = await _agent(`Find source code files (exclude vendor, node_modules, tests).

Execute:
find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" -o -name "*.go" -o -name "*.rb" -o -name "*.sh" \\) | grep -v node_modules | grep -v vendor | grep -v ".git" | grep -v test | head -${MAX_FILES}

Return list of files.`, {
  label: 'Find Source Files',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } }
    }
  }
})

log(`✅ Found ${sourceFiles.files?.length || 0} files to review`)

// Review files
const fileFindings = await pipeline(
  (sourceFiles.files || []).slice(0, MAX_FILES),

  (filepath, idx) => {
    log(`🔍 [${idx + 1}/${Math.min(MAX_FILES, sourceFiles.files?.length || 0)}] Multi-AI reviewing file: ${filepath}`)

    const fileReviewSchema = {
      type: 'object',
      properties: {
        file: { type: 'string' },
        issues: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              severity: { type: 'string' },
              category: { type: 'string' },
              description: { type: 'string' },
              line_hint: { type: 'string' },
              confidence: { type: 'number' }
            }
          }
        }
      }
    }

    const fileReviewPrompt = `Security and logic review of ${filepath}

Find critical issues:
- Security vulnerabilities (SQL injection, XSS, secrets, auth issues)
- Logic bugs (null pointers, race conditions, edge cases)
- Critical performance issues

Focus on high-confidence findings only.`

    return parallel(REVIEW_MODELS.map(m => {
      if (m.type === 'claude') {
        return () => agent(fileReviewPrompt, {
          label: `${m.name}: ${filepath.split('/').pop()}`,
          model: m.name,
          schema: fileReviewSchema
        })
      } else {
        return () => agent(`You are a code review proxy. Call the fleet LLM API to get a security/logic review from model "${m.name}".

First read the file: cat ${filepath}

Then get the API key and call the model:
curl -s http://aio-01:5000/secrets/OPENROUTER_API_KEY | python3 -c "import json,sys; print(json.load(sys.stdin).get('value',''))" > /tmp/.api_key_tmp 2>/dev/null

curl -s https://openrouter.ai/api/v1/chat/completions \\
  -H "Authorization: Bearer $(cat /tmp/.api_key_tmp)" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify({
    model: m.name,
    messages: [{ role: "user", content: fileReviewPrompt + "\n\nReturn your response as JSON: {\"file\": \"" + filepath + "\", \"issues\": [{\"severity\": \"critical|major|minor\", \"category\": \"string\", \"description\": \"string\", \"line_hint\": \"string\", \"confidence\": number}]}" }],
    max_tokens: 4096
  }).replace(/'/g, "'\\''")}'

Parse the API response and return the structured review. Clean up: rm -f /tmp/.api_key_tmp`, {
          label: `${m.name.split('/').pop()}: ${filepath.split('/').pop()}`,
          schema: fileReviewSchema
        })
      }
    })).then(reviews => ({
      file: filepath,
      issues: reviews.filter(Boolean).flatMap(r => r.issues || [])
    }))
  }
)

// Collect file findings
let fileIssueCount = 0
fileFindings.filter(Boolean).forEach(ff => {
  ff.issues?.forEach(issue => {
    if (issue.confidence >= CONFIDENCE_THRESHOLD) {
      fileIssueCount++
      allFindings.push({
        source: 'file_review',
        file: ff.file,
        ...issue
      })
    }
  })
})

log(`✅ File review complete: ${fileIssueCount} issues found (${allFindings.length} total so far)`)
log(`   Top issues: ${fileFindings.filter(Boolean).sort((a, b) => (b.issues?.length || 0) - (a.issues?.length || 0)).slice(0, 3).map(ff => `${ff.file}: ${ff.issues?.filter(i => i.confidence >= CONFIDENCE_THRESHOLD).length || 0}`).join(', ')}`)

// Deduplicate findings
const uniqueFindings = allFindings.reduce((acc, finding) => {
  const key = `${finding.file}:${finding.description?.slice(0, 50)}`
  if (!acc[key]) {
    acc[key] = finding
  }
  return acc
}, {})

const dedupedFindings = Object.values(uniqueFindings)
const duplicatesRemoved = allFindings.length - dedupedFindings.length

log(`✅ Deduplicated: ${dedupedFindings.length} unique issues (removed ${duplicatesRemoved} duplicates)`)

// Show severity breakdown
const severityBreakdown = dedupedFindings.reduce((acc, f) => {
  acc[f.severity || 'unknown'] = (acc[f.severity || 'unknown'] || 0) + 1
  return acc
}, {})
log(`   Severity: critical=${severityBreakdown.critical || 0}, major=${severityBreakdown.major || 0}, minor=${severityBreakdown.minor || 0}`)

// PHASE 2: Meta-Review — independent panel validates review findings before any fixes
phase('Meta-Review')

log(`🔍 Meta-reviewing ${dedupedFindings.length} findings with independent panel...`)
log(`   Meta-review panel: ${META_REVIEW_MODELS.map(m => m.name).join(', ')}`)
log(`   Meta-review arbiter: ${META_REVIEW_ARBITER}`)
log(`   Purpose: Challenge each finding — reject false positives before wasting effort on fixes`)
log(`   ZERO overlap with review panel — prevents self-confirmation bias`)

const metaReviewSchema = {
  type: 'object',
  properties: {
    finding_index: { type: 'number' },
    verdict: { type: 'string', enum: ['confirmed', 'likely_valid', 'questionable', 'false_positive'] },
    reasoning: { type: 'string' },
    revised_severity: { type: 'string', enum: ['critical', 'major', 'minor', 'none'] }
  },
  required: ['finding_index', 'verdict', 'reasoning']
}

const metaReviewResults = await pipeline(
  dedupedFindings.map((f, idx) => ({ ...f, _idx: idx })),

  (finding) => {
    log(`🔎 [${finding._idx + 1}/${dedupedFindings.length}] Meta-reviewing: [${finding.severity}] ${finding.description?.slice(0, 60)}...`)

    const metaPrompt = `You are an ADVERSARIAL reviewer. Your job is to CHALLENGE this finding.
Try to REFUTE it. Default to skepticism — only confirm if you cannot find a reason to reject.

**Finding under review:**
- Severity: ${finding.severity}
- Category: ${finding.category}
- File: ${finding.file}
- Description: ${finding.description}
- Line hint: ${finding.line_hint || 'N/A'}
- Source: ${finding.source}

**Your task:**
1. Read the actual file/code mentioned
2. Determine if this finding is REAL or a false positive
3. Check: Is the issue actually present in the code? Could it be a misunderstanding?
4. Consider: Does the framework/language handle this automatically?
5. Verdict: confirmed (definitely real), likely_valid (probably real), questionable (uncertain), false_positive (not a real issue)

Be HARSH. Better to reject a valid finding than to waste effort fixing a non-issue.`

    return parallel(META_REVIEW_MODELS.map(m => {
      if (m.type === 'claude') {
        return () => agent(metaPrompt, {
          label: `${m.name} meta-review #${finding._idx}`,
          model: m.name,
          schema: metaReviewSchema,
          phase: 'Meta-Review'
        })
      } else {
        return () => agent(`You are a meta-review proxy. Call model "${m.name}" to adversarially challenge a code review finding.

First, read the actual source file to verify the finding:
cat ${finding.file} 2>/dev/null | head -200

Then get the API key and call the model:
curl -s http://aio-01:5000/secrets/OPENROUTER_API_KEY | python3 -c "import json,sys; print(json.load(sys.stdin).get('value',''))" > /tmp/.api_key_tmp 2>/dev/null

curl -s https://openrouter.ai/api/v1/chat/completions \\
  -H "Authorization: Bearer $(cat /tmp/.api_key_tmp)" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify({
    model: m.name,
    messages: [{ role: "user", content: metaPrompt + "\n\nReturn JSON: {\"finding_index\": " + finding._idx + ", \"verdict\": \"confirmed|likely_valid|questionable|false_positive\", \"reasoning\": \"string\", \"revised_severity\": \"critical|major|minor|none\"}" }],
    max_tokens: 2048
  }).replace(/'/g, "'\\''")}'

Parse the API response and return the structured verdict. Clean up: rm -f /tmp/.api_key_tmp`, {
          label: `${m.name.split('/').pop()} meta-review #${finding._idx}`,
          schema: metaReviewSchema,
          phase: 'Meta-Review'
        })
      }
    }))
  },

  // Arbiter synthesizes meta-review verdicts
  (votes, finding) => {
    const validVotes = (votes || []).filter(Boolean)
    if (validVotes.length === 0) return { ...finding, meta_verdict: 'confirmed', meta_reason: 'No meta-review votes received — defaulting to confirmed' }

    const verdictCounts = validVotes.reduce((acc, v) => {
      acc[v.verdict] = (acc[v.verdict] || 0) + 1
      return acc
    }, {})

    const confirmedCount = (verdictCounts.confirmed || 0) + (verdictCounts.likely_valid || 0)
    const rejectedCount = (verdictCounts.false_positive || 0) + (verdictCounts.questionable || 0)

    // Majority vote: need more confirms than rejects to survive
    if (confirmedCount > rejectedCount) {
      return { ...finding, meta_verdict: 'confirmed', meta_votes: verdictCounts, meta_reason: `${confirmedCount}/${validVotes.length} reviewers confirmed` }
    } else {
      return { ...finding, meta_verdict: 'rejected', meta_votes: verdictCounts, meta_reason: `${rejectedCount}/${validVotes.length} reviewers rejected` }
    }
  }
)

const confirmedFindings = metaReviewResults.filter(Boolean).filter(f => f.meta_verdict === 'confirmed')
const rejectedFindings = metaReviewResults.filter(Boolean).filter(f => f.meta_verdict === 'rejected')

log(`✅ Meta-review complete:`)
log(`   Confirmed: ${confirmedFindings.length} findings (proceeding to fix)`)
log(`   Rejected:  ${rejectedFindings.length} findings (filtered out as false positives)`)

if (rejectedFindings.length > 0) {
  log(`   Rejected findings:`)
  rejectedFindings.forEach(f => {
    log(`     ❌ [${f.severity}] ${f.description?.slice(0, 60)} — ${f.meta_reason}`)
  })
}

// Replace dedupedFindings with only confirmed ones for subsequent phases
const validatedFindings = confirmedFindings

// PHASE 3: Create Issues
phase('Create Issues')

let createdIssues = []

if (validatedFindings.length > 0) {
  const issuesToCreate = Math.min(validatedFindings.length, 20)
  log(`📝 Creating ${issuesToCreate} GitHub issues...`)
  if (validatedFindings.length > 20) {
    log(`   ⚠️  Limiting to 20 issues (found ${validatedFindings.length})`)
  }

  createdIssues = await pipeline(
    validatedFindings.slice(0, 20), // Max 20 issues

    (finding, idx) => {
      log(`📝 [${idx + 1}/${issuesToCreate}] Creating issue: [${finding.severity?.toUpperCase()}] ${finding.category} - ${finding.description?.slice(0, 60)}...`)

      const issueTitle = finding.severity + ' ' + finding.category + ' in ' + finding.file
      const issueBody = 'Severity: ' + finding.severity + ', Description: ' + finding.description

      return _agent(`Create a GitHub issue.

Title: ${issueTitle}
Body: ${issueBody}

Execute:
gh issue create --title "${issueTitle}" --body "${issueBody}" --label bug,automated-review

Return the issue number.`, {
      label: `Create Issue: ${finding.description?.slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          issue_number: { type: 'number' }
        }
      }
    })
    }
  )

  const successCount = createdIssues.filter(Boolean).length
  const failedCount = issuesToCreate - successCount
  log(`✅ Created ${successCount}/${issuesToCreate} issues${failedCount > 0 ? ` (${failedCount} failed)` : ''}`)

  // Show created issue numbers
  const issueNums = createdIssues.filter(Boolean).map(i => i.issue_number).filter(Boolean)
  if (issueNums.length > 0) {
    log(`   Issue numbers: ${issueNums.join(', ')}`)
  }
} else {
  log('✅ No issues to create')
}

// PHASE 3: Wait for Issues
phase('Wait')

if (createdIssues.length > 0) {
  log('⏳ Waiting 10 seconds for GitHub to process issues...')

  await _agent(`Wait for issues to be created.

Execute:
sleep 10

This gives GitHub time to create all the issues.`, {
    label: 'Wait for Issues'
  })

  log('✅ Wait complete')
}

// PHASE 4: Code Solve
phase('Code Solve')

const validIssues = createdIssues.filter(Boolean)
let solveResults = []

if (validIssues.length > 0) {
  log(`🔧 Auto-resolving ${validIssues.length} issues...`)

  // Get the issue numbers
  const issueNumbers = validIssues.map(r => r.issue_number)

  log(`📝 Will attempt to solve: ${issueNumbers.join(', ')}`)
  log('')

  // Solve each issue - simplified inline approach without nested workflow calls
  solveResults = await pipeline(
    issueNumbers,

    // Fetch issue details
    (issueNum, idx) => {
      log(`📥 [${idx + 1}/${validIssues.length}] Fetching issue #${issueNum}...`)
      return _agent(`Get full details for issue #${issueNum}.

Execute:
gh issue view ${issueNum} --json number,title,body,labels

Return the issue details.`, {
        label: `Fetch #${issueNum}`,
        schema: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            body: { type: 'string' },
            labels: { type: 'array' }
          }
        }
      })
    },

    // Generate fix - multi-model: all workers propose, arbiter selects best
    (issue, _, idx) => {
      log(`🔧 [${idx + 1}/${validIssues.length}] Multi-AI generating fix for issue #${issue.number}...`)

      const fixSchema = {
        type: 'object',
        properties: {
          issue_number: { type: 'number' },
          fix_description: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 100 },
          files_to_modify: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                file: { type: 'string' },
                changes: { type: 'string' }
              }
            }
          }
        }
      }

      const fixPrompt = `Generate a fix for this issue:

**Issue #${issue.number}**: ${issue.title}

${issue.body}

Analyze the issue, identify the root cause, and propose a complete fix.
Include file paths, code changes, and explanation.`

      // Fix generation uses Claude models — they need tool access to read code and propose edits
      const FIX_MODELS = ['opus', 'sonnet', 'fable', 'haiku']
      return parallel(FIX_MODELS.map(model =>
        () => agent(fixPrompt, {
          label: `${model} Fix #${issue.number}`,
          model: model,
          schema: fixSchema
        })
      )).then(async fixes => {
        const validFixes = fixes.filter(Boolean)
        if (validFixes.length === 0) return { issue_number: issue.number, fix_description: '', files_to_modify: [] }

        // Arbiter selects best fix
        const arbiterResult = await _agent(`Review these ${validFixes.length} fix proposals for issue #${issue.number}:

${validFixes.map((f, i) => `Fix ${i + 1}: ${f.fix_description} (confidence: ${f.confidence || 'N/A'}%)`).join('\n')}

Select the best fix (return its index 0-${validFixes.length - 1}).`, {
          label: `Arbiter: Fix #${issue.number}`,
          model: SOLVE_ARBITER,
          schema: {
            type: 'object',
            properties: {
              selected_index: { type: 'number' },
              reasoning: { type: 'string' }
            },
            required: ['selected_index']
          }
        })

        const selectedIdx = Math.min(Math.max(0, arbiterResult.selected_index || 0), validFixes.length - 1)
        return validFixes[selectedIdx]
      })
    },

    // Apply fix and close issue
    (fix, _, idx) => {
      log(`✅ [${idx + 1}/${validIssues.length}] Applying fix for issue #${fix.issue_number}...`)

      const filesToModify = fix.files_to_modify || []
      if (filesToModify.length === 0) {
        log(`⚠️  No files to modify for #${fix.issue_number}`)
        return { status: 'skipped', issue_number: fix.issue_number, reason: 'No files to modify' }
      }

      return _agent(`Apply the fix for issue #${fix.issue_number}.

Fix description: ${fix.fix_description}

Files to modify:
${filesToModify.map(f => `- ${f.file}: ${f.changes}`).join('\n')}

Execute the following steps:
1. Apply the changes to each file
2. Create a commit with message: "Fix #${fix.issue_number}: ${fix.fix_description?.slice(0, 50)}"
3. Close issue #${fix.issue_number} with: gh issue close ${fix.issue_number} --comment "Fixed via automated code-solve"

Return the status.`, {
        label: `Apply #${fix.issue_number}`,
        schema: {
          type: 'object',
          properties: {
            status: { type: 'string', enum: ['success', 'error'] },
            issue_number: { type: 'number' },
            files_modified: { type: 'array', items: { type: 'string' } },
            commit_hash: { type: 'string' }
          }
        }
      })
    }
  )

  const successful = solveResults.filter(r => r?.status === 'success').length
  const failed = validIssues.length - successful

  log('')
  log(`✅ Code solve complete: ${successful}/${validIssues.length} issues resolved${failed > 0 ? ` (${failed} failed)` : ''}`)

  // Show which issues were solved
  const solvedIssues = solveResults.filter(r => r?.status === 'success').map(r => r.issue_number).filter(Boolean)
  const failedIssues = issueNumbers.filter(n => !solvedIssues.includes(n))

  if (solvedIssues.length > 0) {
    log(`   ✅ Solved: ${solvedIssues.join(', ')}`)
  }
  if (failedIssues.length > 0) {
    log(`   ❌ Failed: ${failedIssues.join(', ')}`)
  }
} else {
  log('ℹ️  No issues to solve')
}

// PHASE 5: Verify Fixes
phase('Verify Fixes')

let verificationResults = []

// Calculate issues solved before using it
const issuesSolved = solveResults?.filter(r => r?.status === 'success').length || 0

if (issuesSolved > 0) {
  log(`🔍 Verifying ${issuesSolved} fixes didn't introduce new bugs...`)

  // Get list of files modified by successful fixes
  const modifiedFiles = solveResults
    .filter(r => r?.status === 'success')
    .flatMap(r => r?.files_modified || [])
    .filter(Boolean)
    .filter((f, idx, arr) => arr.indexOf(f) === idx) // dedupe

  if (modifiedFiles.length > 0) {
    log(`   Files to verify: ${modifiedFiles.slice(0, 5).join(', ')}${modifiedFiles.length > 5 ? ` + ${modifiedFiles.length - 5} more` : ''}`)

    // Quick review of modified files
    verificationResults = await pipeline(
      modifiedFiles.slice(0, 10), // Max 10 files to verify

      (filepath, idx) => {
        log(`🔍 [${idx + 1}/${Math.min(10, modifiedFiles.length)}] Multi-AI verifying: ${filepath}`)

        const verifySchema = {
          type: 'object',
          properties: {
            file: { type: 'string' },
            new_issues: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  severity: { type: 'string' },
                  description: { type: 'string' }
                }
              }
            }
          }
        }

        const verifyPrompt = `Quick verification review of ${filepath} after fix was applied.

Look for:
- New bugs introduced by the fix
- Syntax errors
- Logic errors
- Regressions
- Edge cases not handled

Focus on critical issues only. Return empty array if fix looks good.`

        // Verify uses Claude models — they need tool access to read modified files
        const VERIFY_MODELS = ['opus', 'sonnet', 'fable']
        return parallel(VERIFY_MODELS.map(model =>
          () => agent(verifyPrompt, {
            label: `${model} Verify: ${filepath.split('/').pop()}`,
            model: model,
            schema: verifySchema
          })
        )).then(results => ({
          file: filepath,
          new_issues: results.filter(Boolean).flatMap(r => r.new_issues || [])
        }))
      }
    )

    const newIssuesFound = verificationResults
      .filter(Boolean)
      .flatMap(v => v.new_issues || [])
      .filter(Boolean)

    if (newIssuesFound.length > 0) {
      log(`⚠️  Verification found ${newIssuesFound.length} new issues introduced by fixes`)
      newIssuesFound.forEach(issue => {
        log(`   - [${issue.severity?.toUpperCase()}] ${issue.description}`)
      })
    } else {
      log(`✅ Verification passed - no new issues found in fixes`)
    }
  } else {
    log('ℹ️  No files to verify')
  }
} else {
  log('ℹ️  No fixes to verify (none succeeded)')
}

// PHASE 6: Summary
phase('Summary')

const bySeverity = validatedFindings.reduce((acc, f) => {
  const sev = f.severity || 'unknown'
  acc[sev] = (acc[sev] || 0) + 1
  return acc
}, {})

const bySource = validatedFindings.reduce((acc, f) => {
  acc[f.source] = (acc[f.source] || 0) + 1
  return acc
}, {})

const issuesAttempted = validIssues.length

const newIssuesIntroduced = verificationResults
  .filter(Boolean)
  .flatMap(v => v.new_issues || [])
  .filter(Boolean)
  .length

const summary = {
  review: {
    total_findings: dedupedFindings.length,
    by_severity: bySeverity,
    by_source: bySource,
    issues_created: createdIssues.filter(Boolean).length
  },
  meta_review: {
    findings_reviewed: dedupedFindings.length,
    confirmed: confirmedFindings.length,
    rejected: rejectedFindings.length,
    false_positive_rate: dedupedFindings.length > 0
      ? Math.round((rejectedFindings.length / dedupedFindings.length) * 100)
      : 0
  },
  solve: {
    issues_attempted: issuesAttempted,
    issues_solved: issuesSolved,
    success_rate: issuesAttempted > 0
      ? Math.round((issuesSolved / issuesAttempted) * 100)
      : 0
  },
  verification: {
    files_verified: verificationResults.filter(Boolean).length,
    new_issues_introduced: newIssuesIntroduced,
    verification_passed: newIssuesIntroduced === 0
  }
}

log('═'.repeat(80))
log('✅ CODE REVIEW + SOLVE COMPLETE')
log('═'.repeat(80))
log('')
log('📊 REVIEW RESULTS:')
log(`   Total findings: ${summary.review.total_findings}`)
log(`   Critical: ${summary.review.by_severity?.critical || 0}`)
log(`   Major: ${summary.review.by_severity?.major || 0}`)
log(`   Minor: ${summary.review.by_severity?.minor || 0}`)
log('')
log('🔎 META-REVIEW RESULTS:')
log(`   Findings reviewed: ${summary.meta_review.findings_reviewed}`)
log(`   Confirmed (real issues): ${summary.meta_review.confirmed}`)
log(`   Rejected (false positives): ${summary.meta_review.rejected}`)
log(`   False positive rate: ${summary.meta_review.false_positive_rate}%`)
log(`   Issues created: ${summary.review.issues_created}`)
log('')
log('🔧 SOLVE RESULTS:')
log(`   Issues attempted: ${summary.solve.issues_attempted}`)
log(`   Issues solved: ${summary.solve.issues_solved}`)
log(`   Success rate: ${summary.solve.success_rate}%`)
log('')
log('🔍 VERIFICATION RESULTS:')
log(`   Files verified: ${summary.verification.files_verified}`)
log(`   New issues introduced: ${summary.verification.new_issues_introduced}`)
log(`   Verification: ${summary.verification.verification_passed ? '✅ PASSED' : '⚠️  FAILED'}`)
log('')
log('═'.repeat(80))

return summary

}
