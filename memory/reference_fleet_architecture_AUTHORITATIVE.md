---
name: fleet-architecture-authoritative
description: "AUTHORITATIVE fleet architecture - 1 orchestrator + 8 workers - READ THIS FIRST"
metadata:
  type: reference
  priority: CRITICAL
  originSessionId: bb1a995f-71af-4cc4-b103-e8c04a6b4d48
  date: 2026-07-10
---

# Fleet Architecture (AUTHORITATIVE SOURCE)

**Source:** PostgreSQL `inventory.machines` table on aio-01:5433  
**Last verified:** 2026-07-10

## Architecture: 1 Orchestrator + 8 Workers

### Orchestrator (1)

**aio-01** (192.168.1.11)
- **Role:** Orchestrator - REST API at port 5000
- **Hardware:** AMD E2-1800, 2 CPU, 7.5GB RAM, 954GB SSD
- **Device type:** orchestrator
- **Always on:** Yes
- **Purpose:** Central orchestration API, NOT a worker

### Workers (8 total)

#### Heavy Compute Workers (4)

1. **server-01** (192.168.1.14)
   - Intel i7-3630QM, 8 CPU @ 2.4GHz, 15.8GB RAM, 477GB SSD
   - Device type: server
   - Always on: No

2. **server-02** (192.168.1.15)
   - Intel Xeon X5365, 8 CPU @ 3.0GHz, 32GB RAM, 477GB HDD
   - Device type: server
   - Always on: No

3. **server-03** (192.168.1.16)
   - Intel Xeon X5460, 8 CPU @ 3.16GHz, 32GB RAM, 477GB SSD
   - Device type: server
   - Always on: No

4. **laptop-01** (172.17.0.1)
   - Intel i7-8665U, 8 CPU @ 1.9GHz (up to 4.8GHz), 31.8GB RAM, 475GB SSD
   - Device type: laptop
   - Always on: Yes
   - **Primary dev workstation + heavy worker**

#### Light Workers (4)

5. **pi-01** (192.168.1.9)
   - ARM Cortex-A72, 4 CPU @ 1.2GHz, 892MB RAM, 117GB USB
   - Device type: worker
   - Always on: Yes

6. **pi-02** (no IP listed)
   - ARM Cortex-A72, 4 CPU, 892MB RAM, 128GB USB SSD
   - Device type: worker
   - Always on: Yes

7. **server-ap** (192.168.1.4)
   - Netgear R9000, ARMv7 Alpine, 4 CPU, 1GB RAM, dual 1TB USB
   - Device type: router (but used as NFS server + worker)
   - Always on: Yes
   - **Primary role:** NFS server for media storage

8. **desktop-ap** (192.168.1.5)
   - Netgear R9000, ARMv7 Alpine, 4 CPU, 1GB RAM, 128GB USB SSD
   - Device type: router (but used as NFS client + worker)
   - Always on: Yes
   - Mounts: /mnt/aio-01, /mnt/nas

### Infrastructure (NOT workers)

**admin-ap** (192.168.1.2)
- Netgear WNDR3700, MIPS, 1 CPU, 128MB RAM
- **Role:** DNS/DHCP/mail/NTP infrastructure
- NOT a worker - critical infrastructure only

**util-ap** (192.168.1.3)
- Linksys EA6300, ARMv7, 2 CPU @ 800MHz, 128MB RAM
- **Role:** Utility router with Debian chroot
- NOT a worker

**nas**
- D-Link DNS-320, ARMv5, 1 CPU, 128MB RAM
- **Role:** NFS server
- NOT a worker

## Critical Corrections

**I (Claude) repeatedly got this wrong:**
- ❌ Said pi-02 was the orchestrator (WRONG - it's a worker!)
- ❌ Said pi-01/02 were "just workers" (CORRECT but dismissive)
- ❌ Forgot server-ap and desktop-ap are workers
- ❌ Confused which machines do what

**The truth:**
- ✅ **aio-01 = THE orchestrator** (REST API at port 5000)
- ✅ **8 workers total** (server-01/02/03, laptop-01, pi-01/02, server-ap, desktop-ap)
- ✅ **9 nodes total** = 1 orchestrator + 8 workers

## How Multi-AI Should Work

**User's expectation:**
1. **aio-01:5000 orchestrator API** routes work to 8 workers
2. **Multi-AI consensus** happens via orchestrator endpoints
3. **I (Claude) should call aio-01:5000** instead of spawning my own agents

**Current problem:**
- Orchestrator endpoints for multi-AI consensus don't exist yet
- I've been spawning agents myself instead of using orchestrator

**Solution needed:**
- Implement multi-AI routing endpoints on aio-01:5000
- Then use those endpoints for all consensus/review work

## Database Authority

**Source of truth:** `inventory.machines` table on aio-01:5433/learning

Query to verify:
```sql
SELECT hostname, device_type, primary_role, cpu_cores, ram_mb, always_on
FROM inventory.machines
ORDER BY id;
```

**Never guess - always check the database!**

## Related Memories

- [[feedback_always_use_fleet]] - Always use fleet for work
- [[feedback_always_multi_ai]] - Always use multi-AI consensus
- [[reference_distributed_fleet]] - Fleet utilities and usage patterns

## Why This Memory Exists

User got frustrated with me repeatedly getting the architecture wrong. This memory exists so I **NEVER get it wrong again**.

**Read this FIRST in every session before making assumptions about the fleet!**
