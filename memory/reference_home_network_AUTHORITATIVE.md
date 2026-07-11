---
name: home-network-authoritative
description: "AUTHORITATIVE home network topology and infrastructure - 12 devices total"
metadata:
  type: reference
  priority: CRITICAL
  date: 2026-07-10
---

# Home Network Infrastructure (AUTHORITATIVE)

**Source:** PostgreSQL `inventory.machines` table on **aio-01:5433/learning**  
**Last verified:** 2026-07-10  
**Total devices:** 12

## Network Architecture

### Core Infrastructure (Non-Workers)

**admin-ap** (192.168.1.2)
- Netgear WNDR3700 v4
- **Role:** Critical infrastructure - DNS, DHCP, mail, NTP
- MIPS 74Kc, 1 CPU, 128MB RAM, 128GB USB SSD
- DD-WRT v3.0-r64137M std
- Services: dnsmasq, postfix, sshd, rsync, ntpd, httpd, cron, ddns
- Always on, 100+ days uptime
- **NOT a worker - infrastructure only**

**util-ap** (192.168.1.3)
- Linksys EA6300 v1
- **Role:** Utility router with Debian chroot
- ARMv7 Broadcom Northstar, 2 CPU @ 800MHz, 128MB RAM, 128GB USB SSD
- Debian 13.5 Trixie in chroot, 524MB swap
- DD-WRT 4.4.302-rt232-st71
- Always on, 97+ days uptime
- **NOT a worker**

**nas**
- D-Link DNS-320
- **Role:** NFS server (read-only, mostly)
- ARMv5 Marvell Kirkwood, 1 CPU, 128MB RAM
- Always on
- **NOT a worker**

### Orchestrator (1)

**aio-01** (192.168.1.11)
- Lenovo C345 - AMD E2-1800 APU with Radeon HD Graphics
- **Role:** Fleet orchestrator - REST API at port 5000
- x86_64, 2 CPU @ 1.7GHz, 7.5GB RAM, 954GB SSD
- Debian GNU/Linux 13
- Always on
- **Services running:**
  - PostgreSQL (port 5433) - learning database
  - OrientDB (ports 2424, 2480) - graph database
  - Grafana (port 3000) - monitoring dashboards
  - Prometheus - metrics collection
  - REST API (port 5000) - orchestrator endpoints
- **Networking:** WiFi (wlp5s0) - faster than powerline ethernet
- **USB drives:** 2 external drives
  - /exports/usb/nvme (931GB XFS) - Samsung NVMe
  - /exports/usb/hdd (698GB XFS) - HDD backup

### Workers (8)

#### Heavy Compute Workers (4)

**server-01** (192.168.1.14)
- Toshiba Satellite - Intel Core i7-3630QM
- x86_64, 8 CPU @ 2.4GHz, 15.8GB RAM, 477GB SSD
- Debian GNU/Linux 13
- Always on: No

**server-02** (192.168.1.15)
- Dell Precision 490 - Intel Xeon X5365
- x86_64, 8 CPU @ 3.0GHz, 32GB RAM, 477GB HDD
- Debian GNU/Linux 13
- Always on: No

**server-03** (192.168.1.16)
- Dell Precision T5400 - Intel Xeon X5460
- x86_64, 8 CPU @ 3.16GHz, 32GB RAM, 477GB SSD
- Debian GNU/Linux 13
- Always on: No

**laptop-01** (172.17.0.1)
- Intel Core i7-8665U
- x86_64, 8 CPU @ 1.9GHz (up to 4.8GHz), 31.8GB RAM, 475GB SSD
- Fedora Linux 44
- **Primary dev workstation + heavy worker**
- Always on: Yes

#### Light Workers (4)

**pi-01** (192.168.1.9)
- Raspberry Pi - ARM Cortex-A72
- aarch64, 4 CPU @ 1.2GHz, 892MB RAM, 117GB USB
- Debian GNU/Linux 13
- Always on: Yes
- **Services:** AgentDVR, fail2ban

**pi-02** (no IP listed)
- Raspberry Pi - ARM Cortex-A72
- ARM64, 4 CPU, 892MB RAM, 128GB USB SSD
- Raspberry Pi OS
- Always on: Yes
- **Services:** Jellyfin, fleet-orchestrator

**server-ap** (192.168.1.4)
- Netgear R9000 Nighthawk X10
- **Role:** NFS server - media storage
- ARMv7 AnnapurnaLabs Alpine, 4 CPU, 1GB RAM
- Dual 1TB USB drives (sda: /exports/media-01, sdb: /root)
- DD-WRT 6.12.74, Debian chroot, 2GB swap
- Always on: Yes

**desktop-ap** (192.168.1.5)
- Netgear R9000 Nighthawk X10
- **Role:** Desktop area router - NFS client
- ARMv7 AnnapurnaLabs Alpine, 4 CPU, 1GB RAM, 128GB USB SSD
- DD-WRT 6.12.74, Debian chroot, 2GB swap
- NFS mounts: /mnt/aio-01, /mnt/nas
- Always on: Yes

## Database Authority

**PostgreSQL on aio-01:5433**
- Database: `learning`
- Source table: `inventory.machines`
- **This is the authoritative source for all fleet/network information**

**Query to verify:**
```sql
SELECT hostname, device_type, network_ip, primary_role, cpu_cores, ram_mb, always_on
FROM inventory.machines
ORDER BY id;
```

**Access via REST API (preferred):**
```bash
curl http://aio-01:5000/inventory/machines
```

## Performance Tuning (2026-07-10)

**Completed optimizations:**
- Network buffers increased 78-160× across all systems
- vm.swappiness reduced to 10 on all servers
- Unnecessary services disabled (atop, bluetooth, udisks2, polkit, uuidd)
- VM support enabled on server-01/02/03
- TCP keepalive, BBR congestion control, connection queue limits

**See:** Performance tuning session from other Claude instance

## Critical Points

- ✅ **PostgreSQL is on aio-01:5433** (NOT laptop-01!)
- ✅ **aio-01 is WiFi-connected** (faster than powerline ethernet)
- ✅ **9 nodes total:** 1 orchestrator + 8 workers
- ✅ **3 infrastructure devices:** admin-ap, util-ap, nas (NOT workers)
- ✅ **Database is the source of truth** - always check PostgreSQL before guessing

## Related Memories

- [[reference_fleet_architecture_AUTHORITATIVE]] - Fleet worker architecture
- [[project_2026-07-10_scraping_fleet_deployment]] - Scraping fleet deployment
- [[feedback_always_unified_rest_api]] - Always use REST API for database access

## Why This Memory Exists

Created to document the complete home network topology from the authoritative PostgreSQL source. Previous memory files had conflicting information about where PostgreSQL was located (laptop-01 vs aio-01). This memory clarifies that **PostgreSQL is definitively on aio-01:5433**.

**Always check the database before making assumptions!**
