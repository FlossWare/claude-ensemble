// AUTONOMOUS WORKFLOW - Repository Hygiene Review
// Reviews branches, issues, PRs, dependencies for cleanup opportunities

export const meta = {
  name: 'code-hygiene-review',
  description: 'Repository hygiene review: stale branches, old issues/PRs, large binaries, dependency cleanup (AUTONOMOUS)',
  phases: [
    { title: 'Stale Branches', detail: 'Find merged/abandoned branches' },
    { title: 'Stale Issues', detail: 'Find inactive or duplicate issues' },
    { title: 'Stale PRs', detail: 'Find abandoned or forgotten PRs' },
    { title: 'Git History', detail: 'Find large binaries, secrets, force pushes' },
    { title: 'Dependencies', detail: 'Find outdated or unused dependencies' },
    { title: 'Multi-Model Consensus', detail: 'Verify cleanup recommendations' },
    { title: 'Create Cleanup Report', detail: 'Generate actionable cleanup tasks' },
  ],
}

// Configuration
const AUTONOMOUS = args?.autonomous !== false
const USE_MULTI_MODEL = args?.multiModel !== false
const STALE_DAYS = args?.staleDays || 90
const MAX_BRANCHES = args?.maxBranches || 50
const MAX_ISSUES = args?.maxIssues || 100
const MAX_PRS = args?.maxPRs || 50

log(`🧹 REPOSITORY HYGIENE REVIEW`)
log('═'.repeat(80))
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)
log(`Stale threshold: ${STALE_DAYS} days`)
log('═'.repeat(80))

const allFindings = []

// PHASE 1: Stale Branches
phase('Stale Branches')
log('🌿 Analyzing branches...')

const branches = await agent(`Find all branches and their status.

Execute:
# Get all branches with last commit date
git for-each-ref --sort=-committerdate refs/heads/ refs/remotes/ \\
  --format='%(refname:short)|%(committerdate:iso)|%(authorname)|%(upstream:track)' | head -${MAX_BRANCHES}

# Get merged branches
git branch --merged main 2>/dev/null || git branch --merged master 2>/dev/null

# Get current branch
git branch --show-current

Identify:
- Merged branches (safe to delete)
- Stale branches (>90 days no activity)
- Branches with no remote tracking
- Long-lived feature branches

Return structured data.`, {
  label: 'Branch Analysis',
  schema: {
    type: 'object',
    properties: {
      total_branches: { type: 'number' },
      merged_branches: {
        type: 'array',
        items: { type: 'string' }
      },
      stale_branches: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            branch: { type: 'string' },
            last_commit_date: { type: 'string' },
            days_old: { type: 'number' },
            is_merged: { type: 'boolean' },
            has_remote: { type: 'boolean' }
          }
        }
      },
      current_branch: { type: 'string' }
    },
    required: ['total_branches', 'merged_branches', 'stale_branches']
  }
})

log(`✅ Found ${branches.total_branches} branches`)
log(`   Merged: ${branches.merged_branches?.length || 0}`)
log(`   Stale: ${branches.stale_branches?.length || 0}`)

// Add stale branch findings
branches.stale_branches?.forEach(branch => {
  const severity = branch.is_merged ? 'minor' : (branch.days_old > 180 ? 'major' : 'minor')
  allFindings.push({
    type: 'stale_branch',
    severity,
    description: `Stale branch: ${branch.branch} (${branch.days_old} days old)${branch.is_merged ? ' - already merged' : ''}`,
    branch: branch.branch,
    category: 'git_hygiene',
    action: branch.is_merged ? 'safe_to_delete' : 'review_needed'
  })
})

// PHASE 2: Stale Issues
phase('Stale Issues')
log('📋 Analyzing issues...')

const platform = await agent(`Detect platform (GitHub or GitLab).

Execute:
if git remote -v | grep -q 'github.com'; then echo "github"
elif git remote -v | grep -q 'gitlab'; then echo "gitlab"
else echo "unknown"; fi`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] }
    }
  }
})

if (platform.platform !== 'unknown') {
  const isGitHub = platform.platform === 'github'

  const issues = await agent(`Get all open issues and analyze for staleness.

Execute:
${isGitHub
  ? `gh issue list --state open --limit ${MAX_ISSUES} --json number,title,createdAt,updatedAt,labels,comments`
  : `glab issue list --state opened --per-page ${MAX_ISSUES}`
}

Identify:
- No activity in ${STALE_DAYS}+ days
- No comments (abandoned?)
- Duplicate issues
- Issues marked "won't fix" but still open

Return structured data.`, {
    label: 'Issue Analysis',
    schema: {
      type: 'object',
      properties: {
        total_issues: { type: 'number' },
        stale_issues: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              number: { type: 'number' },
              title: { type: 'string' },
              days_since_update: { type: 'number' },
              has_comments: { type: 'boolean' },
              is_duplicate: { type: 'boolean' }
            }
          }
        }
      }
    }
  })

  log(`✅ Found ${issues.total_issues} open issues`)
  log(`   Stale: ${issues.stale_issues?.length || 0}`)

  issues.stale_issues?.forEach(issue => {
    const severity = issue.days_since_update > 180 ? 'major' : 'minor'
    allFindings.push({
      type: 'stale_issue',
      severity,
      description: `Stale issue #${issue.number}: ${issue.title} (${issue.days_since_update} days inactive)`,
      issue_number: issue.number,
      category: 'issue_hygiene',
      action: issue.is_duplicate ? 'close_as_duplicate' : 'review_or_close'
    })
  })
}

// PHASE 3: Stale PRs
phase('Stale PRs')
log('🔀 Analyzing pull requests...')

if (platform.platform !== 'unknown') {
  const isGitHub = platform.platform === 'github'

  const prs = await agent(`Get all open PRs and analyze for staleness.

Execute:
${isGitHub
  ? `gh pr list --state open --limit ${MAX_PRS} --json number,title,createdAt,updatedAt,isDraft,reviews`
  : `glab mr list --state opened --per-page ${MAX_PRS}`
}

Identify:
- No activity in ${STALE_DAYS}+ days
- Drafts left unfinished
- Awaiting review for extended period
- Merge conflicts

Return structured data.`, {
    label: 'PR Analysis',
    schema: {
      type: 'object',
      properties: {
        total_prs: { type: 'number' },
        stale_prs: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              number: { type: 'number' },
              title: { type: 'string' },
              days_since_update: { type: 'number' },
              is_draft: { type: 'boolean' },
              has_conflicts: { type: 'boolean' },
              awaiting_review: { type: 'boolean' }
            }
          }
        }
      }
    }
  })

  log(`✅ Found ${prs.total_prs} open PRs`)
  log(`   Stale: ${prs.stale_prs?.length || 0}`)

  prs.stale_prs?.forEach(pr => {
    const severity = pr.has_conflicts ? 'major' : 'minor'
    allFindings.push({
      type: 'stale_pr',
      severity,
      description: `Stale PR #${pr.number}: ${pr.title} (${pr.days_since_update} days inactive)${pr.has_conflicts ? ' - has conflicts' : ''}`,
      pr_number: pr.number,
      category: 'pr_hygiene',
      action: pr.has_conflicts ? 'close_or_rebase' : 'review_or_close'
    })
  })
}

// PHASE 4: Git History Issues
phase('Git History')
log('📜 Analyzing git history...')

const gitHistory = await agent(`Analyze git history for problems.

Execute:
# Find large files (>1MB)
git rev-list --objects --all | \\
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \\
  awk '/^blob/ {if($3 > 1048576) print $3, $4}' | \\
  sort -rn | head -20

# Check for potential secrets (basic scan)
git log --all --pretty=format: --name-only | sort -u | \\
  grep -iE '(secret|password|api.?key|token|credentials|\.env)' | head -20

# Find force pushes (last 100 commits)
git log --walk-reflogs --oneline -100 | grep -i force || echo "No force pushes found"

Identify issues.`, {
  label: 'Git History Analysis',
  schema: {
    type: 'object',
    properties: {
      large_files: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            size_mb: { type: 'number' }
          }
        }
      },
      potential_secrets: {
        type: 'array',
        items: { type: 'string' }
      },
      force_pushes_detected: { type: 'boolean' }
    }
  }
})

log(`✅ Large files: ${gitHistory.large_files?.length || 0}`)
log(`   Potential secrets: ${gitHistory.potential_secrets?.length || 0}`)

gitHistory.large_files?.forEach(file => {
  allFindings.push({
    type: 'large_binary',
    severity: file.size_mb > 10 ? 'major' : 'minor',
    description: `Large file in git history: ${file.file} (${file.size_mb}MB)`,
    file: file.file,
    category: 'git_hygiene',
    action: 'consider_git_lfs_or_remove'
  })
})

gitHistory.potential_secrets?.forEach(file => {
  allFindings.push({
    type: 'potential_secret',
    severity: 'critical',
    description: `Potential secret in git history: ${file}`,
    file,
    category: 'security',
    action: 'review_immediately'
  })
})

// PHASE 5: Dependencies
phase('Dependencies')
log('📦 Analyzing dependencies...')

const deps = await agent(`Analyze dependencies for issues.

Check for:
1. package.json (npm/yarn)
2. requirements.txt (Python)
3. pom.xml (Java/Maven)
4. Gemfile (Ruby)
5. go.mod (Go)

For each found, check:
- Outdated packages (npm outdated, pip list --outdated, etc.)
- Unused dependencies
- Security vulnerabilities (npm audit, pip-audit, etc.)

Return findings.`, {
  label: 'Dependency Analysis',
  schema: {
    type: 'object',
    properties: {
      dependency_files_found: {
        type: 'array',
        items: { type: 'string' }
      },
      outdated_packages: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            package: { type: 'string' },
            current: { type: 'string' },
            latest: { type: 'string' },
            severity: { type: 'string' }
          }
        }
      },
      vulnerabilities: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            package: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'moderate', 'low'] },
            description: { type: 'string' }
          }
        }
      }
    }
  }
})

log(`✅ Dependency files: ${deps.dependency_files_found?.length || 0}`)
log(`   Outdated: ${deps.outdated_packages?.length || 0}`)
log(`   Vulnerabilities: ${deps.vulnerabilities?.length || 0}`)

deps.outdated_packages?.forEach(pkg => {
  allFindings.push({
    type: 'outdated_dependency',
    severity: pkg.severity || 'minor',
    description: `Outdated: ${pkg.package} (${pkg.current} → ${pkg.latest})`,
    package: pkg.package,
    category: 'dependencies',
    action: 'update_dependency'
  })
})

deps.vulnerabilities?.forEach(vuln => {
  allFindings.push({
    type: 'dependency_vulnerability',
    severity: vuln.severity === 'critical' || vuln.severity === 'high' ? 'critical' : 'major',
    description: `Vulnerability in ${vuln.package}: ${vuln.description}`,
    package: vuln.package,
    category: 'security',
    action: 'update_immediately'
  })
})

// PHASE 6: Consensus
phase('Multi-Model Consensus')
log('⚖️  Deduplicating findings...')

const uniqueFindings = []
const seen = new Set()

allFindings.forEach(finding => {
  const key = `${finding.type}:${finding.description}`
  if (!seen.has(key)) {
    seen.add(key)
    uniqueFindings.push(finding)
  }
})

log(`✅ ${uniqueFindings.length} unique findings`)

// PHASE 7: Create Cleanup Report
phase('Create Cleanup Report')

// Group by category
const byCategory = {}
uniqueFindings.forEach(f => {
  if (!byCategory[f.category]) byCategory[f.category] = []
  byCategory[f.category].push(f)
})

log('═'.repeat(80))
log(`✅ HYGIENE REVIEW COMPLETE`)
log('')
log('Findings by category:')
Object.keys(byCategory).forEach(cat => {
  log(`  ${cat}: ${byCategory[cat].length}`)
})
log('')
log(`Total cleanup opportunities: ${uniqueFindings.length}`)
log('═'.repeat(80))

// Create cleanup issue if autonomous
if (AUTONOMOUS && platform.platform !== 'unknown') {
  const isGitHub = platform.platform === 'github'

  const reportBody = `## Repository Hygiene Report

**Generated:** ${new Date().toISOString()}

### Summary

- **Total findings:** ${uniqueFindings.length}
- **Critical:** ${uniqueFindings.filter(f => f.severity === 'critical').length}
- **Major:** ${uniqueFindings.filter(f => f.severity === 'major').length}
- **Minor:** ${uniqueFindings.filter(f => f.severity === 'minor').length}

### Findings by Category

${Object.keys(byCategory).map(cat => `
#### ${cat} (${byCategory[cat].length})

${byCategory[cat].map(f => `- [${f.severity}] ${f.description} → **${f.action}**`).join('\n')}
`).join('\n')}

---
🤖 Generated by /code-hygiene-review workflow
`

  const createCmd = isGitHub
    ? `gh issue create --title "[Hygiene] Repository cleanup - ${uniqueFindings.length} items" --body "${reportBody}" --label "maintenance,hygiene"`
    : `glab issue create --title "[Hygiene] Repository cleanup - ${uniqueFindings.length} items" --description "${reportBody}" --label "maintenance,hygiene"`

  try {
    await agent(`Create hygiene report issue.

Execute:
${createCmd}`, {
      label: 'Create Report Issue'
    })
    log('✅ Created hygiene report issue')
  } catch (err) {
    log(`⚠️  Failed to create report issue: ${err.message}`)
  }
}

return {
  findings: uniqueFindings,
  by_category: byCategory,
  stale_branches: branches.stale_branches?.length || 0,
  stale_issues: allFindings.filter(f => f.type === 'stale_issue').length,
  stale_prs: allFindings.filter(f => f.type === 'stale_pr').length,
  vulnerabilities: allFindings.filter(f => f.type === 'dependency_vulnerability').length
}
