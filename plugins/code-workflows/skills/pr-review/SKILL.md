---
name: pr-review
description: This skill should be used when the user asks to "review PR", "review pull request", "review merge request", "auto-review PRs", "continuous PR review", or discusses automatically reviewing pull requests with multi-AI consensus.
version: 2.1.0
---

# PR Review - Continuous Auto-Discovery Mode

**NEW**: Auto-discovers and reviews PRs continuously without prompting!

## Quick Start

### Continuous Mode (Default)

```bash
/pr-review
# Auto-discovers all open PRs
# Reviews them continuously
# Posts comments automatically
# Checks every 5 minutes
```

### With Auto-Approve

```bash
/pr-review --approve --threshold=90
# Same as above + auto-approves PRs with quality >= 90
```

### Single PR

```bash
/pr-review 42
# Review only PR #42
```

## Features

- **Auto-Discovery**: Finds all open PRs automatically
- **Continuous**: Checks every 5 minutes, runs forever
- **Auto-Post**: Posts review comments automatically
- **Auto-Approve**: Approves clean PRs (optional)
- **Strategy Support**: All 5 consensus strategies
- **Worker Configuration**: Choose your AI models

## Usage Modes

### 1. Continuous Auto-Discovery (NEW Default)

```bash
/pr-review
```

- Finds all open PRs
- Reviews each one
- Posts comments
- Repeats every 5 minutes
- Runs forever (Ctrl+C to stop)

### 2. Continuous with Auto-Approve

```bash
/pr-review --approve --threshold=95
```

- Same as above
- Auto-approves PRs with quality >= 95

### 3. Single PR Review

```bash
/pr-review 42
/pr-review 42 --post
/pr-review 42 --approve --threshold=90
```

## Strategy Options

### Rotating Arbiter (Recommended)

```bash
/pr-review --strategy=rotating
```

- Different arbiter each PR
- Most fair consensus

### Fast Majority Vote

```bash
/pr-review --strategy=majority --workers=opus,sonnet
```

- Simple vote, no arbiter
- 40% faster

### Weighted Consensus

```bash
/pr-review --strategy=weighted
```

- Confidence-based voting
- Best for complex PRs

## Options

- `--strategy=MODE` - rotating, single, majority, weighted, pairwise
- `--workers=LIST` - Comma-separated models (opus,sonnet,haiku,gemini)
- `--arbiter=MODEL` - Override arbiter (opus/sonnet/haiku)
- `--approve` - Auto-approve clean PRs
- `--threshold=N` - Quality threshold for auto-approve (default: 90)
- `--post` - Post review comments (default: true in continuous mode)

## Real-World Scenarios

### Scenario 1: Monitor Repo 24/7

```bash
cd ~/my-project
/pr-review --approve --threshold=95
# Reviews all PRs continuously
# Auto-approves excellent ones
# Runs forever
```

### Scenario 2: Review Queue Without Auto-Approve

```bash
cd ~/my-project
/pr-review
# Reviews all PRs
# Posts comments
# Does NOT auto-approve (human decides)
```

### Scenario 3: Single PR Deep Review

```bash
cd ~/my-project
/pr-review 42 --strategy=weighted --workers=opus,sonnet,haiku,gemini
# Most thorough review of PR #42
# 4 models, weighted consensus
```

## Migration

### Before

```bash
/pr-review loop --auto-approve
```

### Now

```bash
/pr-review --approve
```

Simpler! Loop mode is now the default.

## Cost Estimates

| Mode | PRs/Day | Cost/Day |
|------|---------|----------|
| Continuous (3 PRs/day) | 3 | ~$7 |
| Continuous (10 PRs/day) | 10 | ~$24 |
| Single PR | 1 | ~$2.40 |

**Savings**: 2-4 hours/day of manual PR review

## See Also

- `/code-review` - Code review with strategies
- `/code-solve` - Auto-resolve issues
- `/code-improve` - Quality improvement

---

**Version**: 2.1 (Auto-Discovery)  
**Updated**: 2026-06-03
