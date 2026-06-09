---
name: project-solenopsis-metadata
description: "Solenopsis metadata project - Java 17 library for Salesforce WSDL retrieval, recently upgraded from 1.0.0 to 2.0"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

The Solenopsis metadata project is a Java library for downloading Salesforce API and custom Apex class WSDLs.

**Current Status (as of 2026-05-18):**
- Version: 2.0 (upgraded from 1.0.0)
- Java: 17 (upgraded from 1.8)
- Versioning: X.Y format (not X.Y.Z)
- Repository: github.com/solenopsis/metadata (lowercase)
- Main branch: `main` (migrated from `master`)
- Security: All known CVEs fixed via dependency management overrides

**Why: Major refactoring and security hardening completed**
Upgraded all dependencies, replaced Keraiai/jCore with Session/Soap/jcommons, improved web service detection accuracy from 17% to >95%, added comprehensive test suite (57 tests), modernized for Java 17, and fixed all security vulnerabilities including critical CVE-2025-7962 SMTP injection.

**How to apply:**
- Always use Java 17+ features when working on this project
- Use X.Y versioning format (e.g., 2.0, 2.1) not X.Y.Z
- Reference the main branch, never master
- Dependencies: org.solenopsis:session, org.solenopsis:soap, org.flossware:jcommons
- Deployment: packagecloud.io/sfloess/solenopsis

**Related Work:**
- Web service detection uses regex patterns with comment/string removal ([[feedback-regex-webservice-detection]])
- All 6 source files have test coverage
- CHANGELOG.md documents all version changes
