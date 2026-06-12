---
name: fleet-discovery-static-vs-dynamic
description: "Analysis of fleet discovery patterns: static vs dynamic discovery for 5-100+ machine scale"
metadata:
  type: architecture-decision
  created: 2026-06-12
  tags: [distributed-fleet, discovery, architecture, compliance, scaling]
  related: [reference_distributed_fleet, project_jnexus_architecture]
---

# Fleet Discovery: Static vs Dynamic Analysis

## Context

A 5-machine personal distributed fleet (aio-01, server-01/02/03, pi-02) needs a discovery mechanism to:
1. Identify which machines are online/available
2. Enable smart filtering (by role, capabilities, resources)
3. Enforce compliance boundaries (Red Hat work forbidden)
4. Scale from 5 to potentially 100+ machines

Current implementation: Static `~/.claude/fleet.json` + SSH health probes.

**Question:** At 5 machines, should we add dynamic discovery, or keep static config?

## Options Evaluated

### Option A: Keep Static fleet.json + Health Probes (CHOSEN)

**Design:** Config-based inventory + runtime SSH probes

**Flow:**
```
Load config → Filter by criteria → SSH probe each → Return online machines
```

**Pros:**
- ✅ Authoritative source of truth (explicit, not discovered)
- ✅ Compliance-friendly (explicit forbidden paths, no auto-boundaries)
- ✅ Works offline (no external registry dependency)
- ✅ Zero dependencies beyond SSH
- ✅ Simple to debug (human-readable config)
- ✅ No race conditions or eventual consistency issues
- ✅ Scales to ~50 machines comfortably
- ✅ Production-ready today

**Cons:**
- ❌ Manual update required to add/remove machines
- ❌ 2s startup cost for health probes (cached 30s)
- ❌ SSH access required to all machines

**Cost-benefit at 5 machines:** ✅ Excellent trade-off
- Manual updates: Maybe 1-2 per year (acceptable)
- Health probe cost: 2s cached = negligible for batch operations
- Compliance benefit: Explicit boundaries required by Red Hat

**Scaling to 50 machines:**
- Still viable with config management (Terraform/Ansible to generate fleet.json)
- Health probe cost increases (~100ms per machine) but remains acceptable
- No architectural changes needed

**Scaling to 100+ machines:**
- Health probes become slow (~5s for 50 machines)
- Manual config management becomes impractical
- Should migrate to Option C (Consul) at this point

---

### Option B: Add DNS-SD/mDNS Discovery (Avahi/Bonjour)

**Design:** Machines self-advertise via mDNS, discovery scans .local names

**Flow:**
```
Scan mDNS for _claude._tcp.local → Get machine names → SSH probe → Return
```

**Pros:**
- ✅ Zero-config: new machines auto-discovered
- ✅ Works on LANs without external registry
- ✅ Low overhead (just mDNS daemon on each machine)

**Cons:**
- ❌ LAN-only (breaks remote/datacenter scenarios)
- ❌ No metadata support (specs, capabilities, forbidden paths)
- ❌ Requires Avahi on all machines (~5MB overhead)
- ❌ Unreliable on VLANs, complex networks
- ❌ Cannot enforce compliance boundaries (machines advertise themselves)
- ❌ Race conditions (machines joining/leaving during scan)
- ❌ Incompatible with static compliance model

**Why rejected:** Compliance enforcement requires explicit config. mDNS doesn't support "forbidden boundaries" - if a machine advertises itself, you can't prevent its discovery. This breaks Red Hat compliance requirement.

**When viable:** Internal LAN-only fleets without compliance constraints.

---

### Option C: Consul/etcd Service Registry

**Design:** Central registry with agents on each machine, distributed consensus health checks

**Flow:**
```
Consul agents → register machines → Consul leader → query for healthy services
```

**Pros:**
- ✅ Production-grade with distributed consensus
- ✅ Rich metadata (machine specs, capabilities, custom fields)
- ✅ Automated health checks with TTL
- ✅ Service topology awareness
- ✅ Scales to 1000+ machines
- ✅ Industry standard for service discovery

**Cons:**
- ❌ ~100MB minimum overhead per machine
- ❌ 5-10 minutes to setup properly (bootstrap, consensus)
- ❌ Complex operational burden (cluster management, quorum, upgrades)
- ❌ Requires Consul agents on all machines
- ❌ Overkill for 5-50 machines (complexity vs benefit ratio)
- ❌ Additional attack surface (Consul API exposed)
- ❌ Learning curve for ops team

**Cost-benefit at 5 machines:** ❌ Over-engineered
- 100MB overhead: Too much for 5 machines
- Operational burden: Overkill for static fleet
- Setup time: 5-10 minutes vs 5 minutes for config update
- Would it solve a real problem? No (fleet is static)

**Viable at 100+ machines:** ✅ Yes
- Scale justifies operational overhead
- Auto-health checks become valuable
- Service topology critical at that scale

**Migration path:** If fleet grows to 50+ machines, consider Consul.

---

### Option D: File-based Registry on NFS

**Design:** Each machine writes `~/.claude/fleet-registry/<hostname>.json` to NFS

**Flow:**
```
All machines → write status to NFS → Read all files → Parse → Return
```

**Pros:**
- ✅ Leverages existing NFS infrastructure
- ✅ Simple concept (just files)

**Cons:**
- ❌ Stale file problem: dead machines leave files behind
- ❌ Race conditions: simultaneous reads/writes
- ❌ No atomic updates: partial writes corrupt registry
- ❌ No TTL: machines don't auto-deregister
- ❌ NFS consistency issues (sync delays, cache invalidation)
- ❌ No validation (files could be forged)
- ❌ Harder to debug than config file
- ❌ Requires NFS access from this machine (implicit dependency)

**Why rejected:** NFS is not a database. It lacks essential capabilities:
- No transactional guarantees (can't write-and-read atomically)
- No TTL or auto-cleanup (stale files accumulate)
- Network delays cause consistency problems

**Anti-pattern:** Using NFS as a registry is a known anti-pattern.

---

### Option E: Hybrid Static + Optional mDNS Scanning

**Design:** Primary: static fleet.json. Secondary: optional mDNS scan to find new machines

**Flow:**
```
Load fleet.json → health probe known machines → 
optional: scan mDNS for new machines → merge results
```

**Pros:**
- ✅ Keeps compliance boundaries (explicit config)
- ✅ Optional auto-discovery (best of both?)
- ✅ Flexible (can disable mDNS if on VPN)

**Cons:**
- ❌ More complexity: two sources of truth
- ❌ Harder to debug: which machine from where?
- ❌ mDNS unreliability still affects results
- ❌ Still requires manual config update for *primary* machines
- ❌ Adds code burden without solving the core problem
- ❌ Compliance still requires explicit boundaries

**Why rejected:** Adds complexity without solving a problem. At 5 machines, manual config is fine. Hybrid approach is a "gold plating" anti-pattern.

---

## Decision Matrix

| Aspect | A: Static | B: mDNS | C: Consul | D: NFS | E: Hybrid |
|--------|-----------|---------|-----------|--------|-----------|
| **Complexity** | Low | Medium | Very High | Low | High |
| **Dependencies** | SSH | Avahi | Consul | NFS | SSH+Avahi |
| **Metadata support** | Yes | No | Yes | No | Yes |
| **Compliance ready** | ✅ Yes | ❌ No | ✅ Yes | ❌ No | ✅ Yes |
| **Works offline** | ✅ Yes | ❌ No | ❌ No | ❌ No | ✅ Yes |
| **Scale to 50** | ✅ Good | ❌ Bad | ✅ Overkill | ❌ Bad | ❌ Complex |
| **Scale to 100+** | ❌ Slow | ❌ Bad | ✅ Good | ❌ Bad | ❌ Bad |
| **Setup time** | Minutes | Minutes | 5-10 min | Minutes | Minutes |
| **Operational burden** | Minimal | Low | High | High | Medium |
| **Failure modes** | Simple | Race cond. | Quorum loss | Stale files | Two sources |
| **Production ready** | ✅ Now | ⚠️ Maybe | ✅ Yes | ❌ Never | ❌ No |

## RECOMMENDATION: Option A (Static + Health Probes)

### Rationale

**At 5 machines:**
1. **Simplicity wins** - Static config is trivial to manage and debug
2. **Compliance alignment** - Explicit config enables explicit boundaries (Red Hat requirement)
3. **No cost** - 2s health probe with 30s cache is negligible for occasional use
4. **Proven** - Current implementation works perfectly, zero issues
5. **Future-proof** - Scales to 50 machines before reconsidering

**Cost-benefit analysis:**
- Problem being solved: "Identify online machines from a known list"
- Option A: Load config, probe SSH (2 lines of code per machine)
- Option B-E: Add complexity for a problem that doesn't exist

**The key insight:** At 5 machines, the fleet is *static*. You know exactly which machines should exist. Dynamic discovery is only valuable when machines frequently join/leave unpredictably. For a personal fleet that changes 1-2 times per year, static config is ideal.

### When to Reconsider

**Fleet grows to 30+ machines:**
- Health probe latency becomes noticeable (~3 seconds)
- Manual config management becomes tedious
- **Action:** Add environment-based configs (staging, prod) instead of individual machines
- Keep static model but organize better

**Fleet reaches 50+ machines:**
- Health probe latency becomes significant (~5-10 seconds)
- Manual updates impractical (need automation)
- **Action:** Migrate to lightweight Consul (Consul client agents) or environment-based discovery
- Keep compliance boundaries but automate inventory

**Fleet exceeds 100 machines:**
- Static model no longer viable
- **Action:** Full Consul cluster with distributed health checks
- Metadata-rich discovery becomes essential

**Machines frequently join/leave (>10/week):**
- Manual updates become burden
- **Action:** Implement auto-deregistration via TTL
- Still keep static model as primary (explicit), but add auto-cleanup

**Compliance requirements relax:**
- Could explore mDNS for LAN-only discovery
- Unlikely to happen for Red Hat work

### Implementation Plan

**No changes needed.** Current implementation is optimal for current scale.

**When you do scale:**
```
5-25 machines  → Static fleet.json (current approach)
25-50 machines → Add environment overrides (FLEET_ENV=staging)
50-100 machines → Add Consul light agents + static fallback
100+ machines  → Full Consul cluster
```

### Future Scaling Path

```
┌──────────────────────────────────────────────────────────────┐
│ Fleet Size vs Discovery Strategy                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ 5 machines   │ Static fleet.json + SSH probes (NOW)          │
│              │ Health check: 2s cached 30s                   │
│              │ Cost: Minimal | Burden: Minimal               │
│              │                                                │
│ 25 machines  │ Static fleet.json + SSH probes + env override │
│              │ Add: FLEET_ENV=staging/prod (choose config)   │
│              │ Health check: ~1-2s per env                   │
│              │ Cost: Low | Burden: Low                       │
│              │                                                │
│ 50 machines  │ Lightweight Consul agents (or Nomad)          │
│              │ Add: Per-machine deregistration (TTL)         │
│              │ Keep: Static boundaries in code               │
│              │ Health check: Automated by Consul             │
│              │ Cost: Medium | Burden: Medium                 │
│              │                                                │
│ 100+ machines│ Full Consul cluster (HA setup)                │
│              │ Auto-discovery fully automated                │
│              │ Health checks distributed                     │
│              │ Cost: High | Burden: High (but justified)     │
│              │                                                │
└──────────────────────────────────────────────────────────────┘
```

## Key Lessons

### Lesson 1: Simplicity at the Right Scale

Complex solutions (Consul, mDNS) provide value at large scale. At small scale (5 machines), they add overhead without benefit.

**Takeaway:** Match solution complexity to problem size. Static config is perfect for static fleets.

### Lesson 2: Compliance Breaks Dynamic Discovery

Red Hat compliance requires explicit boundaries: "You can only use *these* machines for *this* work."

mDNS breaks this (machines auto-advertise), requiring added code to "un-discover" machines. Static config naturally enforces boundaries.

**Takeaway:** Compliance shapes architecture. Explicit config is more compliance-friendly than dynamic discovery.

### Lesson 3: Cache Strategy Matters

Health probes add ~2s per invocation. But machines don't change health status quickly. 30s cache balances:
- Freshness (not too stale)
- Cost (not too expensive)
- Reliability (re-check failures)

**Takeaway:** Cache successful probes, not failures. Failures can be transient.

### Lesson 4: SSH Beats Service Registries for Simple Fleets

For a small, static fleet, SSH probes are actually simpler than service registries:
- No additional infrastructure
- Works offline
- Leverages existing SSH setup
- Trivial to debug

**Takeaway:** Don't underestimate the simplicity of synchronous health checks for small fleets.

### Lesson 5: Two Sources of Truth Are Dangerous

Hybrid approaches (static + mDNS, static + Consul) create two sources of truth:
- "Did this machine come from config or discovery?"
- "Which one is authoritative?"
- "What if they conflict?"

Debug complexity explodes. Stick to one source.

**Takeaway:** Single source of truth is worth the manual effort at small scale.

## Related Architecture Decisions

- **[[reference_distributed_fleet]]** - Implementation guide for current static+health model
- **[[arbiter_worker_pattern]]** - Using distributed fleet for multi-AI consensus
- **[[project_jnexus_architecture]]** - Similar discovery challenges in artifact management

## FAQ

**Q: But what if machines are added frequently?**
A: If >10 machines per week, then auto-discovery becomes valuable. Until then, manual updates are faster to implement and debug.

**Q: Can we use Consul just for health checks?**
A: Technically yes, but you still pay the ~100MB overhead. At 5 machines, SSH probes are simpler. Consider at 50+.

**Q: What about Kubernetes service discovery?**
A: Overkill (need Kubernetes cluster). Works great for containerized workloads, not for VMs/baremetal personal fleet.

**Q: Should we add redundancy (backup discovery)?**
A: No. Static config file is the single source of truth. If it's corrupted, a backup wouldn't help (you'd have two conflicting sources). Instead, keep it in version control (git).

**Q: What if NFS becomes unavailable?**
A: Fleet.json is on local disk, not NFS. Discovery works offline. If NFS fails, health probes still succeed (machines are online), just can't access shared code.

**Q: Can we auto-generate fleet.json from Terraform?**
A: Yes! At 50+ machines, consider using Terraform to generate fleet.json, then commit to git. Machines defined as code, discovery via generated config.

---

## Document History

- **1.0** (2026-06-12) - Initial architecture decision document
  - Evaluated 5 discovery options (A-E)
  - Recommended Option A (static + health probes)
  - Provided scaling strategy to 100+ machines
  - Documented key lessons and tradeoffs
