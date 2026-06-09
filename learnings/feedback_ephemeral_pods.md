---
name: feedback-ephemeral-pods
description: "Ephemeral pod constraints: can't optimize runtime state (Solr configsets, Zookeeper), only pre-bake static dependencies"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8c2c0c92-e4f2-459b-8fd6-8aabd685e77a
---

When working with Kubernetes ephemeral pods, understand the optimization boundaries clearly before proposing solutions.

**Why:** Attempted "smart configset upload" optimization (only upload changed configsets to Solr Zookeeper) during CI/CD work. User feedback: "that won't work with unit/integration tests." 

Root cause I missed: Ephemeral pods = fresh Zookeeper instance every build = zero configsets exist = ALL configsets must be uploaded for tests to pass. The optimization assumed persistence that doesn't exist.

**How to apply:**

**Can optimize (static, pre-baked):**
- Dependencies in Docker base image (Maven, npm, pip packages)
- Pre-installed tools (Solr binaries, databases, SDKs)
- Configuration files that don't change per-build

**Cannot optimize (runtime state, ephemeral):**
- Zookeeper data (configsets, cluster state)
- Database state (schemas, data)
- Cache that requires shared storage between pods
- Any state that relies on pod persistence

Before proposing optimizations in ephemeral environments:
1. Identify what persists (Docker layers) vs what's ephemeral (pod filesystem, in-memory state)
2. Optimize the persistent layer (base images)
3. Accept unavoidable costs in the ephemeral layer (state recreation)
4. Don't propose caching solutions that require pod-to-pod state sharing without a shared cache server

Related: [[gitlab-ci-cache-fix]] - The CI/CD optimization work that surfaced this constraint
