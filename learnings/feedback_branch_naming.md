---
name: feedback-branch-naming
description: User prefers main branch over master for default branch
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

Use `main` as the default branch name, not `master`.

**Why:** User explicitly requested migration from `master` to `main` and deletion of `master` branch (2026-05-16). This aligns with modern Git conventions and industry best practices.

**How to apply:** 
- When setting up new repositories, use `main` as the default branch
- When reviewing existing FlossWare projects, suggest migrating `master` to `main` if still using old convention
- Configure GitHub Actions and CI/CD workflows to trigger on `main` branch
- Update all documentation references to use `main`
