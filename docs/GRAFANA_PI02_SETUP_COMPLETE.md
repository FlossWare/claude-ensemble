# Grafana Dashboard Setup Summary for pi-02

## Task 1: Configure Prometheus Data Source ✅ COMPLETED

### Actions Taken
1. Created `/etc/grafana/provisioning/datasources/prometheus.yaml` with:
   - Prometheus datasource at `http://localhost:9090` (set as default)
   - SQLite datasource configured (plugin installed)

2. Installed SQLite plugin: `frser-sqlite-datasource v4.0.6`

3. Restarted Grafana service

### Verification
- Prometheus is running and accessible at pi-02:9090
- Grafana successfully connected to Prometheus
- Datasource configuration loaded via provisioning

## Task 2: Import 4 Dashboards ✅ COMPLETED

### Actions Taken
1. Created `/var/lib/grafana/dashboards/` directory
2. Copied 4 dashboard JSON files:
   - autonomous-transparency-dashboard.json
   - grafana-dashboard-fleet.json
   - grafana-dashboard-issues.json
   - transparency-dashboard.json

3. Created `/etc/grafana/provisioning/dashboards/claude-dashboards.yaml`
   - Configured auto-provisioning from `/var/lib/grafana/dashboards/`
   - Set folder: "Fleet Monitoring"
   - 30-second refresh interval

4. Set proper permissions (grafana:grafana)

5. Restarted Grafana to load dashboards

### Verification
- All 4 dashboard files present with correct permissions
- Dashboard provisioning configuration active
- Grafana logs show successful dashboard indexing (5 dashboards total)

## Task 3: Set Up Metrics Exporters ⚠️ PARTIAL

### Currently Working ✅

#### node_exporter (INSTALLED & RUNNING)
- **Status**: Running on multiple fleet nodes
- **Provides**: All required node metrics for fleet dashboard
  - CPU: `node_cpu_seconds_total`
  - Memory: `node_memory_*`
  - Disk: `node_filesystem_*`
  - Network: `node_network_*`
  - Load: `node_load1`, `node_load5`, `node_load15`
  - System: `node_context_switches_total`, `node_boot_time_seconds`

- **Active Targets**:
  - pi-02:9100 (up)
  - server-01:9100 (up)
  - server-02:9100 (up)
  - server-03:9100 (up)
  - aio-01:9100 (up)
  - 192.168.1.126:9100 (down - needs investigation)

#### Existing Custom Metrics (LIMITED)
- `claude_fleet_health_percent`
- `claude_fleet_nodes_reachable`
- `claude_fleet_nodes_total`
- `claude_learning_rate`

### Missing Components ❌

#### 1. Custom Fleet Metrics Exporter (NEEDED)
The `transparency-dashboard.json` requires these metrics that are NOT currently available:
- `fleet_bugs_pending`
- `fleet_bugs_found_total`
- `fleet_bugs_fixed_total`
- `fleet_validations_passed`
- `fleet_validations_failed`
- `fleet_deployments_success`
- `fleet_deployments_failed`
- `fleet_learning_sessions_total`
- `fleet_issues_open`
- `fleet_issues_closed`
- `fleet_bugs_by_severity{severity}`
- `fleet_fix_success_total`
- `fleet_fix_failed_total`
- `fleet_events_total{workflow_id}`

**Recommendation**: Create a custom Prometheus exporter (Python/Go) that:
- Reads from transparency logs/database
- Exposes metrics on port 9101 (or similar)
- Gets scraped by Prometheus

#### 2. Issue Tracking Metrics Exporter (NEEDED)
The `grafana-dashboard-issues.json` requires:
- `issues_open_total{repo}`
- `issues_closed_total{repo}`
- `issues_avg_fix_hours{repo}`
- `issues_auto_fix_success_rate_pct{repo}`
- `issues_auto_fixed_total`
- `issues_human_fixed_total`
- `issues_agents_active_local{repo}`
- `issues_agents_active_fleet{repo}`

**Recommendation**: Create GitHub issues exporter that:
- Uses GitHub API to fetch issue data
- Calculates metrics (auto-fix rate, avg fix time)
- Exposes via Prometheus exporter on port 9102

#### 3. Learning/AI Metrics Exporter (NEEDED)
The `autonomous-transparency-dashboard.json` requires Prometheus metrics:
- `learning_executions_total`
- `learning_active_workflows`
- `fleet_active_nodes`
- `learning_lis_score{model, task_type}`

**Recommendation**: Create AI learning exporter that:
- Monitors workflow execution
- Tracks active AI workers
- Calculates LIS (Learning Intelligence Score)
- Exposes on port 9103

#### 4. SQLite Transparency Database (MISSING)
The `autonomous-transparency-dashboard.json` requires SQLite database at `/var/lib/grafana/transparency.db` with tables:
- `execution_log` - All AI execution records with columns:
  - timestamp, model, model_role, workflow, task_type, phase, label
  - parameters, quality_score, confidence, input_tokens, output_tokens
  - cost_usd, duration_ms, outcome, outcome_notes, error
  
- `model_tuning` - Model performance tracking:
  - model, task_type, avg_quality, avg_confidence, avg_cost_usd
  - avg_duration_ms, sample_count
  
- `model_combinations` - Model synergy analysis:
  - task_type, worker_models, arbiter_model, avg_consensus
  - avg_quality, synergy_score, diversity_score, usage_count
  
- `prompt_patterns` - Prompt effectiveness:
  - model, task_type, pattern_name, avg_quality, avg_confidence
  - usage_count, success_rate, vs_baseline_quality

**Recommendation**: Create database initialization script and populate from:
- Existing workflow logs
- AI execution tracking system
- Cost tracking data
- Model performance metrics

## Next Steps to Complete Setup

### Immediate Actions (High Priority)
1. **Fix down target**: Investigate why 192.168.1.126:9100 is down
2. **Create SQLite database**: 
   ```bash
   cd /var/lib/grafana
   # Create schema and populate from existing logs
   chown grafana:grafana transparency.db
   ```

### Development Required (Medium Priority)
3. **Custom Fleet Metrics Exporter** (Python recommended):
   ```python
   # Pseudocode
   from prometheus_client import start_http_server, Counter, Gauge
   
   bugs_pending = Gauge('fleet_bugs_pending', 'Bugs pending')
   bugs_found = Counter('fleet_bugs_found_total', 'Bugs found')
   # ... etc
   
   start_http_server(9101)
   # Poll transparency database/logs and update metrics
   ```

4. **GitHub Issues Exporter**: Use existing GitHub exporter or create custom one

5. **AI Learning Metrics Exporter**: Integrate with existing AI workflow system

### Testing & Validation
6. Access Grafana at `http://pi-02:3000`
7. Verify dashboards appear under "Fleet Monitoring" folder
8. Check which panels show data vs "No Data"
9. Configure alert rules for critical metrics

## Current Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Prometheus Data Source | ✅ Working | Connected to pi-02:9090 |
| SQLite Data Source | ⚠️ Plugin installed | Database missing |
| Dashboard Files | ✅ Imported | All 4 files loaded |
| node_exporter | ✅ Running | 5/6 targets up |
| Fleet Metrics | ❌ Missing | Custom exporter needed |
| Issues Metrics | ❌ Missing | GitHub exporter needed |
| Learning Metrics | ❌ Missing | AI exporter needed |
| SQLite Database | ❌ Missing | Schema + data needed |

## Estimated Completion
- **Infrastructure**: 100% (Grafana + Prometheus working)
- **Basic Dashboards**: 100% (Fleet dashboard will work with current node_exporter)
- **Advanced Dashboards**: 20% (Need custom exporters + database)
- **Overall**: ~60% functional, 40% requires development work
