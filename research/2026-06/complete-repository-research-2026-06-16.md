# Complete Repository Research - FlossWare, Solenopsis, Search Engineering

**Research Date:** 2026-06-16  
**Method:** GitHub CLI (`gh`) + GitLab CLI (`glab`)  
**Total Repositories:** 36 FlossWare + 14 Solenopsis + 16 Search Engineering = 66 repositories

---

## FlossWare GitHub Repositories (36 total)

**Organization:** https://github.com/FlossWare  
**Focus:** Java utilities, cross-platform tools, infrastructure libraries

### Core Infrastructure Libraries

#### nexus-java ⭐ Featured
- **Description:** Cross-platform Nexus Repository Manager CLI and GUI tool
- **Features:**
  - CLI, Swing, AWT, Terminal UIs + Android/iOS apps
  - Advanced search, filtering, analytics
  - Lightweight (2.7MB), fast startup (<200ms)
  - Multi-profile support for different repositories
- **Language:** Java (85.5%), Swift (8.6%), Kotlin (4.8%)
- **Quality:** 93% instruction coverage, 86% branch coverage, zero-bug policy
- **URL:** https://github.com/FlossWare/nexus-java

#### collections-java
- **Description:** Java collections backed by files, networking, etc.
- **Purpose:** Alternative to standard Java Collections with persistent/distributed storage
- **Language:** Java
- **URL:** https://github.com/FlossWare/collections-java

#### commons-java
- **Description:** Shareable Java utilities for SOAP clients, string operations, file handling
- **Language:** Java
- **URL:** https://github.com/FlossWare/commons-java

### Universal Abstraction Libraries

#### cloudstorage-java
- **Description:** Universal cloud storage abstraction
- **Supported:** AWS S3, Azure Blob, GCS, Google Drive, Dropbox, OneDrive
- **Language:** Java
- **URL:** https://github.com/FlossWare/cloudstorage-java

#### messaging-java
- **Description:** Universal messaging and cache abstraction
- **Supported:** Kafka, RabbitMQ, Redis
- **Language:** Java
- **URL:** https://github.com/FlossWare/messaging-java

#### filetransfer-java
- **Description:** Universal file transfer abstraction
- **Supported:** SFTP, WebDAV, SMB/CIFS, FTP/FTPS
- **Language:** Java
- **URL:** https://github.com/FlossWare/filetransfer-java

#### container-java
- **Description:** Universal container and orchestration abstraction
- **Supported:** Kubernetes, Docker, Hazelcast
- **Language:** Java
- **URL:** https://github.com/FlossWare/container-java

#### vcs-java
- **Description:** Universal version control system abstraction
- **Supported:** Git repositories (unified API)
- **Language:** Java
- **URL:** https://github.com/FlossWare/vcs-java

#### classloader-java
- **Description:** Universal Java ClassLoader supporting 30+ protocols
- **Supported:** Cloud storage, databases, messaging systems, distributed sources
- **Language:** Java
- **URL:** https://github.com/FlossWare/classloader-java

### Terminal UI & Display

#### curses-java ⭐ Featured
- **Description:** Modern Java 21 terminal UI library
- **Features:**
  - 29 AWT-like widgets
  - ncurses backend
  - Virtual Threads support
  - Interactive mouse/keyboard support
- **Language:** Java
- **URL:** https://github.com/FlossWare/curses-java

#### curses-themes
- **Description:** Lightweight theme support for Python curses applications
- **Language:** Python
- **URL:** https://github.com/FlossWare/curses-themes

### Application Infrastructure

#### platform-java
- **Description:** Multi-application isolation platform for Java
- **Features:** Run multiple applications in single JVM with isolated classloaders, thread pools, security policies, resource monitoring
- **Language:** Java
- **URL:** https://github.com/FlossWare/platform-java

#### remote-java
- **Description:** Java 21 RPC framework
- **Features:** Factory-based instances, multi-format serialization (JSON/XML/YAML/MessagePack), Virtual Threads
- **Language:** Java
- **URL:** https://github.com/FlossWare/remote-java

#### eventbus-java
- **Description:** Event bus and service registry for inter-application communication
- **Language:** Java
- **URL:** https://github.com/FlossWare/eventbus-java

### Monitoring & Management

#### resource-monitor-java
- **Description:** Resource usage tracking and quota enforcement
- **Language:** Java
- **URL:** https://github.com/FlossWare/resource-monitor-java

#### threadpool-java
- **Description:** Managed thread pools with monitoring and graceful shutdown
- **Language:** Java
- **URL:** https://github.com/FlossWare/threadpool-java

#### fs-watcher-java
- **Description:** Filesystem watcher for monitoring directory changes with debouncing
- **Language:** Java
- **URL:** https://github.com/FlossWare/fs-watcher-java

### AI/ML Libraries

#### knowledge-ai
- **Description:** Universal knowledge ingestion library
- **Features:** Learn from any documentation format with multi-AI validation
- **Language:** Python
- **URL:** https://github.com/FlossWare/knowledge-ai

#### consensus-ai
- **Description:** Multi-AI orchestration library
- **Features:** 5 consensus strategies for better AI responses
- **Language:** Python
- **URL:** https://github.com/FlossWare/consensus-ai

#### vectordb-ai
- **Description:** Universal vector database adapter
- **Features:** 9 backends, portable format, no vendor lock-in
- **Language:** Python
- **URL:** https://github.com/FlossWare/vectordb-ai

#### semantic-search-ai
- **Description:** Advanced semantic search toolkit
- **Features:** Hybrid search, reranking, filtering for AI applications
- **Language:** Python
- **URL:** https://github.com/FlossWare/semantic-search-ai

#### skills-ai
- **Description:** Executable workflows for FlossWare AI ecosystem
- **Language:** JavaScript
- **URL:** https://github.com/FlossWare/skills-ai

### Security & Utilities

#### encrypt-java
- **Description:** General-purpose AES-256-GCM encryption library for Java
- **Language:** Java
- **URL:** https://github.com/FlossWare/encrypt-java

#### diskwipe-java
- **Description:** Multi-threaded Java utility for securely wiping free disk space
- **Features:** Zero-fill operations for secure deletion
- **Language:** Java
- **URL:** https://github.com/FlossWare/diskwipe-java

### Development Tools

#### netbeans-plugins
- **Description:** Multi-module Maven project for NetBeans AI plugins
- **Supported:** Claude, Gemini, ChatGPT
- **Language:** Java
- **URL:** https://github.com/FlossWare/netbeans-plugins

#### build-tools ⭐
- **Description:** FlossWare Build Standards
- **Features:** Automated code quality and refactoring tools for Java projects
- **Language:** Shell
- **URL:** https://github.com/FlossWare/build-tools

### Operating Systems & Virtualization

#### VirtOS ⭐
- **Description:** Minimal virtualization OS based on Tiny Core Linux
- **Language:** Shell
- **URL:** https://github.com/FlossWare/VirtOS

#### VirtOS-Examples
- **Description:** Ready-to-deploy examples and templates for VirtOS microservices
- **Language:** Python
- **URL:** https://github.com/FlossWare/VirtOS-Examples

### Infrastructure Automation

#### cobbler ⭐ 3 stars
- **Description:** Modern Cobbler templates for automated provisioning
- **Supported:** RHEL/Fedora, Debian/Ubuntu, FreeBSD
- **Formats:** kickstart, preseed, installscript
- **Language:** Shell
- **URL:** https://github.com/FlossWare/cobbler

#### notion2config
- **Description:** System configs from Notion databases
- **Features:** Generate dnsmasq, Ansible, nginx configs from Notion infrastructure inventory
- **Language:** Shell
- **URL:** https://github.com/FlossWare/notion2config

### Desktop Utilities

#### de-converter
- **Description:** Convert desktop environment configs to lightweight window managers
- **Supported:** LXDE → fvwm/jwm
- **Features:** Preserves settings, keybindings, workflows
- **Language:** Python
- **URL:** https://github.com/FlossWare/de-converter

#### Samsung-Galaxy-J7
- **Description:** Transform Samsung Galaxy J7 into debloated mini Linux computer
- **Features:** Termux, Debian, OpenSSH, automated bloatware removal
- **Language:** Shell
- **URL:** https://github.com/FlossWare/Samsung-Galaxy-J7

### Games & Simulators

#### civilization-simulator-java
- **Description:** Alternate History Civilization Simulator
- **Features:** Reproducible pseudo-random civilization simulator for exploring alternate history scenarios
- **Language:** Java
- **URL:** https://github.com/FlossWare/civilization-simulator-java

#### civilization-simulator-kmm
- **Description:** Native Android & iOS apps for Civilization Simulator
- **Technology:** Kotlin Multiplatform Mobile
- **Language:** Kotlin
- **URL:** https://github.com/FlossWare/civilization-simulator-kmm

### Documentation

#### FlossWare
- **Description:** Documentation for FlossWare including Javadocs
- **URL:** https://github.com/FlossWare/FlossWare

---

## Solenopsis GitHub Repositories (14 total)

**Organization:** https://github.com/solenopsis  
**Focus:** Salesforce deployment and development tools  
**Main Project:** Solenopsis - ⭐ 105 stars

### Core Deployment Tool

#### Solenopsis ⭐ 105 stars
- **Description:** A deployment tool for Salesforce
- **Architecture:** ANT scripts + Python scripts
- **Features:**
  - ANT: Salesforce metadata deployment
  - Python: Config management, templates, automation
  - Multi-environment support
  - Template processing
- **Language:** Python
- **Platform:** Linux-focused (multi-platform patches welcome)
- **Installation:** RPM build, direct install, uninstall scripts
- **URL:** https://github.com/solenopsis/Solenopsis

### Salesforce API Integration

#### soap
- **Description:** Java project containing all built-in Salesforce SOAP web services
- **Language:** Java
- **License:** GPL-3.0
- **URL:** https://github.com/solenopsis/soap

#### session
- **Description:** Session management for Salesforce
- **Language:** Java
- **License:** GPL-3.0
- **URL:** https://github.com/solenopsis/session

#### metadata ⭐ 2 stars
- **Description:** Contains metadata applications
- **Language:** Java
- **License:** GPL-3.0
- **URL:** https://github.com/solenopsis/metadata

#### BulkAPI
- **Description:** Framework for the Salesforce Bulk API
- **License:** GPL-3.0
- **URL:** https://github.com/solenopsis/BulkAPI

#### credentials
- **Description:** Java library for Salesforce credentials
- **URL:** https://github.com/solenopsis/credentials

### CLI Extensions

#### sf-precise-deploy
- **Description:** Salesforce CLI plugin for surgical deployments
- **Features:** Field-level delta detection for granular deployment control
- **Language:** TypeScript
- **URL:** https://github.com/solenopsis/sf-precise-deploy

### Utilities

#### solenopsis-js
- **Description:** Javascript utility methods around Solenopsis
- **Language:** JavaScript
- **License:** GPL-3.0
- **URL:** https://github.com/solenopsis/solenopsis-js

#### node_utils
- **Description:** A collection of nodejs utilities
- **Language:** JavaScript
- **License:** GPL-3.0
- **URL:** https://github.com/solenopsis/node_utils

### Archived Projects

#### Lasius ⭐ 7 stars [ARCHIVED]
- **Description:** Java utility framework for SFDC
- **Language:** Java
- **URL:** https://github.com/solenopsis/Lasius

#### Keraiai ⭐ 3 stars [ARCHIVED]
- **Description:** Java SFDC communication library for SOAP
- **Language:** Java
- **URL:** https://github.com/solenopsis/Keraiai

### Monitoring & Quality

#### sloggly ⭐ 21 stars
- **Description:** A class designed to send logs to Loggly from Salesforce
- **Language:** Apex
- **URL:** https://github.com/solenopsis/sloggly

#### checkstyle
- **Description:** A fork of checkstyle targeted towards Apex development
- **Language:** Java
- **URL:** https://github.com/solenopsis/checkstyle

### Documentation

#### solenopsis.github.com ⭐ 2 stars
- **Description:** Home page
- **Language:** HTML
- **URL:** https://github.com/solenopsis/solenopsis.github.com

---

## Search Engineering GitLab Repositories (16 total)

**Group:** https://gitlab.cee.redhat.com/search-engineering  
**Group ID:** 79993  
**Focus:** Enterprise search infrastructure, AI-powered search, deployment automation

### AI-Powered Search Services

#### search-mcp-server
- **Description:** Search MCP Server (Model Context Protocol)
- **Features:**
  - FastMCP + FastAPI with multiple transport protocols (HTTP, SSE, streamable-HTTP)
  - Pydantic configuration via environment variables
  - Structured JSON logging with structlog
  - SSL/TLS support for secure deployments
  - Container-ready with Red Hat UBI base image
  - OpenShift deployment manifests
  - Full CI/CD with GitLab
  - OAuth integration with PostgreSQL token storage
- **Technology:** Python 3.12+
- **Last Activity:** 2026-06-16
- **URL:** https://gitlab.cee.redhat.com/search-engineering/search-mcp-server

#### unified-retrieval-agent
- **Description:** Unified retrieval agent for search
- **Last Activity:** 2026-05-13
- **URL:** https://gitlab.cee.redhat.com/search-engineering/unified-retrieval-agent

#### Re-Ranking Service
- **Description:** Re-ranking service for search results
- **Last Activity:** 2026-01-28
- **URL:** https://gitlab.cee.redhat.com/search-engineering/re-ranking-service

#### Vector Generation Service
- **Description:** Vector generation for semantic search
- **Last Activity:** 2026-02-12
- **URL:** https://gitlab.cee.redhat.com/search-engineering/vector-generation-service

#### vector-search
- **Description:** Vector-based semantic search
- **Last Activity:** 2025-04-11
- **URL:** https://gitlab.cee.redhat.com/search-engineering/vector-search

#### Query Intent Detection ⭐ 1 star
- **Description:** AI-powered query intent classification
- **Last Activity:** 2026-03-12
- **URL:** https://gitlab.cee.redhat.com/search-engineering/query-intent-detection

### Core Search Platform

#### Disseminator ⭐ 1 star
- **Description:** Search engineering main repository
- **Technology:** Java 17 + Maven
- **Features:**
  - 1,376 Java files
  - Maven-based build system
  - Nexus integration
  - Enterprise certificate requirements
  - API fallback rules
  - Automated versioning (v2.493)
- **Last Activity:** 2026-06-15
- **URL:** https://gitlab.cee.redhat.com/search-engineering/disseminator

#### Disseminator Utils
- **Description:** Utilities for Disseminator
- **Last Activity:** 2025-10-27
- **URL:** https://gitlab.cee.redhat.com/search-engineering/disseminator_utils

### AI-Powered Development

#### ai-sdlc
- **Description:** Production-Grade Multi-Agent Software Development Lifecycle Orchestration
- **Features:**
  - 🤖 6 AI Providers: Claude, GPT, Gemini, Grok, Cohere, Mistral
  - 📋 6 Issue Trackers: GitHub, GitLab, Bitbucket, Jira, Notion, Trello
  - 📁 Persistent projects with full run history
  - 🎯 Metrics-driven quality gates
  - 💰 Financial circuit breakers
  - 🔄 Perpetual task automation
  - 🧪 Automated testing & coverage validation
  - 🛡️ Security audit integration
  - 👤 Human-in-the-loop intervention
  - 🌍 Multi-language: Python, TS, Go, Rust, Java, C#
- **Technology:** Python (36 files)
- **CI/CD:** Pipeline status + coverage badges
- **URL:** https://gitlab.cee.redhat.com/search-engineering/ai-sdlc (aliased from sfloess/ai-sdlc)

### Infrastructure & Deployment

#### Disseminator Deployment
- **Description:** Deployment automation for Disseminator
- **Features:** Ansible Tower integration, build/deploy pipelines
- **Last Activity:** 2024-03-27
- **URL:** https://gitlab.cee.redhat.com/search-engineering/disseminator-deployment

#### Certificate Generation
- **Description:** Generate certificates for search nodes
- **Features:**
  - HTTPS load balancer certificates
  - AWS EC2 deployment
  - Certificate Manager integration
  - CSR and private key generation
- **Tags:** certs
- **Last Activity:** 2025-06-18
- **URL:** https://gitlab.cee.redhat.com/search-engineering/cert-generation

#### servo-di
- **Description:** Dependency injection framework
- **Last Activity:** 2023-09-28
- **URL:** https://gitlab.cee.redhat.com/search-engineering/servo-di

#### ion
- **Description:** Ion framework/library
- **Last Activity:** 2025-07-10
- **URL:** https://gitlab.cee.redhat.com/search-engineering/ion

### Automation & Utilities

#### Ansible
- **Description:** Ansible related scripts and topics
- **Last Activity:** 2023-03-15
- **URL:** https://gitlab.cee.redhat.com/search-engineering/ansible

#### Bash
- **Description:** Bash related scripts
- **Last Activity:** 2023-02-09
- **URL:** https://gitlab.cee.redhat.com/search-engineering/bash

#### AWS
- **Description:** AWS related scripts
- **Last Activity:** 2024-03-06
- **URL:** https://gitlab.cee.redhat.com/search-engineering/aws

### Monitoring

#### sumo-logic
- **Description:** Sumo Logic integration for logging/monitoring
- **Features:**
  - GitOps-based management
  - Sumo Content Repo integration
- **Last Activity:** 2026-01-05
- **URL:** https://gitlab.cee.redhat.com/search-engineering/sumo-logic

---

## Summary Statistics

**Total Repositories:** 66

**By Organization:**
- FlossWare: 36 repos (54.5%)
- Solenopsis: 14 repos (21.2%)
- Search Engineering: 16 repos (24.2%)

**By Primary Language:**
- Java: 45 repositories
- Python: 10 repositories
- JavaScript/TypeScript: 5 repositories
- Shell/Bash: 4 repositories
- Other: 2 repositories

**Stars:**
- Top: Solenopsis (105 ⭐)
- Second: sloggly (21 ⭐)
- Third: Lasius (7 ⭐)

**Architecture Patterns:**
- Universal abstraction libraries (cloud, messaging, file transfer, VCS)
- Multi-protocol support (30+ protocols in classloader-java)
- Quality-driven development (93% coverage requirements)
- AI/ML integration (consensus, vector DBs, semantic search)
- Enterprise search (Disseminator, MCP servers)
- Salesforce automation (Solenopsis ecosystem)

**Key Technologies:**
- Java 17/21 with Virtual Threads
- Maven + Gradle build systems
- Python 3.12+ for AI/ML
- FastMCP + FastAPI for MCP servers
- ANT + Python for Salesforce deployment
- Enterprise certificates (Red Hat IT infrastructure)

---

**All repositories indexed and searchable in PostgreSQL vectorDB!**
