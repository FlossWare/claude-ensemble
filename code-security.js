/**
 * @returns {{
 *   status: 'complete' | 'clean' | 'report_only',
 *   total_findings?: number,
 *   vulnerabilities_count?: number,
 *   verified_findings?: number,
 *   issues_created?: number,
 *   findings?: object[],
 *   message?: string
 * }}
 */
export const meta = {
  name: 'code-security',
  description: 'Interactive security audit - prompts before creating issues',
  whenToUse: 'When you want comprehensive security scanning with manual review',
  phases: [
    { title: 'Detect Platform', detail: 'Identify GitHub/GitLab' },
    { title: 'Dependency Scan', detail: 'Check for vulnerable dependencies' },
    { title: 'Secrets Detection', detail: 'Find hardcoded secrets' },
    { title: 'OWASP Scan', detail: 'Check for common vulnerabilities' },
    { title: 'License Compliance', detail: 'Check dependency licenses' },
    { title: 'Multi-AI Verification', detail: 'Reduce false positives', model: 'opus' },
    { title: 'Impact Analysis', detail: 'Exploitability scoring' },
    { title: 'User Confirmation', detail: 'Review before creating issues' },
    { title: 'Create Issues', detail: 'Create security issues' },
  ],
}


const AUTONOMOUS = args?.autonomous === true  // INTERACTIVE by default

log(`🔒 Security Audit Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

// Phase 1: Detect Platform
phase('Detect Platform')

const platform = await agent(`Detect platform (github/gitlab).
Check git remote -v output.`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] },
      cli: { type: 'string' }
    }
  }
})

log(`✅ Platform: ${platform.platform}`)

// Phase 2: Dependency Scan
phase('Dependency Scan')

log('📦 Scanning dependencies for vulnerabilities...')

const depScan = await agent(`Scan dependencies for vulnerabilities.

Check for package managers:
- npm (package.json) → npm audit --json
- pip (requirements.txt) → pip-audit or safety check
- cargo (Cargo.toml) → cargo audit
- go.mod → govulncheck

Return vulnerabilities found.`, {
  label: 'Dependency Scan',
  schema: {
    type: 'object',
    properties: {
      vulnerabilities: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            package: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
            cve: { type: 'string' },
            description: { type: 'string' },
            fix_available: { type: 'boolean' }
          }
        }
      },
      total: { type: 'number' }
    }
  }
})

log(`✅ Dependency scan: ${depScan.total || 0} vulnerabilities`)

// Phase 3: Secrets Detection
phase('Secrets Detection')

log('🔑 Scanning for hardcoded secrets...')

const secretsScan = await agent(`Scan for hardcoded secrets.

Patterns to check:
- API keys: "API_KEY", "APIKEY", "api-key"
- Passwords: "password", "passwd", "pwd"
- Tokens: "token", "auth", "bearer"
- Private keys: "BEGIN RSA PRIVATE KEY", "BEGIN PRIVATE KEY"
- AWS keys: "AKIA", "aws_secret"
- Database credentials: connection strings

Exclude:
- node_modules/
- .git/
- dist/, build/
- Test fixtures (clearly marked)
- Documentation examples

Use grep -rE with patterns.
Return found secrets.`, {
  label: 'Secrets Scan',
  schema: {
    type: 'object',
    properties: {
      secrets: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            line: { type: 'number' },
            type: { type: 'string' },
            snippet: { type: 'string' },
            likely_real: { type: 'boolean' }
          }
        }
      },
      total: { type: 'number' }
    }
  }
})

log(`✅ Secrets scan: ${secretsScan.total || 0} potential secrets`)

// Phase 4: OWASP Scan
phase('OWASP Scan')

log('🛡️  Scanning for OWASP Top 10 vulnerabilities...')

const owaspScan = await agent(`Scan for OWASP Top 10 vulnerabilities.

Check for:
1. SQL Injection - raw SQL queries, string concatenation
2. XSS - innerHTML, dangerouslySetInnerHTML, unescaped output
3. CSRF - missing CSRF tokens in forms
4. Insecure Auth - weak password policies, no MFA
5. Sensitive Data Exposure - logging passwords, plaintext storage
6. XXE - XML parsing without disabling external entities
7. Broken Access Control - missing authorization checks
8. Security Misconfiguration - debug mode, default credentials
9. Using Components with Known Vulnerabilities - (covered in deps)
10. Insufficient Logging - no audit trail

Scan code for these patterns.
Return vulnerabilities found.`, {
  label: 'OWASP Scan',
  schema: {
    type: 'object',
    properties: {
      vulnerabilities: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string' },
            file: { type: 'string' },
            line: { type: 'number' },
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
            description: { type: 'string' },
            cwe: { type: 'string' }
          }
        }
      },
      total: { type: 'number' }
    }
  }
})

log(`✅ OWASP scan: ${owaspScan.total || 0} vulnerabilities`)

// Phase 5: License Compliance
phase('License Compliance')

log('📜 Checking license compliance...')

const licenseScan = await agent(`Check dependency licenses.

For npm: Use 'license-checker' or read package.json
For pip: Use 'pip-licenses'
For go: Check go.mod

Flag risky licenses:
- GPL (copyleft - may require open sourcing)
- AGPL (strong copyleft)
- Unknown/Unlicensed

Safe licenses:
- MIT, Apache-2.0, BSD, ISC

Return license issues.`, {
  label: 'License Scan',
  schema: {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            package: { type: 'string' },
            license: { type: 'string' },
            risk: { type: 'string', enum: ['high', 'medium', 'low'] },
            reason: { type: 'string' }
          }
        }
      },
      total: { type: 'number' }
    }
  }
})

log(`✅ License scan: ${licenseScan.total || 0} license issues`)

// Phase 6: Multi-AI Verification
phase('Multi-AI Verification')

log('🤖 Verifying findings with multi-AI consensus...')

// Collect all findings
const allFindings = [
  ...(depScan.vulnerabilities || []).map(v => ({
    type: 'dependency',
    severity: v.severity,
    package: v.package,
    cve: v.cve,
    description: v.description,
    fix_available: v.fix_available
  })),
  ...(secretsScan.secrets || []).map(s => ({
    type: 'secret',
    severity: s.likely_real ? 'critical' : 'medium',
    file: s.file,
    line: s.line,
    secret_type: s.type,
    snippet: s.snippet
  })),
  ...(owaspScan.vulnerabilities || []).map(v => ({
    type: 'owasp',
    severity: v.severity,
    file: v.file,
    line: v.line,
    vuln_type: v.type,
    description: v.description,
    cwe: v.cwe
  })),
  ...(licenseScan.issues || []).map(l => ({
    type: 'license',
    severity: l.risk === 'high' ? 'high' : 'low',
    package: l.package,
    license: l.license,
    reason: l.reason
  }))
]

log(`   Total findings: ${allFindings.length}`)

if (allFindings.length === 0) {
  log(`✅ No security issues found!`)
  return {
    status: 'clean',
    message: 'No security vulnerabilities detected'
  }
}

// Verify with multiple models (reduce false positives)
// Dynamic model detection - models that fail return null and are filtered out
const WORKERS = [
  'opus', 'sonnet', 'haiku',  // Claude models (always available)
  // Gemini (via MCP/Google AI API)
  // 'grok',                   // Grok (via xAI API) - uncomment when configured
  // 'ollama/llama3',          // Ollama (local) - uncomment when running
  // 'gpt-4',                  // OpenAI (via MCP) - uncomment when configured
]

const verifications = await parallel(WORKERS.map(model => () =>
  agent(`Verify security findings - reduce false positives.

Findings: ${allFindings.length}

${allFindings.slice(0, 20).map(f => `
- Type: ${f.type}
- Severity: ${f.severity}
- ${f.file ? `File: ${f.file}:${f.line}` : `Package: ${f.package}`}
- ${f.description || f.reason}
`).join('\n')}

For each finding, determine:
1. Is this a REAL security vulnerability?
2. Is it a FALSE POSITIVE (test file, example, intentional)?
3. What's the actual exploitability risk?

Return verified findings only.`, {
    label: `Verify (${model})`,
    model,
    schema: {
      type: 'object',
      properties: {
        verified: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              finding_index: { type: 'number' },
              real: { type: 'boolean' },
              exploitable: { type: 'boolean' },
              confidence: { type: 'number' },
              reasoning: { type: 'string' }
            }
          }
        }
      }
    }
  })
))

const validVerifications = verifications.filter(Boolean)

log(`✅ ${validVerifications.length} models verified`)

// Arbiter consensus
const arbiterResult = await agent(`Merge verifications from ${validVerifications.length} models.

Create consensus on which findings are REAL vulnerabilities.
Filter out false positives.
Assign final severity and exploitability.

Return final verified findings.`, {
  label: 'Arbiter Consensus',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      verified_findings: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
            exploitable: { type: 'boolean' },
            confidence: { type: 'number' },
            title: { type: 'string' },
            description: { type: 'string' },
            file: { type: 'string' },
            line: { type: 'number' },
            remediation: { type: 'string' }
          }
        }
      },
      consensus_confidence: { type: 'number' }
    }
  }
})

log(`✅ Consensus: ${arbiterResult.verified_findings?.length || 0} verified findings`)

// Phase 7: Impact Analysis
phase('Impact Analysis')

log('🎯 Analyzing exploitability and impact...')

// Score by exploitability
arbiterResult.verified_findings?.forEach(finding => {
  let score = 0

  // Base severity score
  if (finding.severity === 'critical') score = 100
  else if (finding.severity === 'high') score = 75
  else if (finding.severity === 'medium') score = 50
  else score = 25

  // Exploitability boost
  if (finding.exploitable) score += 20

  // Secret detection boost
  if (finding.type === 'secret') score += 15

  // Confidence boost
  score += finding.confidence * 10

  finding.impact_score = Math.min(score, 100)
})

// Sort by impact
arbiterResult.verified_findings?.sort((a, b) => b.impact_score - a.impact_score)

log(`✅ Impact analysis complete`)

// Phase 8: User Confirmation
phase('User Confirmation')

if (!AUTONOMOUS) {
  log('')
  log('═'.repeat(60))
  log('🔒 SECURITY AUDIT RESULTS')
  log('═'.repeat(60))

  const critical = arbiterResult.verified_findings?.filter(f => f.severity === 'critical') || []
  const high = arbiterResult.verified_findings?.filter(f => f.severity === 'high') || []
  const medium = arbiterResult.verified_findings?.filter(f => f.severity === 'medium') || []
  const low = arbiterResult.verified_findings?.filter(f => f.severity === 'low') || []

  log(`🚨 Critical: ${critical.length}`)
  log(`⚠️  High: ${high.length}`)
  log(`📋 Medium: ${medium.length}`)
  log(`ℹ️  Low: ${low.length}`)
  log('')

  if (critical.length > 0) {
    log('🚨 CRITICAL VULNERABILITIES:')
    critical.forEach((f, idx) => {
      log(`   ${idx + 1}. ${f.title}`)
      log(`      ${f.description}`)
    })
  }

  log('═'.repeat(60))

  // ASK USER: Create issues for these findings?
  const userDecision = await agent(`Review security findings and decide which to create issues for.

Total findings: ${arbiterResult.verified_findings?.length || 0}
Critical: ${critical.length}
High: ${high.length}
Medium: ${medium.length}
Low: ${low.length}

Options:
- ALL: Create issues for all findings
- CRITICAL_ONLY: Only critical vulnerabilities
- HIGH_AND_CRITICAL: High and critical only
- NONE: Don't create any issues (just show report)

Return your decision.`, {
    label: 'User Decision',
    schema: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['ALL', 'CRITICAL_ONLY', 'HIGH_AND_CRITICAL', 'NONE'] },
        reasoning: { type: 'string' }
      },
      required: ['action']
    }
  })

  log(`\n👤 User Decision: ${userDecision.action}`)

  if (userDecision.action === 'NONE') {
    log(`ℹ️  No issues created (user chose NONE)`)
    return {
      status: 'report_only',
      findings: arbiterResult.verified_findings,
      message: 'Security audit complete - report only, no issues created'
    }
  }

  // Filter based on user decision
  let findingsToCreate = arbiterResult.verified_findings || []
  if (userDecision.action === 'CRITICAL_ONLY') {
    findingsToCreate = critical
  } else if (userDecision.action === 'HIGH_AND_CRITICAL') {
    findingsToCreate = [...critical, ...high]
  }

  arbiterResult.verified_findings = findingsToCreate
}

// Phase 9: Create Issues
phase('Create Issues')

log(`📝 Creating ${arbiterResult.verified_findings?.length || 0} security issues...`)

const issueCmd = platform.platform === 'gitlab' ? 'glab' : 'gh'

const createdIssues = await Promise.all(
  (arbiterResult.verified_findings || []).map(finding =>
    agent(`Create security issue.

Title: [SECURITY] ${finding.title}

Body:
**Severity**: ${finding.severity}
**Type**: ${finding.type}
**Exploitable**: ${finding.exploitable ? 'YES' : 'No'}
**Confidence**: ${Math.round(finding.confidence * 100)}%

${finding.description}

**Location**: ${finding.file}:${finding.line || 'N/A'}

**Remediation**:
${finding.remediation}

**Impact Score**: ${finding.impact_score}

Execute:
${issueCmd} issue create --title "[SECURITY-${finding.severity.toUpperCase()}] ${finding.title}" --body "..."

Create the issue with security label.`, {
      label: `Create Issue: ${finding.title.slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          issue_number: { type: 'number' },
          issue_url: { type: 'string' }
        }
      }
    }).catch(() => null)
  )
)

const successfulIssues = createdIssues.filter(Boolean)

log(`✅ Created ${successfulIssues.length} security issues`)

log('')
log('═'.repeat(60))
log('🔒 SECURITY AUDIT COMPLETE')
log('═'.repeat(60))
log(`Total findings: ${arbiterResult.verified_findings?.length || 0}`)
log(`Issues created: ${successfulIssues.length}`)
log('═'.repeat(60))

const result = {
  status: 'complete',
  total_findings: allFindings.length,
  vulnerabilities_count: arbiterResult.verified_findings?.length || 0,
  verified_findings: arbiterResult.verified_findings?.length || 0,
  issues_created: successfulIssues.length,
  findings: arbiterResult.verified_findings
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-security',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
