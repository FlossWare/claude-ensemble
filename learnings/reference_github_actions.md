---
name: reference-github-actions
description: GitHub Actions workflow location and successful build reference
metadata: 
  node_type: memory
  type: reference
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

GitHub Actions workflow for jsecurity located at:
- File: `.github/workflows/main.yml`
- View builds: https://github.com/FlossWare/jsecurity/actions
- Latest successful build (as of 2026-05-15): https://github.com/FlossWare/jsecurity/actions/runs/25947117265

**Build status check commands:**
```bash
# List recent runs
gh run list --repo FlossWare/jsecurity --limit 5

# Watch a specific run
gh run watch <run-id> --repo FlossWare/jsecurity

# View run details
gh run view <run-id> --repo FlossWare/jsecurity

# Check for failures
gh run view <run-id> --repo FlossWare/jsecurity --log-failed
```

**Tags and releases:**
- Current version: 1.1
- Git tag: v1.1
- Check tags: `git fetch github --tags && git tag --list`
- View on GitHub: https://github.com/FlossWare/jsecurity/tags
