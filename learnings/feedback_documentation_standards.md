---
name: feedback_documentation_standards
description: User expects comprehensive documentation and frequent GitHub pushes
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 16591dd8-f645-4e78-96ef-2ee548fe526c
---

User expects all documentation and tests to be kept up to date with code changes before pushing to GitHub.

**Why:** Multiple times during the Nexus CLI refactoring, user asked "is everything pushed out and tests passing" and "are all documentation and unit tests up to date" - indicating this is important to them. They want complete, production-ready commits.

**How to apply:** 
- After implementing features, always update relevant documentation (README, RUNNING, CLAUDE, CHANGELOG)
- Write comprehensive tests for new features (not just unit tests, but integration tests where appropriate)
- Run full test suite before committing
- Push to GitHub frequently (user asked "push to github" multiple times)
- Use detailed commit messages with Co-Authored-By attribution
- When asked to push, verify everything is already pushed before confirming (user asked multiple times even after already pushing)
