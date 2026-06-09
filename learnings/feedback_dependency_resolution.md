---
name: feedback_dependency_resolution
description: Handle dependencies not in Maven Central when corporate Nexus mirror is configured
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f26c00bc-2e0f-4df4-8b1f-d7888af7de1f
---

When dependencies are only available in alternative repositories (like JitPack) but user has a corporate Nexus mirror configured, make them truly optional rather than adding the alternative repository to pom.xml.

**Why:** During jclassloader development, IPFS java-ipfs-http-client (only on JitPack) failed to resolve because user's Maven settings have `<mirrorOf>*</mirrorOf>` pointing to corporate Nexus. Adding JitPack repository to pom.xml doesn't help when mirrors override all repositories.

**How to apply:**
- Remove the dependency from pom.xml entirely
- Rename the implementation file to `.optional` extension
- Document manual setup steps in project documentation
- Let users who need that feature add both the repository and dependency themselves
- Don't fight against corporate Maven mirror configurations
- This pattern worked: removed io.ipfs:java-ipfs-http-client dependency, renamed IpfsClassSource.java to .java.optional, documented JitPack setup in ADVANCED_TRANSPORTS.md
