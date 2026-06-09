---
name: reference-github-cli-setup
description: User has GitHub CLI (gh) installed and authenticated on Fedora 44 for repository management
metadata: 
  node_type: memory
  type: reference
  originSessionId: 27e50fb1-19d7-4f31-9401-6edd9030e58b
---

GitHub CLI (gh) is installed and configured on user's Fedora 44 system.

**Installation:** `sudo dnf install gh` (available in standard Fedora repos)

**Authentication status:** User is authenticated to github.com as account 'sfloess' using keyring storage with HTTPS protocol.

**Usage:** Can use `gh` commands for repository operations like:
- `gh repo rename <new-name>` - rename repositories
- `gh repo view` - view repository details
- `gh pr create` - create pull requests
- Other GitHub operations via CLI

**How to apply:** When user needs GitHub repository operations (rename, create, manage), can use `gh` CLI commands directly rather than requiring manual web browser steps.
