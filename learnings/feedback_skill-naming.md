---
name: skill-naming-convention
description: Universal AI skill naming convention - use dashes to separate words
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 50760802-b2be-4756-b141-b1ad4f67c15f
---

**Rule:** All Universal AI skill names use dashes to separate words, not underscores or camelCase.

**Why:** Consistency with bash/shell conventions and Claude Code skill naming standards. Dashes are the standard for command-line tools and make skills easier to type and remember.

**How to apply:** When creating new skills:
- ✅ `code-solve.sh` not `code_solve.sh` or `codeSolve.sh`
- ✅ `pr-review.sh` not `pr_review.sh`
- ✅ `file-ls.sh` not `file_ls.sh`
- ✅ `metrics-skill.sh` not `metrics_skill.sh`
- ✅ `pipeline-skill.sh` not `pipeline_skill.sh`

**Examples:**
- code-solve, code-improve, code-review
- doc-solve, doc-review, doc-improve
- pr-review
- file-ls
- metrics-skill
- pipeline-skill

**Also applies to:**
- Skill invocation: `/code-solve` not `/code_solve`
- JSON files: `code-solve.json`
- Markdown docs: `code-solve.md`

Related: [[project_gitlab-repository]]
