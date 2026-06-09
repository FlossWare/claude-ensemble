---
name: cross-platform-tooling
description: User values cross-platform support for development tooling
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7f672252-d132-4787-9633-69f7c116bb90
---

Provide Windows equivalents when creating shell-based tooling for FlossWare projects.

**Why:** User requested Windows batch/PowerShell versions of the Linux version bumping script, indicating they want tooling that works across platforms (Linux, macOS, Windows).

**How to apply:** When creating or updating build scripts, CI/CD tooling, or development utilities:
- Provide Linux/macOS shell scripts (.sh)
- Provide Windows PowerShell scripts (.ps1) with proper error handling
- Provide Windows batch files (.bat) as alternative for traditional CMD users
- Document all three in README with platform-specific examples
- PowerShell is preferred over batch for Windows due to better error handling

**Context:** Applied when adding ci/rev-version.ps1 and ci/rev-version.bat to jcollections project.
