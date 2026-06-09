---
name: project-ci-troubleshooting
description: CI pipeline troubleshooting approach and tools for SFDeasy
metadata: 
  node_type: memory
  type: project
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

**CI Pipeline Troubleshooting Approach:**

When GitLab pipeline fails but local builds succeed, the issue is environment-specific. Check in this order:

1. **Certificate Import** - CI runs certificate import step:
   ```bash
   curl https://certs.corp.redhat.com/certs/2022-IT-Root-CA.pem -o /tmp/redhat.pem
   keytool -importcert -alias redhat -file /tmp/redhat.pem -storepass "$KEYTOOL_PASSWORD" -noprompt
   ```
   Requires KEYTOOL_PASSWORD CI/CD variable to be set

2. **SSH Setup** - CI runs `ci/scripts/create_ssh.sh` script
   
3. **Maven Nexus Settings** - CI copies `ci/settings.xml` and replaces NEXUS_PASSWORD:
   ```bash
   cp ci/settings.xml ~/.m2/
   sed -i "s|NEXUS_PASSWORD|${NEXUS_PASSWORD}|g" ~/.m2/settings.xml
   ```
   Requires NEXUS_PASSWORD CI/CD variable to be set

4. **Java Version** - CI uses the base image Java version (check .gitlab-ci.yml image setting)

**Monitoring Tools Created:**

Script: `/tmp/watch_pipeline.sh`
- Polls GitLab API every 30 seconds
- Detects new pipelines automatically
- Shows status updates with timestamps
- Reports failed jobs when pipeline completes
- Usage: `bash /tmp/watch_pipeline.sh`

**API Access:**
- Project ID: customer-platform%2Fsfdeasy (URL-encoded)
- API base: https://gitlab.cee.redhat.com/api/v4
- Pipeline list: `/projects/{project}/pipelines?per_page=1`
- Pipeline jobs: `/projects/{project}/pipelines/{id}/jobs`
- Job trace (requires auth): `/projects/{project}/jobs/{job_id}/trace`

**Why:** Local vs CI differences are common in enterprise environments with custom certificates, proxies, and authentication requirements. Red Hat's internal Nexus and GitLab require special configuration that works in CI but may differ locally.

**How to apply:** When CI fails but local succeeds, don't assume the code is wrong - investigate the CI environment configuration first. Always check GitLab UI logs for exact error messages before attempting fixes.
