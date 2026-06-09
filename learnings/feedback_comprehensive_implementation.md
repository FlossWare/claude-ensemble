---
name: feedback-comprehensive-implementation
description: "User expects comprehensive, production-ready implementations not quick fixes"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

When user asks to "fix" or "implement" issues, they expect comprehensive, production-ready solutions covering all aspects, not minimal patches.

Example: Asked to address 5 issues (CI script, security, tests, serialization, logging). User expected all 5 done together as a complete refactoring, not piecemeal.

**Why:** User is building production software for FlossWare and values thorough engineering. Quick fixes create technical debt and don't meet the standard needed for the project.

**How to apply:** 
- When given a task list, plan to complete all items comprehensively
- Include tests, documentation, logging, and error handling by default
- Don't ask "should I also add tests?" - assume yes
- Use EnterPlanMode for non-trivial tasks to ensure comprehensive approach
- Consider security implications, edge cases, and production readiness
- When implementing features, include the complete stack (models, logic, tests, config)
