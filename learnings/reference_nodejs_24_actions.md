---
name: reference-nodejs-24-actions
description: GitHub Actions with Node.js 24 support - versions and migration guide
metadata: 
  node_type: memory
  type: reference
  originSessionId: 94f4d6f1-3bcc-4b78-a0b9-7eca2b004c75
---

GitHub Actions requiring Node.js 24 support before June 2, 2026 deadline.

**Timeline:**
- June 2, 2026: Node.js 24 becomes default for all actions
- September 16, 2026: Node.js 20 removed from runners completely

**Node.js 24 compatible action versions:**

| Action | Old Version | Node 24 Version | Notes |
|--------|-------------|-----------------|-------|
| actions/checkout | v4 | v6 | Native Node 24 support |
| actions/setup-java | v4 | v5 | Native Node 24 support |
| s4u/maven-settings-action | v3.1.0 | v4.0.0 | Native Node 24 support |
| oleksiyrudenko/gha-git-credentials | @latest | No support yet | Replace with git config commands |

**Replacement for oleksiyrudenko/gha-git-credentials:**
```yaml
- name: Setup git credentials
  run: |
    git config --global user.name 'Your Name'
    git config --global user.email 'your-email@example.com'
```

**Migration steps:**
1. Update official GitHub actions to v5/v6 versions
2. Update third-party actions to Node 24 compatible versions
3. Replace actions without Node 24 support with native commands
4. Remove FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 flag (not needed with native versions)

**Sources:**
- https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
- https://github.com/actions/checkout/releases
- https://github.com/actions/setup-java/releases
- https://github.com/s4u/maven-settings-action/releases

**How to apply:** When setting up or updating GitHub Actions workflows, use these versions to avoid Node.js 20 deprecation warnings and ensure compatibility past June 2026.
