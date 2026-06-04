export const meta = {
  name: 'pr-verify',
  description: 'Verify open PRs: build, test, and quality checks',
  phases: [
    { title: 'Discover PRs', detail: 'Find open pull requests', model: 'gemini' },
    { title: 'Verify PRs', detail: 'Build, test, and quality check each PR in parallel', model: 'gemini' },
    { title: 'Report', detail: 'Post results as PR comments', model: 'gemini' }
  ],
}

const PR_SCHEMA = {
  type: 'object',
  properties: {
    prs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          number: { type: 'number' },
          title: { type: 'string' },
          branch: { type: 'string' },
          url: { type: 'string' }
        },
        required: ['number', 'title', 'branch']
      }
    }
  },
  required: ['prs']
}

const VERIFICATION_SCHEMA = {
  type: 'object',
  properties: {
    prNumber: { type: 'number' },
    success: { type: 'boolean' },
    buildStatus: { enum: ['passed', 'failed', 'skipped'] },
    testStatus: { enum: ['passed', 'failed', 'skipped'] },
    testsPassing: { type: 'number' },
    testsFailing: { type: 'number' },
    qualityStatus: { enum: ['passed', 'failed', 'skipped'] },
    qualityIssues: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    recommendation: { enum: ['approve', 'request-changes', 'needs-review'] }
  },
  required: ['prNumber', 'success', 'buildStatus', 'testStatus', 'summary', 'recommendation']
}

// Phase 1: Discover PRs
phase('Discover PRs')
log('Fetching open pull requests...')

const prList = await agent(
  'List all open pull requests using gh pr list. Return PR number, title, and branch for each.',
  {
    label: 'discover-prs',
    phase: 'Discover PRs',
    schema: PR_SCHEMA,
    model: 'gemini'
  }
)

if (!prList || prList.prs.length === 0) {
  log('No open PRs found')
  return { totalPRs: 0, verified: 0, passed: 0, failed: 0 }
}

log(`Found ${prList.prs.length} open PRs`)

// Phase 2: Verify PRs in parallel
phase('Verify PRs')

// Define verification prompt for each PR
const verificationPrompt = (pr) => `
Verify PR #${pr.number}: "${pr.title}"

Steps to perform IN ISOLATION (use worktree):
1. Checkout PR branch "${pr.branch}" in a fresh worktree
2. Build the project:
   - Desktop: ./mvnw clean package -DskipTests
   - Android (if exists): gradle :jnexus-android:assembleDebug
3. Run tests:
   - Desktop: ./mvnw test
   - Android: gradle :jnexus-android:testDebugUnitTest
4. Quality checks:
   - Code formatting: ./mvnw spotless:check
   - Checkstyle: ./mvnw checkstyle:check
   - Count of spotless/checkstyle violations
5. Clean up worktree when done

Report:
- Build status (passed/failed)
- Test status (passed/failed) + count passing/failing
- Quality status (passed/failed) + list of violations
- Overall recommendation: approve / request-changes / needs-review
- Summary: 2-3 sentence summary of verification results

IMPORTANT:
- Work in worktree isolation to avoid conflicts with other PR verifications
- If build fails, don't run tests (mark as skipped)
- If tests fail, still run quality checks
- Be thorough but concise in summary
`

// Verify PRs in parallel (pipeline for better wall-clock time)
const verifications = await pipeline(
  prList.prs,
  pr => agent(
    verificationPrompt(pr),
    {
      label: `verify-pr-${pr.number}`,
      phase: 'Verify PRs',
      schema: VERIFICATION_SCHEMA,
      isolation: 'worktree',  // Each PR verified in isolated worktree
      model: 'gemini'
    }
  )
)

// Phase 3: Report results
phase('Report')
log('Generating PR verification reports...')

const validVerifications = verifications.filter(Boolean)

// Post comment on each PR with results
const commentPrompts = validVerifications.map(v => {
  const status = v.success ? '✅ PASSED' : '❌ FAILED'
  const emoji = v.recommendation === 'approve' ? '✅' :
                v.recommendation === 'request-changes' ? '❌' : '⚠️'

  return {
    prNumber: v.prNumber,
    prompt: `
Post a comment on PR #${v.prNumber} with these verification results:

---
${emoji} **Automated PR Verification - ${status}**

**Build:** ${v.buildStatus === 'passed' ? '✅' : '❌'} ${v.buildStatus}
**Tests:** ${v.testStatus === 'passed' ? '✅' : '❌'} ${v.testStatus}${v.testsPassing !== undefined ? ` (${v.testsPassing} passing, ${v.testsFailing || 0} failing)` : ''}
**Quality:** ${v.qualityStatus === 'passed' ? '✅' : '❌'} ${v.qualityStatus}${v.qualityIssues && v.qualityIssues.length > 0 ? `\n  - ${v.qualityIssues.join('\n  - ')}` : ''}

**Summary:** ${v.summary}

**Recommendation:** ${v.recommendation.toUpperCase().replace('-', ' ')}

---

## 🤖 Verification Methodology

### Arbiter/Worker Architecture

**Arbiter (Orchestrator):**
- **Model:** Claude Sonnet 4.5
- **Role:** Workflow coordination, phase management, result synthesis
- **Why:** Best-in-class reasoning for orchestration and decision-making

**Worker Agents (Verification):**
- **Model:** Google Gemini
- **Count:** 3 agents (discover, verify, report)
- **Role:** Build execution, test running, quality checks, comment posting
- **Why Accepted:**
  - Cost efficiency (10-20x cheaper than Claude for verification tasks)
  - Excellent at structured tasks (builds, tests, pattern matching)
  - Fast parallel execution
  - Strong syntactic analysis (file extensions, syntax errors, code quality)
- **Why Other Models Not Used:**
  - Claude Haiku: More expensive than Gemini, similar capability for verification
  - Claude Opus: Overkill for structured verification (expensive)
  - GPT-4: Not integrated in this workflow, Gemini more cost-effective

### Verification Process

1. **Discovery Phase** (Gemini worker)
   - Listed all open PRs via \\\`gh pr list\\\`
   - Identified PR #${v.prNumber}

2. **Verification Phase** (Gemini worker in isolated worktree)
   - Checked out PR branch in isolated git worktree
   - Executed build commands
   - Ran test suite
   - Performed quality checks (formatting, linting, syntax validation)

3. **Report Phase** (Gemini worker)
   - Generated structured findings
   - Posted this verification comment

### Quality Assurance

- **Isolated Execution:** Each PR verified in separate git worktree (no conflicts)
- **Reproducible:** Same verification can be re-run with \\\`claude-code workflow run pr-verify\\\`
- **Transparent:** All findings include file paths and line numbers
- **Model-Appropriate:** Gemini for structured tasks, Claude for complex reasoning

### Workflow Location

- Global workflow: \\\`~/.claude/workflows/pr-verify.js\\\`
- Documentation: \\\`~/.claude/docs/PR_VERIFY_GUIDE.md\\\`

---
🤖 Generated by Claude Code PR Verification Workflow

Use: gh pr comment ${v.prNumber} --body "<comment-text>"
`
  }
})

// Post comments in parallel
const comments = await parallel(
  commentPrompts.map(c => () =>
    agent(c.prompt, {
      label: `comment-pr-${c.prNumber}`,
      phase: 'Report',
      model: 'gemini'
    })
  )
)

// Calculate summary statistics
const passed = validVerifications.filter(v => v.success).length
const failed = validVerifications.filter(v => !v.success).length
const approved = validVerifications.filter(v => v.recommendation === 'approve').length
const needsChanges = validVerifications.filter(v => v.recommendation === 'request-changes').length

log(`Verification complete: ${passed} passed, ${failed} failed`)

return {
  totalPRs: prList.prs.length,
  verified: validVerifications.length,
  passed: passed,
  failed: failed,
  approved: approved,
  needsChanges: needsChanges,
  commentsPosted: comments.filter(Boolean).length,
  results: validVerifications.map(v => ({
    prNumber: v.prNumber,
    success: v.success,
    recommendation: v.recommendation
  }))
}
