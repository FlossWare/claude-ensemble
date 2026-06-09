---
name: project-sfdeasy
description: "SFDeasy Java library for Red Hat Salesforce integration, v1.22 with CI pipeline investigation"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

SFDeasy is a JDK 17+ Salesforce integration library providing SOAP API clients and SOQL query builders. Current version 1.22, next pipeline run will auto-increment to 1.23.

**Why:** Major modernization effort completed in May 2026 - added comprehensive test coverage (27 passing tests), logging framework (SLF4J/Logback), CI/CD pipeline (6 stages), security scanning (OWASP), and integration testing capabilities. This was a production-readiness initiative.

**Current status (2026-05-17):** All test failures resolved locally (27/27 tests passing), but CI pipeline failing. Three commits pushed to main:
- Commit 38bea49: Initial comprehensive improvements (logging, tests, JavaDoc, CI/CD)
- Commit 0c76724: Fixed wrong Field class imports in tests
- Commit 576ac7c: Added missing Apex factory methods + fixed BETWEEN condition syntax

**Test failures diagnosed and fixed:**
1. Wrong Field import - tests imported `scala.model.Field` instead of `query.fields.Field`
2. Missing Apex factory methods - APEX enum existed but createApexPort() methods were missing
3. BetweenCondition using `>= AND <=` instead of proper `BETWEEN` keyword

**CI/CD Pipeline Issue (2026-05-17):**
- Pipeline #15585213 failed at compile stage (commit 576ac7c)
- Local compilation succeeds with exact CI commands: `mvn clean compile` works fine
- This indicates CI environment-specific issue, likely:
  - Certificate import failure (Red Hat cert)
  - SSH setup issue (create_ssh.sh script)
  - Maven Nexus credentials not configured
  - Java version mismatch between local and CI
- Monitoring script created at /tmp/watch_pipeline.sh
- Waiting for user to check GitLab UI for specific error message

**How to apply:** 
- Project uses X.Y versioning with auto-increment on main branch
- Integration tests require SF_CREDENTIALS_FILE environment variable
- CI/CD pipeline auto-increments version and creates git tags on main branch
- Dependencies: Solenopsis session 1.11, JUnit Jupiter 5.10.0, Mockito 5.5.0, SLF4J 2.0.9
- Multi-module Maven project: annotations, soap (WSDLs), core (main library)
- Test suite: 27 tests across 5 test classes (SelectQuery, Field, Condition, Filter, RedHatPortFactory)
- CI pipeline URL: https://gitlab.cee.redhat.com/customer-platform/sfdeasy/-/pipelines
