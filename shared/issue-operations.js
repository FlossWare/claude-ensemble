// Issue Operations Utility
// Reusable functions for working with GitHub/GitLab issues
// Used by code-test, code-review, code-solve, and other workflows

/**
 * Detects the platform (GitHub or GitLab)
 *
 * @param {Function} agent - The agent function from workflow context
 * @returns {Promise<Object>} Platform detection result
 */
export async function detectPlatform(agent) {
  const result = await agent(`Detect if this is a GitHub or GitLab repository.

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

  return {
    platform: result.platform,
    isGitHub: result.platform === 'github',
    isGitLab: result.platform === 'gitlab',
    cli: result.platform === 'github' ? 'gh' : result.platform === 'gitlab' ? 'glab' : null
  }
}

/**
 * Fetches open issues from GitHub or GitLab
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Fetch options
 * @param {string} options.platform - 'github' or 'gitlab'
 * @param {number} options.limit - Maximum issues to fetch (default: 100)
 * @param {string[]} options.labels - Filter by labels (optional)
 * @param {string} options.state - Issue state: 'open', 'closed', 'all' (default: 'open')
 * @returns {Promise<Object>} Issues list
 */
export async function fetchIssues(agent, options = {}) {
  const {
    platform,
    limit = 100,
    labels = null,
    state = 'open'
  } = options

  const isGitLab = platform === 'gitlab'
  const isGitHub = platform === 'github'

  let fetchCmd
  if (isGitLab) {
    fetchCmd = `glab issue list --state ${state} --per-page ${limit}`
    if (labels && labels.length > 0) {
      fetchCmd += ` --label "${labels.join(',')}"`
    }
    fetchCmd += ` --json number,title,labels,body,createdAt,closedAt`
  } else if (isGitHub) {
    fetchCmd = `gh issue list --state ${state} --limit ${limit}`
    if (labels && labels.length > 0) {
      labels.forEach(label => {
        fetchCmd += ` --label "${label}"`
      })
    }
    fetchCmd += ` --json number,title,labels,body,createdAt,closedAt`
  } else {
    throw new Error(`Unsupported platform: ${platform}`)
  }

  const result = await agent(`Fetch ${state} issues from ${platform}.

Execute:
${fetchCmd}

Return list of issues.`, {
    label: `Fetch ${state} Issues`,
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

  return {
    issues: result.issues || [],
    count: (result.issues || []).length,
    platform
  }
}

/**
 * Claims an issue by adding a label (prevents duplicate work)
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Claim options
 * @param {string} options.platform - 'github' or 'gitlab'
 * @param {number} options.issueNumber - Issue number to claim
 * @param {string} options.claimLabel - Label to add (default: 'in-progress')
 * @returns {Promise<Object>} Claim result
 */
export async function claimIssue(agent, options = {}) {
  const {
    platform,
    issueNumber,
    claimLabel = 'in-progress'
  } = options

  // Validate inputs
  if (!Number.isInteger(issueNumber) || issueNumber <= 0) {
    throw new Error(`Invalid issue number: ${issueNumber}`)
  }
  if (!/^[a-zA-Z0-9_-]+$/.test(claimLabel)) {
    throw new Error(`Invalid claim label: ${claimLabel}`)
  }

  const isGitLab = platform === 'gitlab'
  const isGitHub = platform === 'github'

  const claimCmd = isGitLab
    ? `# GitLab: Check and claim atomically
ISSUE_ID="${issueNumber}"
LABEL="${claimLabel}"

# Get current labels
CURRENT_LABELS=$(glab issue view "$ISSUE_ID" --json labels 2>/dev/null || echo '{"labels":[]}')

# Check if already claimed
if echo "$CURRENT_LABELS" | jq -e ".labels[]? | select(.name == \\"$LABEL\\")" >/dev/null 2>&1; then
  echo '{"claimed":false,"alreadyClaimed":true}'
else
  # Try to add label
  if glab issue update "$ISSUE_ID" --label "$LABEL" 2>/dev/null; then
    echo '{"claimed":true,"alreadyClaimed":false}'
  else
    echo '{"claimed":false,"alreadyClaimed":false}'
  fi
fi`
    : `# GitHub: Check and claim atomically
ISSUE_ID="${issueNumber}"
LABEL="${claimLabel}"

# Get current labels
CURRENT_LABELS=$(gh issue view "$ISSUE_ID" --json labels 2>/dev/null || echo '{"labels":[]}')

# Check if already claimed
if echo "$CURRENT_LABELS" | jq -e ".labels[]? | select(.name == \\"$LABEL\\")" >/dev/null 2>&1; then
  echo '{"claimed":false,"alreadyClaimed":true}'
else
  # Try to add label
  if gh issue edit "$ISSUE_ID" --add-label "$LABEL" 2>/dev/null; then
    echo '{"claimed":true,"alreadyClaimed":false}'
  else
    echo '{"claimed":false,"alreadyClaimed":false}'
  fi
fi`

  const result = await agent(`Claim issue #${issueNumber} with label "${claimLabel}".

Execute:
${claimCmd}

Return JSON result.`, {
    label: `Claim #${issueNumber}`,
    schema: {
      type: 'object',
      properties: {
        claimed: { type: 'boolean' },
        alreadyClaimed: { type: 'boolean' }
      },
      required: ['claimed', 'alreadyClaimed']
    }
  })

  return {
    claimed: result?.claimed === true,
    alreadyClaimed: result?.alreadyClaimed === true,
    issueNumber
  }
}

/**
 * Removes a claim label from an issue
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Unclaim options
 * @returns {Promise<Object>} Unclaim result
 */
export async function unclaimIssue(agent, options = {}) {
  const {
    platform,
    issueNumber,
    claimLabel = 'in-progress'
  } = options

  const isGitLab = platform === 'gitlab'

  const unclaimCmd = isGitLab
    ? `glab issue update ${issueNumber} --unlabel "${claimLabel}"`
    : `gh issue edit ${issueNumber} --remove-label "${claimLabel}"`

  await agent(`Remove claim label from issue #${issueNumber}.

Execute:
${unclaimCmd}

Return status.`, {
    label: `Unclaim #${issueNumber}`,
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string' }
      }
    }
  })

  return { issueNumber, unclaimed: true }
}

/**
 * Adds a comment to an issue
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Comment options
 * @param {string} options.platform - 'github' or 'gitlab'
 * @param {number} options.issueNumber - Issue number
 * @param {string} options.comment - Comment body (markdown)
 * @returns {Promise<Object>} Comment result
 */
export async function commentOnIssue(agent, options = {}) {
  const {
    platform,
    issueNumber,
    comment
  } = options

  const isGitLab = platform === 'gitlab'

  const commentCmd = isGitLab
    ? `glab issue note ${issueNumber} -m "${comment}"`
    : `gh issue comment ${issueNumber} --body "${comment}"`

  const result = await agent(`Add comment to issue #${issueNumber}.

Execute:
${commentCmd}

Return status.`, {
    label: `Comment on #${issueNumber}`,
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string' }
      }
    }
  })

  return {
    issueNumber,
    commented: true
  }
}

/**
 * Closes an issue with an optional comment
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Close options
 * @param {string} options.platform - 'github' or 'gitlab'
 * @param {number} options.issueNumber - Issue number
 * @param {string} options.comment - Optional closing comment
 * @returns {Promise<Object>} Close result
 */
export async function closeIssue(agent, options = {}) {
  const {
    platform,
    issueNumber,
    comment = null
  } = options

  const isGitLab = platform === 'gitlab'

  let closeCmd
  if (isGitLab) {
    if (comment) {
      closeCmd = `glab issue note ${issueNumber} -m "${comment}" && glab issue close ${issueNumber}`
    } else {
      closeCmd = `glab issue close ${issueNumber}`
    }
  } else {
    if (comment) {
      closeCmd = `gh issue close ${issueNumber} --comment "${comment}"`
    } else {
      closeCmd = `gh issue close ${issueNumber}`
    }
  }

  await agent(`Close issue #${issueNumber}.

Execute:
${closeCmd}

Return status.`, {
    label: `Close #${issueNumber}`,
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string' }
      }
    }
  })

  return {
    issueNumber,
    closed: true
  }
}

/**
 * Reopens a closed issue with an optional comment
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Reopen options
 * @returns {Promise<Object>} Reopen result
 */
export async function reopenIssue(agent, options = {}) {
  const {
    platform,
    issueNumber,
    comment = null
  } = options

  const isGitLab = platform === 'gitlab'

  let reopenCmd
  if (isGitLab) {
    if (comment) {
      reopenCmd = `glab issue reopen ${issueNumber} && glab issue note ${issueNumber} -m "${comment}"`
    } else {
      reopenCmd = `glab issue reopen ${issueNumber}`
    }
  } else {
    reopenCmd = `gh issue reopen ${issueNumber}`
    if (comment) {
      reopenCmd += ` && gh issue comment ${issueNumber} --body "${comment}"`
    }
  }

  await agent(`Reopen issue #${issueNumber}.

Execute:
${reopenCmd}

Return status.`, {
    label: `Reopen #${issueNumber}`,
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string' }
      }
    }
  })

  return {
    issueNumber,
    reopened: true
  }
}

/**
 * Creates a new issue
 *
 * @param {Function} agent - The agent function
 * @param {Object} options - Create options
 * @param {string} options.platform - 'github' or 'gitlab'
 * @param {string} options.title - Issue title
 * @param {string} options.body - Issue body (markdown)
 * @param {string[]} options.labels - Labels to add
 * @returns {Promise<Object>} Created issue
 */
export async function createIssue(agent, options = {}) {
  const {
    platform,
    title,
    body,
    labels = []
  } = options

  const isGitLab = platform === 'gitlab'

  let createCmd
  if (isGitLab) {
    createCmd = `glab issue create --title "${title}" --description "${body}"`
    if (labels.length > 0) {
      createCmd += ` --label "${labels.join(',')}"`
    }
  } else {
    createCmd = `gh issue create --title "${title}" --body "${body}"`
    if (labels.length > 0) {
      labels.forEach(label => {
        createCmd += ` --label "${label}"`
      })
    }
  }

  const result = await agent(`Create new issue.

Execute:
${createCmd}

Return issue number and URL.`, {
    label: `Create Issue`,
    schema: {
      type: 'object',
      properties: {
        issue_url: { type: 'string' },
        issue_number: { type: 'number' }
      }
    }
  })

  return {
    issueNumber: result.issue_number,
    issueUrl: result.issue_url,
    created: true
  }
}

/**
 * Filters issues by label
 *
 * @param {Array} issues - List of issues
 * @param {string} labelName - Label to filter by
 * @param {boolean} exclude - If true, exclude issues with this label
 * @returns {Array} Filtered issues
 */
export function filterByLabel(issues, labelName, exclude = false) {
  return issues.filter(issue => {
    const hasLabel = (issue.labels || []).some(l =>
      (typeof l === 'string' && l === labelName) ||
      (typeof l === 'object' && l.name === labelName)
    )
    return exclude ? !hasLabel : hasLabel
  })
}

/**
 * Gets issues without a specific label (unclaimed issues)
 *
 * @param {Array} issues - List of issues
 * @param {string} claimLabel - Claim label to check for
 * @returns {Array} Unclaimed issues
 */
export function getUnclaimedIssues(issues, claimLabel = 'in-progress') {
  return filterByLabel(issues, claimLabel, true)
}

// ============================================================================
// INLINE VERSION (for workflows that can't use imports)
// ============================================================================

export const INLINE_ISSUE_OPERATIONS = `
// Inline issue operations (no imports needed)

async function fetchOpenIssues(agent, platform, limit = 100) {
  const isGitLab = platform === 'gitlab'
  const fetchCmd = isGitLab
    ? \`glab issue list --state opened --per-page \${limit} --json number,title,labels,body\`
    : \`gh issue list --state open --limit \${limit} --json number,title,labels,body\`

  const result = await agent(\`Fetch open issues from \${platform}.\n\nExecute:\n\${fetchCmd}\n\nReturn list.\`, {
    label: 'Fetch Issues',
    schema: {
      type: 'object',
      properties: {
        issues: { type: 'array', items: { type: 'object' } }
      }
    }
  })

  return result.issues || []
}

async function claimIssue(agent, platform, issueNumber, label = 'in-progress') {
  const isGitLab = platform === 'gitlab'
  const claimCmd = isGitLab
    ? \`glab issue update \${issueNumber} --label "\${label}"\`
    : \`gh issue edit \${issueNumber} --add-label "\${label}"\`

  await agent(\`Claim issue #\${issueNumber}.\n\nExecute:\n\${claimCmd}\`, {
    label: \`Claim #\${issueNumber}\`
  })

  return true
}

async function createIssue(agent, platform, title, body, labels = []) {
  const isGitLab = platform === 'gitlab'
  let createCmd = isGitLab
    ? \`glab issue create --title "\${title}" --description "\${body}"\`
    : \`gh issue create --title "\${title}" --body "\${body}"\`

  if (labels.length > 0) {
    const labelFlag = isGitLab ? \`--label "\${labels.join(',')}"\` : labels.map(l => \`--label "\${l}"\`).join(' ')
    createCmd += \` \${labelFlag}\`
  }

  const result = await agent(\`Create issue.\n\nExecute:\n\${createCmd}\`, {
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
`
