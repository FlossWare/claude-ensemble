---
name: grafana-access
description: Grafana UI credentials and endpoint on aio-01:3000 for fleet monitoring dashboards
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  updated: 2026-07-12
  priority: high
---

# Grafana Access

**Grafana UI:** http://aio-01:3000

**Credentials:**
- Username: admin
- Password: Stored in `.secrets.md` and orchestrator secrets API (`GRAFANA_ADMIN_PASSWORD`)

**OrientDB Studio:** http://aio-01:2480

**Prometheus:** http://aio-01:9090

**How to access:**
1. Navigate to http://aio-01:3000
2. Login with credentials from `.secrets.md`
3. Add Prometheus data source: http://aio-01:9090
4. Create/import dashboards for queue monitoring

**Related:** [[project_infrastructure_inventory]]
