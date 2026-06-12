---
name: fleet-operations-guide
description: "Operational procedures for managing the 5-machine distributed fleet"
metadata:
  type: operations-guide
  created: 2026-06-12
  tags: [fleet, operations, troubleshooting, maintenance]
  related: [reference_distributed_fleet, fleet_discovery_static_vs_dynamic]
---

# Fleet Operations Guide

## Quick Reference

### Common Commands

**Check fleet status:**
```javascript
import { getFleet, clearHealthCache } from './shared/fleet-utils.js';

// Get current status
const fleet = getFleet();
console.log(`Fleet: ${fleet.length} machines online`);
fleet.forEach(m => console.log(`  ${m.hostname} - ${m.role} - ${m.cpus}C/${m.memory_gb}GB`));

// Force re-probe if cached results are stale
clearHealthCache();
const fresh = getFleet();
```

**Test SSH to specific machine:**
```bash
ssh -v server-01 'uname -a'
```

**View fleet configuration:**
```bash
cat ~/.claude/fleet.json | jq .machines
```

**Get high-memory workers:**
```javascript
import { getFleet } from './shared/fleet-utils.js';
const highMem = getFleet({ role: 'worker', minMemoryGb: 16 });
```

---

## Fleet Status Monitoring

### Current Fleet

**Machines (5 total):**

| Hostname | Role | CPUs | Memory | Tags | Capabilities | Purpose |
|----------|------|------|--------|------|--------------|---------|
| aio-01 | controller | 2 | 7GB | personal, always-on | nfs-server, orchestration, cache, metrics | Infrastructure, coordination |
| server-01 | worker | 8 | 15GB | personal, compute | build, test, nfs-client | General compute |
| server-02 | worker | 8 | 31GB | personal, compute, high-memory | build, test, nfs-client | High-memory workloads |
| server-03 | worker | 8 | 31GB | personal, compute, high-memory | build, test, nfs-client | High-memory workloads |
| pi-02 | sentinel | 4 | 1GB | personal, always-on, low-power | monitor, health-check, log-aggregation, file-watcher | Watchdog, lightweight tasks |

**Total compute:** 30 CPUs, 86GB RAM (combined)

**Key metadata:**
- `priority: 1` = aio-01 (run here first)
- `priority: 2` = server-01/02/03 (workers)
- `priority: 3` = pi-02 (sentinel, last resort)
- `max_parallel_workers: 3` policy (cap at 3 workers per job)

### Health Check Flow

```
User code calls getFleet()
  ↓
Load ~/.claude/fleet.json (5 machines)
  ↓
Filter by criteria (e.g., role='worker')
  ↓
Health check each machine:
  aio-01:      ssh -o ConnectTimeout=2s aio-01 'echo ok'
  server-01:   ssh -o ConnectTimeout=2s server-01 'echo ok'
  server-02:   ssh -o ConnectTimeout=2s server-02 'echo ok'
  server-03:   ssh -o ConnectTimeout=2s server-03 'echo ok'
  pi-02:       ssh -o ConnectTimeout=2s pi-02 'echo ok'
  ↓
Cache results for 30 seconds
  ↓
Return only ONLINE machines
```

**Timing:**
- First call: ~2 seconds (5 machines × 2s timeout, but most succeed quickly)
- Subsequent calls (< 30s): < 50ms (cache hit)
- After 30s: ~2 seconds again (cache expires, re-probe)

---

## Adding a New Machine

### Prerequisites

Before adding a machine to the fleet:

1. **Machine is running and accessible**
2. **SSH key is installed:** `~/.ssh/id_rsa_virtos` exists on your machine
3. **SSH access works:** `ssh new-hostname 'echo ok'` succeeds
4. **NFS is mounted:** `ssh new-hostname 'ls ~/Development | head -5'` shows files
5. **User exists:** `ssh new-hostname 'whoami'` returns `sfloess`

### Step 1: Update fleet.json

**Edit:** `~/.claude/fleet.json`

**Add this object to `machines` array:**
```json
{
  "hostname": "server-04",
  "role": "worker",
  "cpus": 8,
  "memory_gb": 31,
  "tags": ["personal", "compute", "high-memory"],
  "capabilities": ["build", "test", "nfs-client"],
  "priority": 2,
  "notes": "Additional worker added 2026-06-12"
}
```

**Field guide:**
- `hostname` (required): DNS-resolvable hostname
- `role` (required): `"worker"` or `"controller"` or `"sentinel"`
- `cpus` (required): Number of CPU cores (from lscpu)
- `memory_gb` (required): RAM in GB (from free -g)
- `tags` (optional): Labels for filtering (AND logic)
- `capabilities` (optional): What this machine can do
- `priority` (optional): Lower = runs first
- `arch` (optional): `"x86_64"` or `"arm64"`
- `notes` (optional): Free-form description

### Step 2: Verify SSH Access

```bash
# Test basic SSH
ssh -v server-04 'echo ok'

# Should print:
# "ok"
# Exit code: 0

# If fails: SSH key issues, check ~/.ssh/id_rsa_virtos
```

### Step 3: Verify NFS Mount

```bash
# Test NFS access (should show files)
ssh server-04 'ls ~/Development | head -3'

# Should print file names like:
# redhat
# personal
# tools
```

### Step 4: Test Discovery

```javascript
import { getFleet, clearHealthCache } from './shared/fleet-utils.js';

// Clear cache (force fresh probe)
clearHealthCache();

// Get all machines
const all = getFleet();

// Check new machine is present
const found = all.find(m => m.hostname === 'server-04');
if (found) {
  console.log(`✓ server-04 discovered: ${found.cpus}C/${found.memory_gb}GB`);
} else {
  console.log('✗ server-04 not found (health check failed?)');
  
  // Debug: force health check
  import { probeHealth } from './shared/fleet-utils.js';
  const ok = probeHealth('server-04', 2000);
  console.log(`SSH probe: ${ok ? 'OK' : 'FAILED'}`);
}
```

### Step 5: Verify Metadata

```javascript
import { getFleet } from './shared/fleet-utils.js';

const all = getFleet({ skipHealthCheck: true });
const machine = all.find(m => m.hostname === 'server-04');

console.log(JSON.stringify(machine, null, 2));
// Verify all fields match your config
```

---

## Removing a Machine

### Process

**1. Update fleet.json:**
- Find the machine object
- Delete it entirely (no "disabled" flag)

**2. Verify removal:**
```javascript
import { getFleet, clearHealthCache } from './shared/fleet-utils.js';

clearHealthCache();
const machines = getFleet();
const stillThere = machines.some(m => m.hostname === 'server-04');

if (!stillThere) {
  console.log('✓ Machine removed from fleet');
} else {
  console.log('✗ Machine still appears in results');
}
```

**3. Stop SSH agent if it was cached:**
```bash
# Optional: clear SSH key cache
ssh-add -d ~/.ssh/id_rsa_virtos
```

---

## Troubleshooting

### Problem 1: Machine Not Appearing in getFleet()

**Symptoms:**
```
const workers = getFleet({ role: 'worker' });
console.log(workers.length);  // Expected 4, got 3
```

**Diagnosis flowchart:**

```
Is the machine in ~/.claude/fleet.json?
  ├─ NO:  Add it (see "Adding a New Machine" above)
  └─ YES: Continue...
       ↓
Does the machine respond to SSH?
  ├─ NO:  Machine is offline. Power it on.
  │       ssh server-04 'echo ok'
  └─ YES: Continue...
       ↓
Is the machine being filtered out?
  ├─ Check your filter options:
  │   - getFleet({ role: 'worker' }) requires role='worker'
  │   - getFleet({ minMemoryGb: 32 }) filters by RAM
  │   - getFleet({ capabilities: ['build'] }) checks capabilities array
  │
  │   Debug: Print actual specs
  │   const config = loadFleetConfig();
  │   const m = config.machines.find(x => x.hostname === 'server-04');
  │   console.log(`Specs: ${m.cpus}C/${m.memory_gb}GB, role: ${m.role}`);
  │
  └─ Continue...
       ↓
Is the result cached incorrectly?
  ├─ Yes: clearHealthCache() then try again
  └─ No: Check max_parallel_workers policy
```

**Common causes:**

1. **Machine offline (SSH fails)**
   ```bash
   ssh server-04 'uptime'
   # If fails: machine is down
   ```

2. **Machine filtered by options**
   ```javascript
   // You asked for high-memory workers
   const workers = getFleet({ role: 'worker', minMemoryGb: 32 });
   
   // But machine has only 15GB
   // Check the config
   const config = loadFleetConfig();
   console.log(config.machines.find(m => m.hostname === 'server-01').memory_gb);
   ```

3. **Health check cached (machine went down)**
   ```javascript
   import { clearHealthCache } from './shared/fleet-utils.js';
   clearHealthCache();
   const fresh = getFleet();  // Forces re-probe
   ```

4. **max_parallel_workers policy limiting results**
   ```javascript
   import { getFleet } from './shared/fleet-utils.js';
   
   // Get all machines (ignore max_parallel_workers)
   const all = getFleet({ skipHealthCheck: true });
   console.log(`All (no limit): ${all.length}`);
   
   // Get with policy applied
   const capped = getFleet();
   console.log(`Capped: ${capped.length}`);
   
   if (all.length > capped.length) {
     console.log(`max_parallel_workers policy capping: ${all.length} → ${capped.length}`);
   }
   ```

---

### Problem 2: Health Check Timeout

**Symptoms:**
```
All machines appear offline even though SSH works manually
```

**Cause analysis:**

```
Does SSH work manually?
  ├─ No:  ssh server-01 'echo ok' fails
  │       → SSH key issue or network problem
  │       → Check: ssh-add -L | grep virtos
  │       → Re-add: ssh-add ~/.ssh/id_rsa_virtos
  │
  └─ Yes: SSH works but getFleet() returns empty
          ↓
          SSH is slow?
          ├─ Time it:  ssh server-01 'sleep 1'
          │            Should be ~1s, not ~2s
          │
          ├─ If ~3s+:  SSH is slow (network lag)
          │            → Increase timeout: getFleet({ skipHealthCheck: true })
          │
          └─ If 1s-2s: Timeout config issue
                        → Check CACHE_TTL_MS in fleet-utils.js
```

**Solutions:**

1. **Timeout too strict (slow SSH)**
   ```javascript
   // 2 second timeout might be too tight for slow networks
   // Skip health check temporarily
   const workers = getFleet({ skipHealthCheck: true });
   
   // Or increase global timeout in fleet.json
   "policies": {
     "health_check_timeout_ms": 5000  // Was 2000
   }
   ```

2. **SSH key not loaded**
   ```bash
   # Check if key is in agent
   ssh-add -L | grep virtos
   
   # If missing, add it
   ssh-add ~/.ssh/id_rsa_virtos
   
   # Verify
   ssh-add -L | grep virtos
   ```

3. **SSH knows_hosts issue**
   ```bash
   # If you see "Host key verification failed"
   ssh -o StrictHostKeyChecking=accept-new server-01 'echo ok'
   
   # Verify it was added
   grep server-01 ~/.ssh/known_hosts
   ```

---

### Problem 3: Compliance Violation Error

**Symptoms:**
```javascript
const workers = getFleet();
// Throws: "COMPLIANCE VIOLATION: Cannot use distributed fleet"
```

**Root cause:** You're in a Red Hat directory

**Location:** `/home/sfloess/Development/redhat/`

**Why:** Red Hat compliance requires that distributed fleet (personal servers) is not used for corporate work.

**Solution:**

```javascript
// Option 1: Force local execution
const workers = getFleet({ localOnly: true });  // Returns []

// Option 2: Move to non-Red Hat directory
cd ~/Development/personal/
const workers = getFleet();  // Works

// Option 3: Use a different machine
// Use localhost or approved Red Hat infrastructure
```

**How enforcement works:**
```javascript
// In getFleet():
const cwd = fs.realpathSync(process.cwd());
const forbidden = '/home/sfloess/Development/redhat/';

if (cwd.startsWith(forbidden)) {
  throw new Error('COMPLIANCE VIOLATION: Cannot use distributed fleet');
}
```

**Note:** This is intentional and cannot be bypassed. It ensures Red Hat work uses only approved infrastructure.

---

### Problem 4: "Fleet config not found"

**Symptoms:**
```
Error: Fleet config not found: ~/.claude/fleet.json
```

**Causes:**

1. **Running from machine without fleet.json**
   ```bash
   # Solution: Copy fleet.json from main machine
   scp ~/.claude/fleet.json sfloess@remote-machine:~/.claude/
   ```

2. **NFS not mounted**
   ```bash
   # If you're on a machine without NFS, fleet.json might not exist
   # Check if ~/Development is mounted
   mount | grep Development
   
   # If not mounted, mount it
   mount -t nfs aio-01:/home/sfloess/Development ~/Development
   ```

3. **Wrong home directory**
   ```bash
   # Check where fleet.json should be
   echo $HOME
   ls -la ~/.claude/
   ```

---

### Problem 5: SSH Hangs or Slow Responses

**Symptoms:**
```
getFleet() takes 10+ seconds instead of 2 seconds
```

**Diagnosis:**

```bash
# Time SSH manually
time ssh server-01 'echo ok'
# Should be < 1 second

# If slow, check:
ssh -v server-01 'echo ok' 2>&1 | head -20
# Look for delays in connection process
```

**Common causes:**

1. **Network latency**
   - Solution: Increase timeout in fleet.json
   - Or run fleet-test to profile actual times

2. **SSH gateway/jump host involved**
   - Check ~/.ssh/config for ProxyCommand
   - Solution: Add jump host to speed up connections

3. **DNS resolution slow**
   ```bash
   # Test DNS
   nslookup server-01
   time ssh -o ConnectTimeout=1 server-01 'echo ok'
   ```

4. **SSH key exchange slow**
   - Solution: Use faster key type
   - Check: ssh -i ~/.ssh/id_rsa_virtos server-01 'echo ok'

---

## Maintenance Tasks

### Weekly: Verify All Machines Online

```javascript
import { getFleet, clearHealthCache } from './shared/fleet-utils.js';

clearHealthCache();
const fleet = getFleet({ skipHealthCheck: true });  // Get all machines
const online = getFleet();  // Get only online machines

console.log(`Fleet status: ${online.length}/${fleet.length} online`);

for (const m of fleet) {
  const is_online = online.find(o => o.hostname === m.hostname);
  console.log(`  ${m.hostname}: ${is_online ? '✓ ONLINE' : '✗ OFFLINE'}`);
}
```

### Monthly: Check Disk Space

```bash
# Check each machine
for host in aio-01 server-01 server-02 server-03 pi-02; do
  echo "=== $host ==="
  ssh $host 'df -h ~/ | tail -1'
done
```

### Quarterly: Test Remote Execution

```bash
import { remoteExec } from './shared/fleet-utils.js';

const testHosts = ['aio-01', 'server-01', 'server-02', 'server-03', 'pi-02'];

for (const host of testHosts) {
  const result = remoteExec(host, 'hostname && uname -a');
  console.log(`${host}: ${result.success ? '✓' : '✗'}`);
  if (!result.success) {
    console.log(`  Error: ${result.stderr}`);
  }
}
```

### Annually: Review fleet.json

- Verify all machine specs still accurate
- Check if machines should be retired
- Update notes with any significant changes
- Commit to git history

---

## Performance Tuning

### Health Check Cache Settings

**Current:** 30 second cache, 2 second timeout

**Trade-offs:**

```
More aggressive caching (60s):
  + Faster repeated calls
  - Slower to detect machines coming back online

Less aggressive caching (10s):
  + Faster recovery from temporary outages
  - More frequent SSH probes

More lenient timeout (5s):
  + Won't fail on slow networks
  - Slower to detect offline machines

Stricter timeout (1s):
  + Faster failure detection
  - May fail on variable latency networks
```

**To adjust:** Edit fleet.json:
```json
"policies": {
  "health_check_timeout_ms": 5000,   // Default 2000
  "max_parallel_workers": 3           // Same as before
}
```

Note: Cache TTL (30 seconds) is hardcoded in fleet-utils.js. To change, edit CACHE_TTL_MS.

---

## Disaster Recovery

### If fleet.json is corrupted

**Recovery:**

```bash
# Git has the history
cd ~/.claude
git log -p fleet.json | head -100

# Restore from git
git checkout fleet.json

# Or from backup
cp fleet.json.bak fleet.json
```

**Prevention:** Commit fleet.json to git

```bash
cd ~/.claude
git add fleet.json
git commit -m "Fleet config: add server-04"
```

### If all SSH keys are lost

**Recovery:**

```bash
# Regenerate key
ssh-keygen -t ed25519 -f ~/.ssh/id_rsa_virtos -N ""

# Re-copy to all machines
for host in aio-01 server-01 server-02 server-03 pi-02; do
  ssh-copy-id -i ~/.ssh/id_rsa_virtos.pub sfloess@$host
done
```

### If NFS mount fails

**Impact:** Fleet still works (config is local), but can't access shared code

**Recovery:**

```bash
# Re-mount NFS
mount -t nfs aio-01:/home/sfloess/Development ~/Development

# Verify
ls ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/

# Add to /etc/fstab for auto-mount
echo "aio-01:/home/sfloess/Development /home/sfloess/Development nfs defaults 0 0" | sudo tee -a /etc/fstab
```

---

## Document History

- **1.0** (2026-06-12) - Initial operations guide
  - Fleet status overview
  - Add/remove machine procedures
  - Troubleshooting flowcharts
  - Maintenance tasks
  - Performance tuning
  - Disaster recovery
