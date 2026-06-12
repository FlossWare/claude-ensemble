---
name: distributed-fleet-architecture
description: "How to use the distributed fleet (aio-01, server-01/02/03) for parallel execution in workflows"
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-12
  updated: 2026-06-12
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

# Distributed Fleet Architecture

## Overview

Personal distributed fleet of 5 machines with NFS-shared storage for parallel workflow execution. **NEVER use for Red Hat work** - compliance enforcement is automatic.

## Quick Start

```javascript
// In any workflow
const { getWorkers, fanOut } = require('./shared/fleet-utils');

// Get online worker machines
const workers = getWorkers({ minMemoryGb: 16 });
// => [server-02, server-03] if online and have 16GB+ RAM

// Execute command on all workers
const results = fanOut(workers, 'cd ~/Development/myproject && make test');
```

## Fleet Configuration

**Config file:** `~/.claude/fleet.json` (NFS-shared, visible to all machines)

**Machines:**
- **aio-01** - Controller (2 CPUs, 7GB RAM) - Infrastructure services only
- **server-01** - Worker (8 CPUs, 15GB RAM) - General compute
- **server-02** - Worker (8 CPUs, 31GB RAM) - High-memory workloads
- **server-03** - Worker (8 CPUs, 31GB RAM) - High-memory workloads
- **pi-02** - Sentinel (4 CPUs, 1GB RAM, ARM64) - Raspberry Pi 3B, monitoring/health checks

**All machines:**
- NFS-mounted at `/home/sfloess/Development` (475GB shared)
- SSH configured with `~/.ssh/id_rsa_virtos` key
- User: `sfloess`
- Same file paths, same repos, just different hostnames

## API Reference

### `getFleet(options)`

Discover and filter fleet machines with automatic health checking.

**Options:**
- `tags: string[]` - Filter by tags (e.g., `['personal', 'compute']`)
- `capabilities: string[]` - Filter by capabilities (e.g., `['build', 'test']`)
- `role: string` - Filter by role (`'controller'` or `'worker'`)
- `minMemoryGb: number` - Minimum RAM (e.g., `16` for high-memory)
- `minCpus: number` - Minimum CPU count
- `skipHealthCheck: boolean` - Skip SSH probe (faster but may include offline machines)
- `localOnly: boolean` - Force local-only (disable fleet)

**Returns:** Array of machine objects with `{ hostname, role, cpus, memory_gb, tags, capabilities }`

**Examples:**
```javascript
// All online machines
const all = getFleet();

// Only high-memory workers
const highMem = getFleet({ role: 'worker', minMemoryGb: 16 });

// Only build-capable machines
const builders = getFleet({ capabilities: ['build'] });

// Force local-only (disable fleet)
const none = getFleet({ localOnly: true });  // => []
```

### `getWorkers(options)`

Shorthand for `getFleet({ role: 'worker', ...options })` - returns only worker machines.

**Example:**
```javascript
const workers = getWorkers({ minMemoryGb: 16 });
```

### `remoteExec(hostname, command, options)`

Execute single command on one machine via SSH.

**Options:**
- `timeout: number` - Timeout in milliseconds (default: 120000)
- `throwOnError: boolean` - Throw if command fails (default: false)

**Returns:** `{ hostname, stdout, stderr, exitCode, success }`

**Example:**
```javascript
const result = remoteExec('server-01', 'uptime');
if (result.success) {
  console.log(result.stdout);
}
```

### `fanOut(machines, command, options)`

Execute command on multiple machines (parallel by default).

**Parameters:**
- `machines: Object[]|string[]` - Array of machine objects or hostnames
- `command: string` - Shell command to execute
- `options.timeout: number` - Per-machine timeout in milliseconds
- `options.throwOnError: boolean` - Throw if any command fails
- `options.sequential: boolean` - Run sequentially instead of parallel

**Returns:** Object mapping `hostname -> result`

**Example:**
```javascript
const workers = getWorkers();
const results = fanOut(workers, 'make test');

for (const [hostname, result] of Object.entries(results)) {
  if (result.success) {
    console.log(`${hostname}: PASS`);
  } else {
    console.log(`${hostname}: FAIL - ${result.stderr}`);
  }
}
```

## Red Hat Compliance

**CRITICAL:** Fleet is automatically disabled when working in Red Hat directories.

**Forbidden paths:**
- `/home/sfloess/Development/redhat/` (and all subdirectories)

**Enforcement:**
- `getFleet()` throws error if `process.cwd()` is under a forbidden path
- Error message explains the violation and suggests `--local-only`
- Cannot be bypassed (intentional design)

**How it works:**
```javascript
// When in ~/Development/redhat/
const workers = getFleet();  
// ❌ Throws: "COMPLIANCE VIOLATION: Cannot use distributed fleet"

// Force local execution instead
const workers = getFleet({ localOnly: true });
// ✅ Returns: [] (empty array, run locally)
```

**Why:** Red Hat compliance requires approved infrastructure only. Personal servers (aio-01, server-01/02/03) are not approved for corporate work.

## Usage Patterns

### Pattern 1: Multi-Model Consensus Across Fleet

Distribute AI model workers across machines for parallel execution:

```javascript
const { getWorkers } = require('./shared/fleet-utils');

const workers = getWorkers();  // Get online workers
const models = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];

// Distribute models across workers (round-robin)
const assignments = models.map((model, i) => ({
  model,
  hostname: workers[i % workers.length]?.hostname || 'localhost'
}));

// Execute in parallel
const results = await parallel(
  assignments.map(({ model, hostname }) => () =>
    agent(`...prompt...`, { 
      model,
      label: `${model}@${hostname}`
      // Note: Agent runs locally, but heavy compute could be SSH'd
    })
  )
);
```

### Pattern 2: Distributed Builds/Tests

Run builds or tests across multiple machines:

```javascript
const { getWorkers, fanOut } = require('./shared/fleet-utils');

const workers = getWorkers({ capabilities: ['build'] });

// Build on all workers in parallel
const buildResults = fanOut(
  workers,
  'cd ~/Development/myproject && make clean && make -j8'
);

const allPassed = Object.values(buildResults).every(r => r.success);
```

### Pattern 3: High-Memory Workload Distribution

Select machines with enough RAM for memory-intensive tasks:

```javascript
const { getWorkers } = require('./shared/fleet-utils');

// Only use machines with 31GB+ RAM
const highMemWorkers = getWorkers({ minMemoryGb: 31 });
// => [server-02, server-03]

// Process large datasets in parallel
const results = await parallel(
  dataSets.map((data, i) => () => {
    const hostname = highMemWorkers[i % highMemWorkers.length]?.hostname;
    if (!hostname) return processLocally(data);
    
    return agent(`SSH to ${hostname}: process large dataset`, { ... });
  })
);
```

### Pattern 4: Graceful Fallback

Handle fleet unavailability gracefully:

```javascript
const { getWorkers } = require('./shared/fleet-utils');

const workers = getWorkers();

if (workers.length === 0) {
  log('Fleet unavailable, running locally');
  return runLocally();
}

log(`Using ${workers.length} workers: ${workers.map(w => w.hostname).join(', ')}`);
return runDistributed(workers);
```

## Testing

**Test workflow:** `/fleet-test`

```bash
# Run fleet test
Workflow({ name: 'fleet-test' })
```

**Expected output:**
- Discovers all 5 machines from config
- Health-checks each via SSH probe
- Tests remote execution on workers
- Reports: X/5 machines online, Y workers operational

## When to Use Fleet

**Use fleet for:**
- ✅ Multi-model consensus (6 models → distribute across 3 workers)
- ✅ Parallel builds/tests across repos
- ✅ High-memory workloads (use server-02/03)
- ✅ Long-running computations that can parallelize
- ✅ Personal/FlossWare/open-source projects

**Don't use fleet for:**
- ❌ Red Hat work (auto-blocked by compliance)
- ❌ Quick operations (health probe overhead ~2s)
- ❌ Single-threaded tasks (no parallelism benefit)
- ❌ Operations requiring user input (SSH non-interactive)

## Troubleshooting

**"COMPLIANCE VIOLATION" error:**
- You're in `/home/sfloess/Development/redhat/` directory
- Fleet is forbidden for Red Hat work
- Solution: Use `localOnly: true` or work in different directory

**Empty array from `getFleet()`:**
- All machines failed health check (offline or SSH issues)
- Check: `ssh aio-01 hostname` manually
- Bypass check: `getFleet({ skipHealthCheck: true })` (risky)

**SSH timeout errors:**
- Increase timeout: `getFleet({ timeout: 5000 })`
- Check network connectivity
- Verify SSH keys: `ssh-add -L | grep virtos`

**"Fleet config not found":**
- Running from machine without `~/.claude/fleet.json`
- NFS not mounted on that machine
- Copy config or use `localOnly: true`

## File Locations

- **Config:** `~/.claude/fleet.json`
- **Library:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet-utils.js`
- **Test workflow:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/fleet-test.js`
- **SSH config:** `~/.ssh/config` (hosts: aio-01, server-01/02/03)
- **SSH key:** `~/.ssh/id_rsa_virtos`

## Related Memory

See also:
- [[project_search_engineering_models]] - Red Hat compliance boundaries
- [[feedback_always_multi_ai]] - Multi-model consensus patterns

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  This Machine (NFS Server, 192.168.1.126)                   │
│  - ~/.claude/fleet.json (source of truth)                   │
│  - ~/Development/ (NFS export)                              │
└─────────────────────────────────────────────────────────────┘
                            │
              NFS Mount (shared ~/Development)
                            │
        ┌───────────────────┼───────────────────┬─────────────┬─────────┐
        │                   │                   │             │         │
   ┌────▼─────┐       ┌────▼─────┐       ┌────▼─────┐  ┌────▼─────┐ ┌─▼──────┐
   │ aio-01   │       │server-01 │       │server-02 │  │server-03 │ │ pi-02  │
   │Controller│       │ Worker   │       │ Worker   │  │ Worker   │ │Sentinel│
   │ 2C/7GB   │       │ 8C/15GB  │       │ 8C/31GB  │  │ 8C/31GB  │ │4C/1GB  │
   │          │       │          │       │          │  │          │ │ARM64   │
   └──────────┘       └──────────┘       └──────────┘  └──────────┘ └────────┘
        │                   │                   │             │           │
        └───────────────────┴───────────────────┴─────────────┴───────────┘
                    SSH (sfloess@hostname)
                    All see same ~/Development files
```

## Discovery Architecture

### Current Architecture: Static Config + Health Probes

**Design pattern:** Config-based inventory with runtime health verification

```
┌────────────────────────────────────────────────────────────────┐
│ Fleet Discovery & Health Check Flow                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  getFleet(options)                                            │
│    ↓                                                           │
│  1. Load ~/.claude/fleet.json (authoritative source)          │
│    ↓                                                           │
│  2. Validate compliance (cwd not in forbidden paths)          │
│    ↓                                                           │
│  3. Filter machines (tags, capabilities, role, etc.)         │
│    ↓                                                           │
│  4. Health check each machine (SSH probe, 2s timeout)        │
│    ├─ Cache hit (< 30s): return cached result               │
│    ├─ Success: mark ONLINE, cache result                    │
│    └─ Failure: mark OFFLINE, do NOT cache                   │
│    ↓                                                           │
│  5. Sort by priority, enforce max_parallel_workers           │
│    ↓                                                           │
│  return [online machines only]                               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Why this design wins at 5-machine scale:**
- Fleet changes on months/years timescale, not hours (manual JSON edit is trivial)
- fleet.json is version-controlled, auditable, readable by any tool
- Compliance enforcement requires explicit forbidden paths in config (dynamic discovery cannot enforce boundaries)
- SSH health probe adds necessary dynamic aspect (filtering offline machines)
- NFS sharing solves config distribution problem automatically
- Current implementation: ~358 LOC, 0 dependencies, all failure modes handled
- Alternative (mDNS): 800+ LOC, daemon per machine, still needs config file for metadata/compliance
- Alternative (Consul): 100MB+ overhead per machine (pi-02 has only 1GB total RAM)

**When to reconsider (fleet size thresholds):**
- **10+ machines:** Auto-generate fleet.json from Notion compute database
- **25+ machines:** Add mDNS as supplementary alerting for new machines
- **50+ machines:** Evaluate Consul/etcd as canonical registry
- **>10 changes/week:** Dynamic discovery becomes cost-effective

See [[fleet-discovery-static-vs-dynamic]] for detailed decision framework.

### Health Check Details

**Mechanism:**
```bash
ssh -o ConnectTimeout=2s -o BatchMode=yes -o StrictHostKeyChecking=accept-new 
    <hostname> 'echo ok'
```

**Security features:**
- `ConnectTimeout=2s` - Quick failure detection
- `BatchMode=yes` - Prevents password prompts (non-interactive)
- `StrictHostKeyChecking=accept-new` - Accepts first connection, rejects key changes (MITM prevention)

**Cache behavior:**
- Successful probes: Cached for 30s (assume machine stays online)
- Failed probes: NOT cached (always re-check next invocation)
- Per-invocation cache (cleared between workflow runs)
- Cache TTL: 30 seconds (configurable via `health_check_timeout_ms`)

**Why failures aren't cached:**
A machine that fails health check may come back online quickly (network hiccup, reboot, SSH service restart). Caching failures would hide recovery from the workflow. Caching successes is safe because a machine that's online is likely to stay online for 30s.

### Future Scaling Options

1. **Auto-generate fleet.json from Notion** (10-25 machines): Use the existing
   Notion compute database (same one that feeds notion-ansible.sh,
   notion-dnsmasq.sh) to generate fleet.json via a converter script. Single
   source of truth stays in Notion; fleet.json is a derived artifact.

2. **mDNS supplementary discovery** (25-50 machines): Keep fleet.json as the
   authoritative config. Use Avahi/mDNS to detect new machines on the LAN.
   Alert when an unknown machine appears so you can manually add it to
   fleet.json with proper metadata and compliance policy.

3. **Service registry** (50+ machines): Move to Consul or etcd as the
   canonical registry. Machines self-register with full metadata. fleet.json
   becomes a fallback for offline registry scenarios.

4. **Kubernetes-style labels** (any scale): If machines start having complex
   selection requirements (affinity, anti-affinity, taints/tolerations),
   consider a label-based selection model instead of the current flat
   tags/capabilities model.

**Why NOT to use alternatives at current 5-machine scale:**
- **mDNS/Avahi:** Requires daemon on every machine. Cannot carry metadata (CPU count, RAM, capabilities, tags, compliance policy). mDNS announces hostname only; CPU/RAM/tags/capabilities still need a config file.
- **Consul/etcd:** 100MB+ memory overhead on machines where pi-02 has only 1GB total. Distributed consensus features solve a problem that doesn't exist at this scale.
- **NFS registry:** Anti-pattern. Introduces race conditions, stale-file cleanup problems, and no atomic updates.
- **Hybrid static + mDNS:** Adds complexity for zero benefit at this scale. Auto-discovered machines have no policy metadata and would need manual approval anyway.

See [[fleet-discovery-static-vs-dynamic]] for complete decision framework and industry validation.

## How getFleet() Works

### Step-by-step execution

**1. Load config:**
```javascript
const config = JSON.parse(fs.readFileSync('~/.claude/fleet.json'));
// Returns: { machines: [...], compliance: {...}, policies: {...} }
```

**2. Validate compliance:**
```javascript
const cwd = fs.realpathSync(process.cwd());  // Real path (no symlinks)
for (const forbidden of config.compliance.forbidden_paths) {
  const realForbidden = fs.realpathSync(forbidden);  // Real path too
  if (cwd.startsWith(realForbidden)) {
    throw new Error('COMPLIANCE VIOLATION: Cannot use distributed fleet');
  }
}
```

**3. Filter machines:**
```javascript
let machines = config.machines;

if (options.tags) {
  machines = machines.filter(m => 
    options.tags.every(tag => m.tags.includes(tag))
  );
  // Require ALL tags (logical AND)
}

if (options.capabilities) {
  machines = machines.filter(m =>
    options.capabilities.every(cap => m.capabilities.includes(cap))
  );
}

if (options.role) {
  machines = machines.filter(m => m.role === options.role);
}

if (options.minMemoryGb) {
  machines = machines.filter(m => m.memory_gb >= options.minMemoryGb);
}
```

**4. Health check:**
```javascript
// Check cache freshness
const now = Date.now();
const useCached = healthCache && (now - cacheTimestamp < CACHE_TTL_MS);

// Refresh cache if stale
if (!useCached) {
  healthCache = new Map();
  cacheTimestamp = now;
}

// Filter by health (only keep ONLINE machines)
machines = machines.filter(m => {
  // For cached successes, trust the cache
  if (useCached && healthCache.has(m.hostname) && healthCache.get(m.hostname)) {
    return true;
  }
  
  // Always re-check failures
  const healthy = probeHealth(m.hostname, timeout);
  healthCache.set(m.hostname, healthy);
  return healthy;
});
```

**5. Sort and limit:**
```javascript
// Sort by priority (lower = higher)
machines.sort((a, b) => (a.priority || 99) - (b.priority || 99));

// Enforce max_parallel_workers policy
const maxWorkers = config.policies?.max_parallel_workers;
if (maxWorkers && maxWorkers > 0) {
  machines = machines.slice(0, maxWorkers);
}

return machines;
```

### Cache behavior example

```javascript
// First call (t=0s)
const workers1 = getFleet();  // SSH probes all machines (2s)
// Cache: aio-01=true, server-01=true, server-02=true, server-03=true
// Returned: [aio-01, server-01, server-02, server-03]

// Second call (t=5s, within cache TTL)
const workers2 = getFleet();  // No SSH probes, uses cached results
// Cache: reused from t=0s
// Returned: [aio-01, server-01, server-02, server-03] (instant)

// Third call (t=35s, cache expired)
const workers3 = getFleet();  // SSH probes all machines again (2s)
// Cache refreshed, old cache discarded
```

## Adding and Removing Machines

### Add a new machine

**1. Update fleet.json:**
```json
{
  "hostname": "server-04",
  "role": "worker",
  "cpus": 8,
  "memory_gb": 31,
  "tags": ["personal", "compute", "high-memory"],
  "capabilities": ["build", "test", "nfs-client"],
  "priority": 2
}
```

**2. Ensure SSH access:**
```bash
# On the new machine
ssh-copy-id -i ~/.ssh/id_rsa_virtos sfloess@server-04

# Verify
ssh server-04 hostname  # Should print: server-04
```

**3. Verify NFS mount:**
```bash
ssh server-04 'ls ~/Development | head -5'
# Should list files from shared NFS
```

**4. Test discovery:**
```bash
node -e "
import { getFleet } from './fleet-utils.js';
const machines = getFleet();
console.log(machines.map(m => m.hostname));
// Should include 'server-04'
"
```

### Remove a machine

**1. Update fleet.json:**
Remove the machine object entirely (no deactivation flag needed).

**2. Verify removal:**
```bash
node -e "
import { getFleet } from './fleet-utils.js';
const machines = getFleet();
console.log(!machines.some(m => m.hostname === 'server-04') ? 'OK: Removed' : 'ERROR: Still present');
"
```

### Machine metadata fields

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `hostname` | string | YES | `"server-01"` |
| `role` | string | YES | `"worker"` \| `"controller"` |
| `cpus` | number | YES | `8` |
| `memory_gb` | number | YES | `31` |
| `tags` | string[] | NO | `["compute", "high-memory"]` |
| `capabilities` | string[] | NO | `["build", "test", "nfs-client"]` |
| `priority` | number | NO | `1` (lower = higher) |
| `arch` | string | NO | `"x86_64"` \| `"arm64"` |
| `notes` | string | NO | Free-form description |

## Troubleshooting

### Machine not appearing in getFleet()

**Cause 1: Machine is offline**
```bash
# Test manually
ssh server-01 echo ok

# If fails: machine is down, fix it
# If succeeds: check cache
```

**Cause 2: Health check is cached incorrectly**
```javascript
import { clearHealthCache } from './fleet-utils.js';
clearHealthCache();
const workers = getFleet();  // Forces re-probe
```

**Cause 3: Machine is filtered out by options**
```javascript
const m = config.machines.find(x => x.hostname === 'server-01');
console.log(`Specs: ${m.cpus}C/${m.memory_gb}GB, tags: ${m.tags}, caps: ${m.capabilities}`);

// Check if your filter matches
const workers = getFleet({ 
  minMemoryGb: 16,
  capabilities: ['build']
});
// Verify server-01 has both
```

**Cause 4: max_parallel_workers policy limiting results**
```javascript
const all = getFleet({ skipHealthCheck: false });
const capped = getFleet();

if (all.length > capped.length) {
  console.log(`max_parallel_workers capping: ${all.length} -> ${capped.length}`);
}
```

### Health check timing out

**Symptom:** All machines appear offline even though SSH works manually

**Cause 1: Timeout too short**
```javascript
// Increase timeout
const workers = getFleet({ skipHealthCheck: true });
// Bypass health check entirely

// OR check manually
for (const m of config.machines) {
  const online = probeHealth(m.hostname, 5000);  // 5 second timeout
  console.log(`${m.hostname}: ${online ? 'OK' : 'OFFLINE'}`);
}
```

**Cause 2: Network connectivity issue**
```bash
# Check basic connectivity
ping -c 1 server-01
ssh -v server-01 echo ok  # Verbose SSH to see where it hangs
```

**Cause 3: SSH key issues**
```bash
# Verify key is loaded
ssh-add -L | grep virtos

# Re-add if needed
ssh-add ~/.ssh/id_rsa_virtos
```

### "COMPLIANCE VIOLATION" error

**Error message:**
```
COMPLIANCE VIOLATION: Cannot use distributed fleet.
Current directory: /home/sfloess/Development/redhat/sfdeasy
Forbidden path: /home/sfloess/Development/redhat/
```

**Solution:** Use `localOnly: true` when working in Red Hat directories
```javascript
import { getFleet } from './fleet-utils.js';

// This will throw in /redhat/ directories
const workers1 = getFleet();

// Use this instead to force local execution
const workers2 = getFleet({ localOnly: true });  // Returns []
```

**Why this exists:** Red Hat compliance requires approved infrastructure only. Personal servers are not approved for corporate work.

### SSH timeout from machine without known_hosts entry

**Error:**
```
Host key verification failed.
```

**Solution:**
```bash
# Accept the host key
ssh -o StrictHostKeyChecking=accept-new server-01 echo ok

# Verify it was added
grep server-01 ~/.ssh/known_hosts

# Now probeHealth should work
```

Note: `StrictHostKeyChecking=accept-new` accepts the first connection (adds to known_hosts), but rejects subsequent connections if the host key changes (MITM protection).

## Compliance Enforcement Mechanism

### How it works

**Forbidden paths checking:**
1. Read `compliance.forbidden_paths` from fleet.json
2. Get current working directory (realpath to resolve symlinks)
3. Get real path of each forbidden directory (realpath)
4. Check if cwd starts with forbidden path
5. If match: throw error, disable fleet

**Why realpath is critical:**
```bash
# Without realpath, symlinks could bypass enforcement
~/Development/redhat/
  ↑
  Might be a symlink to /opt/redhat/corporate/

# If we don't resolve realpath, we'd only check the symlink path
# realpath prevents this:
fs.realpathSync('~/Development/redhat/') 
  → /opt/redhat/corporate/
```

**Example scenario:**
```javascript
// In /home/sfloess/Development/redhat/sfdeasy/my-project
import { getFleet } from './fleet-utils.js';

const workers = getFleet();
// ❌ Throws: "COMPLIANCE VIOLATION: Cannot use distributed fleet"

const workers = getFleet({ localOnly: true });
// ✅ Returns: [] (empty, runs locally)
```

## Version History

- **2.0** (2026-06-12) - Architecture documentation added
  - Discovery architecture explanation (static + health probes)
  - Complete getFleet() flow documentation
  - Health check caching strategy details
  - Scaling strategy for 5-100+ machines
  - Comprehensive troubleshooting guide
  - Machine add/remove procedures
  - Compliance enforcement mechanism
  
- **1.0** (2026-06-12) - Initial implementation
  - Config file with 5 machines: aio-01, server-01/02/03, pi-02
  - fleet-utils.js library with ESM exports
  - Health probing with 30s cache (smart caching: successes cached, failures re-checked)
  - Red Hat compliance enforcement with realpath symlink protection
  - SSH security: StrictHostKeyChecking=accept-new, BatchMode=yes
  - fleet-test workflow
