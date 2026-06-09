---
name: feedback-branch-cleanup
description: "Before merging feature branches: remove hardcoded paths, user-specific references, and branch names from code/docs"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8c2c0c92-e4f2-459b-8fd6-8aabd685e77a
---

Before merging feature branches to main, audit for hardcoded paths and branch-specific references that will become stale or incorrect.

**Why:** During merge of CI/CD optimization work, user asked: "there aren't references to /home/sfloess in the code or documentation are there?" and "no don't mention sfloess_CPSEARCH-10602 anywhere. this is in main now and that branch is going to be removed."

Found and fixed:
- Hardcoded user home paths in documentation (CACHE_FIX_SUMMARY.md: `/home/sfloess/Development/redhat/...`)
- Hardcoded Java paths in scripts (key.sh: `/home/sfloess/.sdkman/candidates/java/17.0.8-tem/...`)
- Branch references in CI config (DEPLOY_FROM_BRANCH: `"sfloess_CPSEARCH-10602"` → `"main"`)

**How to apply:**

Before squash-merging feature branches, search for and generalize:
1. **Hardcoded user paths**: `/home/username/` → `$HOME/` or relative paths
2. **Hardcoded system paths**: `/home/user/.sdkman/...` → `$JAVA_HOME/` or other env vars
3. **Branch names in code**: Feature branch names in configs → `main` or variable
4. **Branch names in docs**: References to feature branches → generic or remove
5. **User-specific examples**: Personal credentials, tokens, machine names

Grep patterns to check before merge:
- `grep -r "/home/$(whoami)" .`
- `grep -r "$(git branch --show-current)" . | grep -v .git`
- Review all changed files in the branch for context-specific references

This keeps the codebase portable and professional after merge.
