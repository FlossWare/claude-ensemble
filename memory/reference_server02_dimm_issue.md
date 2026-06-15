---
name: server-02-dimm-issue
description: server-02 has 32 GB RAM installed but only 23 GB usable due to DIMM issues - limits model size
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  priority: high
  hardware_constraint: true
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

# server-02 DIMM Issue

**Problem:** server-02 has bad/failed DIMMs limiting usable RAM

**Hardware Status:**
- **Installed RAM:** 32 GB (physical)
- **Usable RAM:** 23 GB (OS visible)
- **Missing:** 9 GB unavailable due to DIMM failures

**Impact:**
- Cannot safely run models >15-22B parameters
- deepseek-r1:32b (19 GB) would leave only 4 GB for OS - **TOO TIGHT**
- codestral:22b (12 GB) would leave only 11 GB - **MARGINAL**
- Models ≤13B (7-8 GB) work fine

**Model Size Limits by Server:**
- **server-01:** 15 GB RAM → ≤7B models only
- **server-02:** 23 GB RAM (DIMM issue) → ≤13B models safely
- **server-03:** 31 GB RAM (full) → All models including 32B

**Workaround Applied (2026-06-14):**
- server-02 gets models up to 13B only
- server-03 gets full model set including deepseek-r1:32b
- Servers have different model inventories due to hardware constraint

**Future Fix:**
Replace failed DIMMs on server-02 to restore full 32 GB capacity

**Related:** [[reference_distributed_fleet]] - Fleet hardware profiles
