---
name: reference-github-commands
description: Useful GitHub CLI commands for managing workflows and builds
metadata: 
  node_type: memory
  type: reference
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

**GitHub Actions Workflow Management:**

**Check Recent Build Status:**
```bash
gh run list --limit 5
```
Shows: status (completed/in_progress), result (success/failure), commit message, workflow name, branch, trigger, run ID, duration, timestamp

**View Failed Build Logs:**
```bash
gh run view <run-id> --log-failed
```
Shows only the failed steps and their error messages

**View Complete Build Logs:**
```bash
gh run view <run-id> --log
```

**Check Action Version Availability:**
```bash
gh api repos/<owner>/<repo>/tags --jq '.[].name'
```
Example: `gh api repos/oleksiyrudenko/gha-git-credentials/tags --jq '.[].name'`
Lists all available version tags

**Fetch Latest Tags:**
```bash
git fetch github --tags
git tag | tail -5
```
Shows recently created tags (CI/CD auto-creates these)

**Monitor Remote Branch:**
```bash
git log --oneline github/main -3
```
Check what's on remote without pulling

**Usage Pattern:**
1. Push workflow changes
2. `gh run list --limit 3` to check status
3. If failed: `gh run view <id> --log-failed` to diagnose
4. Fix and push
5. `gh run list --limit 3` to verify success
6. `git fetch github --tags` to see new version tags

**Common in this project:**
- CI/CD runs on every push to main
- Auto-bumps version and creates tags
- Builds typically take 45s-2min
- Success = deployment to packagecloud.io
