---
name: disseminator-workflow
description: Disseminator project workflow - always use feature branches, never push directly to main
metadata:
  type: feedback
---

# Disseminator Project Workflow

**Always use feature branches for the disseminator project. Never push directly to main.**

## Standard Workflow

1. **Create a feature branch** for any changes
2. **Make changes and commit** to the feature branch
3. **Create a merge request (MR)** to main
4. **Merge to main** after review/approval

## Build Pipeline Rules

**Builds run on:**
- Merge requests (MRs)
- Main branch (after merge)

**Builds skip on:**
- Manual pipeline runs with `START_AT_STAGE` set to deploy stages

## Important Caveat

**Build pipeline testing has been problematic for the user.**

When testing .gitlab-ci.yml changes:
- Be aware that the build pipeline may behave unexpectedly
- Validate YAML syntax locally before pushing
- Consider the testing limitations when planning CI/CD changes

## Why This Matters

Feature branch workflow:
- Allows testing CI/CD changes in MR before merging
- Prevents breaking main branch
- Maintains clean git history
- Enables code review

**Exception:** The initial CPSEARCH-10645 fixes were pushed directly to main for urgency, but this was an exception, not the standard workflow.

## How to Apply

When user asks for changes to disseminator:
1. Create a feature branch (not push to main)
2. Make changes on feature branch
3. Offer to create MR or push feature branch for user to create MR
4. Only merge to main after user approval

Never push directly to main unless explicitly instructed.
