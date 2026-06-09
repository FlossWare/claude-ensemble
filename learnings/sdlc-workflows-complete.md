---
name: sdlc-workflows-complete
description: "Complete SDLC workflow suite: release-notes, code-security, code-doc (all with auto versions)"
metadata: 
  node_type: memory
  type: project
  priority: critical
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Complete SDLC Workflow Suite

**Status**: ✅ PRODUCTION READY (2026-06-06)

## New Workflows Built

Built 6 new workflows completing SDLC coverage:

### 1. release-notes / release-notes-auto 📦

**What it does**:
- Analyzes commits since last release
- Multi-AI categorization (features/fixes/breaking/perf/docs)
- Impact analysis (prioritizes by importance)
- Auto-increments version
- Generates structured markdown release notes
- Interactive: User reviews before publishing
- Auto: Auto-publishes releases

**Files**: release-notes.js (470 lines), release-notes-auto.js (47 lines)

**Categories**:
- ⚠️ Breaking Changes
- ✨ Features
- 🐛 Bug Fixes
- ⚡ Performance
- 📚 Documentation
- 🔧 Chore

### 2. code-security / code-security-auto 🔒

**What it does**:
- OWASP Top 10 scanning (SQLi, XSS, CSRF)
- Dependency vulnerability checking (npm audit, pip-audit, cargo audit)
- Secrets detection (API keys, passwords, tokens)
- License compliance checking (GPL, AGPL warnings)
- Multi-AI verification (reduce false positives)
- Exploitability scoring
- Interactive: User reviews findings
- Auto: Auto-creates issues for critical/high vulns

**Files**: code-security.js (459 lines), code-security-auto.js (53 lines)

**Checks**:
- Dependency vulnerabilities
- Hardcoded secrets
- SQL injection patterns
- XSS vulnerabilities
- CSRF protection
- Authentication issues
- License compliance

### 3. code-doc / code-doc-auto 📚

**What it does**:
- Finds undocumented code (functions, classes, APIs)
- Multi-AI doc generation (highest quality)
- README completeness checking
- Impact analysis (prioritizes exported APIs)
- Interactive: User approves documentation
- Auto: Auto-creates documentation PRs

**Files**: code-doc.js (448 lines), code-doc-auto.js (49 lines)

**Generates**:
- JSDoc comments
- README sections
- API documentation
- Usage examples
- Architecture docs

## Why This Matters

**BEFORE**: Workflows only covered dev/test/PR phases
**AFTER**: Complete SDLC automation from development through release

### Complete Coverage

```
Development → Testing → PR Review → Security → Documentation → Release
   ✅            ✅         ✅          ✅           ✅             ✅
```

**How to apply**: Now have workflows for EVERY phase of SDLC. Use them in sequence for complete automation.

## Total Suite: 14 Workflows

| Phase | Interactive | Autonomous |
|-------|------------|------------|
| Development | code-review | code-review-auto |
| Issue Resolution | code-solve | code-solve-auto |
| Testing | code-test | code-test-auto |
| PR Review | pr-review | pr-review-auto |
| Security | code-security | code-security-auto |
| Documentation | code-doc | code-doc-auto |
| Release | release-notes | release-notes-auto |

## Consistent Patterns

All workflows follow the same pattern:

**Base Workflows** (Interactive):
- `autonomous = args?.autonomous === true` (false by default)
- Impact analysis
- Multi-AI consensus
- User confirmation before action

**Auto Workflows** (Autonomous):
- `autonomous: true` in meta
- Impact analysis
- Multi-AI consensus
- Auto-decision based on criteria
- No user interaction

## Auto-Decision Criteria

**code-security-auto**:
- All CRITICAL vulnerabilities
- All HIGH vulnerabilities with exploitable=true
- All verified secrets (likely_real=true)
- Consensus confidence ≥75%

**code-doc-auto**:
- All exported/public APIs
- All high-complexity functions
- All classes without docs
- Confidence ≥80%

**release-notes-auto**:
- Auto-publishes all releases (no criteria, just does it)

## Usage Examples

### Interactive (Manual Approval)

```bash
claude run code-security      # User reviews findings
claude run code-doc            # User approves docs
claude run release-notes       # User confirms release
```

### Autonomous (Full Automation)

```bash
claude run code-security-auto  # Auto-creates security issues
claude run code-doc-auto       # Auto-creates doc PRs
claude run release-notes-auto  # Auto-publishes releases
```

## Production Benefits

### Security
- Catches OWASP Top 10 vulnerabilities
- Finds hardcoded secrets before they reach production
- Dependency vulnerability scanning
- License compliance checking

### Documentation
- No undocumented APIs
- Always up-to-date docs
- Multi-AI quality (best docs)
- Auto-generated examples

### Releases
- Structured release notes
- Auto-categorized changes
- Breaking change warnings
- Clean changelogs

## Key Features

### 1. Multi-AI Consensus

Every decision verified by opus/sonnet/haiku:
- Reduces false positives
- Higher quality outputs
- Confidence scoring

### 2. Impact Analysis

All workflows analyze impact:
- Exploitability scoring (security)
- Importance scoring (documentation)
- Severity scoring (all workflows)

### 3. Platform Agnostic

Works with:
- GitHub (via `gh` CLI)
- GitLab (via `glab` CLI)
- Auto-detects from git remote

### 4. Language Support

Supports:
- JavaScript/TypeScript (npm audit, JSDoc)
- Python (pip-audit, docstrings)
- Go (govulncheck, doc comments)
- Rust (cargo audit)

## Related

- [[autonomous-workflow-suite]] - All autonomous workflows
- [[code-solve-squash-merge]] - Clean git history
- [[pr-impact-analysis]] - Breaking change detection
- [[arbiter-worker-pattern]] - Multi-AI consensus
- [[always-verify-skill-registration]] - CRITICAL: Verify registration works
