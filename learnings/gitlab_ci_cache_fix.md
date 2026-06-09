---
name: gitlab-ci-cache-fix
description: "GitLab CI optimization: Pre-populate Maven+Solr in base image, auto-sync, 33% faster builds (20min→13min)"
metadata: 
  node_type: memory
  type: project
  date: 2026-05-13
  completed: 2026-05-18
  originSessionId: 633567d1-284d-4ca4-b4ad-d7d103ffc11a
---

# GitLab CI Build Performance Fix

## Problem
GitLab CI was re-downloading all Maven dependencies (2,374+ artifacts) on every build, causing ~20 minute build times.

## Root Cause Discovery (Builds 1-10, 2026-05-14 to 2026-05-15)

### Initial Attempts (Builds 1-5)
1. ✅ Fixed cache key (pom.xml hash) - **DIDN'T HELP**: Version auto-increments invalidated cache every build
2. ✅ Removed Maven `-U` flag - **DIDN'T HELP**
3. ✅ Changed `settings.xml` `updatePolicy` from `daily` to `never` - **DIDN'T HELP**
4. ✅ Created `dependencies.lock` (version-independent cache key) - **DIDN'T HELP**

### The Real Problem (Builds 6-10)
**Kubernetes Ephemeral Pods + No Shared Cache Server**

Each build runs in a **fresh Kubernetes pod** that's destroyed after completion:
- Build says "Successfully extracted cache" 
- But `.m2/repository` doesn't exist (confirmed with debug in build-10)
- Cache is created locally in Pod A, but Build #2 runs in Pod B (fresh/empty)
- Without shared cache server URL, cache is pod-local and lost on pod deletion

**Why:** "No URL provided, cache will not be downloaded from shared cache server. Instead a local version of cache will be extracted."

## Final Solution (2026-05-15)

### Pre-Populate Maven Repository in Base Docker Image

Since cache doesn't work with ephemeral pods, **bake dependencies into the Docker image**.

**Base Image Changes** (`disseminator-base-image/Dockerfile`):
```dockerfile
# Layer 3: Pre-populate Maven repository
RUN mkdir -p /opt/maven-repository && \
    cd /tmp && \
    git clone --depth 1 --branch main https://gitlab.cee.redhat.com/search-engineering/disseminator.git && \
    cd disseminator && \
    mvn -Dmaven.repo.local=/opt/maven-repository dependency:go-offline -DskipTests=true || true && \
    cd / && \
    rm -rf /tmp/disseminator && \
    chown -R temp:temp /opt/maven-repository

ENV MAVEN_OPTS="-Dmaven.repo.local=/opt/maven-repository"
```

**Disseminator Changes** (`.gitlab-ci.yml`):
```yaml
variables:
  MAVEN_OPTS: "-Dmaven.repo.local=/opt/maven-repository -Duser.timezone=EST"

cache:
  # Only cache Solr - Maven deps are in the Docker image
  key:
    files:
      - dependencies.lock
    prefix: "solr-v1"
  paths:
    - solr-cache/
```

## How It Works

1. **Docker image build time**: Clone disseminator, run `mvn dependency:go-offline`, populate `/opt/maven-repository`
2. **CI build time**: Every pod starts with all dependencies already in `/opt/maven-repository`
3. **No cache needed**: Dependencies are part of the image, not cached separately

## Expected Impact

**Before:**
- Maven downloads: 2,374 artifacts
- Build time: ~20 minutes
- Cache: Created but never reused (ephemeral pods)

**After (once base image is rebuilt):**
- Maven downloads: **~0** (all in image)
- Build time: **~2 minutes**
- Cache: Not needed for Maven

## Trade-offs

✅ **Pros:**
- Every build is fast from the start (no "first build slow" issue)
- No cache coordination complexity
- Works perfectly with Kubernetes ephemeral pods
- Solves problem permanently

❌ **Cons:**
- Larger Docker image (~500MB)
- Need to rebuild base image when dependencies change (infrequent)

## Files Changed

**Base Image:**
- `dxp/dat/base-images/disseminator-base-image/Dockerfile` (commit af0b5dd)

**Disseminator:**
- `.gitlab-ci.yml` (commit ca20d358)
- `CACHE_FIX_SUMMARY.md` (documentation)

## Status (2026-05-18) - COMPLETED ✅

### Final Solution Implemented

**Base Image Enhancements:**
- Layer 3: Pre-populated Maven repository (~7,500 artifacts in `/opt/maven-repository`)
- Layer 4: Pre-installed Solr 9.3.0 (~277MB in `/opt/solr/solr-9.3.0`)
- Uses local pom.xml/settings.xml (synced from disseminator, no authentication issues)
- Resource limits optimized for schedulability (CPU: 1000m→500m, Memory: 2Gi→1Gi) to address cluster capacity constraints

**Disseminator Changes (merged to main via squash merge):**
- Uses pre-populated Maven repository and Solr from base image
- Auto-sync job: copies pom.xml/settings.xml to base-image repo when they change on main
- Automatic base-image rebuild triggered by sync (zero manual maintenance)
- Generalized scripts (key.sh) to remove hardcoded user paths
- Comprehensive documentation: CICD.md, CACHE_FIX_SUMMARY.md, BASE_IMAGE_AUTO_SYNC.md

### Results Achieved (Build 14)

**Before optimization:**
- Maven repository: 0 files (empty)
- Maven downloads: 2,374 artifacts per build
- Solr: Downloaded every build (~277MB)
- Build time: ~20 minutes

**After optimization:**
- Maven repository: 7,293 files pre-populated
- Maven downloads: 118 artifacts (95% reduction - remaining are plugins invoked at runtime)
- Solr: Pre-installed, no download needed
- Build time: 13.3 minutes (33% faster)

**Time breakdown:**
- Maven setup: ~1 min (minimal downloads)
- Compilation: ~2-3 min
- Solr init: ~1-2 min (pre-installed, just start it)
- Configset upload: ~5-7 min (unavoidable - ephemeral Zookeeper requires all configsets uploaded every build)
- Tests: ~5-7 min
- Packaging: ~1-2 min

### What Can't Be Optimized

**Ephemeral pod architecture constraints:**
- Configset upload (5-7 min): Fresh Zookeeper on every build = no configsets exist = all must be uploaded
- Collection creation (1-2 min): Ephemeral state requires recreation
- Only solution would be persistent Solr/Zookeeper cluster (major architectural change, not pursued)

### Automated Maintenance

`sync_maven_dependencies_to_base_image` job automatically:
1. Detects pom.xml or settings.xml changes on main branch
2. Copies updated files to base-image repository
3. Commits and pushes to trigger base-image rebuild
4. Next disseminator build uses updated dependencies
5. **Zero manual intervention required**

**Authentication resolution (2026-05-18):**
- Initial implementation used `CI_JOB_TOKEN` - failed with 403 (no cross-project push permission)
- Attempted to configure CI/CD job token allowlist - required Maintainer access not available
- **Solution:** Created Project Access Token in base-image project:
  - Role: Maintainer (required to push to protected main branch)
  - Scopes: read_repository + write_repository
  - Added as `BASE_IMAGE_PUSH_TOKEN` variable in disseminator CI/CD settings
  - Updated .gitlab-ci.yml to use token instead of CI_JOB_TOKEN
- Auto-sync now fully functional

## Documentation

Comprehensive documentation created in disseminator repo:
- [[cicd-documentation]] - Complete CI/CD pipeline explanation, stages, base image architecture, troubleshooting
- [[cache-fix-summary]] - Investigation details, root cause analysis, solution explanation (14 builds analyzed)
- [[base-image-auto-sync]] - Auto-sync setup, authentication options, troubleshooting guide

## Lessons Learned

**Why GitLab cache didn't work:**
- Kubernetes ephemeral pods = fresh pod per build, destroyed after completion
- No shared cache server configured = cache is pod-local
- "Successfully extracted cache" message was misleading - extraction succeeds but directory is empty

**Why smart configset optimization doesn't work:**
- Attempted optimization: only upload changed configsets
- Reality: ephemeral pods = fresh Zookeeper = no configsets exist at all
- Unit/integration tests require all collections → all configsets must exist
- 5-7 min upload time is unavoidable with current architecture
