---
name: code-hygiene-review
description: Repository hygiene review - stale branches, old issues/PRs, dependencies, git history (AUTONOMOUS)
tags: [maintenance, hygiene, cleanup, autonomous]
---

# Code Hygiene Review - Repository Cleanup Analysis

Autonomous review of repository health: branches, issues, PRs, dependencies, git history.

## Usage

```bash
/code-hygiene-review                  # Full hygiene analysis
/code-hygiene-review --staleDays=180  # Different stale threshold
/code-hygiene-review --autonomous=false # Interactive mode
```

## What It Reviews

### 1. **Stale Branches**
- Merged branches not deleted
- Branches with no activity (90+ days)
- Branches without remote tracking
- Long-lived feature branches

### 2. **Stale Issues**
- No activity in 90+ days
- No comments (abandoned)
- Duplicate issues
- Issues marked "won't fix" but still open

### 3. **Stale PRs**
- No activity in 90+ days
- Abandoned drafts
- Awaiting review for extended period
- PRs with merge conflicts

### 4. **Git History Problems**
- Large binaries (>1MB)
- Potential secrets in history
- Force push history
- Files that should use Git LFS

### 5. **Dependencies**
- Outdated packages
- Security vulnerabilities
- Unused dependencies
- Breaking changes in updates

## Output

Creates a **single hygiene report issue** with:
- All findings categorized
- Recommended actions
- Severity levels
- Cleanup checklist

## Example

```bash
$ /code-hygiene-review

🧹 REPOSITORY HYGIENE REVIEW
═══════════════════════════════════════
Mode: AUTONOMOUS
Stale threshold: 90 days
═══════════════════════════════════════

🌿 Analyzing branches...
✅ Found 47 branches
   Merged: 12
   Stale: 8

📋 Analyzing issues...
✅ Found 156 open issues
   Stale: 23

🔀 Analyzing pull requests...
✅ Found 12 open PRs
   Stale: 3

📜 Analyzing git history...
✅ Large files: 4
   Potential secrets: 2

📦 Analyzing dependencies...
✅ Dependency files: 3
   Outdated: 15
   Vulnerabilities: 2

⚖️  Deduplicating findings...
✅ 57 unique findings

═══════════════════════════════════════
✅ HYGIENE REVIEW COMPLETE

Findings by category:
  git_hygiene: 24
  issue_hygiene: 23
  pr_hygiene: 3
  dependencies: 15
  security: 2

Total cleanup opportunities: 57
═══════════════════════════════════════

✅ Created hygiene report issue #105
```

## Actions Recommended

Each finding includes an action:
- `safe_to_delete` - Merged branches
- `review_or_close` - Stale issues/PRs
- `close_or_rebase` - Conflicted PRs
- `update_dependency` - Outdated packages
- `update_immediately` - Security vulnerabilities
- `review_immediately` - Potential secrets
- `consider_git_lfs_or_remove` - Large binaries

## Options

- `--staleDays=N` - Days before considering stale (default: 90)
- `--maxBranches=N` - Max branches to analyze (default: 50)
- `--maxIssues=N` - Max issues to analyze (default: 100)
- `--maxPRs=N` - Max PRs to analyze (default: 50)
- `--autonomous=false` - Interactive mode

## When to Run

- **Monthly** - Regular maintenance
- **Before major releases** - Clean house
- **Quarterly** - Deep cleanup
- **After team changes** - New ownership clarity

## Integration

### Scheduled Monthly Cleanup
```bash
# Run first Monday of month
0 9 1 * 1 /code-hygiene-review --auto
```

### CI/CD Alert
```yaml
- name: Hygiene Check
  run: /code-hygiene-review
  schedule:
    - cron: '0 0 1 * *'  # Monthly
```

---

**Version**: 1.0  
**Created**: 2026-06-04  
**Global**: Works on all projects
