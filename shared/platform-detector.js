// Platform Detection and Git Operations
// Auto-detects GitHub/GitLab/Bitbucket and provides unified interface
// Used by: ALL workflows (100%)

export async function detectPlatform(agent) {
  const result = await agent(`Detect the repository platform and return details.

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

export async function syncWithRemote(agent, options = {}) {
  const { branch = 'main' } = options

  const result = await agent(`Sync with remote repository.

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

export async function createIssue(agent, platform, title, body, labels = []) {
  const cli = platform.cli
  const labelStr = labels.length > 0 ? labels.join(',') : ''

  const result = await agent(`Create a GitHub/GitLab issue.

Platform: ${platform.platform}
CLI: ${cli}

Execute:
${cli} issue create --title "${title}" --body-file <temp_file> ${labelStr ? `--label "${labelStr}"` : ''}

Write the body to a temp file first to handle special characters.
Return the issue URL.`, {
    label: 'Create Issue',
    schema: {
      type: 'object',
      properties: {
        issue_url: { type: 'string' },
        issue_number: { type: 'number' },
        status: { type: 'string', enum: ['created', 'failed'] },
      },
      required: ['status'],
    }
  })

  return result
}

export async function createPR(agent, platform, title, body, options = {}) {
  const {
    baseBranch = 'main',
    headBranch = 'current',
    labels = [],
    draft = false
  } = options

  const cli = platform.cli
  const labelStr = labels.length > 0 ? labels.join(',') : ''
  const draftFlag = draft ? '--draft' : ''

  const result = await agent(`Create a Pull Request / Merge Request.

Platform: ${platform.platform}
CLI: ${cli}

Execute:
${cli} pr create --title "${title}" --body-file <temp_file> --base ${baseBranch} ${labelStr ? `--label "${labelStr}"` : ''} ${draftFlag}

Write the body to a temp file first.
Return the PR URL.`, {
    label: 'Create PR',
    schema: {
      type: 'object',
      properties: {
        pr_url: { type: 'string' },
        pr_number: { type: 'number' },
        status: { type: 'string', enum: ['created', 'failed'] },
      },
      required: ['status'],
    }
  })

  return result
}

export async function fetchIssue(agent, platform, issueNumber) {
  const cli = platform.cli

  const result = await agent(`Fetch issue details.

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

export async function fetchPR(agent, platform, prNumber) {
  const cli = platform.cli

  const result = await agent(`Fetch PR/MR details.

Platform: ${platform.platform}
PR Number: ${prNumber}

Execute:
${cli} pr view ${prNumber} --json title,body,labels,state,author,url,headRefName,baseRefName

Parse and return the PR details.`, {
    label: `Fetch PR #${prNumber}`,
    schema: {
      type: 'object',
      properties: {
        number: { type: 'number' },
        title: { type: 'string' },
        body: { type: 'string' },
        state: { type: 'string' },
        author: { type: 'string' },
        url: { type: 'string' },
        head_branch: { type: 'string' },
        base_branch: { type: 'string' },
        labels: { type: 'array', items: { type: 'string' } },
      },
      required: ['number', 'title', 'body', 'state'],
    }
  })

  return result
}

export async function postComment(agent, platform, issueOrPR, number, comment) {
  const cli = platform.cli
  const type = issueOrPR === 'issue' ? 'issue' : 'pr'

  const result = await agent(`Post a comment to ${type} #${number}.

Platform: ${platform.platform}

Execute:
${cli} ${type} comment ${number} --body "${comment}"

Return success status.`, {
    label: `Comment on ${type} #${number}`,
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['posted', 'failed'] },
      },
      required: ['status'],
    }
  })

  return result
}
