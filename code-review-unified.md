# Code Review - Unified Multi-Model Review with Strategies

**Comprehensive code review with 5 review types + multi-AI consensus**

## Features

- **Auto-Sync with Remote** - Always fetches and rebases before review to ensure latest code
- **5 Review Types** - Commits, Issues, Codebase, Dependencies, Security
- **Multi-AI Consensus** - Opus, Sonnet, Haiku with rotating arbiters
- **Configurable Workers** - Choose which AI models review
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket
- **Autonomous** - Auto-creates issues, no manual approval needed

## Pre-Review Sync

Before starting any review, the workflow automatically:
1. **Detects platform** (GitHub, GitLab, or Bitbucket)
2. **Fetches latest changes** from remote (`git fetch origin`)
3. **Rebases current branch** onto `origin/main` (configurable via branch option)
4. **Checks for conflicts or failures** - if found, stops and reports them

**⚠️ Important**: The default branch is assumed to be `main`. If your repository uses a different default branch (e.g., `master`, `develop`), the sync will fail. In this case, manually sync before running the review, or the workflow will detect the failure and stop.

**Sync status handling**:
- **success**: Successfully rebased onto remote
- **up_to_date**: Already current with remote
- **conflicts**: Rebase conflicts detected - workflow stops, manual resolution required
- **failed**: Sync failed (e.g., branch doesn't exist, network error) - workflow stops

This ensures you're always reviewing the most up-to-date code, not stale local changes.

## What It Reviews

### 1. **Recent Commits** (Last 30 days)
- Security vulnerabilities
- Logic bugs
- Performance issues
- Code quality
- Error handling gaps

### 2. **Closed Issues** (Recently closed)
- Issues still broken
- Incomplete fixes
- New issues from bug fixes
- Regressions

### 3. **Full Codebase** (Up to 10 files)
- Comprehensive security scan
- Logic correctness
- Performance bottlenecks
- Code quality issues

### 4. **Dependencies** ⭐ NEW
- Security vulnerabilities (CVEs)
- Outdated packages
- Breaking changes
- License compliance

### 5. **Security Deep Dive** ⭐ NEW
- Secrets in code/history
- OWASP Top 10 vulnerabilities
- Exposed endpoints without auth
- CORS misconfigurations
- Missing security headers
- Command/SQL injection risks
- XSS vulnerabilities

## Consensus Strategies

### 1. **rotating** (Most Democratic) ⭐ RECOMMENDED
```bash
/code-review --strategy=rotating
```
- Different arbiter each time (Opus → Sonnet → Haiku → repeat)
- Prevents single-model bias
- Most fair consensus
- **Use for**: Critical code, production, high-stakes

### 2. **single** (Fastest)
```bash
/code-review --strategy=single --arbiter=opus
```
- One arbiter judges all (default: Opus)
- Fastest, lowest cost
- Potential bias
- **Use for**: Quick scans, lower-risk code

### 3. **majority** (No Arbiter Overhead)
```bash
/code-review --strategy=majority
```
- Simple vote count, no arbiter
- Very fast
- Democratic
- **Use for**: Clear-cut issues, speed priority

### 4. **weighted** (Confidence-Based)
```bash
/code-review --strategy=weighted
```
- Votes weighted by confidence scores
- Higher confidence = more influence
- Quality-aware
- **Use for**: Complex issues, uncertain cases

### 5. **pairwise** (Balanced)
```bash
/code-review --strategy=pairwise
```
- Workers review in pairs
- Cross-validation
- Balanced approach
- **Use for**: Medium complexity

## Worker Configuration

### Default Workers
```bash
/code-review  # Uses: opus, sonnet, haiku
```

### Custom Workers
```bash
/code-review --workers=opus,sonnet,haiku,gemini  # 4 models
/code-review --workers=opus,sonnet              # 2 models (faster)
/code-review --workers=opus,haiku               # Skip sonnet
```

## Arbiter Selection

### Auto (Based on Strategy)
```bash
/code-review --strategy=rotating  # Auto-rotates
```

### Manual Override
```bash
/code-review --arbiter=opus    # Always Opus
/code-review --arbiter=sonnet  # Always Sonnet
/code-review --arbiter=haiku   # Always Haiku
```

## Conflict Handling

If git rebase conflicts are detected during sync, the workflow will:
1. **Stop immediately** before starting any review
2. **Report conflict files** to the user
3. **Return a conflicts status**

Example output:
```
🔧 Detecting platform and syncing with remote...
✅ Platform: gitlab (using glab)
⚠️ Rebase conflicts detected: src/main.js, package.json

Cannot proceed with review - resolve conflicts first
```

To resolve:
```bash
# First, abort the failed rebase from the workflow
git rebase --abort

# Manually sync with the correct default branch
git fetch origin
git rebase origin/<your-default-branch>  # e.g., origin/main or origin/master

# Resolve any conflicts
git status
# Fix conflicted files
git add <resolved-files>
git rebase --continue

# Then re-run code review
/code-review
```

## Usage Examples

### Example 1: Brutal Review (Most Thorough)
```bash
/code-review --strategy=rotating --workers=opus,sonnet,haiku,gemini
```
- 4 worker models
- Rotating arbiter (most fair)
- Highest quality, highest cost

### Example 2: Fast Review
```bash
/code-review --strategy=majority --workers=opus,sonnet
```
- 2 workers only
- Majority vote (no arbiter)
- Fast, low cost

### Example 3: Opus-Led Review
```bash
/code-review --strategy=single --arbiter=opus --workers=opus,sonnet,haiku
```
- 3 workers
- Opus always arbitrates
- Consistent decision-making

### Example 4: Weighted Consensus
```bash
/code-review --strategy=weighted --workers=opus,sonnet,haiku
```
- 3 workers
- Confidence-weighted voting
- Quality over quantity

## Options

- `--strategy=MODE` - Consensus strategy (rotating/single/majority/weighted/pairwise)
- `--arbiter=MODEL` - Override arbiter model (opus/sonnet/haiku/gemini)
- `--workers=LIST` - Comma-separated worker models
- `--path=DIR` - Target directory (default: .)
- `--create-issues` - Create GitHub issues (default: true)
- `--days=N` - Number of days back for commit review (default: 30)
- `--maxCommits=N` - Max commits to review (default: 5)
- `--maxIssues=N` - Max issues to review (default: 5)
- `--maxFiles=N` - Max files to scan (default: 10)

### Removed Options

**⚠️ Breaking Change in v2.0.0**:
- `--sync` - **REMOVED**. Sync with remote is now always enabled and cannot be disabled. The workflow always fetches and rebases before review to ensure up-to-date code.

**Migration**: If you need to review without syncing (e.g., to review a specific historical commit):
```bash
# Option 1: Checkout to detached HEAD at specific commit
git checkout <commit-hash>
/code-review

# Option 2: Create a temporary branch at the commit
git checkout -b temp-review <commit-hash>
/code-review
git checkout -  # Return to previous branch
git branch -d temp-review
```

## Output

```
═══════════════════════════════════════
🔍 Multi-Model Code Review
═══════════════════════════════════════
Strategy: rotating
Workers: opus, sonnet, haiku
Arbiter: auto (rotating)
═══════════════════════════════════════

🔧 Detecting platform and syncing with remote...
✅ Platform: github (using gh)
✅ Successfully synced with remote

🔍 Scanning...
Found 12 potential issues

🤖 Running rotating strategy review...
🎯 Strategy: rotating | Workers: opus, sonnet, haiku
✅ Multi-model review complete

⚖️ Arbiter making decisions (rotating strategy)...
⚖️ Arbiter: Opus (rotating strategy)
⚖️ Arbiter: Sonnet (rotating strategy)
⚖️ Arbiter: Haiku (rotating strategy)
✅ Decisions complete

═══════════════════════════════════════
📊 Code Review Results
═══════════════════════════════════════
Total Scanned: 12
Reviewed: 10
Real Issues: 3
False Positives: 7
Strategy: rotating
Consensus: 95% avg
═══════════════════════════════════════

📝 Creating 3 GitHub issues...
✅ Created 3 issues
```

## Strategy Comparison

| Strategy | Speed | Cost | Quality | Bias | Use When |
|----------|-------|------|---------|------|----------|
| **rotating** | Medium | High | Highest | None | Production, critical |
| **single** | Fast | Low | Good | Some | Quick scans |
| **majority** | Fastest | Lowest | Good | None | Speed priority |
| **weighted** | Slow | High | Highest | None | Complex issues |
| **pairwise** | Medium | Medium | High | Low | Balanced needs |

## Migration from auto-review-brutal

**Before**:
```bash
/auto-review-brutal
```

**Now**:
```bash
/code-review --strategy=rotating
```

**Same functionality**, but with:
- ✅ Strategy selection
- ✅ Worker configuration  
- ✅ Arbiter swapping
- ✅ Better performance

## Cost Optimization

### Minimize Cost
```bash
/code-review --strategy=majority --workers=opus,sonnet
```
- 2 workers, no arbiter
- ~40% cost reduction

### Balance Cost/Quality
```bash
/code-review --strategy=single --workers=opus,sonnet,haiku
```
- 3 workers, 1 arbiter
- Standard cost

### Maximum Quality
```bash
/code-review --strategy=rotating --workers=opus,sonnet,haiku,gemini
```
- 4 workers, rotating arbiter
- ~150% cost increase

## Files

- `~/.claude/workflows/code-review.js`
- `~/.claude/workflows/shared/consensus-engine.js` (enhanced)
- `~/.claude/skills/code-review-unified.md`

## See Also

- `/pr-review` - PR-specific review
- `/code-solve` - Auto-resolve issues
- `/code-improve` - Iterative improvement

---

**Version**: 2.0 (Unified)  
**Created**: 2026-06-03  
**Global**: Works on all projects
