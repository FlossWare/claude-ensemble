---
name: project_jnexus_current_state
description: Current state of JNexus CLI project after rename from nexus and major refactoring
metadata: 
  node_type: memory
  type: project
  originSessionId: 16591dd8-f645-4e78-96ef-2ee548fe526c
---

JNexus CLI project (formerly nexus, now jnexus) has been completely refactored from Spring Boot to plain Java 21 with modern features.

**Current State (as of 2026-05-16):**
- Version: 1.0 (using X.Y versioning format)
- Repository: https://github.com/FlossWare/jnexus (renamed from FlossWare/nexus)
- Location: /home/sfloess/Development/github/FlossWare/jnexus
- Branch: `main` (clean, up to date with github/main)
- Package: org.flossware.jnexus (renamed from org.flossware.nexus)
- Main classes: JNexus.java, JNexusUI.java (renamed from Nexus.java, NexusUI.java)
- JAR: jnexus-1.0-jar-with-dependencies.jar (2.8MB)
- Scripts: jnexus.sh, jnexus-ui.sh
- Startup time: <200ms
- Test coverage: 55 tests, all passing

**Project Rename Completed (2026-05-16):**
✅ Maven artifactId: nexus → jnexus
✅ Java package: org.flossware.nexus → org.flossware.jnexus
✅ Main classes: Nexus → JNexus, NexusUI → JNexusUI
✅ Scripts: nexus.sh → jnexus.sh, nexus-ui.sh → jnexus-ui.sh
✅ All documentation updated (README, CLAUDE, RUNNING, CHANGELOG, etc.)
✅ SCM URLs updated to github.com/FlossWare/jnexus
✅ GitHub repository renamed via `gh repo rename jnexus`
✅ Git remote URL automatically updated to https://github.com/FlossWare/jnexus.git
✅ Local directory renamed: /home/sfloess/Development/github/FlossWare/jnexus
✅ All changes committed and pushed to GitHub main branch
✅ Build verified: all 55 tests passing, JARs built successfully

**Major Features Implemented:**
1. **Plain Java 21 refactor** - Removed Spring Boot completely
2. **Terminal UI** - Interactive ncurses interface using jcurses 1.6
3. **Intelligent caching** - 5-minute TTL, thread-safe ConcurrentHashMap
4. **UI default values** - Pre-populate fields from jnexus.properties
5. **CLI with Picocli** - Subcommands for list and delete operations
6. **X.Y versioning** - Automated version bumping with ci/rev-version.sh
7. **CI/CD** - GitHub Actions (automated) and GitLab CI (manual)

**Technical Stack:**
- Java 21 with preview features (for jcurses FFM API)
- Picocli 4.7.6 for CLI
- jcurses 1.6 for terminal UI
- Jackson for JSON
- JUnit 5 + Mockito for testing
- Maven for build

**Configuration:**
- Required: nexus.url, nexus.user, nexus.password
- Optional UI defaults: nexus.default.repository, nexus.default.regex, nexus.default.dryrun
- Supports env vars (priority) and ~/.flossware/nexus/nexus.properties
- Example config: src/main/resources/jnexus.properties.example

**Architecture:**
- Layered: CLI → Service → Client → HTTP
- Caching in NexusClient layer (ConcurrentHashMap)
- Credentials class manages config + UI defaults
- Terminal UI: fixed 120x40 size (not resizable)

**Why:** Complete refactor done to eliminate Spring Boot bloat, add modern UI, and improve performance for a simple CLI tool. Renamed to "jnexus" to distinguish from Sonatype Nexus server.

**How to apply:** When working on this project, remember:
- It's now called "jnexus" (not "nexus")
- Package is org.flossware.jnexus
- Lightweight CLI tool without Spring dependencies
- Uses caching to reduce Nexus server load
- Has both CLI and terminal UI interfaces
- All documentation must stay updated (user expects comprehensive docs)
