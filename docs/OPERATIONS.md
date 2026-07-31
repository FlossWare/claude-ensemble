# Operations Guide

**Version**: 12 | **Last Updated**: 2026-06-13 | **Status**: Production Ready

Deployment procedures, monitoring setup, day-to-day operations, and troubleshooting for Claude Global Skills and its fleet infrastructure.

---

## Table of Contents

- [Deployment](#deployment)
  - [Initial Setup](#initial-setup)
  - [Permissions Setup](#permissions-setup)
  - [Fleet Deployment](#fleet-deployment)
  - [Monitoring Deployment](#monitoring-deployment)
  - [Verification Checklist](#verification-checklist)
- [Day-to-Day Operations](#day-to-day-operations)
  - [Running Skills](#running-skills)
  - [Scheduling Automated Runs](#scheduling-automated-runs)
  - [Managing Token Budgets](#managing-token-budgets)
  - [Workflow Transcript Cleanup](#workflow-transcript-cleanup)
  - [Memory Management](#memory-management)
- [Fleet Operations](#fleet-operations)
  - [Health Monitoring](#health-monitoring)
  - [Fleet Status Checking](#fleet-status-checking)
  - [Worker Maintenance](#worker-maintenance)
  - [NFS Operations](#nfs-operations)
- [Monitoring](#monitoring)
  - [Dashboard Access](#dashboard-access)
  - [Alert Management](#alert-management)
  - [Key Metrics to Watch](#key-metrics-to-watch)
  - [Capacity Planning](#capacity-planning)
- [Operational Procedures](#operational-procedures)
  - [Adding a New Worker](#adding-a-new-worker)
  - [Removing a Worker](#removing-a-worker)
  - [Updating Models](#updating-models)
  - [Updating Dependencies](#updating-dependencies)
  - [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)
  - [Fleet Mode Not Activating](#fleet-mode-not-activating)
  - [Fleet Mode Fails Mid-Execution](#fleet-mode-fails-mid-execution)
  - [SSH Authentication Issues](#ssh-authentication-issues)
  - [NFS Mount Problems](#nfs-mount-problems)
  - [PostgreSQL/pgvector/Embeddings Issues](#postgresqlpgvectorembeddings-issues)
  - [Model Failures](#model-failures)
  - [Workflow Registration Issues](#workflow-registration-issues)
  - [Permission Prompt Issues](#permission-prompt-issues)
  - [High API Costs](#high-api-costs)
  - [Monitoring Issues](#monitoring-issues)
- [Maintenance Schedule](#maintenance-schedule)
- [Incident Response](#incident-response)
- [Environment Variables](#environment-variables)
- [Cross-References](#cross-references)

---

## Deployment

### Initial Setup

```bash
# 1. Clone the repository
git clone https://gitlab.cee.redhat.com/sfloess/claude-global-skills.git
cd claude-global-skills

# 2. Install Node.js dependencies
npm install

# 3. Install Python dependencies (for RAG features)
pip install -r requirements.txt

# 4. Verify Node.js version
node --version
# Must be >= 18.0.0

# 5. Set up permissions
./fix-permissions.sh

# 6. Verify skills are registered
claude --list-skills
```

### Permissions Setup

**Option 1: Auto-approve everything (recommended for autonomous workflows)**

Create `~/.claude/settings.json`:
```json
{
  "permissions": {
    "mode": "dontAsk"
  },
  "skipWorkflowUsageWarning": true
}
```

Create `~/.claude/settings.local.json`:
```json
{
  "permissions": {
    "mode": "dontAsk"
  }
}
```

**Option 2: Granular allowlist (for fine-grained control)**

See `PERMISSIONS.md` for the complete allowlist covering:
- GitHub/GitLab CLI commands
- Git operations
- Node.js/npm/yarn/pnpm
- Maven/Gradle
- Python/pip
- Docker/Podman
- SSH/SCP (fleet operations)
- Kubernetes (future)

**Option 3: Automated setup**

```bash
./fix-permissions.sh
# Sets dontAsk mode globally and for all projects
```

### Fleet Deployment

**Prerequisites**:
- SSH key-based authentication to all workers
- NFS share from controller to all workers
- Claude Code installed on all workers

**Step 1: Create fleet configuration**

Create `~/.claude/fleet.json` on the controller machine (see [fleet.json Setup](INTEGRATION_GUIDE.md#fleetjson-setup) for the complete format).

**Step 2: Verify connectivity**

```bash
# Test SSH access to all workers
for host in server-01 server-02 server-03; do
  echo -n "$host: "
  ssh -o BatchMode=yes -o ConnectTimeout=2 $host echo OK || echo FAIL
done

# Test Claude Code is installed on workers
for host in server-01 server-02 server-03; do
  echo -n "$host claude: "
  ssh $host which claude 2>/dev/null || echo NOT_FOUND
done
```

**Step 3: Verify NFS mounts**

```bash
# On controller (aio-01)
showmount -e localhost

# On workers
for host in server-01 server-02 server-03; do
  echo -n "$host NFS: "
  ssh $host "df -h | grep Development" || echo NOT_MOUNTED
done
```

**Step 4: Run fleet tests**

```bash
# Test fleet connectivity
./scripts/fleet/test-fleet.sh

# Test fleet-aware skill logic
./scripts/fleet/test-fleet-aware-skills.sh
```

### Monitoring Deployment

```bash
cd monitoring

# Phase 1: Verify connectivity (dry run)
./deploy-fleet-prometheus.sh --dry-run

# Phase 2: Install node_exporter on all machines
./deploy-fleet-prometheus.sh --node-exporter --parallel

# Phase 3: Install Prometheus on controller
./deploy-fleet-prometheus.sh --prometheus

# Phase 4: Install Grafana on controller (optional)
./deploy-fleet-prometheus.sh --grafana

# All-in-one deployment
./deploy-fleet-prometheus.sh --ntfy-topic YOUR-UNIQUE-TOPIC
```

**Post-deployment verification**:
```bash
# Check all targets are up
curl -s http://aio-01:9090/api/v1/targets | \
  jq '.data.activeTargets[] | {instance: .labels.instance, state: .health}'

# Check no alerts firing
curl -s http://aio-01:9090/api/v1/alerts | \
  jq '.data.alerts[] | {alert: .labels.alertname, state: .state}'
```

### Verification Checklist

After initial deployment, verify each component:

- [ ] `node --version` shows >= 18
- [ ] `npm install` completes without errors
- [ ] `claude --list-skills` shows expected skills
- [ ] `node --check code-review.js` passes (syntax check)
- [ ] `/ai-prompt "test"` returns a multi-AI response
- [ ] `cat ~/.claude/fleet.json` exists (if using fleet)
- [ ] `ssh server-01 echo OK` succeeds (if using fleet)
- [ ] `curl http://aio-01:9090/-/healthy` returns OK (if using monitoring)
- [ ] `curl http://aio-01:3000` loads Grafana (if using monitoring)

---

## Day-to-Day Operations

### Running Skills

```bash
# Interactive mode (prompts for decisions)
/code-review                          # Review code
/code-solve 42                        # Fix issue #42
/code-security                        # Security audit
/ai-prompt "Design question..."       # Multi-AI consultation

# Autonomous mode (no prompts)
claude run code-review-auto            # Auto-create issues
claude run code-solve-auto             # Auto-fix issues
claude run code-sdlc-auto +500k        # Full pipeline

# With fleet distribution
/ai-pdf-deep-research *.pdf           # Auto-detects fleet
/ai-web-learn urls.txt --fleet         # Force fleet mode
/code-review --local                   # Force local mode

# Continuous mode
sdlc-loop.sh 5 500k                   # 5 iterations, 500k budget each
```

### Scheduling Automated Runs

```bash
# Nightly code review
0 2 * * * cd ~/my-project && claude run code-sdlc-auto +800k

# Weekly security scan (Monday 9 AM)
0 9 * * 1 cd ~/my-project && claude run code-security-auto

# Monthly test review (1st of month)
0 9 1 * * cd ~/my-project && claude run code-test-auto

# Monthly repo hygiene (1st of month, 10 AM)
0 10 1 * * cd ~/my-project && claude run code-hygiene-review
```

### Managing Token Budgets

| Repo Size | Budget | Full SDLC Time |
|-----------|--------|----------------|
| Small (<1k files) | +300k-500k | ~20-30 min |
| Medium (1k-5k files) | +500k-800k | ~40-60 min |
| Large (5k+ files) | +800k-1.5M | ~60-120 min |

**Monitor costs with the ai-cost-tracker skill**:
```bash
/ai-cost-tracker              # View cost breakdown by model and workflow
/ai-cost-tracker --report     # Generate cost report
```

### Workflow Transcript Cleanup

Workflow transcripts accumulate over time and can fill disk space:

```bash
# Interactive cleanup (shows what will be cleared)
/workflow-cleanup

# Dry run (shows sizes without clearing)
/workflow-cleanup --dry-run

# Auto-clear without confirmation
/workflow-cleanup --auto
```

**When to clean up**:
- Monthly as routine maintenance
- Before large workflow runs
- When context limits are hit
- When disk space is low

### Memory Management

```bash
# Index all memories in PostgreSQL + pgvector (via REST API at aio-01:5000)
claude run memory-rag-index

# Search memories semantically (uses pgvector similarity search)
claude run memory-rag-search query="how does fleet distribution work"

# Extract learnings from recent sessions
claude run ai-extract-learning
```

**Memory file locations**:
- `memory/` -- Git-tracked cross-session memory
- `learnings/` -- Extracted learnings and case studies
- `knowledge/` -- Ingested knowledge bases

---

## Fleet Operations

### Health Monitoring

```bash
# Quick health check (all workers)
for host in server-01 server-02 server-03; do
  echo -n "$host: "
  ssh -o ConnectTimeout=2 $host "uptime" 2>/dev/null || echo "UNREACHABLE"
done

# Detailed resource check
for host in server-01 server-02 server-03; do
  echo "=== $host ==="
  ssh $host "free -h | head -2; df -h / | tail -1; uptime"
  echo
done
```

### Fleet Status Checking

```bash
# Check fleet configuration
cat ~/.claude/fleet.json | jq '.machines[] | {hostname, role, memory_gb, cpus}'

# Run fleet test suite
./scripts/fleet/test-fleet.sh

# Check fleet-aware skill logic
./scripts/fleet/test-fleet-aware-skills.sh

# Verify fleet mode resolution for a specific item count
node -e "
import { resolveFleetMode } from './shared/fleet-utils.js';
const result = resolveFleetMode([], 100, 10);
console.log(JSON.stringify(result, null, 2));
"
```

### Worker Maintenance

**Restarting a worker**:
```bash
# Verify worker is responsive
ssh server-01 echo OK

# Check for running Claude sessions (do not interrupt)
ssh server-01 "ps aux | grep claude | grep -v grep"

# If worker needs restart, wait for active sessions to complete
```

**Updating Claude Code on workers**:
```bash
for host in server-01 server-02 server-03; do
  echo "Updating $host..."
  ssh $host "npm update -g @anthropic-ai/claude-code"
done
```

**Checking worker dependencies**:
```bash
for host in server-01 server-02 server-03; do
  echo "=== $host ==="
  ssh $host "node --version; npm --version; which claude"
done
```

### NFS Operations

**Verify NFS exports** (on controller aio-01):
```bash
showmount -e localhost
exportfs -v
```

**Verify NFS mounts** (on workers):
```bash
for host in server-01 server-02 server-03; do
  ssh $host "mount | grep Development"
done
```

**NFS troubleshooting**:
```bash
# Check NFS service on controller
ssh aio-01 systemctl status nfs-server

# Force remount on a worker
ssh server-01 "sudo mount -a"

# Check NFS performance
ssh server-01 "dd if=/dev/zero of=/home/sfloess/Development/test_write bs=1M count=10 && rm /home/sfloess/Development/test_write"
```

---

## Model Compliance Operations

### Verifying Model Restrictions

**Check active path restrictions**:
```bash
# View all restrictions
cat ~/.claude/fleet.json | jq '.compliance.path_restrictions'

# Check which restriction applies to current directory
node -e "
const config = require(require('path').join(process.env.HOME, '.claude/fleet.json'));
const cwd = process.cwd();
const matching = (config.compliance?.path_restrictions || [])
  .filter(r => cwd.startsWith(r.path))
  .sort((a, b) => b.path.length - a.path.length);
console.log('Active restriction:', matching[0] || 'None');
"
```

**Test model compliance**:
```bash
# Test if specific models are allowed
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

for model in opus sonnet haiku gemini gpt-4o; do
  node -e "
  import('./shared/model-compliance.js').then(m => {
    const result = m.isModelAllowed('$model');
    console.log('$model: ' + (result.allowed ? '✓ allowed' : '✗ denied'));
  })
  "
done
```

### Adding New Path Restrictions

**Example: Block GPT models from client directory**:
```bash
# Edit fleet.json
nano ~/.claude/fleet.json

# Add restriction:
{
  "compliance": {
    "path_restrictions": [
      {
        "path": "/home/sfloess/Development/redhat/",
        "denied_models": ["gpt-*"],
        "reason": "Red Hat compliance - no OpenAI"
      },
      {
        "path": "/home/sfloess/Development/client-work/",
        "allowed_models": ["claude-*"],
        "reason": "Client contract - Anthropic only"
      }
    ]
  }
}

# Save and exit
# No restart needed - compliance checked on each agent creation
```

### Testing Model Compliance Changes

**After updating path_restrictions**:
```bash
# Test 1: Verify pattern matching
cd /path/to/restricted/directory
node -e "
import('./shared/model-compliance.js').then(m => {
  const workers = ['opus', 'sonnet', 'haiku', 'gemini', 'gpt-4o'];
  const allowed = m.filterAllowedModels(workers);
  console.log('Allowed workers:', allowed);
})
"

# Test 2: Run workflow to confirm auto-filtering
node -e "import('./workflows/ai-prompt.js').then(w => w.default())"
# Should only use allowed models
```

### Troubleshooting Compliance Errors

**Error: "Model X not allowed in /path/"**

1. Check current directory matches restriction path
2. Verify model matches denied_models pattern
3. Check if model is in allowed_models (if specified)

```bash
# Debug compliance check
cd /problem/directory
node -e "
import('./shared/model-compliance.js').then(m => {
  const model = 'gpt-4o';
  const result = m.isModelAllowed(model);
  console.log('Model:', model);
  console.log('Allowed:', result.allowed);
  console.log('Reason:', result.reason);
})
"
```

**Fix**: Update path_restrictions or use different model:
```bash
# Option 1: Use allowed model instead
# Instead of gpt-4o, use opus or sonnet

# Option 2: Update restriction to allow model
nano ~/.claude/fleet.json
# Remove gpt-* from denied_models, or add to allowed_models
```

### Monitoring Model Usage

**Track which models are being used**:
```bash
# Check workflow logs for model usage
grep -r "model:" ~/.claude/logs/*.log | sort | uniq -c

# Expected: Only allowed models appear in restricted directories
```

---

## Monitoring

### Dashboard Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://aio-01:3000 | admin/admin (change on first login) |
| Prometheus | http://aio-01:9090 | No auth |
| Alertmanager | http://aio-01:9093 | No auth |

### Alert Management

**View active alerts**:
```bash
# Via Prometheus API
curl -s http://aio-01:9090/api/v1/alerts | jq '.data.alerts[] | {alert: .labels.alertname, state: .state, severity: .labels.severity}'

# Via Alertmanager
curl -s http://aio-01:9093/api/v2/alerts | jq '.[] | {alertname: .labels.alertname, status: .status.state}'
```

**Silence an alert** (temporarily suppress during maintenance):
```bash
# Via Alertmanager API
curl -X POST http://aio-01:9093/api/v2/silences -d '{
  "matchers": [{"name": "alertname", "value": "HostDown", "isRegex": false}],
  "startsAt": "2026-06-13T00:00:00Z",
  "endsAt": "2026-06-13T06:00:00Z",
  "createdBy": "maintenance",
  "comment": "Planned maintenance window"
}'
```

**Alert notification channels**:
- **ntfy** (primary): Mobile and desktop push notifications
  - Warning channel: `fleet-alerts`
  - Critical channel: `fleet-alerts-critical`

### Key Metrics to Watch

| Metric | Warning Threshold | Critical Threshold | Location |
|--------|-------------------|-------------------|----------|
| CPU usage | > 85% for 10m | > 95% for 5m | All workers |
| Memory usage | > 85% for 10m | > 95% for 5m | All workers |
| Disk usage | > 80% | > 90% | All machines |
| Controller CPU | > 60% for 5m | N/A | aio-01 only |
| Sentinel memory | > 70% for 5m | N/A | pi-02 only |
| Network errors | > 10/sec | N/A | All machines |
| Systemd failures | Any | N/A | All machines |
| Prometheus storage | > 80% of 3GB | N/A | aio-01 |

### Capacity Planning

**Current resource utilization**:

| Machine | CPU Typical | Memory Typical | Disk Typical |
|---------|-------------|----------------|-------------|
| aio-01 (7 GB) - Controller ONLY | 10-20% | 50-60% (NFS + monitoring + databases) | 30-40% |
| server-01 (15 GB) | 5-40% (during fleet work) | 10-30% | 20-30% |
| server-02 (31 GB) | 5-30% | 5-20% | 15-25% |
| server-03 (31 GB) | 5-40% | 10-30% | 20-30% |
| desktop-ap (1 GB) | 5-15% | 40-60% | 20-30% |
| server-ap (1 GB) | 5-15% | 40-60% | 20-30% |
| pi-01 (1 GB) | 5-10% | 40-60% | 20-30% |
| pi-02 (1 GB) | 5-10% | 40-60% | 20-30% |

**Scaling triggers**:
- If fleet jobs queue consistently, consider adding workers
- If aio-01 memory exceeds 80%, reduce Prometheus retention or add RAM
- If disk fills on workers, clean `/tmp` scratch directories
- Threshold to add dynamic discovery (Consul/mDNS): ~15+ machines

---

## Operational Procedures

### Adding a New Worker

1. **Configure SSH access**:
```bash
ssh-copy-id new-worker-hostname
ssh -o BatchMode=yes new-worker-hostname echo OK
```

2. **Install Claude Code**:
```bash
ssh new-worker-hostname "npm install -g @anthropic-ai/claude-code"
```

3. **Set up NFS mount**:
```bash
ssh new-worker-hostname "sudo mount aio-01:/home/sfloess/Development /home/sfloess/Development"
# Add to /etc/fstab for persistence
```

4. **Install node_exporter** (for monitoring):
```bash
./monitoring/deploy-fleet-prometheus.sh --host new-worker-hostname --node-exporter
```

5. **Update fleet.json**:
```json
{
  "hostname": "new-worker-hostname",
  "role": "worker",
  "memory_gb": 32,
  "cpus": 16,
  "priority": 4,
  "capabilities": ["python", "nodejs"]
}
```

6. **Update Prometheus static targets** (in `install-prometheus.sh`).

7. **Verify**:
```bash
./scripts/fleet/test-fleet.sh
```

### Removing a Worker

1. Wait for any active Claude sessions on the worker to complete
2. Remove the worker entry from `~/.claude/fleet.json`
3. Remove the Prometheus scrape target
4. Optionally unmount NFS and remove SSH keys

### Updating Models

**Adding a new model to the worker array**:

1. Ensure the API key or model server is configured
2. Edit the worker array in the relevant workflow files
3. Test: `/ai-prompt test-prompt` to verify the model responds
4. Update `multi-ai-config.json` with the new model

See `ADDING_MODELS.md` for detailed per-model setup instructions.

### Updating Dependencies

```bash
# Update Node.js dependencies
npm update

# Check for security vulnerabilities
npm audit

# Fix vulnerabilities (use with caution)
npm audit fix

# Update Python dependencies
pip install -r requirements.txt --upgrade

# Update on all fleet workers
for host in server-01 server-02 server-03; do
  ssh $host "cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && npm install"
done
```

### Backup and Recovery

**What to back up**:
- `memory/` -- Cross-session memory (git-tracked, so git push is the backup)
- `learnings/` -- Extracted learnings (git-tracked)
- `~/.claude/fleet.json` -- Fleet configuration
- `multi-ai-config.json` -- Multi-AI configuration
- `arbiter-state.json` -- Arbiter rotation state (per-machine, optional)
- Prometheus data (if custom retention is important): `/var/lib/prometheus/`

**Recovery procedure**:
```bash
# Restore from git
git clone https://gitlab.cee.redhat.com/sfloess/claude-global-skills.git
cd claude-global-skills
npm install
./fix-permissions.sh

# Restore fleet config
cp /backup/fleet.json ~/.claude/fleet.json

# Re-deploy monitoring
cd monitoring && ./deploy-fleet-prometheus.sh --ntfy-topic YOUR-TOPIC
```

---

## Troubleshooting

### Fleet Mode Not Activating

**Symptom**: Fleet mode does not activate even with many items.

**Diagnostics**:
```bash
# 1. Check fleet.json exists
cat ~/.claude/fleet.json

# 2. Verify machines are reachable
for host in server-01 server-02 server-03; do
  ssh -o BatchMode=yes -o ConnectTimeout=2 $host echo OK
done

# 3. Check item count exceeds threshold
echo "Items: $(ls *.pdf | wc -l)"

# 4. Check compliance (are you in a forbidden path?)
pwd
# If under /home/sfloess/Development/redhat/, fleet is auto-blocked
```

**Solutions**:
1. Create `~/.claude/fleet.json` with worker definitions
2. Fix SSH connectivity (ensure key-based auth, `BatchMode=yes`)
3. Increase item count above break-even threshold
4. Move out of compliance-restricted directories
5. Use `--fleet` flag to force fleet mode and see detailed error messages

### Fleet Mode Fails Mid-Execution

**Symptom**: Fleet starts but workers fail.

**Diagnostics**:
```bash
# Check worker disk space
ssh server-01 df -h

# Check worker load
ssh server-01 uptime

# Check worker permissions
ssh server-01 ls -la /tmp

# Check Claude Code is installed on workers
ssh server-01 which claude
```

**Solutions**:
1. Free up disk space on workers
2. Wait for workers to become available (high load)
3. Install Claude Code on workers
4. Use `--local` while diagnosing

### SSH Authentication Issues

**Symptom**: SSH connections fail to workers.

**Solutions**:
```bash
# 1. Set up key-based auth
ssh-copy-id server-01

# 2. Verify BatchMode works
ssh -o BatchMode=yes server-01 echo OK

# 3. Check SSH config
cat ~/.ssh/config
# Should have: StrictHostKeyChecking accept-new

# 4. Verify hostname resolution
getent hosts server-01

# 5. Debug SSH connection
ssh -vvv server-01 echo OK 2>&1 | head -50
```

### NFS Mount Problems

**Symptom**: Workers cannot see project files.

**Solutions**:
```bash
# 1. Verify NFS export on controller
ssh aio-01 showmount -e

# 2. Verify NFS mount on workers
ssh server-01 "df -h | grep Development"

# 3. Check NFS service
ssh aio-01 systemctl status nfs-server

# 4. Ensure project path is under NFS
# Must start with /home/sfloess/Development

# 5. Force remount
ssh server-01 "sudo umount /home/sfloess/Development && sudo mount -a"
```

### PostgreSQL/pgvector/Embeddings Issues

**Symptom**: Memory RAG or web learning workflows fail with database or embedding errors.

**Solutions**:
```bash
# 1. Verify PostgreSQL is reachable via REST API
curl -s http://aio-01:5000/health | jq .

# 2. Check pgvector extension is installed
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"

# 3. Verify REST API endpoints
curl -s http://aio-01:5000/models/ | jq . | head

# 4. Install Python dependencies (embeddings run on laptop-01/02 ONLY)
pip install -r requirements.txt

# 5. Verify Node.js version
node --version  # Must be >= 18

# 6. Check embedding worker connectivity
curl -s http://aio-01:5000/embeddings/status | jq .
```

**Important**: Embeddings (sentence-transformers) run ONLY on laptop-01/02, never on fleet workers. All database access goes through the REST API at aio-01:5000, never direct PostgreSQL connections.

### Model Failures

**Symptom**: Some models return null in consensus results.

**This is expected behavior.** Models that fail (network error, rate limit, misconfiguration) return `null` and are filtered with `.filter(Boolean)`. The workflow continues with available models.

**To diagnose specific model failures**:
```bash
# Test a specific model
/ai-prompt "Hello" --model gpt-4o

# Check API key configuration
echo $PERSONAL_OPENAI_API_KEY | head -c 10
echo $GOOGLE_API_KEY | head -c 10
```

### Workflow Registration Issues

**Symptom**: Workflow does not appear in skills list.

**Root cause**: The `export const meta` block is not the first meaningful statement in the file.

**Solution**: Ensure `export const meta = { ... }` is at line 1-4 of the workflow file, before any other code or imports.

### Permission Prompt Issues

**Symptom**: Autonomous workflows pause for permission prompts.

**Solutions**:
```bash
# Option 1: Set dontAsk mode
./fix-permissions.sh

# Option 2: Manual setup
echo '{"permissions":{"mode":"dontAsk"}}' > ~/.claude/settings.json
echo '{"permissions":{"mode":"dontAsk"}}' > ~/.claude/settings.local.json

# Option 3: Add specific permissions
# See PERMISSIONS.md for the complete allowlist
```

### High API Costs

**Symptom**: Multi-AI consensus is consuming more tokens than expected.

**Solutions**:
1. Reduce the number of worker models:
```json
// In multi-ai-config.json
{ "workers": { "models": ["opus", "sonnet", "haiku"], "count": 3 } }
```

2. Use the `fast-consensus` preset for non-critical tasks

3. Use the `free-tier` strategy (free API models from Pollinations, ZeroLimitAI, OpenRouter free, zero cost):
```bash
claude run code-review --strategy=free-tier
```

4. Reduce token budget:
```bash
claude run code-sdlc +300k  # Instead of +800k
```

5. Review cost breakdown:
```bash
/ai-cost-tracker --report
```

### Monitoring Issues

**Prometheus target down**:
```bash
# Check node_exporter on affected machine
ssh server-01 systemctl status node_exporter

# Check firewall allows port 9100
ssh server-01 sudo firewall-cmd --list-ports

# Manual scrape test
curl http://server-01:9100/metrics | head
```

**Prometheus high memory**:
```bash
# Check cgroup limits
ssh aio-01 systemctl show prometheus | grep Memory

# Reduce retention if needed
# Edit prometheus.yml: --storage.tsdb.retention.time=7d
ssh aio-01 sudo systemctl restart prometheus
```

**Alertmanager not sending**:
```bash
# Check Alertmanager logs
ssh aio-01 sudo journalctl -u alertmanager -n 50

# Test ntfy directly
curl -d "Test alert" https://ntfy.sh/YOUR-TOPIC
```

---

## Maintenance Schedule

### Weekly

- [ ] Check `npm audit` for new vulnerabilities
- [ ] Review workflow transcript sizes (`/workflow-cleanup --dry-run`)
- [ ] Verify fleet health (`./scripts/fleet/test-fleet.sh`)

### Monthly

- [ ] Run transcript cleanup (`/workflow-cleanup`)
- [ ] Review arbiter rotation balance in `arbiter-state.json`
- [ ] Check fleet worker disk space
- [ ] Review monitoring dashboard for trends
- [ ] Update dependencies (`npm update`)

### Quarterly

- [ ] Audit `memory/` files for relevance and accuracy
- [ ] Review compliance configuration
- [ ] Check model performance trends (`/ai-performance-monitor`)
- [ ] Review and optimize break-even thresholds
- [ ] Update fleet.json if machine specs have changed

---

## Incident Response

### Fleet Worker Unresponsive

1. Check SSH connectivity: `ssh server-01 echo OK`
2. If unreachable, check physical machine / network
3. Active workflows will continue with remaining workers
4. If >50% workers fail, workflows fall back to local processing
5. Once worker recovers, no action needed (auto-detected on next run)

### API Rate Limiting

1. Workflows with `.filter(Boolean)` handle individual model rate limits
2. If all models are rate-limited, wait and retry
3. Consider reducing worker count temporarily
4. Use `free-tier` strategy to use zero-cost API models (Pollinations, ZeroLimitAI, OpenRouter free)

### Data Loss in Memory

1. Memory is git-tracked: `git log memory/` to find last good state
2. `git checkout <commit> -- memory/` to restore specific files
3. Re-index pgvector embeddings: `claude run memory-rag-index`

### Monitoring System Down

1. Check Prometheus: `ssh aio-01 systemctl status prometheus`
2. Check Grafana: `ssh aio-01 systemctl status grafana-server`
3. Restart if needed: `ssh aio-01 sudo systemctl restart prometheus grafana-server alertmanager`
4. Verify targets: `curl http://aio-01:9090/-/healthy`

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `HOME` | User home directory (for `~/.claude/fleet.json` lookup) | Yes (system) |
| `ANTHROPIC_API_KEY` | Claude API access | Yes |
| `PERSONAL_OPENAI_API_KEY` | OpenAI GPT-4o access (via MCP) | Only if using GPT-4o |
| `PERSONAL_GROQ_API_KEY` | Groq LPU inference access | Only if using Groq |
| `PERSONAL_DEEPSEEK_API_KEY` | DeepSeek model access | Only if using DeepSeek |
| `GOOGLE_API_KEY` | Google Gemini access | Only if using Gemini |
| `XAI_API_KEY` | Grok/xAI API access | Only if using Grok |

**Note**: API keys for third-party providers use the `PERSONAL_` prefix convention (e.g., `PERSONAL_GROQ_API_KEY`, `PERSONAL_DEEPSEEK_API_KEY`). The 21 provider API keys are managed via the REST API at aio-01:5000 and stored in the orchestrator configuration.
| `FLEET_NTFY_TOPIC` | ntfy notification topic for fleet alerts | Optional |
| `FLEET_DISPATCHER` | Enable/disable fleet dispatcher (`true`/`false`) | Optional |
| `MULTI_AI` | Override multi-AI mode (`off`/`dual`/`triple`/`quad`) | Optional (future) |
| `DEBUG` | Enable debug logging (`claude:workflows`) | Optional |

---

## Cross-References

- **[ARCHITECTURE.md](ARCHITECTURE.md)** -- System design, components, architecture decisions
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** -- How to integrate workflows, migration guide, examples
- **[API_REFERENCE.md](API_REFERENCE.md)** -- Complete API documentation for shared libraries
- **[FLEET_AWARE_SKILLS.md](FLEET_AWARE_SKILLS.md)** -- Detailed fleet-aware skill implementation
- **[FLEET_TROUBLESHOOTING.md](../FLEET_TROUBLESHOOTING.md)** -- Fleet-specific troubleshooting
- **[PERMISSIONS.md](../PERMISSIONS.md)** -- Detailed permissions setup
- **[KNOWN_ISSUES.md](../KNOWN_ISSUES.md)** -- Known issues and resolutions
- **[monitoring/README.md](../monitoring/README.md)** -- Monitoring deployment details
