---
name: reference-cicd-docs
description: "CI/CD pipeline documentation in disseminator repo: CICD.md, CACHE_FIX_SUMMARY.md, BASE_IMAGE_AUTO_SYNC.md"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8c2c0c92-e4f2-459b-8fd6-8aabd685e77a
---

The disseminator repository has comprehensive CI/CD documentation created during the May 2026 build optimization work.

**Documentation files (all in repo root):**

1. **CICD.md** - Complete pipeline reference
   - All pipeline stages and their purpose
   - Base image architecture (4 layers: system packages, Ansible, Maven repo, Solr)
   - Automatic dependency synchronization mechanism
   - Build optimizations and performance metrics
   - Troubleshooting guide for common issues
   - Time breakdown of typical builds

2. **CACHE_FIX_SUMMARY.md** - Investigation and solution explanation
   - Problem statement and root cause analysis
   - Investigation process across 14 builds
   - Why GitLab cache didn't work (ephemeral pods, no shared cache server)
   - Final solution: pre-populate dependencies in Docker base image
   - Results: 95% reduction in Maven downloads, 33% faster builds
   - Trade-offs and maintenance approach

3. **BASE_IMAGE_AUTO_SYNC.md** - Automation setup and maintenance
   - How auto-sync works (pom.xml changes → base-image rebuild)
   - Authentication setup (CI_JOB_TOKEN vs Project Access Token)
   - Troubleshooting common sync failures
   - Manual rebuild procedures if needed

**When to reference:**
- Questions about build times, CI/CD performance, or pipeline stages
- Troubleshooting build failures or slow builds
- Understanding base image architecture or maintenance
- Explaining why certain optimizations are/aren't possible

Related: [[gitlab-ci-cache-fix]] - The project that created these docs
