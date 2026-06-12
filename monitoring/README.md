# Fleet Monitoring with Prometheus

Production-ready Prometheus + node_exporter + Grafana deployment for the distributed fleet.

**Multi-AI Consensus (91% confidence):**
- Native binaries (not Docker) - pi-02 has only 1GB RAM
- Static discovery with rich labels - 5-machine fleet doesn't justify dynamic discovery
- Alertmanager for alert delivery - grouping, inhibition, repeat intervals
- Grafana co-located on aio-01 - centralizes monitoring, memory-capped at 512MB
- 15-day retention with 3GB cap - conservatively sized for 7GB controller
- ntfy for notifications - two channels (fleet-alerts, fleet-alerts-critical)

## Quick Start

```bash
cd monitoring

# Phased deployment (recommended)
./deploy-fleet-prometheus.sh --dry-run                    # Verify connectivity
./deploy-fleet-prometheus.sh --node-exporter --parallel   # Install exporters
./deploy-fleet-prometheus.sh --prometheus                 # Install Prometheus
./deploy-fleet-prometheus.sh --grafana                    # Install Grafana (optional)

# All-in-one deployment
./deploy-fleet-prometheus.sh --ntfy-topic YOUR-UNIQUE-TOPIC
```

## Components

### Scripts

- **`install-node-exporter.sh`** (167 lines)
  - Auto-detects architecture (amd64/arm64/armv7/armv6)
  - Creates `node_exporter` system user
  - Systemd service with security hardening
  - Firewall configuration (firewalld/ufw)
  - Idempotent installation

- **`install-prometheus.sh`** (788 lines)
  - Prometheus 3.12.0 + Alertmanager 0.32.1
  - Complete `prometheus.yml` with 5 fleet machines
  - 21 alert rules across 7 groups
  - Systemd memory limits (Prometheus: 3GB, Alertmanager: 256MB)
  - Config validation via promtool

- **`install-grafana.sh`** (214 lines)
  - Official RPM/APT repository installation
  - Auto-provisions Prometheus datasource
  - Node Exporter Full dashboard (#1860)
  - Systemd memory limit (512MB)

- **`deploy-fleet-prometheus.sh`** (398 lines)
  - Bash orchestrator for fleet deployment
  - SCP + SSH deployment pattern
  - Supports `--dry-run`, `--parallel`, `--skip-grafana`
  - Connectivity pre-check, post-deployment verification

- **`deploy-fleet-prometheus.js`** (279 lines)
  - Node.js equivalent using fleet-utils.js patterns
  - Compatible with existing SSH security settings

### Alert Rules (21 rules in 7 groups)

**host_availability:**
- HostDown (2m, critical)
- HostRebootDetected (instant, warning)

**cpu_alerts:**
- HighCpuUsage (>85% for 10m, warning)
- CriticalCpuUsage (>95% for 5m, critical)
- ControllerCpuTooHigh (>60% for 5m on aio-01 - protects NFS latency)

**memory_alerts:**
- HighMemoryUsage (>85% for 10m, warning)
- CriticalMemoryUsage (>95% for 5m, critical)
- SentinelMemoryHigh (>70% for 5m on pi-02 - respects 1GB limit)

**disk_alerts:**
- DiskSpaceLow (>80%, warning)
- DiskSpaceCritical (>90%, critical)
- DiskWillFillIn24h (predictive, warning)
- DiskInodesLow (>90%, warning)

**network_alerts:**
- NetworkInterfaceDown (2m, warning)
- HighNetworkErrors (>10/sec, warning)

**system_health:**
- SystemdServiceFailed (1m, warning)
- HighLoadAverage (>2x CPUs for 15m, warning)
- ClockSkew (>50ms for 5m, warning)
- HighSwapUsage (>50%, warning)

**prometheus_self:**
- PrometheusTargetDown (3m, critical)
- PrometheusTsdbStorageHigh (>80% of 3GB, warning)
- PrometheusConfigReloadFailed (5m, warning)

## Memory Budget (aio-01: 7GB total)

| Component | MemoryMax | MemoryHigh | Usage |
|-----------|-----------|------------|-------|
| Prometheus | 3GB | 2GB | ~1.5GB typical |
| Grafana | 512MB | 384MB | ~300MB typical |
| Alertmanager | 256MB | - | ~50MB typical |
| **Total capped** | **3.75GB** | - | - |
| **OS + NFS + other** | - | - | **~3.25GB available** |

## Architecture Decisions

**1. Native binaries over Docker/Podman**
- Unanimous multi-AI agreement
- Docker daemon overhead: 100-200MB idle (unacceptable on 1GB pi-02)
- node_exporter native: 15-20MB RSS
- Zero build dependencies

**2. Static discovery over dynamic**
- 5-machine fleet doesn't justify Consul/mDNS
- Full metadata in labels (role, cpus, memory_gb, arch)
- Threshold to reconsider: 15+ machines

**3. Full Alertmanager (not simple webhook)**
- Alert grouping: multiple alerts → one notification
- Inhibition: critical alerts suppress warnings
- Repeat intervals: prevent notification fatigue
- Only 30MB binary, 50MB RSS

**4. Grafana on aio-01 (not server-01)**
- Centralizes monitoring infrastructure
- Memory-capped at 512MB (safe for 7GB machine)
- Doesn't waste high-memory worker on UI

**5. 15-day retention with 3GB cap**
- Conservative for 7GB machine running multiple services
- ~30-40MB/day ingestion at 30s scrape interval
- Prevents Prometheus from starving NFS/OS

**6. ntfy for alert delivery**
- Free, self-hosted, no account needed
- Two channels: warnings vs critical
- Mobile notifications

## ARM Architecture Note

**Raspberry Pi 3B (pi-02):**
- Hardware: ARMv8 (64-bit Cortex-A53)
- Common OS: 32-bit ARMv7 userspace (Raspberry Pi OS 32-bit)
- Script handles both: detects via `uname -m`
  - `armv7l` → downloads armv7 binaries
  - `aarch64` → downloads arm64 binaries

Verify your pi-02 architecture:
```bash
ssh pi-02 'uname -m'
```

## Customization

Before deploying:

1. **Verify hostnames resolve:**
```bash
for host in aio-01 server-01 server-02 server-03 pi-02; do
  getent hosts $host || echo "MISSING: $host"
done
```

2. **Set unique ntfy topic:**
```bash
./deploy-fleet-prometheus.sh --ntfy-topic YOUR-FLEET-$(uuidgen | cut -d- -f1)
```

3. **Check SSH access:**
```bash
for host in aio-01 server-01 server-02 server-03 pi-02; do
  ssh $host 'echo OK' || echo "FAIL: $host"
done
```

4. **Verify sudo NOPASSWD:**
```bash
ssh server-01 'sudo -n true' && echo "OK" || echo "FAIL: requires password"
```

## Deployment Options

```bash
# Dry run (connectivity check only)
./deploy-fleet-prometheus.sh --dry-run

# Node exporters only (all 5 machines)
./deploy-fleet-prometheus.sh --node-exporter --parallel

# Prometheus only (aio-01)
./deploy-fleet-prometheus.sh --prometheus

# Grafana only (aio-01)
./deploy-fleet-prometheus.sh --grafana

# Single host
./deploy-fleet-prometheus.sh --host server-01

# Custom ntfy settings
./deploy-fleet-prometheus.sh \
  --ntfy-topic my-fleet-alerts \
  --ntfy-url https://ntfy.sh
```

## Post-Deployment

**Access Grafana:**
```
http://aio-01:3000
Default credentials: admin/admin (change on first login)
```

**Access Prometheus:**
```
http://aio-01:9090
```

**Access Alertmanager:**
```
http://aio-01:9093
```

**Verify targets:**
```bash
curl -s http://aio-01:9090/api/v1/targets | jq '.data.activeTargets[] | {instance: .labels.instance, state: .health}'
```

**Check alerts:**
```bash
curl -s http://aio-01:9090/api/v1/alerts | jq '.data.alerts[] | {alert: .labels.alertname, state: .state}'
```

## Troubleshooting

**Target down:**
```bash
# Check node_exporter service
ssh server-01 'systemctl status node_exporter'

# Check firewall
ssh server-01 'sudo firewall-cmd --list-ports'  # Should include 9100/tcp

# Manual scrape test
curl http://server-01:9100/metrics | head
```

**Memory limits hit:**
```bash
# Check Prometheus memory usage
ssh aio-01 'systemctl status prometheus | grep -i memory'

# Check cgroup limits
ssh aio-01 'systemctl show prometheus | grep Memory'
```

**Alertmanager not sending:**
```bash
# Check Alertmanager logs
ssh aio-01 'sudo journalctl -u alertmanager -n 50'

# Test ntfy directly
curl -d "Test alert" https://ntfy.sh/YOUR-TOPIC
```

## Versions

| Component | Version | Source |
|-----------|---------|--------|
| Prometheus | 3.12.0 | GitHub releases |
| node_exporter | 1.11.1 | GitHub releases |
| Alertmanager | 0.32.1 | GitHub releases |
| Grafana | Latest | Official repo |

## Multi-AI Contributors

**Design decisions from:**
- Opus: Comprehensive alert rules, Alertmanager architecture, memory budget analysis
- Sonnet: ARM architecture awareness, NodeFlapping alert, runbook annotations
- Haiku: Confirmed consensus, provided validation

**Consensus level:** HIGH (3/3 models agreed)
**Final confidence:** 91%

## Related Documentation

- [[reference_distributed_fleet]] - Fleet architecture
- [[fleet-discovery-static-vs-dynamic]] - Why static discovery at 5-machine scale
- `~/.claude/fleet.json` - Fleet configuration with machine specs

## License

Multi-AI generated, production-hardened for personal fleet deployment.
