---
name: flossware-naming-convention
description: FlossWare org standard — all repo names, project names, and references are lowercase kebab-case, no PascalCase
metadata:
  type: feedback
---

All FlossWare repo names and project name references must be lowercase kebab-case. No PascalCase. Source code always follows its language's own conventions.

**Why:** User explicitly said "not gonna do pascal case" and "all lower case" — applies to repo names, local directory names, project names in prose/docs/code, and GitHub URLs. For source code: "always adhere to conform to conventions" — language standards override org standards inside code.

**How to apply — two-layer rule:**

**Layer 1: Org naming (repos, docs, prose, URLs, directories)**
- Repo names: `tftp-os`, `pxe-os`, `virt-os` (not TftpOS, PxeOS, VirtOS)
- Local clone dirs: must match the GitHub repo name exactly
- In prose/docs/README: use `tftp-os` not `TftpOS`
- GitHub URLs: `FlossWare/pxe-os` not `FlossWare/PxeOS`
- Naming pattern: `{thing}-{domain}` suffix (`-java`, `-ai`, `-os`, `-android`)

**Layer 2: Source code follows language conventions (overrides org naming)**
- Python: classes=`PascalCase`, functions/vars=`snake_case`, packages=`lowercase` (`tftpos`, `pxeos`) — see [[python-import-naming]]
- Java: classes=`PascalCase`, methods/vars=`camelCase`, files=`PascalCase`
- Go: exported=`PascalCase`, unexported=`camelCase`, packages=`lowercase`
- Shell: vars=`UPPER_SNAKE`/`snake_case`, functions=`snake_case`
- JavaScript: classes=`PascalCase`, functions/vars=`camelCase`

**Validated by 17 free AI models (2026-07-29):** Groq (4), Cerebras (3), Gemini (3), Cohere (3), OpenRouter (4) — unanimous on both layers.

**Org-level conventions (apply to ALL FlossWare repos):**
- Lowercase kebab-case repo names
- `{thing}-{domain}` suffix pattern
- Source code follows language conventions, not org naming
- BATS tests for every shell script — even a lone single script/function gets a test (see [[bats-testing-standard]])
- GPL-3.0 license
- Single-number versioning (1, 2, 3 — see [[versioning-policy]])
- Issue titles tagged with AI source (see [[issue-tagging-convention]])
- Minimal documentation, no bloat (see [[minimal-docs-no-bloat-global]])
