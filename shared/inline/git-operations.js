// INLINE Git Operations
// Copy these functions directly into your workflow
//
// Common git operations used across workflows

// ============================================================================
// COMMIT OPERATIONS
// ============================================================================

async function getCommitHistory(agent, days = 30, limit = 50) {
  const result = await agent(`Get commit history for last ${days} days.

Execute:
git log --since="${days} days ago" --pretty=format:"%H|%an|%ad|%s" --date=short ${limit ? `| head -${limit}` : ''}

Return structured commit data.`, {
    label: 'Get Commit History',
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
              message: { type: 'string' }
            }
          }
        },
        total_commits: { type: 'number' }
      }
    }
  })

  return result
}

async function getDiff(agent, commitHash) {
  const result = await agent(`Get diff for commit ${commitHash}.

Execute:
git show ${commitHash} --stat
git diff ${commitHash}^..${commitHash}

Return files changed and diff content.`, {
    label: `Diff: ${commitHash.slice(0, 8)}`,
    schema: {
      type: 'object',
      properties: {
        files_changed: { type: 'array', items: { type: 'string' } },
        diff: { type: 'string' },
        commit_hash: { type: 'string' }
      }
    }
  })

  return result
}

async function getCurrentBranch(agent) {
  const result = await agent(`Get current git branch.

Execute:
git branch --show-current

Return branch name.`, {
    label: 'Get Current Branch',
    schema: {
      type: 'object',
      properties: {
        branch: { type: 'string' }
      }
    }
  })

  return result.branch
}

async function getRemoteUrl(agent) {
  const result = await agent(`Get git remote URL.

Execute:
git remote get-url origin

Return remote URL.`, {
    label: 'Get Remote URL',
    schema: {
      type: 'object',
      properties: {
        url: { type: 'string' }
      }
    }
  })

  return result.url
}

// ============================================================================
// FILE OPERATIONS
// ============================================================================

async function findSourceFiles(agent, patterns = ['*.js', '*.ts', '*.py', '*.java', '*.go', '*.rb', '*.sh'], exclude = ['node_modules', 'vendor', '.git', 'test', '__tests__'], limit = 50) {
  const patternStr = patterns.map(p => `-name "${p}"`).join(' -o ')
  const excludeStr = exclude.map(e => `grep -v ${e}`).join(' | ')

  const result = await agent(`Find source code files.

Execute:
find . -type f \\( ${patternStr} \\) | ${excludeStr} | head -${limit}

Return list of files.`, {
    label: 'Find Source Files',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result.files || []
}

async function getFileHistory(agent, filepath, limit = 10) {
  const result = await agent(`Get commit history for file: ${filepath}

Execute:
git log --follow --pretty=format:"%H|%an|%ad|%s" --date=short ${limit ? `-${limit}` : ''} -- "${filepath}"

Return file history.`, {
    label: `File History: ${filepath}`,
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
              message: { type: 'string' }
            }
          }
        }
      }
    }
  })

  return result.commits || []
}

async function getBlame(agent, filepath) {
  const result = await agent(`Get git blame for ${filepath}.

Execute:
git blame --line-porcelain "${filepath}"

Return blame info showing who last modified each line.`, {
    label: `Blame: ${filepath}`,
    schema: {
      type: 'object',
      properties: {
        lines: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              line_number: { type: 'number' },
              commit: { type: 'string' },
              author: { type: 'string' },
              content: { type: 'string' }
            }
          }
        }
      }
    }
  })

  return result.lines || []
}

// ============================================================================
// STATUS OPERATIONS
// ============================================================================

async function getStatus(agent) {
  const result = await agent(`Get git status.

Execute:
git status --porcelain
git status

Return status of working tree.`, {
    label: 'Git Status',
    schema: {
      type: 'object',
      properties: {
        modified: { type: 'array', items: { type: 'string' } },
        added: { type: 'array', items: { type: 'string' } },
        deleted: { type: 'array', items: { type: 'string' } },
        untracked: { type: 'array', items: { type: 'string' } },
        clean: { type: 'boolean' }
      }
    }
  })

  return result
}

async function hasUncommittedChanges(agent) {
  const result = await agent(`Check for uncommitted changes.

Execute:
git diff --quiet && git diff --cached --quiet && echo "clean" || echo "dirty"

Return whether there are uncommitted changes.`, {
    label: 'Check Uncommitted',
    schema: {
      type: 'object',
      properties: {
        has_changes: { type: 'boolean' }
      }
    }
  })

  return result.has_changes
}

// ============================================================================
// USAGE EXAMPLE
// ============================================================================

/*

// 1. Get recent commits
const history = await getCommitHistory(agent, 30, 50)
log(`Found ${history.total_commits} commits`)

// 2. Get diff for a commit
const diff = await getDiff(agent, history.commits[0].hash)
log(`Files changed: ${diff.files_changed.join(', ')}`)

// 3. Find source files
const files = await findSourceFiles(agent,
  ['*.js', '*.ts'],
  ['node_modules', 'dist'],
  100
)
log(`Found ${files.length} source files`)

// 4. Get file history
const fileHistory = await getFileHistory(agent, 'src/index.js', 10)
log(`File has ${fileHistory.length} commits`)

// 5. Get current status
const status = await getStatus(agent)
log(`Modified: ${status.modified.length}, Clean: ${status.clean}`)

// 6. Check if clean
const hasChanges = await hasUncommittedChanges(agent)
if (hasChanges) {
  log('⚠️  Uncommitted changes detected')
}

*/
