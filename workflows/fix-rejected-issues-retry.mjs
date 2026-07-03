export const meta = {
  name: 'fix-rejected-issues-retry',
  description: 'Fix 3 rejected issues from 252-model validation with retry loops',
  phases: [
    { title: 'Fix with Retry', detail: 'Fix → Review → Retry loop until FIXED (max 10 attempts per issue)' },
    { title: 'Commit Changes', detail: 'Squash commits and create feature branches for FIXED issues' }
  ]
}

// 3 issues that failed 252-model massive validation
const rejectedIssues = [
  {
    issue: '273',
    category: 'broken-import',
    file: 'shared/fleet_executor.py',
    problem: 'Fix exists on branch fix/issue-273-fleet-executor but NOT merged to main',
    fix: 'Merge branch fix/issue-273-fleet-executor into main',
    consensus: '1.59%',
    validators_failed: 248
  },
  {
    issue: '274',
    category: 'broken-import',
    file: 'shared/generate-embedding.py',
    problem: 'ZERO FILES UPDATED - all 4 files still reference generate-embedding.py (singular)',
    fix: 'Update all 4 files to use generate-embeddings.py (plural): shared/vector-store-postgres.py, workflows/deep-research-with-autostorage.mjs, workflows/tests/custom-deep-research.mjs, learning/scripts/migrate-completed-workflows.js',
    consensus: '25%',
    validators_failed: 3
  },
  {
    issue: '267',
    category: 'dead-code',
    file: 'shared/experiment-manager.cjs',
    problem: 'DOCUMENTATION ONLY - NO CODE INTEGRATION - consensus-replay.cjs has no require() or generateStatisticalVerdict() method',
    fix: 'Actually integrate experiment-manager into consensus-replay.cjs OR mark as deprecated',
    consensus: '0%',
    validators_failed: 4
  }
];

// Phase 1: Fix with Retry Loop
phase('Fix with Retry');

const MAX_ATTEMPTS = 10;

const fixResults = await parallel(
  rejectedIssues.map(issue => async () => {
    const issueNum = issue.issue;
    const problemDesc = issue.problem;

    let attempt = 0;
    let status = 'UNFIXED';
    let fixHistory = [];
    let reviewHistory = [];

    log(`Starting fix/review loop for issue #${issueNum} (failed ${issue.validators_failed} validators, ${issue.consensus} consensus)`);

    while (status !== 'FIXED' && attempt < MAX_ATTEMPTS) {
      attempt++;
      log(`Issue #${issueNum}: Attempt ${attempt}/${MAX_ATTEMPTS}`);

      // Build fix prompt with review feedback if this is a retry
      let fixPrompt = `Fix issue #${issueNum}: ${issue.file}

PROBLEM: ${problemDesc}
FIX STRATEGY: ${issue.fix}
ATTEMPT: ${attempt}/${MAX_ATTEMPTS}

VALIDATION FAILURE CONTEXT:
- 252-model massive validation consensus: ${issue.consensus}
- ${issue.validators_failed} validators voted FALSE
- This issue FAILED massive validation and needs proper fix`;

      if (attempt > 1 && reviewHistory.length > 0) {
        const lastReview = reviewHistory[reviewHistory.length - 1];
        fixPrompt += `

PREVIOUS ATTEMPT FAILED:
${lastReview.verdict}

EVIDENCE OF FAILURE:
${lastReview.evidence.join('\n')}

Instructions for this retry:
1. Review what went wrong in the previous attempt
2. Apply a DIFFERENT fix strategy based on the review feedback
3. Test more thoroughly this time`;
      }

      fixPrompt += `

You have WRITE and EDIT permissions - make the necessary changes.

Return JSON with:
- issue_number (string)
- attempt_number (number)
- fix_applied (string - what you did THIS attempt)
- files_modified (array of file paths)
- verification (string - how you tested)`;

      // Apply fix
      const fix = await agent(fixPrompt, {
        label: `fix-#${issueNum}-attempt-${attempt}`,
        phase: 'Fix with Retry',
        schema: {
          type: 'object',
          properties: {
            issue_number: { type: 'string' },
            attempt_number: { type: 'number' },
            fix_applied: { type: 'string' },
            files_modified: { type: 'array', items: { type: 'string' } },
            verification: { type: 'string' }
          },
          required: ['issue_number', 'attempt_number', 'fix_applied', 'files_modified', 'verification']
        }
      });

      if (!fix) {
        log(`Issue #${issueNum}: Fix attempt ${attempt} returned null - skipping`);
        break;
      }

      fixHistory.push(fix);

      // Review the fix
      const review = await agent(`Re-review fix for issue #${issueNum} (attempt ${attempt}/${MAX_ATTEMPTS})

ORIGINAL PROBLEM: ${problemDesc}

FIX APPLIED (Attempt ${attempt}): ${fix.fix_applied}

FILES MODIFIED: ${JSON.stringify(fix.files_modified)}

Instructions:
1. Run the SAME verification tests as the 252-model massive validator
2. Be STRICT - only return FIXED if the issue is completely resolved
3. If STILL_BROKEN or PARTIAL, provide SPECIFIC feedback on what's still wrong

For issue #273: Verify file exists at shared/fleet_executor.py on main branch
For issue #274: Grep all 4 files to verify they use generate-embeddings.py (plural)
For issue #267: Verify consensus-replay.cjs has require('./experiment-manager.cjs') and generateStatisticalVerdict() method

Return JSON with:
- issue_number (string)
- attempt_number (number)
- verification_status: "FIXED" | "STILL_BROKEN" | "PARTIAL"
- evidence (array of strings - test outputs)
- verdict (string - WHY you chose this status, what's still wrong if not FIXED)`, {
        label: `review-#${issueNum}-attempt-${attempt}`,
        phase: 'Fix with Retry',
        schema: {
          type: 'object',
          properties: {
            issue_number: { type: 'string' },
            attempt_number: { type: 'number' },
            verification_status: { type: 'string', enum: ['FIXED', 'STILL_BROKEN', 'PARTIAL'] },
            evidence: { type: 'array', items: { type: 'string' } },
            verdict: { type: 'string' }
          },
          required: ['issue_number', 'attempt_number', 'verification_status', 'evidence', 'verdict']
        }
      });

      if (!review) {
        log(`Issue #${issueNum}: Review attempt ${attempt} returned null - skipping`);
        break;
      }

      reviewHistory.push(review);
      status = review.verification_status;

      log(`Issue #${issueNum}: Attempt ${attempt} result = ${status}`);

      if (status === 'FIXED') {
        log(`Issue #${issueNum}: FIXED after ${attempt} attempt(s)!`);
        break;
      }
    }

    // Return final status
    return {
      issue_number: issueNum,
      category: issue.category,
      final_status: status,
      attempts_made: attempt,
      fix_history: fixHistory,
      review_history: reviewHistory,
      all_files_modified: fixHistory.flatMap(f => f.files_modified || [])
    };
  })
);

// Filter results
const fixedIssues = fixResults.filter(r => r?.final_status === 'FIXED');
const unfixedIssues = fixResults.filter(r => r && r.final_status !== 'FIXED');

log(`Fix/review loop complete: ${fixedIssues.length} FIXED, ${unfixedIssues.length} UNFIXED after max attempts`);

// Phase 2: Commit Changes
phase('Commit Changes');

const commitSummary = await agent(`Create feature branches with squashed commits for all FIXED issues.

FIXED ISSUES (ready for commit):
${JSON.stringify(fixedIssues, null, 2)}

UNFIXED ISSUES (skipped - max attempts exhausted):
${JSON.stringify(unfixedIssues, null, 2)}

Instructions:
1. For each FIXED issue, create a feature branch with ONE squashed commit

2. Branch naming:
   - Issue #273: fix/issue-273-fleet-executor-v2
   - Issue #274: fix/issue-274-generate-embedding-plural
   - Issue #267: fix/issue-267-experiment-manager-integration

3. For each FIXED issue:
   - Create branch from main
   - Stage ALL files from all_files_modified array
   - Create ONE commit (squashing all fix attempts)
   - Use conventional commit format

4. Commit messages:
   - "fix: Merge fleet_executor branch to main (#273)"
   - "fix: Update 4 files to use generate-embeddings.py plural (#274)"
   - "fix: Integrate experiment-manager into consensus-replay (#267)"

5. Include attempt count in commit body if attempts_made > 1:
   "fix: Update 4 files to use generate-embeddings.py plural (#274)

   Fixed after 3 attempts with 252-model validator feedback.

   Previously failed with 25% consensus (3/4 validators voted FALSE).
   Now passes all validation tests."

Return JSON with:
- branches_created (array of branch names)
- commits_created (number)
- commit_messages (array of strings)
- files_changed (number)
- git_status (string)
- unfixed_issues (array of issue numbers that couldn't be fixed)`, {
  label: 'commit-squashed',
  phase: 'Commit Changes',
  schema: {
    type: 'object',
    properties: {
      branches_created: { type: 'array', items: { type: 'string' } },
      commits_created: { type: 'number' },
      commit_messages: { type: 'array', items: { type: 'string' } },
      files_changed: { type: 'number' },
      git_status: { type: 'string' },
      unfixed_issues: { type: 'array', items: { type: 'string' } }
    },
    required: ['branches_created', 'commits_created', 'commit_messages', 'files_changed', 'git_status', 'unfixed_issues']
  }
});

log(`Feature branches created: ${commitSummary.branches_created?.length || 0}`);
log(`Commits created: ${commitSummary.commits_created}`);
log(`Unfixed issues: ${commitSummary.unfixed_issues?.join(', ') || 'none'}`);

// Calculate summary metrics
const totalAttempts = fixResults.reduce((sum, r) => sum + (r?.attempts_made || 0), 0);
const avgAttemptsPerIssue = totalAttempts / fixResults.length;

log(`Summary: ${fixedIssues.length} fixed, ${unfixedIssues.length} unfixed, ${totalAttempts} total attempts, ${avgAttemptsPerIssue.toFixed(1)} avg attempts/issue`);

return {
  fixResults: fixResults.filter(Boolean),
  summary: {
    fixed: fixedIssues.length,
    unfixed: unfixedIssues.length,
    total: fixResults.length,
    total_attempts: totalAttempts,
    avg_attempts: avgAttemptsPerIssue,
  },
  commitSummary,
  branches: commitSummary.branches_created || [],
  unfixedIssues: commitSummary.unfixed_issues || []
};
