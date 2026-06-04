# Code Review Workflow - Complete Overview

**Updated:** 2026-06-04  
**Now includes:** Dependencies & Security scanning

## What `/code-review` Does

Comprehensive autonomous code review with **5 review types** and **7 phases**:

### Phase 1: Recent Commits ✅
Reviews last 30 days of commits (up to 5 commits)
- **3 AI workers per commit** (Opus, Sonnet, Haiku - rotated)
- Security vulnerabilities
- Logic bugs
- Performance issues
- Code quality
- Error handling

### Phase 2: Closed Issues ✅
Reviews recently closed issues (up to 5)
- Checks if issues still broken
- Finds incomplete fixes
- Detects regressions
- Auto-reopens broken issues

### Phase 3: Full Codebase ✅
Brutal scan of entire codebase (up to 10 files)
- **3 AI workers** review each file
- Security, logic, performance
- Comprehensive issue detection

### Phase 4: Dependencies ⭐ NEW
Scans for dependency issues
- **npm audit** (Node.js)
- **pip-audit** (Python)
- **bundle audit** (Ruby)
- **cargo audit** (Rust)
- **mvn dependency-check** (Java)
- Finds CVEs, outdated packages, breaking changes

### Phase 5: Security Scan ⭐ NEW
Deep security analysis
- Secrets in code/git history
- OWASP Top 10 vulnerabilities:
  - SQL injection
  - XSS
  - Command injection
  - Path traversal
  - Insecure deserialization
- Exposed endpoints without auth
- CORS misconfigurations
- Missing security headers

### Phase 6: Multi-Model Consensus ✅
Deduplicates and verifies findings
- Groups similar issues
- Removes duplicates
- Filters by confidence threshold

### Phase 7: Create Issues ✅
Auto-creates GitHub/GitLab issues
- Up to 50 issues per run
- Full attribution (which AI found it)
- Severity labels
- Confidence scores

## Total AI Agents Per Run

**Approximate:**
- Commits: 3 workers × 5 commits = **15 agents**
- Issues: 3 workers × 5 issues = **15 agents**
- Codebase: 3 workers × 10 files = **30 agents**
- Dependencies: **1 agent**
- Security: **1 agent**
- **Total: ~60 agents**

## Usage

```bash
/code-review                          # Full review (all 5 types)
/code-review --days=60                # Review last 60 days of commits
/code-review --maxCommits=10          # Review more commits
/code-review --maxFiles=20            # Review more files
/code-review --autonomous=false       # Interactive mode
/code-review --multiModel=false       # Single model (faster)
/code-review --create-issues=false    # Review only, no issues
```

## Cost Estimates

**Per run (approximate):**
- **Full review:** ~$15-25 (60 agents)
- **Single model:** ~$8-12 (20 agents)
- **Dependencies only:** ~$0.50 (1 agent)
- **Security only:** ~$0.50 (1 agent)

## When to Run

- **Daily/Weekly:** Continuous quality monitoring
- **Pre-release:** Before major releases
- **Post-merge:** After merging large PRs
- **Monthly:** Comprehensive cleanup
- **CI/CD:** Automated quality gates

## Output

Creates GitHub/GitLab issues for:
- Critical security vulnerabilities
- Major bugs
- Performance issues
- Dependency vulnerabilities
- OWASP security risks
- Code quality issues

## Related Workflows

- `/code-test-review` - Test quality analysis
- `/code-hygiene-review` - Repository cleanup
- `/code-solve` - Auto-resolve issues
- `/pr-review` - Continuous PR monitoring

---

**Version:** 2.0 (with Dependencies & Security)  
**File:** `~/.claude/workflows/code-review.js`
