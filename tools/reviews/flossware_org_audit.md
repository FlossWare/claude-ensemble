# FlossWare GitHub Organization Audit

**Date:** 2026-07-26
**Organization:** https://github.com/FlossWare
**Related Orgs:** FlossWare-Archives, solenopsis, sfloess-archives, coderwall-bear, redhataccess, NexCore-Labs

---

## Repository Inventory (37 repos, all public, none archived)

### Active Repos by Last Updated

| # | Repository | Description | Last Updated | Has README | Local Clone |
|---|-----------|-------------|-------------|------------|-------------|
| 1 | hotspot-android | Free Android hotspot app for internet outages | 2026-07-23 | Yes | Yes |
| 2 | nexus-java | Cross-platform Nexus Repository Manager CLI/GUI tool | 2026-07-19 | **NO** | Yes |
| 3 | flossware-nexus | Desktop, Android, iOS clients for Nexus Repository Manager | 2026-07-19 | **NO** | Yes |
| 4 | PxeOS | Cross-OS PXE boot provisioning (Linux, BSD, Windows) | 2026-07-19 | Yes | Yes |
| 5 | curses-themes | Lightweight theme support for Python curses apps | 2026-07-19 | Yes | Yes |
| 6 | .github | Organization profile and architecture documentation | 2026-07-19 | **NO** (has profile/README.md) | Yes |
| 7 | curses-java | Terminal UI library with 29 AWT-like widgets, ncurses backend | 2026-07-18 | Yes | Yes |
| 8 | build-tools | Automated code quality and refactoring tools for Java | 2026-07-18 | **NO** | Yes |
| 9 | platform-java | Multi-application isolation platform for Java | 2026-07-16 | Yes | No |
| 10 | consensus-ai | Multi-AI orchestration library, 5 consensus strategies | 2026-07-16 | Yes | Yes |
| 11 | netbeans-plugins | NetBeans AI plugins (Claude, Gemini, ChatGPT) | 2026-07-16 | Yes | Yes |
| 12 | diskwipe-java | Secure disk space wiping with zero-fill | 2026-07-16 | Yes | Yes |
| 13 | cobbler | Cobbler templates for RHEL/Fedora, Debian/Ubuntu, FreeBSD | 2026-07-16 | Yes | Yes |
| 14 | fs-watcher-java | Filesystem watcher with debouncing | 2026-07-16 | Yes | Yes |
| 15 | collections-java | Java collections backed by files, networking | 2026-07-15 | Yes | Yes |
| 16 | cloudstorage-java | Universal cloud storage abstraction (S3, Azure, GCS, etc.) | 2026-07-15 | Yes | Yes |
| 17 | civilization-simulator-java | Alternate history civilization simulator | 2026-07-15 | Yes | Yes |
| 18 | filetransfer-java | Universal file transfer abstraction (SFTP, WebDAV, SMB, FTP) | 2026-07-15 | Yes | Yes |
| 19 | messaging-java | Universal messaging/cache abstraction (Kafka, RabbitMQ, Redis) | 2026-07-15 | Yes | Yes |
| 20 | vcs-java | Universal VCS abstraction (Git) | 2026-07-15 | Yes | Yes |
| 21 | classloader-java | Universal ClassLoader supporting 30+ protocols | 2026-07-15 | Yes | Yes |
| 22 | commons-java | Shared Java utilities for SOAP, strings, files | 2026-07-15 | Yes | Yes |
| 23 | knowledge-ai | Universal knowledge ingestion from any doc format | 2026-07-02 | Yes | Yes |
| 24 | skills-ai | Executable workflows for AI ecosystem | 2026-07-02 | Yes | Yes |
| 25 | Samsung-Galaxy-J7 | Transform Galaxy J7 into mini Linux computer | 2026-07-02 | Yes | Yes |
| 26 | eventbus-java | Event bus and service registry | 2026-06-09 | Yes | Yes |
| 27 | threadpool-java | Managed thread pools with monitoring | 2026-06-09 | Yes | Yes |
| 28 | resource-monitor-java | Resource usage tracking and quota enforcement | 2026-06-09 | Yes | Yes |
| 29 | encrypt-java | AES-256-GCM encryption library | 2026-06-09 | Yes | Yes |
| 30 | container-java | Universal container/orchestration abstraction (K8s, Docker) | 2026-06-09 | Yes | Yes |
| 31 | remote-java | RPC framework with multi-format serialization | 2026-06-09 | Yes | Yes |
| 32 | notion2config | Generate system configs from Notion databases | 2026-06-09 | Yes | Yes |
| 33 | de-converter | Convert desktop environment configs to lightweight WMs | 2026-06-09 | Yes | Yes |
| 34 | VirtOS-Examples | Templates for VirtOS microservices | 2026-06-09 | Yes | Yes |
| 35 | vectordb-ai | Universal vector database adapter (9 backends) | 2026-06-09 | Yes | Yes |
| 36 | semantic-search-ai | Hybrid search, reranking, filtering for AI | 2026-06-09 | Yes | Yes |
| 37 | FlossWare | Legacy documentation repo (Javadocs) | 2020-05-19 | Yes | No |

---

## Repos Missing README.md (4 repos)

| Repository | Root Contents | Notes |
|-----------|--------------|-------|
| **nexus-java** | Maven/Gradle project (pom.xml, build.gradle, src/) | Active repo (pushed 2026-07-20), needs README |
| **flossware-nexus** | Maven/Gradle + mobile (jnexus-android, jnexus-ios, fastlane) | Desktop/mobile Nexus client, needs README |
| **build-tools** | Shell scripts (apply-maven-quality.sh, auto-refactor.sh, etc.) | Build automation tooling, needs README |
| **VirtOS** | Full project (Makefile, build/, kernel/, config/, tests/) | Has TESTING.md.backup but no README.md |

Note: `.github` repo has no root README.md but does have `profile/README.md` which serves as the org profile page. This is the correct GitHub convention.

---

## Organization Profile (.github repo)

The `.github` repo is well-structured with comprehensive documentation:

**Root:**
- `ARCHITECTURE.md` - Complete system architecture
- `profile/README.md` - Organization profile (detailed, well-written)

**Docs tree (18 files across 7 categories):**
- `docs/architecture/` - consensus.md, fleet.md, orchestration.md, routing.md
- `docs/databases/` - orientdb.md, postgres.md, redis.md
- `docs/development/` - coding_standards.md, contributing.md, getting_started.md
- `docs/knowledge/` - chunking.md, embeddings.md, graph.md, scraping.md
- `docs/learning/` - genetic_algorithms.md, thompson_sampling.md
- `docs/operations/` - deployment.md, monitoring.md, scaling.md
- `docs/philosophy.md` - Design philosophy

---

## User Preferences (from Memory Files)

### Architecture Direction (finalized 2026-07-19)

- **Vertical-first architecture**: Build working verticals, extract reusable capabilities only after real usage
- **Three naming tiers**: capability libraries (`*-java`, `*-ai`), platform services (`flossware-*`), applications (`flossware-*`)
- **17 planned repositories** (only 5 of the capability libraries exist today; 0 of 12 planned new repos created yet)
- Fleet-reviewed and meta-reviewed with zero model overlap

### Planned But Not Yet Created (12 repos)

| Planned Repo | Type | Status |
|-------------|------|--------|
| core-ai | Capability Library | NOT CREATED |
| models-ai | Capability Library | NOT CREATED |
| router-ai | Capability Library | NOT CREATED |
| optimization-ai | Capability Library | NOT CREATED |
| scraper-ai | Capability Library | NOT CREATED |
| graphdb-ai | Capability Library | NOT CREATED |
| telemetry-java | Capability Library | NOT CREATED |
| guard-java | Capability Library | NOT CREATED |
| flossware-runtime | Platform Service | NOT CREATED |
| flossware-engineer | Application | NOT CREATED |
| flossware-nexus | Application | EXISTS (but as nexus client, not knowledge platform) |
| flossware-studio | Application | NOT CREATED |

Note: `flossware-nexus` exists but as a Nexus Repository Manager client, not the "Knowledge management platform" described in the architecture direction. These may be the same repo evolving, or a naming conflict.

### Model Usage Policy

- **commons-java**: Gets ALL models (paid + free) -- core library, worth investment
- **All other FlossWare repos**: FREE models only
- Tag embeddings/LLM calls with project name for cost tracking

### Solenopsis Repos (separate org, not FlossWare)

User cares about only 3 repos in the `solenopsis` org: soap, session, solenopsis. Ignore all others.

---

## FlossWare-Archives (Separate Org, 22 repos, all archived)

Contains historical/deprecated projects moved out of main org:

| Repository | Description |
|-----------|-------------|
| civilization-simulator-kmm | KMM version of civilization simulator |
| freemind | Mindmaps |
| freeplane | Freeplane mindmaps |
| solr | Solr utilities |
| groovy | Groovy library |
| pbc | Po' Boy Cloud |
| docker | Docker functionality |
| beanshell | Beanshell functionality |
| bash | Bash scripts |
| puppet | Puppet related functionality |
| chroot | Chroot environments |
| ant | Reusable Ant functionality |
| ansible | Ansible scripts |
| gofl | Gang of Four Using Lambdas |
| scripts | Utility scripts (Bintray, Jenkins, etc.) |
| core | Java library (old) |
| jCore | Java core library (old) |
| jplate | Reusable frameworks/tools |
| keros | Cross-platform scripting environment |
| entware-ng | Entware-ng related work |
| dnsmasq | DNSMasq config generator |
| rootfs | Debian rootfs builder |
| admin | Administrative work |

---

## Legacy/Stale Repo

**FlossWare/FlossWare** - Last updated 2020-05-19 (6+ years old). Contains only CNAME, LICENSE, README.md, _config.yml. Appears to be an old GitHub Pages site for Javadocs. May warrant archiving.

---

## What Needs Updating

### Priority 1: Missing READMEs (4 repos)

1. **nexus-java** - Actively pushed (2026-07-20), has code, no README. High priority.
2. **VirtOS** - Active project, has full build system and tests, no README. High priority.
3. **flossware-nexus** - Multi-platform Nexus client, no README. Medium-high priority.
4. **build-tools** - Build automation scripts, no README. Medium priority.

### Priority 2: Architecture Alignment

- The org profile (.github/profile/README.md) lists 37 repos but the architecture direction specifies 17. The profile describes the full org accurately; the architecture direction is the forward-looking plan.
- 12 of 17 planned repos do not exist yet. These are the future roadmap, not documentation gaps.
- Potential naming conflict: `flossware-nexus` exists as a Nexus Repository Manager client, but the architecture direction defines `flossware-nexus` as a "Knowledge management platform."

### Priority 3: Consider Archiving

- **FlossWare/FlossWare** (legacy docs repo) - Not updated since 2020. If Javadocs are no longer generated/published here, consider archiving.
- 20+ repos in the main org that are not part of the 17-repo architecture direction may eventually need to be archived or moved to FlossWare-Archives.

### Priority 4: Documentation Freshness

- Repos last updated 2026-06-09 (11 repos: eventbus-java, threadpool-java, resource-monitor-java, encrypt-java, container-java, remote-java, notion2config, de-converter, VirtOS-Examples, vectordb-ai, semantic-search-ai) may need README/doc review if they've been substantially changed.
- The .github org profile is comprehensive and recent (2026-07-19).

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total repos (FlossWare org) | 37 |
| Archived repos | 0 |
| With README.md | 33 |
| Missing README.md | 4 |
| Local clones (/home/sfloess/Development/github/FlossWare/) | 35+ |
| Planned repos not yet created | 11-12 |
| Repos in FlossWare-Archives | 22 (all archived) |
| Org profile documentation files | 18 |
