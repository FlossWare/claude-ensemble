---
type: feedback
date: 2026-06-09
---

# Feedback: Always Verify Before Push

**DO NOT push code to remote repositories until multi-AI review completes and verifies the changes.**

## What Happened
I implemented fixes based on multi-AI design recommendations, then immediately:
1. Committed the changes
2. Pushed to GitLab
3. THEN launched multi-AI verification review

This is backwards and risky.

## Correct Workflow

**ALWAYS:**
1. Implement fixes
2. Commit locally (do NOT push)
3. Launch multi-AI review
4. **WAIT for review results**
5. If review passes → push
6. If review finds issues → fix them, then repeat from step 2

## Why This Matters
- Multi-AI review might find critical bugs or issues
- Once pushed, bad code is in the shared repository
- Other developers/systems might pull broken code
- Harder to fix issues after pushing (requires new commit + push)

## Key Principle
**Verification comes BEFORE deployment, not after.**

This applies to:
- Git push to remote
- Production deployments
- Publishing releases
- Any action that affects shared/external systems

