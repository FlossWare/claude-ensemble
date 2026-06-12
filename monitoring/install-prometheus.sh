#!/usr/bin/env bash
# =============================================================================
# install-prometheus.sh - Install Prometheus server + Alertmanager on aio-01
#
# Designed for the controller node (2C/7GB RAM).
# Includes Prometheus, Alertmanager, and pre-configured alert rules.
# Idempotent: safe to run multiple times.
#
# Usage:
#   sudo ./install-prometheus.sh
#
# Environment variables:
#   PROMETHEUS_VERSION     - Prometheus version (default: 3.12.0)
#   ALERTMANAGER_VERSION   - Alertmanager version (default: 0.32.1)
#   RETENTION_TIME         - Metrics retention period (default: 15d)
#   RETENTION_SIZE         - Max storage size (default: 3GB)
#   SKIP_FIREWALL          - Set to 1 to skip firewall configuration
#   NTFY_TOPIC             - ntfy notification topic (default: fleet-alerts)
#   NTFY_URL               - ntfy server URL (default: https://ntfy.sh)
# =============================================================================
set -euo pipefail

# --- Configuration ---
readonly PROM_VERSION="${PROMETHEUS_VERSION:-3.12.0}"
readonly AM_VERSION="${ALERTMANAGER_VERSION:-0.32.1}"
readonly RETENTION_TIME="${RETENTION_TIME:-15d}"
readonly RETENTION_SIZE="${RETENTION_SIZE:-3GB}"
readonly NTFY_TOPIC="${NTFY_TOPIC:-fleet-alerts}"
readonly NTFY_URL="${NTFY_URL:-https://ntfy.sh}"

readonly PROM_USER="prometheus"
readonly PROM_DIR="/etc/prometheus"
readonly PROM_DATA="/var/lib/prometheus"
readonly PROM_BINARY="/usr/local/bin/prometheus"
readonly PROMTOOL_BINARY="/usr/local/bin/promtool"
readonly AM_BINARY="/usr/local/bin/alertmanager"
readonly AM_DIR="/etc/alertmanager"
readonly AM_DATA="/var/lib/alertmanager"

readonly DOWNLOAD_BASE_PROM="https://github.com/prometheus/prometheus/releases/download"
readonly DOWNLOAD_BASE_AM="https://github.com/prometheus/alertmanager/releases/download"

# --- Logging ---
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
err()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

# --- Preflight checks ---
[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."

command -v curl  >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || die "Neither curl nor wget found."
command -v tar   >/dev/null 2>&1 || die "tar is required."
command -v systemctl >/dev/null 2>&1 || die "systemctl is required."

# --- Detect architecture ---
detect_arch() {
    local arch
    arch="$(uname -m)"
    case "${arch}" in
        x86_64|amd64)   echo "amd64" ;;
        aarch64|arm64)  echo "arm64" ;;
        *)              die "Unsupported architecture for Prometheus server: ${arch}" ;;
    esac
}

ARCH="$(detect_arch)"
log "Detected architecture: ${ARCH}"

# --- Download helper ---
download() {
    local url="$1" dest="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "${dest}" "${url}" || die "Download failed: ${url}"
    else
        wget -q -O "${dest}" "${url}" || die "Download failed: ${url}"
    fi
}

# --- Create service user ---
if ! id "${PROM_USER}" &>/dev/null; then
    log "Creating system user: ${PROM_USER}"
    useradd --system --no-create-home --shell /usr/sbin/nologin "${PROM_USER}"
else
    log "User ${PROM_USER} already exists."
fi

# --- Create directories ---
for dir in "${PROM_DIR}" "${PROM_DIR}/rules" "${PROM_DATA}" "${AM_DIR}" "${AM_DATA}"; do
    mkdir -p "${dir}"
    chown "${PROM_USER}:${PROM_USER}" "${dir}"
done

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

# =============================================================================
# PROMETHEUS SERVER
# =============================================================================
install_prometheus() {
    local current_version=""

    if [[ -x "${PROM_BINARY}" ]]; then
        current_version="$("${PROM_BINARY}" --version 2>&1 | grep -oP 'version \K[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")"
        if [[ "${current_version}" == "${PROM_VERSION}" ]]; then
            log "Prometheus ${PROM_VERSION} already installed. Skipping binary install."
            return 0
        fi
        log "Prometheus ${current_version} found, upgrading to ${PROM_VERSION}."
    fi

    local tarball="prometheus-${PROM_VERSION}.linux-${ARCH}.tar.gz"
    local url="${DOWNLOAD_BASE_PROM}/v${PROM_VERSION}/${tarball}"

    log "Downloading Prometheus ${PROM_VERSION}..."
    download "${url}" "${TMPDIR}/${tarball}"

    log "Extracting Prometheus..."
    tar -xzf "${TMPDIR}/${tarball}" -C "${TMPDIR}"

    local extract_dir="${TMPDIR}/prometheus-${PROM_VERSION}.linux-${ARCH}"

    # Stop if running
    systemctl is-active --quiet prometheus 2>/dev/null && systemctl stop prometheus

    # Install binaries
    install -m 0755 "${extract_dir}/prometheus" "${PROM_BINARY}"
    install -m 0755 "${extract_dir}/promtool"   "${PROMTOOL_BINARY}"

    # Install console templates (if they exist in the release)
    if [[ -d "${extract_dir}/consoles" ]]; then
        cp -r "${extract_dir}/consoles" "${PROM_DIR}/"
    fi
    if [[ -d "${extract_dir}/console_libraries" ]]; then
        cp -r "${extract_dir}/console_libraries" "${PROM_DIR}/"
    fi

    chown -R "${PROM_USER}:${PROM_USER}" "${PROM_DIR}"
    log "Prometheus ${PROM_VERSION} binaries installed."
}

# =============================================================================
# ALERTMANAGER
# =============================================================================
install_alertmanager() {
    local current_version=""

    if [[ -x "${AM_BINARY}" ]]; then
        current_version="$("${AM_BINARY}" --version 2>&1 | grep -oP 'version \K[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")"
        if [[ "${current_version}" == "${AM_VERSION}" ]]; then
            log "Alertmanager ${AM_VERSION} already installed. Skipping binary install."
            return 0
        fi
        log "Alertmanager ${current_version} found, upgrading to ${AM_VERSION}."
    fi

    local tarball="alertmanager-${AM_VERSION}.linux-${ARCH}.tar.gz"
    local url="${DOWNLOAD_BASE_AM}/v${AM_VERSION}/${tarball}"

    log "Downloading Alertmanager ${AM_VERSION}..."
    download "${url}" "${TMPDIR}/${tarball}"

    log "Extracting Alertmanager..."
    tar -xzf "${TMPDIR}/${tarball}" -C "${TMPDIR}"

    local extract_dir="${TMPDIR}/alertmanager-${AM_VERSION}.linux-${ARCH}"

    systemctl is-active --quiet alertmanager 2>/dev/null && systemctl stop alertmanager

    install -m 0755 "${extract_dir}/alertmanager" "${AM_BINARY}"
    install -m 0755 "${extract_dir}/amtool" "/usr/local/bin/amtool"

    log "Alertmanager ${AM_VERSION} binaries installed."
}

# --- Run installations ---
install_prometheus
install_alertmanager

# =============================================================================
# PROMETHEUS CONFIGURATION
# =============================================================================
log "Writing Prometheus configuration..."
cat > "${PROM_DIR}/prometheus.yml" <<'PROMCFG'
# =============================================================================
# Prometheus Configuration - Personal Fleet
# Generated by install-prometheus.sh
# =============================================================================
global:
  scrape_interval: 30s
  evaluation_interval: 30s
  scrape_timeout: 10s

  external_labels:
    fleet: "personal"
    environment: "homelab"

# --- Alert Rules ---
rule_files:
  - "rules/*.yml"

# --- Alertmanager ---
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - "localhost:9093"

# --- Scrape Targets ---
scrape_configs:

  # Prometheus self-monitoring
  - job_name: "prometheus"
    scrape_interval: 15s
    static_configs:
      - targets: ["localhost:9090"]
        labels:
          instance_name: "aio-01"
          role: "controller"

  # Alertmanager self-monitoring
  - job_name: "alertmanager"
    scrape_interval: 30s
    static_configs:
      - targets: ["localhost:9093"]
        labels:
          instance_name: "aio-01"

  # --- Fleet Node Exporters ---
  - job_name: "node"
    scrape_interval: 30s
    scrape_timeout: 10s
    static_configs:

      # Controller
      - targets: ["aio-01:9100"]
        labels:
          instance_name: "aio-01"
          role: "controller"
          cpus: "2"
          memory_gb: "7"

      # Workers
      - targets: ["server-01:9100"]
        labels:
          instance_name: "server-01"
          role: "worker"
          cpus: "8"
          memory_gb: "15"

      - targets: ["server-02:9100"]
        labels:
          instance_name: "server-02"
          role: "worker"
          cpus: "8"
          memory_gb: "31"

      - targets: ["server-03:9100"]
        labels:
          instance_name: "server-03"
          role: "worker"
          cpus: "8"
          memory_gb: "31"

      # Sentinel (ARM64 Raspberry Pi)
      - targets: ["pi-02:9100"]
        labels:
          instance_name: "pi-02"
          role: "sentinel"
          arch: "arm64"
          cpus: "4"
          memory_gb: "1"
PROMCFG

chown "${PROM_USER}:${PROM_USER}" "${PROM_DIR}/prometheus.yml"

# =============================================================================
# ALERT RULES
# =============================================================================
log "Writing alert rules..."
cat > "${PROM_DIR}/rules/alerts.yml" <<'ALERTRULES'
# =============================================================================
# Fleet Alert Rules
# =============================================================================
groups:

  # =========================================================================
  # Host Availability
  # =========================================================================
  - name: host_availability
    rules:

      - alert: HostDown
        expr: up{job="node"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Host {{ $labels.instance_name }} is DOWN"
          description: >-
            Node exporter on {{ $labels.instance_name }}
            ({{ $labels.instance }}) has been unreachable for over 2 minutes.
            Role: {{ $labels.role }}

      - alert: HostRebootDetected
        expr: node_boot_time_seconds != node_boot_time_seconds offset 10m
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Host {{ $labels.instance_name }} rebooted"
          description: >-
            {{ $labels.instance_name }} appears to have rebooted.
            Previous boot time differs from 10 minutes ago.

  # =========================================================================
  # CPU Alerts
  # =========================================================================
  - name: cpu_alerts
    rules:

      - alert: HighCpuUsage
        expr: >-
          100 - (avg by (instance, instance_name, role)
            (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}%"
          description: >-
            CPU usage on {{ $labels.instance_name }} ({{ $labels.role }})
            has been above 85% for 10 minutes.

      - alert: CriticalCpuUsage
        expr: >-
          100 - (avg by (instance, instance_name, role)
            (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical CPU on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}%"
          description: >-
            CPU usage on {{ $labels.instance_name }} ({{ $labels.role }})
            has been above 95% for 5 minutes. Immediate attention needed.

      # Special: aio-01 controller must stay below 60% for NFS latency
      - alert: ControllerCpuTooHigh
        expr: >-
          100 - (avg by (instance, instance_name)
            (rate(node_cpu_seconds_total{mode="idle", role="controller"}[5m])) * 100) > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Controller CPU above 60%: {{ $value | printf \"%.1f\" }}%"
          description: >-
            aio-01 CPU exceeds 60% threshold. NFS latency may be impacted.
            Consider offloading work to worker nodes.

  # =========================================================================
  # Memory Alerts
  # =========================================================================
  - name: memory_alerts
    rules:

      - alert: HighMemoryUsage
        expr: >-
          (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
          * 100 > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}%"
          description: >-
            Memory usage on {{ $labels.instance_name }} ({{ $labels.role }})
            has exceeded 85% for 10 minutes.
            Available: {{ with printf "node_memory_MemAvailable_bytes{instance='%s'}" $labels.instance | query }}{{ . | first | value | humanize1024 }}{{ end }}

      - alert: CriticalMemoryUsage
        expr: >-
          (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
          * 100 > 95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical memory on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}%"
          description: >-
            Memory usage on {{ $labels.instance_name }} is critical.
            OOM killer may activate.

      # Special: pi-02 sentinel has only 1GB - tighter threshold
      - alert: SentinelMemoryHigh
        expr: >-
          (1 - node_memory_MemAvailable_bytes{role="sentinel"}
               / node_memory_MemTotal_bytes{role="sentinel"})
          * 100 > 70
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Sentinel pi-02 memory above 70%: {{ $value | printf \"%.1f\" }}%"
          description: >-
            pi-02 has only 1GB RAM. Available memory is critically low.
            Max recommended RSS: 500MB total.

  # =========================================================================
  # Disk Alerts
  # =========================================================================
  - name: disk_alerts
    rules:

      - alert: DiskSpaceLow
        expr: >-
          (1 - node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs"}
               / node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs"})
          * 100 > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Disk {{ $labels.mountpoint }} on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}% full"
          description: >-
            Filesystem {{ $labels.mountpoint }} on {{ $labels.instance_name }}
            is {{ $value | printf "%.1f" }}% full.

      - alert: DiskSpaceCritical
        expr: >-
          (1 - node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs"}
               / node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs"})
          * 100 > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL: Disk {{ $labels.mountpoint }} on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}% full"
          description: >-
            Filesystem {{ $labels.mountpoint }} on {{ $labels.instance_name }}
            is nearly full. Immediate action required.

      - alert: DiskWillFillIn24h
        expr: >-
          predict_linear(
            node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs"}[6h], 24*3600
          ) < 0
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Disk {{ $labels.mountpoint }} on {{ $labels.instance_name }} will fill in < 24h"
          description: >-
            Based on current growth rate, {{ $labels.mountpoint }} on
            {{ $labels.instance_name }} will run out of space within 24 hours.

      - alert: DiskInodesLow
        expr: >-
          (1 - node_filesystem_files_free{fstype=~"ext4|xfs|btrfs"}
               / node_filesystem_files{fstype=~"ext4|xfs|btrfs"})
          * 100 > 90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Inodes on {{ $labels.mountpoint }} ({{ $labels.instance_name }}): {{ $value | printf \"%.1f\" }}% used"
          description: "Inode exhaustion approaching on {{ $labels.instance_name }}."

  # =========================================================================
  # Network Alerts
  # =========================================================================
  - name: network_alerts
    rules:

      - alert: NetworkInterfaceDown
        expr: node_network_up{device!~"lo|veth.*|br-.*|docker.*|virbr.*"} == 0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Network interface {{ $labels.device }} down on {{ $labels.instance_name }}"
          description: >-
            Interface {{ $labels.device }} on {{ $labels.instance_name }}
            has been down for over 2 minutes.

      - alert: HighNetworkErrors
        expr: >-
          rate(node_network_receive_errs_total[5m])
          + rate(node_network_transmit_errs_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Network errors on {{ $labels.instance_name }} interface {{ $labels.device }}"
          description: "More than 10 network errors/sec detected."

  # =========================================================================
  # System Health
  # =========================================================================
  - name: system_health
    rules:

      - alert: SystemdServiceFailed
        expr: node_systemd_unit_state{state="failed"} == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Systemd unit {{ $labels.name }} failed on {{ $labels.instance_name }}"
          description: >-
            Service {{ $labels.name }} is in failed state on
            {{ $labels.instance_name }}.

      - alert: HighLoadAverage
        expr: >-
          node_load15 / count without (cpu, mode)
            (node_cpu_seconds_total{mode="idle"}) > 2
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High load on {{ $labels.instance_name }}: 15m avg = {{ $value | printf \"%.2f\" }}"
          description: >-
            15-minute load average is more than 2x the CPU count
            on {{ $labels.instance_name }}.

      - alert: ClockSkew
        expr: >-
          abs(node_timex_offset_seconds) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Clock skew on {{ $labels.instance_name }}: {{ $value | printf \"%.3f\" }}s"
          description: >-
            System clock on {{ $labels.instance_name }} is drifting.
            NTP may not be working correctly.

      - alert: HighSwapUsage
        expr: >-
          (1 - node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes) * 100 > 50
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High swap usage on {{ $labels.instance_name }}: {{ $value | printf \"%.1f\" }}%"
          description: >-
            Swap usage above 50% indicates memory pressure on
            {{ $labels.instance_name }}.

  # =========================================================================
  # Prometheus Self-Monitoring
  # =========================================================================
  - name: prometheus_self
    rules:

      - alert: PrometheusTargetDown
        expr: up == 0
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Scrape target {{ $labels.job }}/{{ $labels.instance }} is DOWN"
          description: "Prometheus cannot reach {{ $labels.instance }} for job {{ $labels.job }}."

      - alert: PrometheusTsdbStorageHigh
        expr: >-
          prometheus_tsdb_storage_blocks_bytes / (3 * 1024 * 1024 * 1024) * 100 > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Prometheus TSDB storage at {{ $value | printf \"%.0f\" }}% of 3GB limit"
          description: >-
            TSDB storage is approaching the configured 3GB limit.
            Consider reducing retention or adding disk space.

      - alert: PrometheusConfigReloadFailed
        expr: prometheus_config_last_reload_successful == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Prometheus config reload failed"
          description: "The last Prometheus configuration reload attempt failed."
ALERTRULES

chown "${PROM_USER}:${PROM_USER}" "${PROM_DIR}/rules/alerts.yml"

# =============================================================================
# ALERTMANAGER CONFIGURATION
# =============================================================================
log "Writing Alertmanager configuration..."
cat > "${AM_DIR}/alertmanager.yml" <<AMCFG
# =============================================================================
# Alertmanager Configuration - Personal Fleet
# Delivers alerts via ntfy (push notifications)
# =============================================================================
global:
  resolve_timeout: 5m

# --- Inhibition Rules ---
# Suppress warning alerts when critical alerts are already firing for the same host
inhibit_rules:
  - source_matchers:
      - severity = critical
    target_matchers:
      - severity = warning
    equal: ['instance', 'instance_name']

# --- Routing ---
route:
  receiver: ntfy-default
  group_by: ['alertname', 'instance_name', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical alerts: shorter repeat, higher priority
    - matchers:
        - severity = critical
      receiver: ntfy-critical
      group_wait: 10s
      repeat_interval: 1h

# --- Receivers ---
receivers:
  - name: ntfy-default
    webhook_configs:
      - url: "${NTFY_URL}/${NTFY_TOPIC}"
        send_resolved: true
        http_config:
          follow_redirects: true

  - name: ntfy-critical
    webhook_configs:
      - url: "${NTFY_URL}/${NTFY_TOPIC}-critical"
        send_resolved: true
        http_config:
          follow_redirects: true
AMCFG

chown "${PROM_USER}:${PROM_USER}" "${AM_DIR}/alertmanager.yml"

# =============================================================================
# SYSTEMD SERVICES
# =============================================================================

# --- Prometheus service ---
log "Creating Prometheus systemd service..."
cat > /etc/systemd/system/prometheus.service <<PROMSVC
[Unit]
Description=Prometheus Monitoring Server
Documentation=https://prometheus.io/docs/introduction/overview/
Wants=network-online.target
After=network-online.target

[Service]
User=${PROM_USER}
Group=${PROM_USER}
Type=simple
Restart=on-failure
RestartSec=5

ExecReload=/bin/kill -HUP \$MAINPID
ExecStart=${PROM_BINARY} \\
    --config.file=${PROM_DIR}/prometheus.yml \\
    --storage.tsdb.path=${PROM_DATA} \\
    --storage.tsdb.retention.time=${RETENTION_TIME} \\
    --storage.tsdb.retention.size=${RETENTION_SIZE} \\
    --web.listen-address=:9090 \\
    --web.enable-lifecycle \\
    --web.enable-admin-api

# Memory limits suitable for 7GB machine
# Reserve ~3GB for OS, NFS, and other services
MemoryMax=3G
MemoryHigh=2G

# Hardening
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=read-only
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
PROMSVC

# --- Alertmanager service ---
log "Creating Alertmanager systemd service..."
cat > /etc/systemd/system/alertmanager.service <<AMSVC
[Unit]
Description=Prometheus Alertmanager
Documentation=https://prometheus.io/docs/alerting/alertmanager/
Wants=network-online.target
After=network-online.target

[Service]
User=${PROM_USER}
Group=${PROM_USER}
Type=simple
Restart=on-failure
RestartSec=5

ExecReload=/bin/kill -HUP \$MAINPID
ExecStart=${AM_BINARY} \\
    --config.file=${AM_DIR}/alertmanager.yml \\
    --storage.path=${AM_DATA} \\
    --web.listen-address=:9093

# Minimal memory footprint
MemoryMax=256M

# Hardening
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=read-only
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
AMSVC

# --- Validate configuration ---
log "Validating Prometheus configuration..."
if "${PROMTOOL_BINARY}" check config "${PROM_DIR}/prometheus.yml" 2>&1; then
    log "Configuration validation passed."
else
    warn "Configuration validation reported issues (may be non-fatal). Continuing."
fi

# --- Enable and start services ---
systemctl daemon-reload

systemctl enable --now alertmanager
log "Alertmanager service enabled and started."

systemctl enable --now prometheus
log "Prometheus service enabled and started."

# --- Verify ---
sleep 2

SERVICES_OK=true
for svc in prometheus alertmanager; do
    if systemctl is-active --quiet "${svc}"; then
        log "${svc} is running."
    else
        err "${svc} failed to start. Check: journalctl -u ${svc} -n 20"
        SERVICES_OK=false
    fi
done

# --- Firewall ---
if [[ "${SKIP_FIREWALL:-0}" != "1" ]]; then
    PORTS=(9090 9093)
    if command -v firewall-cmd >/dev/null 2>&1; then
        for port in "${PORTS[@]}"; do
            firewall-cmd --permanent --add-port="${port}/tcp" 2>/dev/null || true
        done
        firewall-cmd --reload 2>/dev/null || true
        log "Firewalld configured for ports: ${PORTS[*]}"
    elif command -v ufw >/dev/null 2>&1; then
        for port in "${PORTS[@]}"; do
            ufw allow "${port}/tcp" 2>/dev/null || true
        done
        log "UFW configured for ports: ${PORTS[*]}"
    else
        warn "No firewall manager detected. Ensure ports ${PORTS[*]} are open."
    fi
fi

if $SERVICES_OK; then
    log "=========================================="
    log "  Installation Complete"
    log "=========================================="
    log "  Prometheus:   http://aio-01:9090"
    log "  Alertmanager: http://aio-01:9093"
    log "  Retention:    ${RETENTION_TIME} / max ${RETENTION_SIZE}"
    log "  Alerts:       ntfy topic '${NTFY_TOPIC}'"
    log "=========================================="
else
    die "One or more services failed to start."
fi
