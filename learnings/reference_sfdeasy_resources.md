---
name: reference-sfdeasy-resources
description: URLs and locations for SFDeasy project resources
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

**GitLab Repository:**
- URL: https://gitlab.cee.redhat.com/customer-platform/sfdeasy
- Remote name: `gitlab` (not `origin`)
- Main branch: `main`

**CI/CD Pipeline:**
- Pipelines: https://gitlab.cee.redhat.com/customer-platform/sfdeasy/-/pipelines
- Variables: https://gitlab.cee.redhat.com/customer-platform/sfdeasy/-/settings/ci_cd

**Artifact Repositories:**
- Releases: https://nexus.corp.redhat.com/repository/information-retrieval-maven2-releases/
- Snapshots: https://nexus.corp.redhat.com/repository/information-retrieval-maven2-snapshots/

**External Dependencies:**
- Solenopsis session library: https://github.com/solenopsis/session
- FlossWare commons: https://github.com/FlossWare/commons

**CI/CD Variables Required:**
- `NEXUS_PASSWORD` - Nexus repository authentication
- `KEYTOOL_PASSWORD` - Java keystore for Red Hat cert import
- `SF_CREDENTIALS_FILE` (optional) - Salesforce credentials for integration tests
