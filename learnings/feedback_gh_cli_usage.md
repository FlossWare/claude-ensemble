---
name: feedback_gh_cli_usage
description: Use GitHub CLI (gh) for repository operations instead of manual web interface
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 16591dd8-f645-4e78-96ef-2ee548fe526c
---

When renaming or managing GitHub repositories, use the `gh` CLI tool instead of asking the user to manually rename via the web interface.

**Why:** The `gh` CLI provides programmatic access to GitHub operations and can automate repository management tasks. The user has `gh` installed and authenticated, making it the preferred method for GitHub operations.

**How to apply:**
- For repository rename: `gh repo rename <new-name> -y`
- Always check `gh auth status` first to verify authentication
- If git push fails with auth errors, run `gh auth setup-git` to configure git credential helper
- The `gh` CLI automatically updates git remote URLs when renaming repositories
- Use `gh repo view --json <field>` to verify changes

**Example from this session:**
```bash
# Renamed repository successfully
gh repo rename jnexus -y

# Git remote was automatically updated to:
# github → https://github.com/FlossWare/jnexus.git

# Fixed git authentication
gh auth setup-git

# Successfully pushed commits
git push github main
```

This avoided the manual web interface step and streamlined the entire rename process.
