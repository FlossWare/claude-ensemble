---
name: code-pr-review
description: Interactive PR review with multi-AI consensus - prompts before approve/reject
---

# code-pr-review

Interactive PR review with multi-AI consensus and breaking change detection. Prompts user before approving or rejecting PRs.

## Usage

```bash
# Review all open PRs
claude run code-pr-review

# Review specific PR
claude run code-pr-review 123
```

## What it does

1. **Setup**: Detects platform (GitHub/GitLab) and syncs with remote
2. **Discover PRs**: Finds all open PRs needing review
3. **Fetch PR**: Gets PR details and diff
4. **Impact Analysis**: Detects breaking changes and cross-codebase impact
5. **Multi-Model Review**: Reviews with opus/sonnet/haiku/gemini consensus
6. **Arbiter Decision**: Synthesizes final AI recommendation
7. **User Confirmation**: Prompts user to approve/reject/skip
8. **Post Results**: Comments and updates PR status

## Key Features

- **Multi-AI consensus** (opus/sonnet/haiku/gemini)
- **Breaking change detection** (signature changes, removed exports)
- **Impact analysis** (severity, file count, scope)
- **User approval gates** (you decide final action)
- **Platform support** (GitHub via gh, GitLab via glab)
- **Quality scoring** (0-100 scale)

## Interactive vs Autonomous

**code-pr-review (this workflow)**:
- Prompts before approve/reject
- Shows detailed summaries
- User controls final decision

**code-pr-review-auto**:
- Auto-approves quality ≥90, no breaking changes
- Auto-rejects quality <60 or breaking changes
- Zero user interaction

## Example Output

```
PR #123: Add user authentication
Quality: 85/100 (4 AI consensus)
Breaking Changes: None
Files Impacted: 12
Recommendation: APPROVE

Your decision?
[A]pprove / [R]eject / [S]kip: A

✅ Approved PR #123
```

## Requirements

- GitHub: `gh` CLI authenticated
- GitLab: `glab` CLI authenticated
- Permissions: `Bash(gh pr *)` or `Bash(glab mr *)`
