---
name: project-workflow-incident
description: GitHub Actions workflow failure incident and resolution (2026-05-15)
metadata: 
  node_type: memory
  type: project
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

**Incident Timeline (2026-05-15):**

**Phase 1: Workflow Improvement**
- Updated GitHub Actions workflows across all three projects
- Changed `actions/checkout@v2` to `@v4`
- Changed `gha-git-credentials@latest` to `@v0.4` (incorrect version)
- Added Maven caching, timeouts, concurrency control, test reporting
- Pushed changes to GitHub

**Phase 2: Build Failures Detected**
- User reported: "please review github because the builds are failing"
- All three projects showing build failures within seconds
- Error: `Unable to resolve action oleksiyrudenko/gha-git-credentials@v0.4, unable to find version v0.4`

**Phase 3: Investigation**
- Used `gh run list` to identify failing builds
- Used `gh run view --log-failed` to see error details
- Checked available tags: `gh api repos/oleksiyrudenko/gha-git-credentials/tags`
- Found available versions: v2.1.2, v2.1, v2, v1, latest (no v0.4)

**Phase 4: Fix Applied**
- Changed `@v0.4` to `@v2.1` in all three workflow files
- Committed: "Fix GitHub Actions workflow - use correct action version"
- Pushed to GitHub across all projects

**Phase 5: Verification**
- Monitored builds with `gh run list`
- All builds completed successfully:
  - Commons: 59s SUCCESS
  - SOAP: 1m44s SUCCESS
  - Session: 49s SUCCESS
- CI/CD auto-bumped versions: Commons 1.13, SOAP 1.10, Session 1.15
- User requested final confirmation: "please ensure the builds arent failing at github"
- Verified all three projects showing SUCCESS on latest builds

**Root Cause:** Incorrect assumption about available version tags without verification.

**Lesson:** Always verify action versions exist before using them. Use `gh api repos/<owner>/<repo>/tags` to check available versions.

**Resolution Time:** ~20 minutes from detection to verified fix.
