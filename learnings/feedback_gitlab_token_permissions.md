---
name: feedback-gitlab-token-permissions
description: GitLab cross-repo automation needs Project Access Token with Maintainer role for protected branches
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8c2c0c92-e4f2-459b-8fd6-8aabd685e77a
---

When implementing GitLab CI automation that pushes to another repository's protected branches, use Project Access Token with appropriate role, not CI_JOB_TOKEN.

**Why:** Implemented auto-sync job to push pom.xml/settings.xml from disseminator to base-image repo. Multiple authentication approaches failed:

1. `CI_JOB_TOKEN` → 403 "You are not allowed to push code to this project"
2. CI/CD job token allowlist → Requires Maintainer access to configure (user didn't have)
3. Project Access Token with Developer role → 403 "not allowed to push code to protected branches"
4. Project Access Token with **Maintainer role** → ✅ Success

**How to apply:**

For cross-repository push automation in GitLab CI:

**Don't use:**
- `CI_JOB_TOKEN` - limited to same-project or requires complex allowlist configuration
- Developer role tokens - can't push to protected branches

**Do use:**
1. Create Project Access Token in **target repository** (the one being pushed to):
   - Role: **Maintainer** (if main/master is protected)
   - Scopes: `read_repository` + `write_repository` (or `api` if those aren't available)
   - Set expiration appropriately (e.g., 1 year)

2. Add token to **source repository** CI/CD variables:
   - Mask the variable
   - Use descriptive name (e.g., `TARGET_REPO_PUSH_TOKEN`)

3. Use in git clone/push:
   ```yaml
   git clone https://gitlab-ci-token:${TARGET_REPO_PUSH_TOKEN}@gitlab.../repo.git
   ```

**Protected branch consideration:** If target branch is protected, token must have Maintainer or Owner role. Developer role is insufficient even with write_repository scope.

Related: [[gitlab-ci-cache-fix]] - The auto-sync implementation that required this
