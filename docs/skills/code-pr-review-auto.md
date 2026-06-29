---
name: code-pr-review-auto
description: Autonomous PR review bot - auto-approves/rejects until no PRs left
autonomous: true
---

# code-pr-review-auto

Fully autonomous PR review bot. Automatically approves or rejects PRs based on strict criteria with zero user interaction. Continues until all open PRs are reviewed.

## Usage

```bash
# Review all open PRs autonomously
claude run code-pr-review-auto

# Review specific PRs
claude run code-pr-review-auto 123 456
```

## What it does

1. **Setup**: Detects platform (GitHub/GitLab) and syncs with remote
2. **Discover PRs**: Finds all open PRs needing review
3. **Fetch PR**: Gets PR details and diff
4. **Impact Analysis**: Detects breaking changes and cross-codebase impact
5. **Multi-Model Review**: Reviews with opus/sonnet/haiku/gemini consensus
6. **Arbiter Decision**: Synthesizes final AI recommendation
7. **Auto-Decision**: Automatically approves or rejects based on criteria
8. **Post Results**: Comments and updates PR status
9. **Loop**: Continues until no PRs left to review

## Auto-Decision Criteria

**APPROVE if:**
- ✅ Quality ≥ 90/100
- ✅ AI consensus ≥ 85%
- ✅ No breaking changes detected
- ✅ ≤ 50 files impacted

**REJECT if:**
- ❌ Breaking changes detected
- ❌ Quality < 60/100

**SKIP if:**
- Neither approve nor reject criteria met
- Medium quality (60-89) with concerns
- Needs human review

## Key Features

- **Zero user interaction** (fully autonomous)
- **Multi-AI consensus** (opus/sonnet/haiku/gemini)
- **Breaking change detection** (automatic rejection)
- **Safe defaults** (skips uncertain cases)
- **Platform support** (GitHub via gh, GitLab via glab)
- **Continuous operation** (reviews until queue empty)

## Interactive vs Autonomous

**code-pr-review**:
- Prompts user before approve/reject
- User controls final decision
- Shows detailed summaries

**code-pr-review-auto (this workflow)**:
- Auto-approves/rejects based on criteria
- Zero user interaction
- Loops until no PRs left

## Example Output

```
🔄 Loop 1/100: Reviewing open PRs

PR #123: Add user authentication
Quality: 92/100 (4 AI consensus)
Breaking Changes: None
Files Impacted: 12

✅ AUTO-APPROVED (quality ≥90, no breaking changes)

PR #124: Refactor API endpoints
Quality: 75/100
Breaking Changes: Yes (3 removed endpoints)

❌ AUTO-REJECTED (breaking changes detected)

🔄 Loop 2/100: Reviewing open PRs
No open PRs left to review
```

## Requirements

- GitHub: `gh` CLI authenticated
- GitLab: `glab` CLI authenticated
- Permissions: `Bash(gh pr *)` or `Bash(glab mr *)`

## Use Cases

- **Nightly automation**: Review PRs automatically overnight
- **CI/CD integration**: Auto-review on PR creation
- **Queue management**: Clear PR backlog automatically
- **Team productivity**: Reduce manual review burden
