---
name: feedback-security
description: User addresses security vulnerabilities immediately and updates dependencies proactively
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

When security vulnerabilities are identified, user expects immediate action across all affected areas.

**Why:** Security vulnerabilities can expose production systems. Dependabot alerts should be resolved quickly, not deferred.

**How to apply:**
- Address Dependabot security alerts as soon as they're reported
- Update vulnerable dependencies to latest secure versions
- Update related dependencies in the same commit for consistency
- Document security fixes prominently in CHANGELOG.md
- Run full test suite to ensure updates don't break functionality

**Example from conversation:**
- Dependabot reported moderate vulnerability in Session project
- User requested: "please update for the vulnerability in session project"
- Updated saaj-impl 3.0.3 → 3.0.5 (security fix)
- Also updated Mockito 5.15.2 → 5.23.0 and SOAP dependency 1.8 → 1.9
- Added security section to CHANGELOG with "Update immediately" recommendation

Security fixes are high priority, not backlog items.
