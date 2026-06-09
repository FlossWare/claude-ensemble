---
name: reference_commons_cicd
description: commons project at ../commons serves as reference for GitHub Actions CI/CD workflow
metadata: 
  node_type: memory
  type: reference
  originSessionId: 991c96d3-12be-4e89-a221-88c867f72eb4
---

The commons project located at `/home/sfloess/Development/github/FlossWare/commons` serves as a reference template for how FlossWare projects should set up GitHub Actions CI/CD workflows.

**Key patterns from commons:**
- GitHub Actions workflow on main branch pushes
- Guard condition to prevent version-bump commits from triggering new builds
- Maven build-helper:parse-version and versions:set for automatic version bumps
- Dependency updates using versions:update-properties
- Deploy to packagecloud.io with Bearer token authentication
- Maven SCM plugin for git checkin and tagging
- Version bump commits use version-bump@flossware.org email
- Commit message includes [ci skip] to prevent loops

**Why:** User asked to "review the project at ../commons" for CI/CD automation including version bumping, building, testing, and artifact publishing.

**How to apply:** When setting up GitHub Actions for FlossWare projects, follow commons workflow structure. Adapt Java version as needed (commons uses 17, jcollections uses 21).
