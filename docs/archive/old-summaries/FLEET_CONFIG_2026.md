# Fleet Configuration 2026-06-28

## Architecture: API-Only Workers

**Strategy:** 8 API-only workers + 1 infrastructure orchestrator  
**Total Cores:** 44+ for parallel API calls  
**SSH User:** `claude` (all workers)  
**Local Models:** Dormant (not deleted, not actively used)

---

## Infrastructure Orchestrator (NOT a Worker)

**Node:** `aio-01` (192.168.1.11)  
**Role:** Infrastructure only  
**Services:**
- PostgreSQL 17 (port 5433)
- Neo4j
- Routing logic

**Notes:** Does NOT participate in workload distribution

---

## Workers (8 Total)

### High-Performance Workers (3x)

1. **server-01**
   - CPU: 8 cores
   - RAM: High
   - SSH: `claude@server-01`
   - Role: API-only worker

2. **server-02**
   - CPU: 8 cores
   - RAM: High
   - SSH: `claude@server-02`
   - Role: API-only worker

3. **server-03**
   - CPU: 8 cores
   - RAM: High
   - SSH: `claude@server-03`
   - Role: API-only worker

### Development Worker (1x)

4. **laptop-01**
   - CPU: 8 cores
   - RAM: 28GB available
   - SSH: `claude@laptop-01`
   - Role: API-only worker + development

### Lightweight Workers (2x)

5. **pi-01**
   - CPU: 4 cores
   - RAM: 424MB
   - SSH: `claude@pi-01`
   - Role: API-only worker (lightweight tasks)

6. **pi-02**
   - CPU: 4 cores
   - RAM: 365MB
   - SSH: `claude@pi-02`
   - Role: API-only worker (monitoring + lightweight)

### Unknown Spec Workers (2x)

7. **desktop-ap**
   - CPU: Unknown
   - RAM: Unknown
   - SSH: `claude@desktop-ap`
   - Role: API-only worker
   - Notes: Verify specs if needed

8. **server-ap**
   - CPU: Unknown
   - RAM: Unknown
   - SSH: `claude@server-ap`
   - Role: API-only worker
   - Notes: Verify specs if needed

---

## API Access Policy

**All workers can use:**
- Free APIs (Groq, DeepInfra, Together, HuggingFace, etc.)
- Paid APIs (Anthropic, OpenAI, Google)

**Distribution:** Tasks distributed across all 8 workers for parallel execution

---

## Local Models Status

**Status:** Dormant (not deleted)  
**Endpoints:** Ollama services remain installed but not actively used  
**Strategy:** API-only approach for all workloads

**Local model endpoints still available (if needed):**
- Ollama: port 11434
- llama.cpp: port 8081

---

## Configuration Files

1. **Fleet Topology:** `shared/fleet-topology.js`
   - Single source of truth for fleet nodes
   - Used by monitoring and orchestration

2. **API Policy:** `lib/fleet-api-policy.json`
   - Defines API access rules per node
   - Enforces API-only strategy

3. **Model Registry:** `fleet-model-registry.json`
   - Cloud API model definitions
   - Local model definitions (dormant)

---

## Key Changes from Previous Config

**Before:**
- Mixed local/API strategy
- aio-01 as worker
- 5-6 active workers
- Local models actively used

**After (2026-06-28):**
- API-only strategy
- aio-01 as infrastructure orchestrator only
- 8 dedicated API workers
- Local models dormant
- All workers use SSH user `claude`
- Total 44+ cores for parallel API calls

---

## Verification Commands

```bash
# Test SSH connectivity to all workers
for host in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
  echo "Testing $host..."
  ssh -o ConnectTimeout=5 claude@$host "hostname && echo OK" || echo "FAILED: $host"
done

# Check PostgreSQL on orchestrator
ssh claude@aio-01 "psql -h localhost -p 5433 -U sfloess -d learning -c 'SELECT 1'"

# Verify no active Ollama usage (should show dormant or no processes)
for host in server-01 server-02 server-03 laptop-01; do
  echo "Checking Ollama on $host..."
  ssh claude@$host "pgrep -a ollama || echo 'No active Ollama processes'"
done
```

---

## Quick Reference

| Node | Role | Cores | RAM | SSH User |
|------|------|-------|-----|----------|
| aio-01 | Orchestrator | - | - | claude |
| server-01 | Worker | 8 | High | claude |
| server-02 | Worker | 8 | High | claude |
| server-03 | Worker | 8 | High | claude |
| laptop-01 | Worker + Dev | 8 | 28GB | claude |
| pi-01 | Worker (light) | 4 | 424MB | claude |
| pi-02 | Worker (light) | 4 | 365MB | claude |
| desktop-ap | Worker | ? | ? | claude |
| server-ap | Worker | ? | ? | claude |

**Total Workers:** 8  
**Total Cores:** 44+ (excluding unknown specs)  
**Architecture:** API-only for all workloads
