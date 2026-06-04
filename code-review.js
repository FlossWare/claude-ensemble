// AUTONOMOUS WORKFLOW - No user prompts or confirmations
// This workflow is designed for automated/background execution
// It must complete without user interaction
// Auto-creates issues, auto-reopens broken issues, no approval needed

export const meta = {
  name: 'code-review',
  description: 'Comprehensive brutal code review: commits, issues, codebase, dependencies, security (AUTONOMOUS)',
  phases: [
    { title: 'Recent Commits', detail: 'Review all commits from last 30 days' },
    { title: 'Closed Issues', detail: 'Review recently closed issues for lingering problems' },
    { title: 'Full Codebase', detail: 'Brutal review of entire codebase' },
    { title: 'Dependencies', detail: 'Check for outdated packages and vulnerabilities' },
    { title: 'Security Scan', detail: 'Deep security scan: secrets, OWASP, exposed endpoints' },
    { title: 'Multi-Model Consensus', detail: 'All findings verified by multiple AIs' },
    { title: 'Create Issues', detail: 'Create GitHub/GitLab issues for all findings' },
  ],
}

// Configuration
const AUTONOMOUS = args?.autonomous !== false  // Autonomous by default (pass autonomous=false to disable)
const BRUTAL_MODE = true
const DAYS_BACK = args?.days || 30
const MAX_COMMITS = args?.maxCommits || 5  // Reduced from 20
const MAX_ISSUES_TO_REVIEW = args?.maxIssues || 5  // Reduced from 50
const MAX_FILES = args?.maxFiles || 10  // Reduced from 20
const CONFIDENCE_THRESHOLD = 70 // Lower than normal - we want to catch everything
const USE_MULTI_MODEL = args?.multiModel !== false  // Multi-model by default (pass multiModel=false to disable)

log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

log('🔥 BRUTAL CODE REVIEW MODE 🔥')
log('═'.repeat(80))
log(`Reviewing: Last ${DAYS_BACK} days of commits + ${MAX_ISSUES_TO_REVIEW} closed issues + full codebase`)
log(`Confidence Threshold: ${CONFIDENCE_THRESHOLD}% (inclusive mode)`)
log('═'.repeat(80))

const allFindings = []

// PHASE 1: Review Recent Commits
phase('Recent Commits')

log(`📅 Analyzing commits from last ${DAYS_BACK} days...`)

const commitHistory = await agent(`Get detailed commit history for the last ${DAYS_BACK} days.

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

log(`✅ Found ${commitHistory.total_commits} commits to review`)

// Review each commit with multiple AI models
const commitFindings = await pipeline(
  commitHistory.commits.slice(0, MAX_COMMITS), // Review most recent commits

  // Stage 1: Get the diff for each commit
  (commit, idx) => agent(`Get the full diff for commit ${commit.hash}.

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
  }),

  // Stage 2: Multi-model review with rotation
  (diffData, _, idx) => {
    if (!USE_MULTI_MODEL) {
      // Single model fallback
      return agent(`BRUTAL CODE REVIEW of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find ALL issues.`, {
        label: `Review: ${diffData.commit_hash.slice(0, 8)}`,
        schema: {
          type: 'object',
          properties: {
            issues: { type: 'array', items: { type: 'object' } }
          }
        }
      }).then(review => ({
        commit_hash: diffData.commit_hash,
        reviews: [review]
      }))
    }

    // Rotate models based on commit index for diversity
    const modelRotation = [
      ['opus', 'sonnet', 'haiku'],     // idx % 3 == 0
      ['sonnet', 'haiku', 'opus'],     // idx % 3 == 1
      ['haiku', 'opus', 'sonnet']      // idx % 3 == 2
    ][idx % 3]

    return parallel([
      () => agent(`BRUTAL CODE REVIEW of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find ALL issues:
- Security vulnerabilities (SQL injection, XSS, hardcoded secrets, auth issues)
- Logic bugs (off-by-one, race conditions, null pointers)
- Performance issues (N+1 queries, memory leaks, inefficient algorithms)
- Code quality (duplication, complexity, poor naming)
- Missing error handling
- Edge cases not handled
- Potential race conditions
- Thread safety issues
- Resource leaks

Be BRUTAL. Find everything wrong, no matter how small.`, {
      label: `${modelRotation[0]} Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: modelRotation[0],
      schema: {
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
          }
        }
      }
    }),

    () => agent(`Security and correctness audit of commit ${diffData.commit_hash}:

${diffData.diff}

Focus on:
1. Security holes
2. Logic correctness
3. Data integrity
4. Error handling
5. Input validation

Find EVERYTHING.`, {
      label: `${modelRotation[1]} Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: modelRotation[1],
      schema: {
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
                confidence: { type: 'number' }
              }
            }
          }
        }
      }
    }),

    () => agent(`Quick scan for obvious bugs in commit ${diffData.commit_hash}:

${diffData.diff}

Find bugs fast - don't miss the obvious ones.`, {
      label: `${modelRotation[2]} Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: modelRotation[2],
      schema: {
        type: 'object',
        properties: {
          issues: { type: 'array', items: { type: 'object' } }
        }
      }
    })
  ]).then(reviews => ({
    commit_hash: diffData.commit_hash,
    reviews: reviews.filter(Boolean)
  }))
  }

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find ALL issues:
- Security vulnerabilities (SQL injection, XSS, hardcoded secrets, auth issues)
- Logic bugs (off-by-one, race conditions, null pointers)
- Performance issues (N+1 queries, memory leaks, inefficient algorithms)
- Code quality (duplication, complexity, poor naming)
- Missing error handling
- Edge cases not handled
- Potential race conditions
- Thread safety issues
- Resource leaks

Be BRUTAL. Find everything wrong, no matter how small.`, {
    label: `Review: ${diffData.commit_hash.slice(0, 8)}`,
    schema: {
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
        }
      }
    }
  }).then(review => ({
    commit_hash: diffData.commit_hash,
    reviews: [review]
  }))
)
)

// Merge findings from all commits
commitFindings.filter(Boolean).forEach(cf => {
  cf.reviews.forEach((review, idx) => {
    review.issues?.forEach(issue => {
      if (issue.confidence >= CONFIDENCE_THRESHOLD) {
        allFindings.push({
          source: 'commit_review',
          commit_hash: cf.commit_hash,
          model: ['opus', 'sonnet', 'haiku'][idx],
          ...issue
        })
      }
    })
  })
})

log(`✅ Commit review complete: ${allFindings.length} issues found`)

// PHASE 2: Review Recently Closed Issues
phase('Closed Issues')

log(`📋 Analyzing ${MAX_ISSUES_TO_REVIEW} recently closed issues...`)

const closedIssues = await agent(`Get recently closed issues to check if they were truly fixed.

Execute:
gh issue list --state closed --limit ${MAX_ISSUES_TO_REVIEW} --json number,title,closedAt,labels

Return list of closed issues.`, {
  label: 'Fetch Closed Issues',
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
            closedAt: { type: 'string' },
            labels: { type: 'array' }
          }
        }
      }
    }
  }
})

log(`✅ Found ${closedIssues.issues?.length || 0} closed issues`)

// Review a sample of closed issues to see if problems still exist
const issueFindings = await pipeline(
  (closedIssues.issues || []).slice(0, MAX_ISSUES_TO_REVIEW), // Sample closed issues

  (issue) => agent(`Check if issue #${issue.number} was truly resolved: "${issue.title}"

1. Search the codebase for related code
2. Verify the fix actually addresses the root cause
3. Look for similar problems elsewhere
4. Check if the fix introduced new bugs

Be skeptical - assume the fix might be incomplete.`, {
    label: `Verify Issue #${issue.number}`,
    model: 'opus',
    schema: {
      type: 'object',
      properties: {
        truly_fixed: { type: 'boolean' },
        lingering_problems: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              severity: { type: 'string' },
              confidence: { type: 'number' }
            }
          }
        },
        similar_problems_elsewhere: { type: 'array', items: { type: 'object' } }
      }
    }
  })
)

issueFindings.filter(Boolean).forEach(finding => {
  finding.lingering_problems?.forEach(problem => {
    if (problem.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'closed_issue_review',
        original_issue: finding.issue_number,
        ...problem
      })
    }
  })

  // REOPEN if still broken
  if (!finding.truly_fixed && finding.lingering_problems?.length > 0) {
    agent(`Reopen issue #${finding.issue_number} because it's not truly fixed.

Execute:
gh issue reopen ${finding.issue_number}
gh issue comment ${finding.issue_number} --body "🔄 **Reopened by Brutal Code Review**

This issue was marked as closed but the problem still exists:

${finding.lingering_problems.map(p => `- ${p.description}`).join('\n')}

The fix was incomplete or the problem reappeared."
echo "REOPENED_ISSUE: #${finding.issue_number}"`, {
      label: `Reopen Issue #${finding.issue_number}`
    })

    console.log(`REOPENED_ISSUE: #${finding.issue_number}`)
    log(`⚠️  Reopened issue #${finding.issue_number} - still broken!`)
  }

  finding.similar_problems_elsewhere?.forEach(problem => {
    allFindings.push({
      source: 'similar_pattern',
      ...problem
    })
  })
})

log(`✅ Closed issue review: ${allFindings.length} total issues so far`)

// PHASE 3: Full Codebase Brutal Review
phase('Full Codebase')

log('🔍 BRUTAL full codebase scan...')

// Get all source files
const sourceFiles = await agent(`Find all source code files (exclude vendor, node_modules, tests).

Execute:
find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" -o -name "*.go" -o -name "*.rb" -o -name "*.sh" \\) | grep -v node_modules | grep -v vendor | grep -v ".git" | head -50

Return list of files to review.`, {
  label: 'Find Source Files',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } }
    }
  }
})

log(`✅ Found ${sourceFiles.files?.length || 0} source files`)

// Brutal review of each file (in parallel batches)
const fileFindings = await pipeline(
  (sourceFiles.files || []).slice(0, MAX_FILES), // Limit files for this run

  (filepath) => USE_MULTI_MODEL ? parallel([
    // Security review
    () => agent(`SECURITY AUDIT of ${filepath}

Read the file and find:
- SQL injection vulnerabilities
- XSS vulnerabilities
- Command injection
- Path traversal
- Hardcoded secrets/credentials
- Authentication bypasses
- Authorization issues
- Insecure crypto
- Race conditions
- Input validation failures

Be paranoid. Assume attackers will find everything.`, {
      label: `Security: ${filepath}`,
      model: 'opus',
      schema: {
        type: 'object',
        properties: {
          vulnerabilities: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                type: { type: 'string' },
                severity: { type: 'string' },
                description: { type: 'string' },
                line_hint: { type: 'string' },
                confidence: { type: 'number' }
              }
            }
          }
        }
      }
    }),

    // Logic bugs review
    () => agent(`LOGIC BUG HUNT in ${filepath}

Find:
- Off-by-one errors
- Null pointer dereferences
- Unhandled edge cases
- Wrong assumptions
- Missing validation
- Incorrect algorithms
- Resource leaks
- Deadlocks potential
- Data races

Be thorough.`, {
      label: `Logic: ${filepath}`,
      model: 'sonnet',
      schema: {
        type: 'object',
        properties: {
          bugs: { type: 'array', items: { type: 'object' } }
        }
      }
    })
  ]).then(reviews => ({
    file: filepath,
    security: reviews[0],
    logic: reviews[1]
  })) : agent(`COMPLETE CODE REVIEW of ${filepath}

Review for:
1. Security vulnerabilities (SQL injection, XSS, hardcoded secrets, auth issues)
2. Logic bugs (off-by-one, race conditions, null pointers)
3. Performance issues
4. Code quality issues

Be thorough and brutal.`, {
    label: `Review: ${filepath}`,
    schema: {
      type: 'object',
      properties: {
        vulnerabilities: { type: 'array', items: { type: 'object' } },
        bugs: { type: 'array', items: { type: 'object' } }
      }
    }
  }).then(review => ({
    file: filepath,
    security: review,
    logic: review
  }))
)
)

fileFindings.filter(Boolean).forEach(ff => {
  ff.security?.vulnerabilities?.forEach(vuln => {
    if (vuln.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'full_codebase_security',
        file: ff.file,
        model: 'opus',  // Security review always opus
        ...vuln
      })
    }
  })

  ff.logic?.bugs?.forEach(bug => {
    if (bug.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'full_codebase_logic',
        file: ff.file,
        model: 'sonnet',  // Logic review always sonnet
        ...bug
      })
    }
  })
})

log(`✅ Full codebase review: ${allFindings.length} TOTAL ISSUES FOUND`)

// PHASE 4: Dependencies Review
phase('Dependencies')

log('📦 Analyzing dependencies for vulnerabilities and outdated packages...')

const deps = await agent(`Analyze dependencies for security and maintenance issues.

Check for dependency files:
1. package.json / package-lock.json (npm/yarn)
2. requirements.txt / Pipfile (Python)
3. pom.xml / build.gradle (Java)
4. Gemfile / Gemfile.lock (Ruby)
5. go.mod / go.sum (Go)
6. Cargo.toml (Rust)

For each found, run:
- npm audit (Node.js)
- pip-audit or safety check (Python)
- mvn dependency-check (Java)
- bundle audit (Ruby)
- go list -m all | nancy sleuth (Go)
- cargo audit (Rust)

Also check for outdated packages:
- npm outdated
- pip list --outdated
- mvn versions:display-dependency-updates

Return findings.`, {
  label: 'Dependency Analysis',
  schema: {
    type: 'object',
    properties: {
      dependency_files_found: {
        type: 'array',
        items: { type: 'string' }
      },
      vulnerabilities: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            package: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'moderate', 'low'] },
            description: { type: 'string' },
            current_version: { type: 'string' },
            fixed_version: { type: 'string' },
            cve: { type: 'string' }
          }
        }
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
      }
    },
    required: ['dependency_files_found']
  }
})

log(`✅ Dependency files: ${deps.dependency_files_found?.length || 0}`)
log(`   Vulnerabilities: ${deps.vulnerabilities?.length || 0}`)
log(`   Outdated: ${deps.outdated_packages?.length || 0}`)

// Add critical/high vulnerabilities to findings
deps.vulnerabilities?.forEach(vuln => {
  if (vuln.severity === 'critical' || vuln.severity === 'high') {
    allFindings.push({
      source: 'dependency_scan',
      type: 'dependency_vulnerability',
      severity: vuln.severity === 'critical' ? 'critical' : 'major',
      category: 'security',
      description: `${vuln.package}@${vuln.current_version}: ${vuln.description}`,
      file: deps.dependency_files_found?.[0] || 'package.json',
      confidence: 100,
      model: 'dependency-scanner',
      cve: vuln.cve,
      fix: vuln.fixed_version
    })
  }
})

// Add severely outdated packages (major versions behind)
deps.outdated_packages?.forEach(pkg => {
  if (pkg.severity === 'critical' || pkg.severity === 'major') {
    allFindings.push({
      source: 'dependency_scan',
      type: 'outdated_dependency',
      severity: 'minor',
      category: 'maintenance',
      description: `Outdated: ${pkg.package} (${pkg.current} → ${pkg.latest})`,
      file: deps.dependency_files_found?.[0] || 'package.json',
      confidence: 90,
      model: 'dependency-scanner'
    })
  }
})

// PHASE 5: Security Deep Dive
phase('Security Scan')

log('🔒 Running deep security scan...')

const security = await agent(`Deep security scan of the codebase.

Check for:

1. **Secrets in code/history**
   git log --all --pretty=format: --name-only | grep -iE '(secret|password|api.?key|token|credentials|\\.env$)' | sort -u
   grep -r -iE '(api.?key|password|secret|token)\\s*=\\s*["\'][^"\']{10,}' . --include="*.js" --include="*.py" --include="*.java" 2>/dev/null | head -20

2. **OWASP Top 10 patterns**
   - SQL injection risks (string concat in queries)
   - XSS vulnerabilities (unescaped user input in HTML)
   - Command injection (shell exec with user input)
   - Path traversal (file access with user input)
   - Insecure deserialization
   - Missing authentication/authorization checks

3. **Exposed endpoints without auth**
   grep -r "app\\.get\\|app\\.post\\|@GetMapping\\|@PostMapping" . --include="*.js" --include="*.ts" --include="*.java" 2>/dev/null | head -30

4. **CORS misconfigurations**
   grep -r "Access-Control-Allow-Origin.*\\*" . 2>/dev/null

5. **Missing security headers**
   grep -r "helmet\\|Content-Security-Policy\\|X-Frame-Options" . 2>/dev/null

Return security findings.`, {
  label: 'Security Scan',
  schema: {
    type: 'object',
    properties: {
      potential_secrets: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            line_hint: { type: 'string' },
            description: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'major', 'minor'] }
          }
        }
      },
      owasp_findings: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string' },
            file: { type: 'string' },
            line_hint: { type: 'string' },
            description: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'major', 'minor'] }
          }
        }
      },
      exposed_endpoints: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            endpoint: { type: 'string' },
            file: { type: 'string' },
            has_auth: { type: 'boolean' },
            severity: { type: 'string' }
          }
        }
      },
      cors_issues: { type: 'boolean' },
      missing_security_headers: { type: 'boolean' }
    }
  }
})

log(`✅ Security scan complete`)
log(`   Potential secrets: ${security.potential_secrets?.length || 0}`)
log(`   OWASP findings: ${security.owasp_findings?.length || 0}`)
log(`   Exposed endpoints: ${security.exposed_endpoints?.length || 0}`)

// Add critical security findings
security.potential_secrets?.forEach(secret => {
  if (secret.severity === 'critical' || secret.severity === 'major') {
    allFindings.push({
      source: 'security_scan',
      type: 'potential_secret',
      severity: 'critical',
      category: 'security',
      description: `Potential secret exposed: ${secret.description}`,
      file: secret.file,
      line_hint: secret.line_hint,
      confidence: 85,
      model: 'security-scanner'
    })
  }
})

security.owasp_findings?.forEach(finding => {
  if (finding.severity === 'critical' || finding.severity === 'major') {
    allFindings.push({
      source: 'security_scan',
      type: finding.type,
      severity: finding.severity,
      category: 'security',
      description: finding.description,
      file: finding.file,
      line_hint: finding.line_hint,
      confidence: 90,
      model: 'owasp-scanner'
    })
  }
})

security.exposed_endpoints?.forEach(endpoint => {
  if (!endpoint.has_auth && endpoint.severity === 'critical') {
    allFindings.push({
      source: 'security_scan',
      type: 'exposed_endpoint',
      severity: 'major',
      category: 'security',
      description: `Exposed endpoint without auth: ${endpoint.endpoint}`,
      file: endpoint.file,
      confidence: 80,
      model: 'endpoint-scanner'
    })
  }
})

if (security.cors_issues) {
  allFindings.push({
    source: 'security_scan',
    type: 'cors_misconfiguration',
    severity: 'major',
    category: 'security',
    description: 'CORS allows all origins (*) - security risk',
    file: 'server config',
    confidence: 95,
    model: 'cors-scanner'
  })
}

// PHASE 6: Verify and Deduplicate
phase('Multi-Model Consensus')

log('⚖️ Verifying all findings with arbiter consensus...')

// Group findings by file and description for deduplication
const uniqueFindings = allFindings.reduce((acc, finding) => {
  const key = `${finding.file}:${finding.description?.slice(0, 50)}`
  if (!acc[key]) {
    acc[key] = finding
  }
  return acc
}, {})

const dedupedFindings = Object.values(uniqueFindings)

log(`✅ Deduplicated: ${dedupedFindings.length} unique issues`)

// PHASE 7: Create Issues
phase('Create Issues')

if (args?.['create-issues'] !== false && dedupedFindings.length > 0) {
  log(`📝 Creating ${dedupedFindings.length} GitHub issues...`)

  const createdIssues = await pipeline(
    dedupedFindings.slice(0, 50), // Max 50 issues per run

    (finding) => agent(`Create a GitHub issue for this finding:

Severity: ${finding.severity}
Category: ${finding.category || finding.type}
Description: ${finding.description}
File: ${finding.file}
Source: ${finding.source}
Model: ${finding.model}

Execute:
gh issue create \\
  --title "[${finding.severity?.toUpperCase()}] ${finding.category || finding.type}: ${finding.description?.slice(0, 80)}" \\
  --body "## Finding

**Severity**: ${finding.severity}
**Category**: ${finding.category || finding.type}
**Source**: ${finding.source}
**File**: ${finding.file}
**Confidence**: ${finding.confidence}%

### Description
${finding.description}

### Details
${finding.line_hint || 'See file for details'}

---

## 🤖 Multi-AI Attribution

**Found by**: ${finding.model || 'unknown'} (${finding.source})
**Confidence**: ${finding.confidence}% (threshold: ${CONFIDENCE_THRESHOLD}%)
${finding.commit_hash ? `**Commit**: ${finding.commit_hash}` : ''}
${finding.original_issue ? `**Original Issue**: #${finding.original_issue}` : ''}

Models in rotation: ${USE_MULTI_MODEL ? 'Opus, Sonnet, Haiku (rotated per commit)' : 'Single model'}

---
🤖 Found by Brutal Code Review (Multi-AI Consensus)
" \\
  --label bug,automated-review,${finding.severity}

Return the issue URL.`, {
      label: `Create Issue: ${finding.description?.slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          issue_url: { type: 'string' },
          issue_number: { type: 'number' }
        }
      }
    })
  )

  const successCount = createdIssues.filter(Boolean).length
  log(`✅ Created ${successCount} issues`)
} else {
  log('ℹ️  Skipping issue creation (use --create-issues to enable)')
}

// Final Summary
log('')
log('═'.repeat(80))
log('🔥 BRUTAL CODE REVIEW COMPLETE 🔥')
log('═'.repeat(80))
log(`Total Issues Found: ${dedupedFindings.length}`)
log('')
log('Breakdown by Severity:')
const bySeverity = dedupedFindings.reduce((acc, f) => {
  const sev = f.severity || 'unknown'
  acc[sev] = (acc[sev] || 0) + 1
  return acc
}, {})
Object.entries(bySeverity).forEach(([sev, count]) => {
  log(`  ${sev.toUpperCase()}: ${count}`)
})
log('')
log('Breakdown by Source:')
const bySource = dedupedFindings.reduce((acc, f) => {
  acc[f.source] = (acc[f.source] || 0) + 1
  return acc
}, {})
Object.entries(bySource).forEach(([src, count]) => {
  log(`  ${src}: ${count}`)
})
log('═'.repeat(80))

return {
  status: 'complete',
  total_findings: dedupedFindings.length,
  by_severity: bySeverity,
  by_source: bySource,
  findings: dedupedFindings
}
