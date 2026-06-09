---
name: reference_deployment_locations
description: FlossWare project deployment and repository locations
metadata: 
  node_type: memory
  type: reference
  originSessionId: f26c00bc-2e0f-4df4-8b1f-d7888af7de1f
---

FlossWare Java projects are deployed to packagecloud.io and hosted on GitHub under the FlossWare organization.

**Deployment:**
- Maven repository: https://packagecloud.io/flossware/java/maven2/
- Requires: PACKAGECLOUD_TOKEN secret in GitHub Actions
- Distribution ID in pom.xml: `packagecloud-flossware`

**Source repositories:**
- Organization: https://github.com/FlossWare
- Example projects: jcollections, jclassloader

**Important:** Projects must be under FlossWare organization (not personal personal account) to access the organization's PACKAGECLOUD_TOKEN secret for automated deployment.
