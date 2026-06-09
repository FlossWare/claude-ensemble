---
name: project-jsecurity
description: jsecurity project overview - disk wiping utility with multi-threaded free space overwrite
metadata: 
  node_type: memory
  type: project
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

jsecurity is a Java-based disk wiping utility that securely overwrites free disk space with zero-filled files. Part of the FlossWare organization on GitHub.

**Key characteristics:**
- Multi-threaded disk space wiping (default 4 threads)
- Configurable buffer sizes for performance tuning
- Safety guards preventing wipe of critical system directories
- Command-line interface with confirmation prompts
- Single-pass zero-fill implementation
- Java 11+ required
- Maven-based build system

**Architecture:**
- Package: `org.flossware.jsecurity.disk`
- Main classes: CleanDisk (CLI entry point), FileWorker (worker threads), WipeConfiguration (builder)
- Comprehensive test suite: 76 tests across 3 test classes
- Uses JUnit Jupiter 5.10.2

**Build artifacts:**
- JAR: `jsecurity-1.0.jar` (executable)
- Main class: `org.flossware.jsecurity.disk.CleanDisk`

**Repository:** https://github.com/FlossWare/jsecurity

**Related:** Similar CI/CD setup to [[project-jcollections]]
