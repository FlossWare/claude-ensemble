---
name: feedback-verify-builds
description: Always verify GitHub Actions builds after pushing workflow changes
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

After making changes to GitHub Actions workflows, user expects immediate verification that builds are passing.

**Why:** Workflow changes can introduce subtle errors (incorrect action versions, typos) that break builds. These failures block CI/CD pipeline, preventing deployments and version bumps.

**How to apply:**
- After pushing workflow changes, use `gh run list` to check build status
- If builds are failing, use `gh run view <id> --log-failed` to diagnose
- Fix issues immediately and push corrections
- Wait to verify the fix builds successfully before considering work complete

**Example from conversation:**
- Improved workflows pushed with `oleksiyrudenko/gha-git-credentials@v0.4`
- User reported: "please review github because the builds are failing"
- Investigated and found v0.4 doesn't exist (available: v2.1, v2, v1, latest)
- Fixed to `@v2.1` across all three projects
- Verified all builds passed before confirming work complete
- User requested final verification: "please ensure the builds arent failing at github"
- Confirmed all three projects showing SUCCESS status on latest builds
- Commons: 49s, SOAP: 1m44s, Session: 59s - all successful

Don't assume workflow changes work - verify they build successfully. User expects this verification proactively and appreciates final confirmation.
