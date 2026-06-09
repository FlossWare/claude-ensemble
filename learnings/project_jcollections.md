---
name: project_jcollections
description: jcollections is a file-backed Java 21 collections library at v1.3 with fully functional CI/CD
metadata: 
  node_type: memory
  type: project
  originSessionId: 43468100-682a-41f1-8f56-f5c078edba57
---

jcollections is a file-backed persistent collections library for Java 21. Currently at version 1.3, released and live on GitHub with fully functional CI/CD pipeline.

**Key Architecture:**
- FileBackedList, FileBackedMap, FileBackedSet implement SequencedCollection/SequencedMap
- Builder pattern for configuration (enableChecksums, enableMmap, enableCache, enableBTreeIndex)
- File format version 2 with magic bytes 0x4A434F4C ("JCOL")
- Memory-mapped I/O using MappedByteBuffer for performance
- B-tree indexing (ORDER=128) for O(log n) map lookups
- CRC32 checksums for data integrity
- FileLockManager for multi-process safety
- WriteCache for write-behind caching
- IntList primitive collection to avoid boxing
- Critical: actualDataSize tracking separate from file size to handle mmap pre-allocation

**Version Management:**
- Uses X.Y semantic versioning (e.g., 1.0, 1.1, 2.0)
- Maven enforcer plugin enforces version format rules
- GitHub Actions automates version bumps using build-helper:parse-version and versions:set
- ci/rev-version.sh exists but CI/CD pipeline is the primary version management mechanism

**CI/CD:**
- GitHub Actions workflow (.github/workflows/main.yml) fully functional
- Triggers on main branch pushes, auto-increments minor version
- Dependency updates for junit-jupiter to latest versions
- Build, test (20/20 passing), and deploy to packagecloud.io/flossware/java
- Automated git commit and tag with version-bump@flossware.org
- Prevents infinite loops by skipping version-bump commits
- Requires PACKAGECLOUD_TOKEN organization-level secret for deployment
- Successfully deployed: v1.0, v1.1, v1.2, v1.3 to packagecloud.io
- Resolved issues: added build-helper-maven-plugin (required for version parsing)
- Running on Node.js 24: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true + updated actions (checkout@v4, maven-settings-action@v3.1.0)

**Repository:**
- GitHub: github.com/FlossWare/jcollections
- Maven artifacts: packagecloud.io/flossware/java
- Status: Production-ready, all tests passing, CI/CD active

**Why:** User consolidated what was V1/V2 nomenclature into single clean 1.0 API. Removed all dual-version confusion. All 20 tests passing.

**How to apply:** When discussing features or making changes, refer to classes without version suffixes. The project uses builder patterns extensively. Version bumps happen automatically via GitHub Actions CI/CD on main branch pushes. Development follows feature branch → squash merge to main → delete branch workflow.
