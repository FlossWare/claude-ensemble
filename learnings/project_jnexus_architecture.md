---
name: project_jnexus_architecture
description: Key architectural decisions and constraints for JNexus CLI project
metadata: 
  node_type: memory
  type: project
  originSessionId: 16591dd8-f645-4e78-96ef-2ee548fe526c
---

JNexus CLI follows specific architectural patterns and has important technical constraints.

**Caching Implementation:**
- Uses Cache-Aside pattern in NexusClient
- ConcurrentHashMap<String, CacheEntry> for thread safety
- Default TTL: 5 minutes (300 seconds)
- Cache key: repository name
- Cache value: CacheEntry(List<RepoRecord>, Instant timestamp)
- List operations use cache by default
- Delete operations always bypass cache (forceRefresh=true)
- Delete operations clear cache after execution
- Defensive copies returned to prevent external modification

**Versioning Strategy:**
- X.Y format (not X.Y.Z) - e.g., 1.0, 1.1, 2.0
- X = major version (breaking changes)
- Y = minor version (features, fixes, backwards compatible)
- Maven enforcer plugin validates format with regex: `v.matches("^\\d+\\.\\d+$")`
- Automated version bumping via ci/rev-version.sh
- No SNAPSHOT versions in releases

**Terminal UI Constraints:**
- Fixed size: 120 columns × 40 rows (hardcoded in buffer and components)
- NOT resizable via mouse or keyboard
- Uses jcurses library (requires ncurses-devel installed)
- Requires Java preview features enabled (--enable-preview)
- Requires native access enabled (--enable-native-access=ALL-UNNAMED)
- Pre-populates fields from jnexus.properties defaults

**Configuration Hierarchy:**
1. Environment variables (NEXUS_URL, NEXUS_USER, NEXUS_PASSWORD) - highest priority
2. Properties file (~/.flossware/nexus/nexus.properties)
3. UI defaults only from properties file (nexus.default.repository, etc.)

**Why:** These constraints ensure performance (caching), simplicity (X.Y versioning), and proper separation of concerns. Terminal UI size is fixed because dynamic resizing would require SIGWINCH handling and component repositioning logic.

**How to apply:** Don't add Spring dependencies, keep JAR under 5MB, maintain test coverage, use caching for read operations but bypass for write operations. UI defaults are convenience features loaded from properties file only.
