---
name: feedback-code-quality
description: "User requires explicit imports, comprehensive tests, and current documentation for all projects"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

User has strict code quality standards that must be maintained across all projects.

**Why:** Wildcard imports reduce IDE support and code clarity. Outdated documentation misleads users. Missing tests allow bugs to slip through.

**How to apply:**
- Never use wildcard imports - always explicit imports (even for static JUnit assertions)
- Ensure README.md and CHANGELOG.md reflect current versions and dependencies
- Add comprehensive test coverage for all utility classes
- Update documentation whenever dependencies or versions change

**Specific requirements:**
- "please ensure there are no wild card imports" - applied to all 3 projects
- "please ensure all documentation including md files reflect the current state of all the projects"
- Comprehensive test suites added: 104 tests (Commons), 25 tests (SOAP), 14 tests (Session)

User will explicitly request these improvements when noticed.
