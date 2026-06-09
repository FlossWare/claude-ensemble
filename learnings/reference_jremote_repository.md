---
name: reference-jremote-repository
description: Location and details of the jremote repository and build configuration
metadata: 
  node_type: memory
  type: reference
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

**Repository location:** /home/sfloess/Development/github/FlossWare/jremote

**Remote:** git@github.com:FlossWare/jremote.git (configured as "github" remote locally)

**Default branch:** main

**Build system:** Maven
- Java 21 (maven.compiler.release=21)
- Enforcer plugin validates X.Y version format strictly
- Current version: 1.12 (as of 2026-05-18)
- No SNAPSHOTs allowed by enforcer rules

**CI/CD:** 
- GitHub Actions: .github/workflows/main.yml
- Triggers on push to main
- Auto-increments minor version (X.Y → X.Y+1)
- Builds, tests, and deploys to packagecloud.io
- Creates git tags via maven-scm-plugin
- Skips if commit email is version-bump@flossware.org

**Key dependencies:**
- Jackson 2.17.0 (core, databind, dataformat-xml, dataformat-yaml)
- MessagePack 0.9.8 (jackson-dataformat-msgpack)
- SLF4J 2.0.12 + Logback 1.5.3 (logging)
- JUnit 5.10.2 (testing)

**Why:** Quick reference for repository operations, build commands, and version management.

**How to apply:** Use this info when running git commands, Maven builds, or discussing version changes. Standard git push/pull commands use `git push github main`.
