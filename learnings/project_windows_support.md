---
name: windows-version-scripts
description: Windows PowerShell and batch scripts added for cross-platform version bumping
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f672252-d132-4787-9633-69f7c116bb90
---

Windows version bumping scripts added to jcollections (commit 6d74a42, 2026-05-18).

**Why:** Provide cross-platform support for developers working on Windows who need to manually bump versions outside of the automated CI/CD pipeline.

**What was added:**
- `ci/rev-version.ps1` - PowerShell version with enhanced error handling, colored output, and $LASTEXITCODE checking
- `ci/rev-version.bat` - Traditional Windows Command Prompt batch file with errorlevel checking
- Both scripts mirror the functionality of `ci/rev-version.sh` (Linux/macOS)

**How to apply:** When discussing version management or CI/CD tooling, remember that all three platforms are now supported. Windows users can use either PowerShell (recommended) or batch files for manual version bumping.

**Documentation:** Both README.md and CHANGELOG.md updated with cross-platform usage examples.

Related: [[jcollections-project]]
