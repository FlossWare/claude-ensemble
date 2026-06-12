---
name: fleet-architecture-complete
description: "Complete fleet architecture documentation: discovery strategy, implementation, and scaling"
metadata:
  type: architecture-guide
  created: 2026-06-12
  tags: [fleet, architecture, discovery, compliance, distributed-systems]
  related: [reference_distributed_fleet, fleet_discovery_static_vs_dynamic, fleet_operations_guide]
---

# Fleet Architecture - Complete Documentation

## Executive Summary

**Current Implementation:** Static `~/.claude/fleet.json` configuration + SSH health probes

**Recommendation:** Keep current approach (Option A) for 5-50 machine scale

**Scaling Path:**
- **5-25 machines:** Static config (current, no changes)
- **25-50 machines:** Add environment variables (staging/prod)
- **50-100 machines:** Lightweight Consul agents
- **100+ machines:** Full Consul cluster

**Key Design Principles:**
1. Single source of truth (config file, not discovery)
2. Explicit compliance boundaries (Red Hat required)
3. Minimal operational overhead
4. Scales comfortably to 50+ machines

---

## Architecture Overview

### Fleet Topology

```
┌─────────────────────────────────────────────────────────────┐
│ Main Machine (workstation/laptop)                           │
│ - ~/.claude/fleet.json (authoritative config)              │
│ - NFS root for shared code                                 │
│ - Workflow execution                                        │
└─────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┬────────────┐
        │                │                │            │
    ┌───▼───┐        ┌───▼───┐       ┌────▼────┐  ┌───▼───┐
    │aio-01 │        │srv-01 │       │ srv-02  │  │srv-03 │
    │ 2C/7G │        │ 8C/15G│       │ 8C/31G  │  │8C/31G │
    │       │        │       │       │         │  │       │
    │Ctrl   │        │Worker │       │ Worker  │  │Worker │
    └───────┘        └───────┘       └─────────┘  └───────┘
        │                │                │            │
        └────────────────┼────────────────┴────────────┘
                 SSH (bidirectional)
                 + NFS (read shared code)

    + pi-02 (4C/1GB Sentinel, optional)
```

### Discovery Flow

```
┌─ Fleet Discovery ─────────────────────────────────────┐
│                                                        │
│  1. getFleet(options)                                 │
│      ├─ Load ~/.claude/fleet.json                     │
│      ├─ Validate compliance (forbidden paths)         │
│      ├─ Filter by criteria (role, capabilities, etc) │
│      ├─ Health check via SSH (with 30s cache)        │
│      ├─ Sort by priority                             │
│      ├─ Enforce max_parallel_workers                 │
│      └─ Return [online machines only]                │
│                                                        │
│  Cost:                                               │
│  - First call: ~2s (5 machines × ~400ms each)       │
│  - Cached: <50ms                                     │
│  - After 30s: ~2s again (cache expires)             │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Configuration Structure

**File:** `~/.claude/fleet.json`

```json
{
  "version": "1.0",
  "description": "Personal distributed fleet",
  "default_user": "sfloess",
  "nfs_root": "/home/sfloess/Development",
  
  "machines": [
    {
      "hostname": "aio-01",
      "role": "controller",
      "cpus": 2,
      "memory_gb": 7,
      "tags": ["personal", "always-on"],
      "capabilities": ["nfs-server", "orchestration"],
      "priority": 1,
      "notes": "..."
    },
    { /* worker machines */ }
  ],
  
  "compliance": {
    "forbidden_paths": ["/home/sfloess/Development/redhat/"],
    "enforcement": "strict",
    "reason": "Red Hat compliance: distributed fleet not allowed"
  },
  
  "policies": {
    "health_check_timeout_ms": 2000,
    "max_parallel_workers": 3,
    "require_nfs": true,
    "fallback_to_local": true
  }
}
```

---

## Why This Architecture?

### Discovery Method Comparison

| Aspect | Static Config | mDNS | Consul | NFS | Hybrid |
|--------|---------------|------|--------|-----|--------|
| **Complexity** | Low ✅ | Medium | Very High | Low | High |
| **Compliance** | Yes ✅ | No | Yes | No | Yes |
| **Works offline** | Yes ✅ | No | No | No | Yes |
| **Metadata** | Yes ✅ | No | Yes | No | Yes |
| **At 5 machines** | Perfect ✅ | Overkill | Overkill | Bad | Complex |
| **At 100 machines** | Slow | Bad | Perfect | Bad | Complex |
| **Source of truth** | Config ✅ | Discovery | Registry | Files | Dual (conflict) |

**Decision: Static Config + Health Probes**

**Rationale:**
1. **Fleet is static** - Machines rarely change (maybe 1-2 times/year)
2. **Compliance required** - Explicit boundaries needed for Red Hat work
3. **Simplicity wins** - Config file is easier than service registry
4. **Production ready** - Already implemented, zero issues
5. **Costs aligned** - 2s startup penalty acceptable for occasional use

**Key Insight:** Dynamic discovery is only valuable when machines *frequently* join/leave. For a *static* fleet, configuration is simpler.

---

## Implementation Details

### getFleet() Algorithm

```javascript
function getFleet(options = {}) {
  // Step 1: Load & validate config
  const config = loadFleetConfig();
  validateCompliance(config);
  
  // Step 2: Start with all machines
  let machines = [...config.machines];
  
  // Step 3: Apply filters (AND logic for all)
  if (options.tags) {
    machines = machines.filter(m =>
      options.tags.every(tag => m.tags.includes(tag))
    );
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
  
  // Step 4: Health check (with smart caching)
  if (!options.skipHealthCheck) {
    const now = Date.now();
    const useCached = healthCache && (now - cacheTimestamp < CACHE_TTL_MS);
    
    if (!useCached) {
      healthCache = new Map();
      cacheTimestamp = now;
    }
    
    machines = machines.filter(m => {
      // Only cache successes; always re-check failures
      if (useCached && healthCache.get(m.hostname) === true) {
        return true;
      }
      
      const healthy = probeHealth(m.hostname, timeout);
      healthCache.set(m.hostname, healthy);
      return healthy;
    });
  }
  
  // Step 5: Sort by priority, enforce policy
  machines.sort((a, b) => (a.priority || 99) - (b.priority || 99));
  
  const maxWorkers = config.policies?.max_parallel_workers;
  if (maxWorkers && maxWorkers > 0) {
    machines = machines.slice(0, maxWorkers);
  }
  
  return machines;
}
```

### Health Check Strategy

**Why Smart Caching Matters:**

```
Naive approach (always probe):
  getFleet() at t=0s:   SSH aio-01, server-01, server-02, server-03 = 2s
  getFleet() at t=0.1s: SSH aio-01, server-01, server-02, server-03 = 2s  (wasteful!)
  getFleet() at t=1s:   SSH aio-01, server-01, server-02, server-03 = 2s  (wasteful!)

Smart caching (cache successes, not failures):
  getFleet() at t=0s:   SSH probe all = 2s
                        Cache: {aio-01: true, srv-01: true, srv-02: true, srv-03: true}
  
  getFleet() at t=0.1s: Use cache (< 30s) = <50ms  (efficient!)
  getFleet() at t=1s:   Use cache (< 30s) = <50ms  (efficient!)
  
  srv-01 goes down at t=2s
  getFleet() at t=2.5s: Use cache (still valid) = <50ms
                        Returns: [aio-01, server-02, server-03]  (doesn't know srv-01 is down)
  
  getFleet() at t=32s:  Cache expired (> 30s)
                        SSH probe all = 2s
                        srv-01: FAIL (detected)
                        Cache: {aio-01: true, srv-01: false, srv-02: true, srv-03: true}
```

**Why not cache failures:**
A machine that fails health check might recover quickly (network hiccup, SSH restart, etc.). If we cached failures, we'd hide the recovery. Caching successes is safe - if a machine is online, it's likely to stay online for 30 seconds.

---

## Compliance Enforcement

### How It Works

```javascript
// Before returning machines, validate compliance
function validateCompliance(config) {
  const cwd = fs.realpathSync(process.cwd());  // Resolve symlinks
  const forbidden = config.compliance.forbidden_paths;
  
  for (const path of forbidden) {
    const forbiddenReal = fs.realpathSync(path);  // Resolve symlinks
    
    if (cwd.startsWith(forbiddenReal)) {
      throw new Error(
        `COMPLIANCE VIOLATION: Cannot use distributed fleet.\n` +
        `Current directory: ${cwd}\n` +
        `Forbidden path: ${forbiddenReal}\n` +
        `Reason: Red Hat compliance`
      );
    }
  }
}
```

### Why Realpath Matters

**Problem:** Symlinks could bypass enforcement

```bash
# Attacker creates symlink
ln -s /home/sfloess/Development/redhat ~/Development/redhat-alias

# Without realpath:
process.cwd() = '/home/sfloess/Development/redhat-alias'
forbidden = '/home/sfloess/Development/redhat'
'redhat-alias'.startsWith('redhat') = false  ❌ BYPASSED!

# With realpath:
fs.realpathSync('/home/sfloess/Development/redhat-alias')
  → '/home/sfloess/Development/redhat'
fs.realpathSync('/home/sfloess/Development/redhat')
  → '/home/sfloess/Development/redhat'
'.../redhat'.startsWith('.../redhat') = true  ✅ CAUGHT!
```

### Configuration Example

```json
{
  "compliance": {
    "forbidden_paths": [
      "/home/sfloess/Development/redhat/",
      "/opt/redhat/",
      "/home/sfloess/work/corporate/"
    ],
    "enforcement": "strict",
    "reason": "Red Hat compliance: only approved infrastructure permitted"
  }
}
```

---

## Scaling Strategy

### Growth Threshold Map

```
Machine Count    │ Strategy           │ Pain Points     │ Action
─────────────────┼────────────────────┼─────────────────┼──────────────────
5-25             │ Static config      │ None            │ Keep current
                 │ SSH health probes   │ ~2s startup    │ No change
─────────────────┼────────────────────┼─────────────────┼──────────────────
25-50            │ Static config      │ Manual updates  │ Add environment
                 │ + env override      │ tedious         │ variables:
                 │ (staging/prod)      │                │ FLEET_ENV=prod
─────────────────┼────────────────────┼─────────────────┼──────────────────
50-100           │ Lightweight        │ Health check    │ Add Consul
                 │ Consul agents       │ slow (~5-10s)  │ light agents,
                 │ + static fallback   │                │ keep static
─────────────────┼────────────────────┼─────────────────┼──────────────────
100+             │ Full Consul        │ Operational     │ Deploy Consul
                 │ cluster            │ overhead high  │ cluster,
                 │ (auto-discovery)   │ (HA, quorum)   │ automated health
```

### Example: 50 Machine Scaling

**Before (static, painful):**
```json
{
  "machines": [
    { "hostname": "server-01", ... },
    { "hostname": "server-02", ... },
    // ... 48 more entries ...
    { "hostname": "server-50", ... }
  ]
}
```

**After (environment-based, manageable):**
```bash
# environments/prod.json
{
  "machines": [
    { "hostname": "prod-server-01", ... },
    // ... 25 production machines ...
  ]
}

# environments/staging.json
{
  "machines": [
    { "hostname": "stage-server-01", ... },
    // ... 25 staging machines ...
  ]
}
```

**Usage:**
```bash
# Load appropriate config
export FLEET_ENV=prod
# Load ~/.claude/fleet-${FLEET_ENV}.json

export FLEET_ENV=staging
# Load ~/.claude/fleet-${FLEET_ENV}.json
```

---

## When to Reconsider

### Trigger Events

**At 50+ machines:**
- Manual fleet.json updates become impractical
- Consider: Terraform to generate fleet.json
- Or: Lightweight Consul agents

**At 100+ machines:**
- Health probe latency unacceptable (~5-10 seconds)
- Consider: Full Consul cluster
- Migrate to: Distributed health checks (TTL-based)

**If machines join/leave >10/week:**
- Manual updates unsustainable
- Consider: Auto-discovery (Consul, Nomad)
- Or: Terraform automated config generation

**If compliance boundaries relax:**
- Could explore: mDNS for LAN-only discovery
- Unlikely in Red Hat environment

**If NFS infrastructure changes:**
- Currently assuming NFS available on all machines
- If changes: May need service registry

---

## Operations

### Common Tasks

**Check fleet status:**
```javascript
import { getFleet } from './shared/fleet-utils.js';
const fleet = getFleet();
console.log(`${fleet.length} machines online`);
```

**Add machine:**
1. Update ~/.claude/fleet.json (add machine object)
2. Verify SSH works: `ssh new-host 'echo ok'`
3. Verify NFS works: `ssh new-host 'ls ~/Development'`
4. Test discovery: `const found = getFleet().find(m => m.hostname === 'new-host')`

**Remove machine:**
1. Delete machine object from fleet.json
2. Verify removal: `const found = getFleet().find(m => m.hostname === 'old-host')`

**Troubleshoot missing machine:**
1. Is it in fleet.json? (No → add it)
2. Is it online? (No → power on)
3. Does SSH work? (No → check key)
4. Is it filtered? (Yes → check options)
5. Is cache stale? (Maybe → clearHealthCache())

### Maintenance

**Weekly:** Verify all machines online
```javascript
import { getFleet, clearHealthCache } from './shared/fleet-utils.js';
clearHealthCache();
const online = getFleet();
console.log(`${online.length} machines online`);
```

**Monthly:** Check disk space, update notes

**Quarterly:** Test remote execution on all machines

**Annually:** Review fleet.json, retire unused machines

---

## Security Considerations

### SSH Hardening

**Current settings (secure):**
```bash
ConnectTimeout=2s         # Fail fast
BatchMode=yes             # No password prompts
StrictHostKeyChecking=yes # Requires known_hosts (MITM prevention)
```

**If mismatch found:**
```bash
ssh server-01 'echo ok'
# Permission denied (publickey)
# → SSH key issue, not health check failure

ssh-add ~/.ssh/id_rsa_virtos  # Re-add key
```

### Command Injection Prevention

**Single-quote escaping used throughout:**
```javascript
// Don't do this:
ssh host 'command with ' + variable  // Unsafe!

// Do this:
const escaped = variable.replace(/'/g, "'\\''");
ssh host 'command with ' + escaped  // Safe
```

### Symlink Bypass Prevention

**Realpath used for compliance checks:**
```javascript
const cwd = fs.realpathSync(process.cwd());  // Resolves symlinks
const forbidden = fs.realpathSync('/redhat');  // Resolves symlinks
if (cwd.startsWith(forbidden)) { ... }  // Can't bypass with symlinks
```

---

## Key Files and Locations

| File | Purpose | Owner | Access |
|------|---------|-------|--------|
| `~/.claude/fleet.json` | Configuration (source of truth) | User | R/W |
| `~/Development/.../fleet-utils.js` | Discovery library | Code | R |
| `~/Development/.../fleet-integration.js` | Workflow integration | Code | R |
| `~/Development/.../fleet-test.js` | Test workflow | Code | R |
| `~/.ssh/id_rsa_virtos` | SSH key | User | R |
| `~/.ssh/known_hosts` | Trusted hosts | SSH | R/W |

---

## Testing

### Fleet Test Workflow

```bash
# Run comprehensive fleet test
Workflow({ name: 'fleet-test' })
```

**Expected output:**
```
Discovering fleet from ~/.claude/fleet.json
Found 5 machines in config

Health checks:
  aio-01:      OK (2C/7GB)
  server-01:   OK (8C/15GB)
  server-02:   OK (8C/31GB)
  server-03:   OK (8C/31GB)
  pi-02:       OK (4C/1GB)

5/5 machines online ✓

Remote execution test:
  aio-01:      Executed: uptime
  server-01:   Executed: uptime
  ...
```

### Manual Verification

```javascript
// Load and validate config
import { getFleet } from './shared/fleet-utils.js';

// Test 1: Config loads
const config = loadFleetConfig();
console.log(`${config.machines.length} machines in config`);

// Test 2: Compliance works
try {
  const workers = getFleet();
  console.log('Compliance check passed');
} catch (e) {
  if (e.message.includes('COMPLIANCE')) {
    console.log('Compliance correctly enforced in forbidden path');
  }
}

// Test 3: Health checks work
const online = getFleet();
console.log(`${online.length} machines online`);

// Test 4: Filtering works
const workers = getFleet({ role: 'worker' });
const highMem = getFleet({ minMemoryGb: 30 });
console.log(`${workers.length} workers, ${highMem.length} with 30GB+`);
```

---

## Lessons Learned

### Key Insights

1. **Simplicity scales** - Static config handles 5-50 machines fine. Only add complexity when required.

2. **Compliance shapes architecture** - Red Hat boundaries require explicit config, not discovery.

3. **Cache strategy matters** - Cache successes (machines stay online), not failures (may recover).

4. **Single source of truth** - Don't mix static + dynamic. Dual sources cause debug nightmares.

5. **SSH is underrated** - For small fleets, synchronous SSH probes beat service registries.

6. **Health check TTL** - 30 seconds balances freshness (know within 30s when machine goes down) vs cost (cache most calls).

### Anti-Patterns Avoided

- ❌ Using NFS as a database (stale files, race conditions)
- ❌ Dual sources of truth (static + mDNS = confusion)
- ❌ Over-engineering (Consul for 5 machines)
- ❌ Caching failures (hides recoveries)
- ❌ Lax compliance (no realpath bypass prevention)

---

## Document History

- **1.0** (2026-06-12) - Complete architecture documentation
  - Discovery method comparison and decision rationale
  - Implementation details (getFleet algorithm, caching)
  - Compliance enforcement mechanism
  - Scaling strategy to 100+ machines
  - Operations guide and troubleshooting
  - Security considerations
  - Related documents cross-reference

---

## Related Documents

**Reference:**
- [[reference_distributed_fleet]] - API documentation and quick start

**Decision:**
- [[fleet_discovery_static_vs_dynamic]] - Detailed option analysis

**Operations:**
- [[fleet_operations_guide]] - Procedures, troubleshooting, maintenance

---

## Quick Decision Table

**Should I use the fleet for this task?**

| Situation | Use Fleet? | Why |
|-----------|-----------|-----|
| Personal project, parallel build | ✅ Yes | Perfect fit |
| Red Hat work | ❌ No | Compliance blocks |
| Quick one-off operation | ❌ Maybe | 2s startup cost |
| Multi-model consensus (6 models) | ✅ Yes | Distribute across workers |
| Single-machine task | ❌ No | No parallelism benefit |
| Temporary connectivity issue | ⚠️ Try local | Use --local-only |

---

## FAQ

**Q: Why not use mDNS?**
A: Breaks compliance (machines auto-advertise without boundaries). Red Hat compliance requires explicit config.

**Q: Why not use Consul now?**
A: 5 machines don't justify 100MB overhead + operational burden. Viable at 100+ machines.

**Q: Can we make health checks faster?**
A: Cache is already optimized. Could skip checks with `skipHealthCheck: true`, but loses freshness.

**Q: What if a machine goes down?**
A: getFleet() excludes it from results (health check fails). If it comes back up within 30s, cached results still exclude it. After 30s, health check refreshes.

**Q: Can we disable compliance checking?**
A: No (intentional). Use `localOnly: true` instead if you must override.

**Q: How do we scale to 100 machines?**
A: At 50+, migrate to Consul with automated health checks. See scaling strategy above.
