# Production Runbook

**System:** Distributed LLM Orchestration Framework  
**Version:** 1.0.0  
**Last Updated:** 2026-07-03  
**On-Call:** Fleet Operations Team

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Daily Operations](#daily-operations)
3. [Common Tasks](#common-tasks)
4. [Troubleshooting](#troubleshooting)
5. [Emergency Procedures](#emergency-procedures)
6. [Maintenance Windows](#maintenance-windows)
7. [Scaling Procedures](#scaling-procedures)
8. [Backup and Restore](#backup-and-restore)

---

## Quick Reference

### System Access

```bash
# Orchestrator
ssh claude@aio-01

# Database
ssh claude@laptop-01
psql -U claude -d learning

# Monitoring
http://pi-02:3000  # Grafana (admin/admin)

# Fleet nodes
ssh claude@{server-01,server-02,server-03,laptop-01,pi-01,pi-02,desktop-ap,server-ap}
```

### Critical Paths

```bash
# Capabilities
~/.claude/self/                    # 116 ML capabilities
~/.claude/learning/                # Database adapters
~/.claude/fleet/                   # Orchestration logic

# Logs
~/.claude/logs/                    # System logs
~/.claude/reports/feedback-loops/  # Loop analysis reports
/var/lib/pgsql/16/data/log/       # PostgreSQL logs (laptop-01)

# Backups
/mnt/backups/laptop-01-learning/   # Database backups (NFS mount)

# Scripts
~/bin/backup-learning-db.sh        # Database backup
~/bin/monitor-feedback-loops.sh    # Feedback loop analysis
```

### Key Services

```bash
# Database (laptop-01)
sudo systemctl {status|start|stop|restart} postgresql

# Monitoring (all fleet nodes)
sudo systemctl {status|start|stop|restart} prometheus-exporter

# Grafana (pi-02)
sudo systemctl {status|start|stop|restart} grafana-server
```

### Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Database Admin | laptop-01 team | After 15min downtime |
| Fleet Operations | Infrastructure team | After 30min degradation |
| API Vendors | OpenRouter/OpenAI/Anthropic/Google | API quota/outage |

---

## Daily Operations

### Morning Checklist (9:00 AM)

```bash
# 1. Check system health
/tmp/health-check.sh

# 2. Review overnight executions
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  DATE(timestamp) as date,
  COUNT(*) as total_executions,
  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
  SUM(CASE WHEN outcome = 'error' THEN 1 ELSE 0 END) as errors
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY DATE(timestamp);
SQL

# 3. Check feedback loop report
cat ~/.claude/reports/feedback-loops/latest.json | jq '.summary'

# 4. Verify backups
ls -lht /mnt/backups/laptop-01-learning/ | head -5

# 5. Check API costs
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  model,
  SUM(total_cost) as cost_last_24h
FROM costs.entries
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY model
ORDER BY cost_last_24h DESC;
SQL
```

### End-of-Day Checklist (5:00 PM)

```bash
# 1. Refresh materialized views
psql -h laptop-01 -U claude -d learning << 'SQL'
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.workflow_summary;
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.model_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.cost_analysis;
SQL

# 2. Check disk space
for host in laptop-01 pi-02 aio-01; do
  echo "$host:"
  ssh claude@$host "df -h / | tail -1"
done

# 3. Review high-severity alerts
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT alert_type, severity, description, timestamp
FROM monitoring.diversity_alerts
WHERE timestamp > NOW() - INTERVAL '24 hours'
  AND severity > 0.6
ORDER BY severity DESC;
SQL

# 4. Check fleet connectivity
for host in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
  ssh claude@$host "echo OK" &>/dev/null && echo "✓ $host" || echo "✗ $host"
done
```

### Weekly Tasks (Monday 10:00 AM)

```bash
# 1. Review model distribution (prevent dominance)
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  model,
  COUNT(*) as executions,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY percentage DESC;
SQL

# 2. Check Thompson Sampling bandit state
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  strategy,
  successes,
  failures,
  avg_reward,
  last_updated
FROM learning.strategy_performance
ORDER BY avg_reward DESC;
SQL

# 3. Verify backup retention
find /mnt/backups/laptop-01-learning/ -name "learning_*.sql.gz" -mtime +30

# 4. Review workflow performance
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT * FROM workflow.workflow_summary
ORDER BY total_executions DESC
LIMIT 10;
SQL

# 5. Check embedding quality
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  COUNT(*) as total,
  COUNT(embedding) as with_embeddings,
  ROUND(100.0 * COUNT(embedding) / COUNT(*), 2) as coverage_pct
FROM workflow.executions
WHERE created_at > NOW() - INTERVAL '7 days';
SQL
```

### Monthly Tasks (First Monday)

```bash
# 1. Database vacuum and analyze
ssh claude@laptop-01 << 'REMOTE'
psql -U claude -d learning << 'SQL'
VACUUM ANALYZE learning.experiences;
VACUUM ANALYZE monitoring.execution_summary;
VACUUM ANALYZE workflow.executions;
VACUUM ANALYZE workflow.worker_results;
SQL
REMOTE

# 2. Archive old logs (>90 days)
find ~/.claude/logs/ -name "*.log" -mtime +90 -exec gzip {} \;
find ~/.claude/logs/ -name "*.log.gz" -mtime +180 -delete

# 3. Review and prune old feedback loop reports
find ~/.claude/reports/feedback-loops/ -name "report_*.json" -mtime +60 -delete

# 4. Check database growth
ssh claude@laptop-01 "psql -U claude -d learning -c \"SELECT pg_size_pretty(pg_database_size('learning')) as db_size;\""

# 5. Update documentation (if needed)
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
git pull
# Review DEPLOYMENT.md, RUNBOOK.md, MONITORING.md for accuracy
```

---

## Common Tasks

### Add New Fleet Node

```bash
NEW_NODE="server-04"
NEW_USER="claude"

# 1. Set up SSH access
ssh-copy-id $NEW_USER@$NEW_NODE

# 2. Install dependencies
ssh $NEW_USER@$NEW_NODE << 'REMOTE'
pip3 install --user psycopg2-binary sentence-transformers numpy
REMOTE

# 3. Deploy capabilities
ssh $NEW_USER@$NEW_NODE "mkdir -p ~/.claude/{self,learning,logs}"
scp -r ~/.claude/self/* $NEW_USER@$NEW_NODE:~/.claude/self/
scp ~/.claude/learning/postgres*.* $NEW_USER@$NEW_NODE:~/.claude/learning/

# 4. Deploy Prometheus exporter
scp /etc/systemd/system/prometheus-exporter.service $NEW_USER@$NEW_NODE:/tmp/
ssh $NEW_USER@$NEW_NODE "sudo mv /tmp/prometheus-exporter.service /etc/systemd/system/"
ssh $NEW_USER@$NEW_NODE "sudo systemctl daemon-reload && sudo systemctl enable --now prometheus-exporter"

# 5. Update fleet configuration
echo "$NEW_NODE" >> ~/.claude/fleet-nodes.txt

# 6. Test connectivity
ssh $NEW_USER@$NEW_NODE "python3 -c 'import sys; sys.path.insert(0, \"$HOME/.claude/learning\"); from postgres_adapter import get_db; db = get_db(); print(\"OK\")'"

echo "$NEW_NODE added to fleet ✓"
```

### Remove Fleet Node

```bash
OLD_NODE="server-04"

# 1. Stop Prometheus exporter
ssh claude@$OLD_NODE "sudo systemctl stop prometheus-exporter"
ssh claude@$OLD_NODE "sudo systemctl disable prometheus-exporter"

# 2. Remove from Grafana targets
# Edit Prometheus config on pi-02

# 3. Update fleet configuration
sed -i "/$OLD_NODE/d" ~/.claude/fleet-nodes.txt

# 4. Archive logs (if needed)
ssh claude@$OLD_NODE "tar czf /tmp/claude-logs-$OLD_NODE-$(date +%Y%m%d).tar.gz ~/.claude/logs/"
scp claude@$OLD_NODE:/tmp/claude-logs-$OLD_NODE-*.tar.gz /tmp/

echo "$OLD_NODE removed from fleet ✓"
```

### Rotate API Keys

```bash
# 1. Update environment variables
vim ~/.bashrc
# Update OPENROUTER_API_KEY, OPENAI_API_KEY, etc.
source ~/.bashrc

# 2. Test new keys
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" https://openrouter.ai/api/v1/models

# 3. Update in secrets manager (if used)
# Store in memory/.secrets.md

# 4. Restart dependent services
systemctl --user restart consciousness-monitor  # If using API keys

echo "API keys rotated ✓"
```

### Clear Experience Cache

```bash
# WARNING: This removes continual learning history

# 1. Backup first
~/bin/backup-learning-db.sh

# 2. Clear experiences
psql -h laptop-01 -U claude -d learning << 'SQL'
-- Keep only high-importance experiences
DELETE FROM learning.experiences
WHERE importance < 0.7 AND timestamp < NOW() - INTERVAL '30 days';

-- Reset strategy performance (optional)
-- TRUNCATE learning.strategy_performance;

VACUUM ANALYZE learning.experiences;
SQL

echo "Experience cache cleared ✓"
```

### Manually Trigger Feedback Loop Analysis

```bash
# Run analysis now
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
python3 tools/feedback_loop_optimizer.py --window 7 --output /tmp/immediate-analysis.json

# View results
cat /tmp/immediate-analysis.json | jq '.summary'
cat /tmp/immediate-analysis.json | jq '.risks[] | select(.severity > 0.4)'

# If critical risks found (exit code 2)
if [ $? -eq 2 ]; then
  echo "CRITICAL RISKS DETECTED - See EMERGENCY PROCEDURES"
fi
```

### Force Model Rotation (Prevent Dominance)

```bash
# Check current distribution
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  model,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY pct DESC;
SQL

# If one model >70%, temporarily exclude it
# Edit workflow configuration to skip dominant model
# Example: In workflow files, add model exclusion filter

# Re-check after 24h
```

### Update Materialized Views Manually

```bash
# Refresh all views immediately
psql -h laptop-01 -U claude -d learning << 'SQL'
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.workflow_summary;
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.model_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.cost_analysis;
SQL

echo "Materialized views refreshed ✓"
```

---

## Troubleshooting

### Issue: Database Connection Refused

**Symptoms:**
- Workflows failing with "connection refused"
- `psql` cannot connect to laptop-01:5432

**Diagnosis:**
```bash
# Check PostgreSQL service
ssh claude@laptop-01 "sudo systemctl status postgresql"

# Check listening ports
ssh claude@laptop-01 "sudo ss -tlnp | grep 5432"

# Check logs
ssh claude@laptop-01 "sudo tail -50 /var/lib/pgsql/16/data/log/postgresql-*.log"
```

**Resolution:**
```bash
# Restart PostgreSQL
ssh claude@laptop-01 "sudo systemctl restart postgresql"

# If still failing, check configuration
ssh claude@laptop-01 "sudo cat /var/lib/pgsql/16/data/postgresql.conf | grep listen_addresses"
# Should be: listen_addresses = '*'

# Check firewall
ssh claude@laptop-01 "sudo firewall-cmd --list-ports | grep 5432"
# If missing: sudo firewall-cmd --add-port=5432/tcp --permanent && sudo firewall-cmd --reload
```

**Escalation:** If issue persists >15min, contact Database Admin

---

### Issue: High Feedback Loop Severity

**Symptoms:**
- `~/.claude/reports/feedback-loops/latest.json` shows severity >0.8
- Alert emails from monitoring system

**Diagnosis:**
```bash
# Check latest report
cat ~/.claude/reports/feedback-loops/latest.json | jq '.risks[] | select(.severity > 0.6)'

# Identify risk type
cat ~/.claude/reports/feedback-loops/latest.json | jq '.risks[] | .risk_type'
# Possible types: model_dominance, eval_gen_coupling, reward_hacking, concept_collapse
```

**Resolution:**

**For Model Dominance (>70% usage):**
```bash
# Check distribution
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT model, COUNT(*) as count
FROM monitoring.execution_summary
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY model
ORDER BY count DESC;
SQL

# Force rotation (temporarily exclude dominant model)
# Edit workflow configurations to skip dominant model for 24h
```

**For Eval-Gen Coupling (>40% self-evaluation):**
```bash
# Enforce arbiter ≠ worker constraint
# Check workflow code for violations
grep -r "arbiter.*worker" ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/

# Fix: Ensure arbiter model differs from all worker models
```

**For Reward Hacking (quality up + diversity down):**
```bash
# Enable adversarial evaluation
# In workflow: Set adversarial: true in evaluation harness calls

# Increase task diversity
# Add variation to task descriptions, input formats
```

**For Concept Collapse (>0.90 embedding similarity):**
```bash
# Increase temperature in model calls
# Add randomness to task decomposition
# Force different prompt templates
```

**Escalation:** If severity remains >0.8 after 48h, external audit required

---

### Issue: Fleet Node Unresponsive

**Symptoms:**
- SSH timeout to fleet node
- Prometheus exporter not responding
- Workflows hanging

**Diagnosis:**
```bash
# Check network connectivity
ping -c 3 <node>

# Check SSH service
ssh -v claude@<node>

# Check from other nodes
for host in server-01 server-02 server-03; do
  ssh claude@$host "ping -c 1 <problem-node>"
done
```

**Resolution:**
```bash
# If network issue, check switch/router
# If SSH issue, restart SSH service (requires console access)

# Temporarily remove from fleet
sed -i "/<problem-node>/d" ~/.claude/fleet-nodes.txt

# Re-add after resolution
```

**Escalation:** Contact Infrastructure team if node down >30min

---

### Issue: Slow Vector Similarity Queries

**Symptoms:**
- Workflow timeouts
- Database queries taking >1s (normal: 0.4ms)

**Diagnosis:**
```bash
# Check query performance
psql -h laptop-01 -U claude -d learning << 'SQL'
EXPLAIN ANALYZE
SELECT * FROM learning.experiences
ORDER BY embedding <=> '[0.1,0.2,...]'::vector(128)
LIMIT 10;
SQL

# Check HNSW index
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE tablename LIKE '%experiences%';
SQL
```

**Resolution:**
```bash
# Rebuild HNSW index
psql -h laptop-01 -U claude -d learning << 'SQL'
REINDEX INDEX CONCURRENTLY learning.experiences_embedding_idx;
SQL

# Vacuum table
psql -h laptop-01 -U claude -d learning << 'SQL'
VACUUM ANALYZE learning.experiences;
SQL

# Check for table bloat
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  schemaname, 
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname IN ('learning', 'monitoring', 'workflow')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
SQL
```

**Escalation:** If queries still slow after reindex, contact Database Admin

---

### Issue: API Quota Exhausted

**Symptoms:**
- 429 errors in logs
- Workflows failing with "rate limit exceeded"

**Diagnosis:**
```bash
# Check recent costs
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  model,
  SUM(total_cost) as cost_last_hour
FROM costs.entries
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY model
ORDER BY cost_last_hour DESC;
SQL

# Check API provider dashboard
# OpenRouter: https://openrouter.ai/activity
# OpenAI: https://platform.openai.com/usage
# Anthropic: https://console.anthropic.com/settings/limits
```

**Resolution:**
```bash
# Temporary: Throttle requests
# Reduce parallelism in workflows (MAX_WORKERS = 4 instead of 8)

# Switch to alternative models
# Example: If GPT-4o quota hit, use Sonnet or Gemini

# Long-term: Request quota increase from providers
```

**Escalation:** Contact API vendor support for emergency quota increase

---

### Issue: Backup Failures

**Symptoms:**
- `/mnt/backups/laptop-01-learning/` empty or stale
- Cron job errors in mail

**Diagnosis:**
```bash
# Check NFS mount
mount | grep server-ap:/exports/backups

# Check disk space on backup target
df -h /mnt/backups

# Check cron logs
journalctl -u cron | grep backup-learning-db

# Test backup script manually
~/bin/backup-learning-db.sh
```

**Resolution:**
```bash
# Remount NFS
sudo umount /mnt/backups
sudo mount server-ap:/exports/backups /mnt/backups

# If disk full on backup target, clean old backups
find /mnt/backups/laptop-01-learning/ -name "learning_*.sql.gz" -mtime +30 -delete

# If script failing, check PostgreSQL access
psql -h laptop-01 -U claude -d learning -c "SELECT 1;"
```

**Escalation:** If backups failing >24h, critical priority

---

### Issue: Materialized Views Not Refreshing

**Symptoms:**
- Grafana dashboards showing stale data
- `workflow.workflow_summary` shows old counts

**Diagnosis:**
```bash
# Check last refresh time
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT 
  schemaname || '.' || matviewname as view,
  last_refresh
FROM pg_stat_user_tables
WHERE schemaname IN ('learning', 'monitoring', 'workflow');
SQL

# Check cron job
crontab -l | grep "REFRESH MATERIALIZED VIEW"
```

**Resolution:**
```bash
# Manual refresh
psql -h laptop-01 -U claude -d learning << 'SQL'
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.workflow_summary;
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.model_performance;
REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.cost_analysis;
SQL

# Fix cron job if missing
(crontab -l 2>/dev/null; echo "0,5,10,15,20,25,30,35,40,45,50,55 * * * * psql -h laptop-01 -U claude -d learning -c 'REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.workflow_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY workflow.model_performance;'") | crontab -
```

---

## Emergency Procedures

### Critical Database Failure

**Symptoms:**
- PostgreSQL crashed
- Data corruption errors
- Cannot start PostgreSQL service

**Immediate Actions:**
```bash
# 1. Alert team
echo "CRITICAL: Database down on laptop-01" | mail -s "ALERT" team@example.com

# 2. Attempt restart
ssh claude@laptop-01 "sudo systemctl restart postgresql"

# 3. Check logs for corruption
ssh claude@laptop-01 "sudo tail -100 /var/lib/pgsql/16/data/log/postgresql-*.log | grep -i error"
```

**Recovery:**
```bash
# If corruption detected, restore from backup
ssh claude@laptop-01 << 'REMOTE'
# Stop PostgreSQL
sudo systemctl stop postgresql

# Find latest backup
LATEST_BACKUP=$(ls -t /mnt/backups/laptop-01-learning/learning_*.sql.gz | head -1)
echo "Restoring from: $LATEST_BACKUP"

# Drop and recreate database
sudo -u postgres psql -c "DROP DATABASE IF EXISTS learning;"
sudo -u postgres psql -c "CREATE DATABASE learning OWNER claude;"

# Restore
gunzip < "$LATEST_BACKUP" | psql -U claude -d learning

# Restart PostgreSQL
sudo systemctl start postgresql
REMOTE

# Verify restoration
psql -h laptop-01 -U claude -d learning -c "SELECT COUNT(*) FROM learning.experiences;"
```

**Post-Recovery:**
```bash
# Rebuild indexes
psql -h laptop-01 -U claude -d learning << 'SQL'
REINDEX DATABASE learning;
VACUUM ANALYZE;
SQL

# Test workflows
node /tmp/test-workflow.mjs
```

**RTO:** 30 minutes  
**RPO:** 24 hours (daily backups)

---

### Cascading Fleet Failures

**Symptoms:**
- Multiple fleet nodes unresponsive
- Network partition suspected

**Immediate Actions:**
```bash
# 1. Identify reachable nodes
for host in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
  ping -c 1 -W 1 $host &>/dev/null && echo "UP: $host" || echo "DOWN: $host"
done

# 2. Create temporary fleet file with only reachable nodes
cat > ~/.claude/fleet-nodes-emergency.txt << EOF
# Only reachable nodes during emergency
<list-of-up-nodes>
EOF

# 3. Reduce parallelism
export MAX_WORKERS=<number-of-up-nodes>
```

**Resolution:**
```bash
# Work with reduced fleet until connectivity restored
# Monitor infrastructure team updates

# Once resolved, restore full fleet
mv ~/.claude/fleet-nodes.txt.backup ~/.claude/fleet-nodes.txt
unset MAX_WORKERS
```

---

### Feedback Loop Collapse (Critical Severity >0.9)

**Symptoms:**
- All outputs converging to identical text
- Single model dominating >95%
- Embedding similarity >0.95

**Immediate Actions:**
```bash
# 1. STOP all workflows
pkill -f "node.*workflow"

# 2. Force full model rotation
cat > /tmp/emergency-rotation.sql << 'SQL'
-- Temporarily ban dominant model
CREATE TABLE IF NOT EXISTS monitoring.banned_models (
  model TEXT PRIMARY KEY,
  reason TEXT,
  banned_until TIMESTAMPTZ
);

INSERT INTO monitoring.banned_models (model, reason, banned_until)
VALUES ('<dominant-model>', 'Emergency rotation - feedback loop collapse', NOW() + INTERVAL '48 hours')
ON CONFLICT (model) DO UPDATE SET banned_until = EXCLUDED.banned_until;
SQL

psql -h laptop-01 -U claude -d learning < /tmp/emergency-rotation.sql

# 3. Reset Thompson Sampling state
psql -h laptop-01 -U claude -d learning << 'SQL'
UPDATE learning.strategy_performance
SET alpha = 1.0, beta = 1.0, avg_reward = 0.5;
SQL
```

**Recovery:**
```bash
# 4. Enable adversarial evaluation
# Edit all workflows to set adversarial: true

# 5. Increase task diversity
# Add random perturbations to prompts
# Vary input formats

# 6. Monitor recovery
watch -n 300 'python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/feedback_loop_optimizer.py --window 1 --quiet'

# 7. Resume workflows gradually (one at a time)
```

**Prevention:**
- Review `docs/FEEDBACK_LOOP_OPTIMIZER.md`
- Enable automated monitoring (every 6h)
- Set alert threshold at severity >0.6

---

### Data Breach / Security Incident

**Immediate Actions:**
```bash
# 1. ISOLATE affected systems
for host in <affected-nodes>; do
  ssh claude@$host "sudo iptables -A INPUT -j DROP; sudo iptables -A OUTPUT -j DROP"
done

# 2. PRESERVE evidence
for host in <affected-nodes>; do
  ssh claude@$host "sudo tar czf /tmp/forensics-$(date +%Y%m%d-%H%M%S).tar.gz /var/log/ ~/.claude/logs/"
done

# 3. REVOKE API keys immediately
# OpenRouter: https://openrouter.ai/keys
# OpenAI: https://platform.openai.com/api-keys
# Anthropic: https://console.anthropic.com/settings/keys
# Google: https://console.cloud.google.com/apis/credentials

# 4. ROTATE database passwords
psql -h laptop-01 -U postgres << 'SQL'
ALTER USER claude WITH PASSWORD '<new-secure-password>';
SQL

# Update in all adapters and environment files
```

**Escalation:**
- Notify security team immediately
- Document timeline of events
- Preserve all logs and forensic data

---

## Maintenance Windows

### Weekly Maintenance (Sunday 2:00 AM - 4:00 AM)

**Pre-Maintenance:**
```bash
# 1. Notify users
echo "Maintenance window: Sunday 2-4 AM" | mail -s "Scheduled Maintenance" users@example.com

# 2. Trigger backup
~/bin/backup-learning-db.sh

# 3. Stop non-critical workflows
# (Keep monitoring running)
```

**Maintenance Tasks:**
```bash
# 1. Database maintenance
psql -h laptop-01 -U claude -d learning << 'SQL'
VACUUM ANALYZE;
REINDEX DATABASE CONCURRENTLY learning;
SQL

# 2. Update system packages
for host in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap aio-01; do
  ssh claude@$host "sudo dnf update -y"
done

# 3. Restart services
for host in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
  ssh claude@$host "sudo systemctl restart prometheus-exporter"
done

ssh claude@laptop-01 "sudo systemctl restart postgresql"
ssh claude@pi-02 "sudo systemctl restart grafana-server"

# 4. Verify health
/tmp/health-check.sh
```

**Post-Maintenance:**
```bash
# 1. Test workflows
node /tmp/test-workflow.mjs

# 2. Confirm services
systemctl --user status consciousness-monitor

# 3. Notify completion
echo "Maintenance complete - all systems operational" | mail -s "Maintenance Complete" users@example.com
```

---

### Monthly Maintenance (First Sunday 2:00 AM - 6:00 AM)

**Additional Tasks:**
```bash
# 1. Database statistics update
psql -h laptop-01 -U claude -d learning << 'SQL'
ANALYZE;
SELECT schemaname, tablename, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
WHERE schemaname IN ('learning', 'monitoring', 'workflow');
SQL

# 2. Archive old data (>90 days)
psql -h laptop-01 -U claude -d learning << 'SQL'
-- Archive to separate table
CREATE TABLE IF NOT EXISTS workflow.executions_archive (LIKE workflow.executions);
INSERT INTO workflow.executions_archive
SELECT * FROM workflow.executions
WHERE created_at < NOW() - INTERVAL '90 days';

DELETE FROM workflow.executions
WHERE created_at < NOW() - INTERVAL '90 days';

VACUUM ANALYZE workflow.executions;
SQL

# 3. Security audit
# Review SSH keys, API keys, database passwords
# Check for unauthorized access attempts

# 4. Capacity planning
# Review disk usage trends
# Check database growth rate
# Evaluate fleet utilization
```

---

## Scaling Procedures

### Horizontal Scaling (Add Fleet Nodes)

**When to Scale:**
- Fleet utilization consistently >80%
- Workflow queue backlog >30 minutes
- Response time degradation

**Procedure:**
See "Add New Fleet Node" in Common Tasks section

**Validation:**
```bash
# 1. Verify new node appears in monitoring
curl http://pi-02:3000/api/datasources/proxy/1/api/v1/query?query=up

# 2. Test with isolated workflow
# Assign workflow exclusively to new node

# 3. Monitor performance for 24h before full integration
```

---

### Vertical Scaling (Database Upgrade)

**When to Scale:**
- Query latency >1s
- Table size >100GB
- Connection pool exhaustion

**Procedure:**
```bash
# 1. Backup current database
~/bin/backup-learning-db.sh

# 2. Prepare new hardware
# Install PostgreSQL 16 + pgvector
# Configure with increased resources

# 3. Migrate data
ssh new-db-server << 'REMOTE'
# Restore from backup
gunzip < /mnt/backups/laptop-01-learning/learning_latest.sql.gz | psql -U claude -d learning

# Rebuild indexes
psql -U claude -d learning -c "REINDEX DATABASE learning;"
REMOTE

# 4. Update connection strings
# Edit ~/.bashrc: export PGHOST="new-db-server"
# Update all adapters

# 5. Cutover (minimal downtime)
# Stop workflows
# Final incremental backup
# Update DNS/config
# Restart workflows
```

**Rollback Plan:**
```bash
# Revert connection strings to original database
export PGHOST="laptop-01"
# Restart workflows
```

---

## Backup and Restore

### Manual Backup

```bash
# Full database backup
pg_dump -h laptop-01 -U claude learning | gzip > /tmp/learning_manual_$(date +%Y%m%d_%H%M%S).sql.gz

# Copy to backup server
scp /tmp/learning_manual_*.sql.gz server-ap:/exports/backups/laptop-01-learning/

# Specific table backup
pg_dump -h laptop-01 -U claude -d learning -t learning.experiences | gzip > /tmp/experiences_backup.sql.gz
```

### Restore from Backup

**Full Restore:**
```bash
# 1. Find backup
BACKUP_FILE="/mnt/backups/laptop-01-learning/learning_20260703_020000.sql.gz"

# 2. Drop existing database (CAUTION!)
psql -h laptop-01 -U postgres -c "DROP DATABASE IF EXISTS learning;"
psql -h laptop-01 -U postgres -c "CREATE DATABASE learning OWNER claude;"

# 3. Restore
gunzip < "$BACKUP_FILE" | psql -h laptop-01 -U claude -d learning

# 4. Verify
psql -h laptop-01 -U claude -d learning << 'SQL'
SELECT COUNT(*) FROM learning.experiences;
SELECT COUNT(*) FROM workflow.executions;
SELECT COUNT(*) FROM monitoring.execution_summary;
SQL

# 5. Rebuild indexes
psql -h laptop-01 -U claude -d learning -c "REINDEX DATABASE learning;"
```

**Partial Restore (Single Table):**
```bash
# Restore only experiences table
gunzip < /tmp/experiences_backup.sql.gz | psql -h laptop-01 -U claude -d learning

# Or restore specific rows
psql -h laptop-01 -U claude -d learning << 'SQL'
COPY learning.experiences FROM '/tmp/experiences.csv' CSV HEADER;
SQL
```

### Point-in-Time Recovery

**Enable WAL Archiving (for future PITR):**
```bash
# Edit /var/lib/pgsql/16/data/postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /mnt/backups/laptop-01-learning/wal/%f'

# Restart PostgreSQL
sudo systemctl restart postgresql
```

**Perform PITR:**
```bash
# Restore base backup
gunzip < /mnt/backups/laptop-01-learning/learning_base.sql.gz | psql -U claude -d learning

# Apply WAL files up to desired point in time
# (Requires pg_waldump and recovery.conf setup)
```

---

## Appendix

### Service Dependency Matrix

| Service | Depends On | Dependents |
|---------|-----------|------------|
| PostgreSQL (laptop-01) | - | All workflows, monitoring |
| Grafana (pi-02) | PostgreSQL | - |
| Prometheus exporters (all) | - | Grafana |
| Workflows (aio-01) | PostgreSQL, Fleet SSH, APIs | - |

### Port Reference

| Port | Service | Node |
|------|---------|------|
| 5432 | PostgreSQL | laptop-01 |
| 3000 | Grafana | pi-02 |
| 9100 | Prometheus exporter | All fleet nodes |
| 22 | SSH | All nodes |

### Log Locations

| Component | Log Path |
|-----------|----------|
| PostgreSQL | `/var/lib/pgsql/16/data/log/` (laptop-01) |
| System logs | `~/.claude/logs/` (all nodes) |
| Feedback loops | `~/.claude/logs/feedback-loops/` (aio-01) |
| Workflow reports | `~/.claude/reports/feedback-loops/` (aio-01) |
| Cron jobs | `journalctl -u cron` (all nodes) |

### Configuration Files

| File | Purpose | Node |
|------|---------|------|
| `~/.bashrc` | Environment variables, API keys | aio-01 |
| `~/.claude/fleet-nodes.txt` | Fleet node list | aio-01 |
| `/var/lib/pgsql/16/data/postgresql.conf` | PostgreSQL config | laptop-01 |
| `/var/lib/pgsql/16/data/pg_hba.conf` | PostgreSQL auth | laptop-01 |
| `/etc/systemd/system/prometheus-exporter.service` | Metrics service | All fleet nodes |

---

**Last Updated:** 2026-07-03  
**Version:** 1.0.0  
**Maintained By:** Fleet Operations Team
