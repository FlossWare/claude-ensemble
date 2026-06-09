---
name: project-recent-work
description: Comprehensive improvements completed across all three projects in May 2026
metadata: 
  node_type: memory
  type: project
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

**Work Completed (2026-05-15):**

**All Three Projects:**
- Removed all wildcard imports, replaced with explicit imports
- Improved GitHub Actions workflows:
  - Upgraded actions/checkout v2 → v4
  - Added Maven dependency caching for faster builds
  - Added 30-minute build timeout
  - Added concurrency control
  - Added permissions blocks (least privilege)
  - Added test report publishing
  - Fixed typo: "latests depenendencies" → "latest dependencies"
  - **Fixed workflow failure**: Changed gha-git-credentials from non-existent @v0.4 to correct @v2.1
- Updated all documentation to reflect current versions

**FlossWare Commons 1.10 → 1.13:**
- Fixed logger initialization bug (StringUtils.class → StringUtil.class)
- Changed UUID generation from timestamp to UUID.randomUUID()
- Added Base64 encoding for binary serialization
- Added input validation to SoapUtil methods
- Created comprehensive test suite (104 tests total)
- Deprecated ensureString() in favor of requireNonBlank()
- CI/CD auto-bumped to 1.13 after workflow fix

**Solenopsis SOAP 1.7 → 1.10:**
- Updated FlossWare Commons dependency 1.7 → 1.10
- Created comprehensive test suite (25 tests)
- Updated Apache CXF to 4.0.9
- CI/CD auto-bumped to 1.10 after workflow fix

**Solenopsis Session 1.10 → 1.15:**
- Updated SOAP dependency 1.7 → 1.9
- Fixed security vulnerability: saaj-impl 3.0.3 → 3.0.5
- Updated Mockito 5.15.2 → 5.23.0
- Created comprehensive test suite (14 tests)
- CI/CD auto-bumped to 1.15 after workflow fix

**Commons → JCommons Rename (2026-05-15):**
- Renamed FlossWare Commons → JCommons across all projects
- GitHub repository: FlossWare/commons → FlossWare/jcommons
- Maven artifact: org.flossware:commons → org.flossware:jcommons
- Java packages: org.flossware.commons.* → org.flossware.jcommons.*
- Updated all dependent projects with new imports
- **Final versions after rename:**
  - JCommons 1.14 (from Commons 1.13)
  - SOAP 1.11 (updated to jcommons 1.14)
  - Session 1.16 (updated to SOAP 1.11 with jcommons)
- All 143 tests passing, all CI/CD builds successful

**Why:** Projects hadn't been comprehensively reviewed recently. Addressing one issue (Commons review) revealed systematic improvements needed across entire stack. Rename to "jcommons" better reflects Java-specific nature.

**How to apply:** When user references "the recent improvements" or "the work we did," this is the context. Latest versions: JCommons 1.14, SOAP 1.11, Session 1.16. All deployed to packagecloud.io.
