---
name: feedback-work-style
description: User prefers comprehensive improvements across related projects with full documentation updates
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

When addressing issues, user expects comprehensive treatment across all related projects, not just the immediate problem.

**Why:** User maintains a three-tier architecture (Commons → SOAP → Session) where changes cascade through dependencies. Partial fixes create inconsistency.

**How to apply:**
- When fixing issues in one project, check and update dependent projects
- Always update documentation (README.md, CHANGELOG.md) to reflect current state
- Ensure version numbers are consistent across all references
- Push all changes to GitHub when work is complete, handling CI/CD rebase conflicts as needed

**Example from conversation:**
- Started with Commons review
- Expanded to "address all concerns in commons, soap and session"
- Expected "push out all changes to github for all projects"
- Required "ensure all documentation including md files reflect the current state of all the projects"

User values thorough, complete work over quick partial fixes.
