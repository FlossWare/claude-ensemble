---
name: windows-scripts
description: Windows batch and PowerShell build scripts added for cross-platform development support
metadata: 
  node_type: memory
  type: project
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

# Windows Build Scripts

Added complete set of Windows batch (.bat) and PowerShell (.ps1) scripts for cross-platform development support.

**When:** 2026-05-18 (commit c99999f)

**What was added:**
- 13 new script files providing Windows equivalents to Unix/Linux workflows
- CI/CD: `ci/rev-version.bat` and `ci/rev-version.ps1` (version bumping, tagging, pushing)
- Build helpers: build, test, install, package, clean (both .bat and .ps1 versions)
- Documentation: `SCRIPTS.md` with usage examples for CMD and PowerShell

**Why:** Enable Windows developers to use the same convenient build workflows as Unix/Linux users without requiring WSL or Git Bash. Provides native Windows integration with proper error handling.

**How to apply:**
- Windows developers can now run `build.bat`, `test.bat`, `install.bat`, etc. from Command Prompt
- PowerShell users get colored output and better error messages with `.ps1` scripts
- CI/CD pipelines can use the rev-version scripts on Windows build agents
- All scripts wrap Maven commands, so behavior is identical across platforms

**Related files:**
- bash: `ci/rev-version.sh` (original Unix version)
- [[jremote-repository]] for remote configuration (renamed from "gitlab" to "github" on 2026-05-18)
