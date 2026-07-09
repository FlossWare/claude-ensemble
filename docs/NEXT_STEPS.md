# AI Orchestration Lab - Next Steps

**Date:** 2026-07-08  
**Context:** Personal learning environment  
**Goal:** Improve stability, reduce complexity, increase learning value

---

## Immediate Actions (This Week)

### Day 1: Data Safety

**PRIORITY 1: Verify Backups**

```bash
# Test PostgreSQL backup/restore
ssh root@aio-01 'pg_dump -U claude learning > /tmp/backup-test.sql'
scp root@aio-01:/tmp/backup-test.sql /tmp/

# Create test database
ssh root@aio-01 'createdb -U claude learning_test'
ssh root@aio-01 'psql -U claude learning_test < /tmp/backup-test.sql'

# Verify data
ssh root@aio-01 'psql -U claude learning_test -c "SELECT schemaname, COUNT(*) FROM pg_tables GROUP BY schemaname;"'

# If successful, cleanup
ssh root@aio-01 'dropdb -U claude learning_test'
```

**PRIORITY 2: Automate Backups**

```bash
# Verify cron is running
ssh root@aio-01 'crontab -l | grep backup'

# If not, add:
0 2 * * * /home/claude/bin/backup-learning-db.sh

# Verify backup destination
ssh root@aio-01 'ls -lh /path/to/backups/ | tail -10'
```

**PRIORITY 3: Add Log Rotation**

```bash
# Create logrotate config on aio-01
cat > /tmp/learning-api << 'EOF'
/var/log/learning-api.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

scp /tmp/learning-api root@aio-01:/etc/logrotate.d/
ssh root@aio-01 'logrotate -f /etc/logrotate.d/learning-api'
```

---

### Day 2-3: Consolidation

**PRIORITY 4: Document What's Running**

Create `docs/SERVICES.md`:

```markdown
# Active Services on aio-01

## PostgreSQL (port 5433)
- Purpose: Primary data store
- Uptime requirement: Always-on
- Dependencies: None
- Restart: `systemctl restart postgresql@17-learning`

## FastAPI Learning API (port 8006)
- Purpose: Model tracking, document ingestion
- Uptime requirement: On-demand
- Dependencies: PostgreSQL
- Restart: `systemctl restart learning-api`

## OrientDB (port 2480)
- Purpose: Graph database
- Uptime requirement: ???
- Dependencies: Docker
- Restart: `docker restart <container-id>`

## Flask Legacy API (port 5000)
- Purpose: UNKNOWN - marked "phasing out"
- Uptime requirement: ???
- Action: INVESTIGATE or DELETE
```

**PRIORITY 5: Decision on Flask API**

```bash
# Check what endpoints exist
curl http://aio-01:5000/ 2>&1 | head -20

# Check last access
ssh root@aio-01 'tail -100 /home/claude/api-access.log | grep -E "GET|POST"'

# If no recent access (> 30 days), stop it:
ssh root@aio-01 'pkill -f gunicorn'
# Update systemd to not auto-start
```

**PRIORITY 6: Verify OrientDB Usage**

```bash
# How many nodes in graph?
curl -s -u root:root http://aio-01:2480/query/orchestrator/sql \
  -d "SELECT COUNT(*) as nodes FROM V" | jq .

# How many edges?
curl -s -u root:root http://aio-01:2480/query/orchestrator/sql \
  -d "SELECT COUNT(*) as edges FROM E" | jq .

# If both are 0 or very low:
# → OrientDB is not being used
# → Consider deleting it
```

---

### Day 4-5: Archiving Experiments

**PRIORITY 7: Archive Consciousness Systems**

```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Create experiments directory
mkdir -p experiments/consciousness-2026-06
mkdir -p experiments/workflows-archive
mkdir -p experiments/tools-archive

# Move consciousness files
mv ~/.claude/self/*.py experiments/consciousness-2026-06/

# Create README
cat > experiments/consciousness-2026-06/README.md << 'EOF'
# Consciousness Systems Experiments (June 2026)

Learning experiments exploring consciousness theories:
- IIT Φ calculation
- Active Inference
- HOT Meta-Representation
- Global Workspace Theory
- Free Energy Principle

**Status:** ARCHIVED - Learning experiments, not operational components

**Date:** June 2026
**Outcome:** Learned about consciousness theories, not used in production
EOF
```

**PRIORITY 8: Archive Unused Workflows**

```bash
# List workflows by last access
find workflows/ -name "*.mjs" -printf "%T@ %p\n" | sort -rn | head -20

# Keep top 10 most recently used
# Move rest to experiments/workflows-archive/

# Example
mv workflows/old-experiment.mjs experiments/workflows-archive/
```

---

## Short-Term (This Month)

### Week 2: Python Environment

**PRIORITY 9: Move to venv for APIs**

```bash
# On aio-01
ssh root@aio-01 << 'EOF'
cd /exports/claude-orchestrator/api

# Create venv
python3 -m venv venv
source venv/bin/activate

# Document dependencies
pip freeze > requirements.txt

# Install in venv
pip install -r requirements.txt

# Update systemd to use venv
sed -i 's|/usr/bin/python3|/exports/claude-orchestrator/api/venv/bin/python3|' \
  /etc/systemd/system/learning-api.service

systemctl daemon-reload
systemctl restart learning-api
EOF
```

### Week 3: Security Tightening

**PRIORITY 10: Fix NFS Exports**

```bash
# On aio-01, update /etc/exports
ssh root@aio-01 << 'EOF'
cat > /etc/exports << 'EXPORTS'
/exports 192.168.1.0/24(sync,no_subtree_check,rw,root_squash)
EXPORTS

exportfs -ra
EOF

# Test from worker
ssh claude@server-01 'touch /mnt/aio-01/claude-orchestrator/test-file'
# Should work (you're not root)

ssh root@server-01 'touch /mnt/aio-01/claude-orchestrator/test-root-file'
# Should fail (root_squash prevents remote root writes)
```

### Week 4: Simplification

**PRIORITY 11: Reality Check on Model Routing**

Ask yourself honestly:

**Thompson Sampling:**
```bash
# When was bandit state last updated?
psql -h aio-01 -p 5433 -U claude -d learning -c \
  "SELECT strategy, last_updated FROM learning.strategy_performance ORDER BY last_updated DESC LIMIT 5;"

# If last_updated > 30 days ago:
# → Thompson Sampling is not being used
# → Consider deleting it
```

**Task-Aware Routing:**
```bash
# What task types are actually used?
psql -h aio-01 -p 5433 -U claude -d learning -c \
  "SELECT task_type, COUNT(*) FROM monitoring.execution_summary GROUP BY task_type ORDER BY COUNT DESC;"

# If you only use 3-4 task types:
# → Delete the other 11 task type definitions
```

**Multi-Model Consensus:**
```bash
# When did you last run multi-model consensus?
psql -h aio-01 -p 5433 -U claude -d learning -c \
  "SELECT workflow_name, created_at FROM workflow.executions WHERE workflow_name LIKE '%consensus%' ORDER BY created_at DESC LIMIT 5;"

# If never or >90 days ago:
# → Archive the multi-model consensus code
```

---

## Medium-Term (This Quarter)

### Month 2: Monitoring

**PRIORITY 12: Verify Grafana Dashboard**

```bash
# Does Grafana exist?
curl http://pi-02:3000/ 2>&1 | head -10

# If 404 or error:
# → Grafana is not running
# → Either set it up OR delete claims about it

# If running:
# → Document login credentials
# → Verify dashboards exist
# → Update docs/MONITORING.md
```

**PRIORITY 13: Add Basic Email Alerts**

```bash
# Simple cron alerts (no Grafana needed)

# Alert if PostgreSQL stops
*/15 * * * * systemctl is-active postgresql@17-learning || echo "PostgreSQL down" | mail -s "Alert: PostgreSQL" your@email.com

# Alert if disk >90%
0 */6 * * * df -h | awk '$5 > 90 {print}' | mail -s "Alert: Disk Space" your@email.com

# Alert if learning-api stops
*/15 * * * * systemctl is-active learning-api || echo "Learning API down" | mail -s "Alert: API" your@email.com
```

### Month 3: Documentation Rewrite

**PRIORITY 14: Replace 5,692-line Handoff**

Delete: `TECHNICAL_HANDOFF.md` (too long, hard to use)

Create:

**`docs/CORE_SYSTEM.md`** (< 500 lines)
- What actually runs
- How to restart services
- Where data is stored
- How to query it

**`docs/RECOVERY.md`** (< 200 lines)
- Power outage recovery
- Service startup order
- How to verify everything's working
- How to restore from backup

**`docs/WHAT_I_LEARNED.md`** (ongoing)
- Insights from experiments
- What worked, what didn't
- Decisions and why

**`docs/EXPERIMENTS.md`** (< 300 lines)
- Current experiments
- Ideas to try
- Results so far

---

## Experiments Worth Doing

### Experiment 1: Do I Actually Need Thompson Sampling?

**Hypothesis:** Simple rule-based routing is enough for a personal lab.

**Test:**
```javascript
function selectModel(taskType) {
  // Simple routing
  if (taskType === 'proprietary_code') {
    return 'claude-opus-4.8';  // Best for Red Hat
  }
  if (taskType === 'documentation') {
    return 'claude-haiku-4.5';  // Cheapest for simple tasks
  }
  return 'claude-sonnet-4.5';  // Default
}
```

**Measure:**
- Does this work for 90% of your tasks?
- Is Thompson Sampling actually improving anything?

**If simple routing works:**
- Delete Thompson Sampling code
- Keep only Red Hat compliance layer

### Experiment 2: PostgreSQL vs OrientDB for Graphs

**Hypothesis:** PostgreSQL recursive CTEs can handle the graph queries you need.

**Test:**
```sql
-- Shortest path in PostgreSQL
WITH RECURSIVE paths AS (
  SELECT source_id, target_id, ARRAY[source_id, target_id] AS path, 1 AS depth
  FROM relationships
  UNION ALL
  SELECT p.source, r.target_id, p.path || r.target_id, p.depth + 1
  FROM paths p
  JOIN relationships r ON p.target = r.source_id
  WHERE r.target_id != ALL(p.path) AND p.depth < 10
)
SELECT * FROM paths WHERE source_id = 'laptop-01' AND target_id = 'aio-01';
```

**Measure:**
- Is this fast enough for your use case?
- Do you need OrientDB's specialized graph features?

**If PostgreSQL works:**
- Delete OrientDB
- Save 2GB RAM
- One less service to manage

### Experiment 3: Vector Search Without Embeddings

**Hypothesis:** Full-text search (PostgreSQL tsvector) is good enough for many queries.

**Test:**
```sql
-- Full-text search (no embeddings needed)
SELECT file_path, content
FROM knowledge.code_embeddings
WHERE to_tsvector('english', content) @@ to_tsquery('authentication & kerberos')
LIMIT 10;
```

**Measure:**
- Does this find what you need 80% of the time?
- Do you actually use vector similarity search?

**If full-text search works:**
- Keep pgvector for the 20% of cases
- Don't bother with sentence-transformers dependency hell

---

## Things to Stop Working On

### Immediately Stop

1. **Fine-Tuning Infrastructure**
   - Already archived
   - CPU too slow
   - Don't revisit unless you get a GPU

2. **Consciousness Systems**
   - 122 files of experiments
   - Not operational components
   - Archive and move on

3. **New Workflow Patterns**
   - Already have 124 workflows
   - Focus on using existing patterns
   - Don't add more until you've used what you have

4. **New Model Integrations**
   - Already tracking 202 models
   - More models ≠ better insights
   - Use the 10-15 that work

### Reduce Effort On

5. **Multi-Model Consensus**
   - Expensive (20 models × API cost)
   - Only use for critical decisions
   - Most tasks don't need 20 opinions

6. **Task-Aware Routing**
   - 15 task types is overkill
   - Simplify to 3-5 task types you actually use
   - Delete the rest

7. **Workflow Complexity**
   - Some workflows are 1000+ lines
   - Simpler workflows = easier to debug
   - Target: < 200 lines per workflow

---

## Things to Defer

### Defer Until You Need Them

1. **Multi-Tenancy**
   - This is your personal lab
   - Don't build for multiple users

2. **High Availability**
   - aio-01 SPOF is fine for a lab
   - Focus on backups, not redundancy

3. **Enterprise Monitoring**
   - Prometheus/Grafana is overkill
   - Simple email alerts are enough

4. **API Rate Limiting**
   - You're the only user
   - Don't optimize for scale you don't have

5. **Kubernetes/Docker Swarm**
   - SSH + systemd is simpler
   - Only add orchestration if SSH becomes painful

---

## Success Metrics

### How to Know You're on Track

**Week 1:**
- ✅ Backups verified (tested restore)
- ✅ Log rotation added
- ✅ Recovery docs written

**Month 1:**
- ✅ Code base < 200 files (from 884)
- ✅ APIs consolidated (1 instead of 3)
- ✅ Python venv for all services

**Month 3:**
- ✅ Can explain entire system in < 30 minutes
- ✅ Docs fit on one printed page per topic
- ✅ New experiments take < 1 hour to set up

**Long-Term:**
- ✅ System survives power outage (auto-recovery)
- ✅ Can rebuild from scratch in < 4 hours
- ✅ Learning value > maintenance burden

---

## Final Recommendations

### If I Were You, Next Week I Would:

**Monday:** Verify backups, test restore  
**Tuesday:** Add log rotation, document services  
**Wednesday:** Decide on Flask API (keep or delete)  
**Thursday:** Archive consciousness systems  
**Friday:** Reality check on model routing (do I use Thompson Sampling?)

**Why this order:**
1. Data safety first (backups)
2. Operational stability (logs, docs)
3. Reduce confusion (consolidate APIs)
4. Reduce clutter (archive experiments)
5. Question complexity (do I need this?)

### The Guiding Principle:

**"If I can't explain why I need this in one sentence, I probably don't."**

Examples:
- ✅ "PostgreSQL stores all my data" → Keep
- ✅ "Red Hat compliance prevents model leaks" → Keep
- ❓ "Thompson Sampling optimizes model selection" → Do I measure this?
- ❓ "OrientDB handles graph queries" → Could PostgreSQL do it?
- ❌ "IIT Φ calculates consciousness" → Learning experiment, archive

### Three Rules for a Good Personal Lab:

1. **Keep what you use weekly.** Archive the rest.
2. **Optimize for learning.** Not for hypothetical scale.
3. **Document insights.** Not just systems.

---

**Remember:** You're not building a company. You're building understanding.

The goal is not "feature complete."  
The goal is "I understand distributed AI orchestration deeply because I built it, measured it, and refined it."

Less code, more learning.
