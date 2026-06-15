---
name: grafana-access
description: Grafana UI credentials and endpoint for Claude fleet monitoring dashboards
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  priority: high
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

# Grafana Access

**Grafana UI:** http://pi-02:3000

**Credentials:**
- Username: admin (default)
- Password: [STORED IN SESSION-ONLY CONTEXT - NOT PERSISTED TO MEMORY]

**Security Note:** 
The password is stored in the active Claude session context only (not written to disk).
To access: Ask Claude "what's the Grafana password" within an active session.
Password is NOT committed to git or saved to memory files.

**Claude Monitoring Endpoints:**
- **Prometheus metrics:** http://pi-02:9101/metrics
- **Session tracker:** Running as systemd service on pi-02
- **Dashboard JSON:** /tmp/claude-session-dashboard.json

**Purpose:**
Real-time monitoring of all Claude Code sessions across the fleet:
- Active sessions by node
- CPU/memory usage per session
- Model inference performance (tokens/sec)
- Job queue length

**How to access:**
1. Navigate to http://pi-02:3000
2. Login with credentials above
3. Add Prometheus data source: http://pi-02:9101
4. Import dashboard from /tmp/claude-session-dashboard.json

**Metrics refresh:** Every 15 seconds
