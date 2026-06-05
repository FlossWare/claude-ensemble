// INLINE Platform Detection & Issue Operations
// Copy these functions directly into your workflow (workflows can't use imports with scriptPath)
//
// Reference: ../platform-detector.js
// Usage: Copy the functions you need into your workflow file

// ============================================================================
// PLATFORM DETECTION
// ============================================================================

async function detectPlatform(agent) {
  const platformDetect = await agent(`Detect repository platform.

Execute:
if git remote -v | grep -q 'github.com'; then
  echo "github"
elif git remote -v | grep -q 'gitlab'; then
  echo "gitlab"
elif git remote -v | grep -q 'bitbucket'; then
  echo "bitbucket"
else
  echo "unknown"
fi

Return the platform name.`, {
    label: 'Detect Platform',
    schema: {
      type: 'object',
      properties: {
        platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket', 'unknown'] }
      },
      required: ['platform']
    }
  })

  return {
    platform: platformDetect.platform,
    isGitHub: platformDetect.platform === 'github',
    isGitLab: platformDetect.platform === 'gitlab',
    isBitbucket: platformDetect.platform === 'bitbucket'
  }
}

// ============================================================================
// ISSUE OPERATIONS
// ============================================================================

async function listIssues(agent, platform, state, limit = 100) {
  const fetchCmd = platform.isGitLab
    ? `glab issue list --state ${state === 'open' ? 'opened' : state} --per-page ${limit}`
    : platform.isBitbucket
    ? `echo "[]"  # Bitbucket not yet supported`
    : `gh issue list --state ${state} --limit ${limit} --json number,title,body,labels,createdAt,closedAt`

  const result = await agent(`Get ${state} issues from ${platform.platform}.

Execute:
${fetchCmd}

Return list of issues.`, {
    label: `List ${state} Issues`,
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
              labels: { type: 'array' },
              createdAt: { type: 'string' },
              closedAt: { type: 'string' }
            }
          }
        }
      }
    }
  })

  return result.issues || []
}

async function createIssue(agent, platform, title, body, labels = []) {
  const labelStr = labels.join(',')

  const createCmd = platform.isGitLab
    ? `glab issue create --title "${title}" --description "${body}" ${labelStr ? `--label "${labelStr}"` : ''}`
    : platform.isBitbucket
    ? `echo "Bitbucket not supported" && echo '{"issue_url": "", "issue_number": 0}'`
    : `gh issue create --title "${title}" --body "${body}" ${labelStr ? `--label "${labelStr}"` : ''}`

  const result = await agent(`Create issue on ${platform.platform}.

Title: ${title}
Body: ${body}
Labels: ${labelStr}

Execute:
${createCmd}

Return issue number and URL.`, {
    label: 'Create Issue',
    schema: {
      type: 'object',
      properties: {
        issue_url: { type: 'string' },
        issue_number: { type: 'number' }
      }
    }
  })

  return result
}

async function reopenIssue(agent, platform, issueNumber, comment = '') {
  const reopenCmd = platform.isGitLab
    ? `glab issue reopen ${issueNumber}${comment ? ` && glab issue note ${issueNumber} --message "${comment}"` : ''}`
    : platform.isBitbucket
    ? `echo "Bitbucket not supported"`
    : `gh issue reopen ${issueNumber}${comment ? ` && gh issue comment ${issueNumber} --body "${comment}"` : ''}`

  await agent(`Reopen issue #${issueNumber} on ${platform.platform}.

Execute:
${reopenCmd}
echo "REOPENED_ISSUE: #${issueNumber}"

Return status.`, {
    label: `Reopen #${issueNumber}`
  })

  console.log(`REOPENED_ISSUE: #${issueNumber}`)
}

async function closeIssue(agent, platform, issueNumber, comment = '') {
  const closeCmd = platform.isGitLab
    ? `${comment ? `glab issue note ${issueNumber} -m "${comment}" && ` : ''}glab issue close ${issueNumber}`
    : platform.isBitbucket
    ? `echo "Bitbucket not supported"`
    : `gh issue close ${issueNumber}${comment ? ` --comment "${comment}"` : ''}`

  await agent(`Close issue #${issueNumber} on ${platform.platform}.

Execute:
${closeCmd}
echo "CLOSED_ISSUE: #${issueNumber}"

Return status.`, {
    label: `Close #${issueNumber}`
  })

  console.log(`CLOSED_ISSUE: #${issueNumber}`)
}

async function commentOnIssue(agent, platform, issueNumber, comment) {
  const commentCmd = platform.isGitLab
    ? `glab issue note ${issueNumber} --message "${comment}"`
    : platform.isBitbucket
    ? `echo "Bitbucket not supported"`
    : `gh issue comment ${issueNumber} --body "${comment}"`

  await agent(`Add comment to issue #${issueNumber} on ${platform.platform}.

Execute:
${commentCmd}

Return status.`, {
    label: `Comment #${issueNumber}`
  })
}

async function updateLabels(agent, platform, issueNumber, addLabels = [], removeLabels = []) {
  const addStr = addLabels.join(',')
  const removeStr = removeLabels.join(',')

  const updateCmd = platform.isGitLab
    ? `${addStr ? `glab issue update ${issueNumber} --label "${addStr}"` : ''}${removeStr ? ` && glab issue update ${issueNumber} --unlabel "${removeStr}"` : ''}`
    : platform.isBitbucket
    ? `echo "Bitbucket not supported"`
    : `${addStr ? `gh issue edit ${issueNumber} --add-label "${addStr}"` : ''}${removeStr ? ` && gh issue edit ${issueNumber} --remove-label "${removeStr}"` : ''}`

  await agent(`Update labels for issue #${issueNumber} on ${platform.platform}.

Add: ${addStr || 'none'}
Remove: ${removeStr || 'none'}

Execute:
${updateCmd}

Return status.`, {
    label: `Update Labels #${issueNumber}`
  })
}

// ============================================================================
// USAGE EXAMPLE
// ============================================================================

/*

// 1. Detect platform
const platform = await detectPlatform(agent)
log(`Platform: ${platform.platform}`)

// 2. List issues
const openIssues = await listIssues(agent, platform, 'open', 50)
log(`Found ${openIssues.length} open issues`)

// 3. Create issue
const newIssue = await createIssue(agent, platform,
  'Bug: Login fails',
  'Details of the bug...',
  ['bug', 'high-priority']
)
log(`Created issue #${newIssue.issue_number}`)

// 4. Comment on issue
await commentOnIssue(agent, platform, newIssue.issue_number, 'Working on fix')

// 5. Update labels
await updateLabels(agent, platform, newIssue.issue_number,
  ['in-progress'],  // add
  ['high-priority'] // remove
)

// 6. Close issue
await closeIssue(agent, platform, newIssue.issue_number, 'Fixed in commit abc123')

// 7. Reopen if needed
await reopenIssue(agent, platform, newIssue.issue_number, 'Bug still present')

*/
