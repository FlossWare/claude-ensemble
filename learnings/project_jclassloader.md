---
name: project_jclassloader
description: JClassLoader project - comprehensive Java ClassLoader supporting 30+ transport protocols
metadata: 
  node_type: memory
  type: project
  originSessionId: f26c00bc-2e0f-4df4-8b1f-d7888af7de1f
---

JClassLoader is a flexible Java ClassLoader that loads classes from 30+ transport protocols including local files, HTTP/HTTPS, FTP/FTPS, SFTP, WebDAV, cloud storage (S3, Azure, GCS, Google Drive, Dropbox, OneDrive), Maven repositories, messaging systems (Kafka, Redis), distributed file systems (HDFS), version control (Git), and Kubernetes ConfigMaps.

**Why:** Created to provide the most comprehensive ClassLoader ever built, supporting both local and remote class loading with caching and authentication.

**How to apply:**
- Repository: FlossWare/jclassloader (transferred from personal account on 2026-05-17)
- Version: 1.0 (X.Y format, auto-bumped by CI/CD)
- Tests: 26 tests across 3 test classes, all passing
- Build: Java 11 source/target, built with JDK 21
- CI/CD: Matches [[cicd_pattern_jcollections]], deploys to packagecloud.io
- Dependencies: Most protocols are optional Maven dependencies
- IPFS support requires manual JitPack repository setup (dependency not in Maven Central)
- 23 core ClassSource implementations + 7+ S3-compatible via MinioClassSource
