#!/usr/bin/env bash
# =============================================================================
# install-grafana.sh - Install Grafana on aio-01 (co-located with Prometheus)
#
# Uses official Grafana RPM/APT repository for proper package management.
# Idempotent: safe to run multiple times.
#
# Usage:
#   sudo ./install-grafana.sh
#
# Environment variables:
#   GRAFANA_PORT       - Listen port (default: 3000)
#   SKIP_FIREWALL      - Set to 1 to skip firewall configuration
#   SKIP_DATASOURCE    - Set to 1 to skip auto-configuring Prometheus datasource
# =============================================================================
set -euo pipefail

readonly PORT="${GRAFANA_PORT:-3000}"

# --- Logging ---
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
err()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."
command -v systemctl >/dev/null 2>&1 || die "systemctl is required."

# --- Detect package manager and install ---
install_grafana() {
    if command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then
        install_grafana_rpm
    elif command -v apt-get >/dev/null 2>&1; then
        install_grafana_deb
    else
        die "Unsupported package manager. Install Grafana manually."
    fi
}

install_grafana_rpm() {
    local repo_file="/etc/yum.repos.d/grafana.repo"

    if [[ ! -f "${repo_file}" ]]; then
        log "Adding Grafana RPM repository..."
        cat > "${repo_file}" <<'REPO'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
REPO
    else
        log "Grafana repository already configured."
    fi

    log "Installing Grafana via dnf/yum..."
    if command -v dnf >/dev/null 2>&1; then
        dnf install -y grafana
    else
        yum install -y grafana
    fi
}

install_grafana_deb() {
    log "Adding Grafana APT repository..."

    apt-get install -y apt-transport-https software-properties-common wget 2>/dev/null || true

    if [[ ! -f /etc/apt/keyrings/grafana.gpg ]]; then
        mkdir -p /etc/apt/keyrings/
        wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor -o /etc/apt/keyrings/grafana.gpg
    fi

    if [[ ! -f /etc/apt/sources.list.d/grafana.list ]]; then
        echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
            > /etc/apt/sources.list.d/grafana.list
    fi

    apt-get update -qq
    apt-get install -y grafana
}

# Check if already installed
if command -v grafana-server >/dev/null 2>&1 || command -v grafana >/dev/null 2>&1; then
    CURRENT="$(grafana-server -v 2>&1 | grep -oP '[0-9]+\.[0-9]+\.[0-9]+' || echo "installed")"
    log "Grafana ${CURRENT} is already installed. Ensuring it is configured and running."
else
    install_grafana
fi

# --- Configure port if non-default ---
GRAFANA_INI="/etc/grafana/grafana.ini"
if [[ "${PORT}" != "3000" ]] && [[ -f "${GRAFANA_INI}" ]]; then
    log "Setting Grafana to listen on port ${PORT}..."
    sed -i "s/^;*http_port = .*/http_port = ${PORT}/" "${GRAFANA_INI}"
fi

# --- Memory limit for 7GB controller ---
GRAFANA_SERVICE_DIR="/etc/systemd/system/grafana-server.service.d"
mkdir -p "${GRAFANA_SERVICE_DIR}"
cat > "${GRAFANA_SERVICE_DIR}/memory-limit.conf" <<OVERRIDE
[Service]
MemoryMax=512M
MemoryHigh=384M
OVERRIDE
log "Grafana memory limit set to 512M max."

# --- Auto-configure Prometheus datasource ---
if [[ "${SKIP_DATASOURCE:-0}" != "1" ]]; then
    PROVISIONING_DIR="/etc/grafana/provisioning/datasources"
    mkdir -p "${PROVISIONING_DIR}"

    cat > "${PROVISIONING_DIR}/prometheus.yml" <<'DSCFG'
# Auto-provisioned Prometheus datasource
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: "30s"
      httpMethod: POST
DSCFG

    chown -R grafana:grafana "${PROVISIONING_DIR}"
    log "Prometheus datasource auto-provisioned."
fi

# --- Auto-provision Node Exporter dashboard ---
DASHBOARD_PROV_DIR="/etc/grafana/provisioning/dashboards"
DASHBOARD_DIR="/var/lib/grafana/dashboards"
mkdir -p "${DASHBOARD_PROV_DIR}" "${DASHBOARD_DIR}"

cat > "${DASHBOARD_PROV_DIR}/default.yml" <<'DBPROV'
apiVersion: 1

providers:
  - name: default
    orgId: 1
    folder: Fleet
    type: file
    disableDeletion: false
    updateIntervalSeconds: 60
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
DBPROV

# Download the canonical Node Exporter Full dashboard (ID 1860)
if [[ ! -f "${DASHBOARD_DIR}/node-exporter-full.json" ]]; then
    log "Downloading Node Exporter Full dashboard (Grafana ID 1860)..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "${DASHBOARD_DIR}/node-exporter-full.json" \
            "https://grafana.com/api/dashboards/1860/revisions/37/download" 2>/dev/null || \
            warn "Failed to download dashboard. You can import it manually from Grafana (ID: 1860)."
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "${DASHBOARD_DIR}/node-exporter-full.json" \
            "https://grafana.com/api/dashboards/1860/revisions/37/download" 2>/dev/null || \
            warn "Failed to download dashboard. Import manually from Grafana (ID: 1860)."
    fi

    # Fix the datasource reference to use our provisioned name
    if [[ -f "${DASHBOARD_DIR}/node-exporter-full.json" ]]; then
        sed -i 's/"datasource":.*"uid":.*"DS_PROMETHEUS"/"datasource": {"type": "prometheus", "uid": "prometheus"}/g' \
            "${DASHBOARD_DIR}/node-exporter-full.json" 2>/dev/null || true
        log "Dashboard downloaded and configured."
    fi
fi

chown -R grafana:grafana "${DASHBOARD_DIR}" "${DASHBOARD_PROV_DIR}"

# --- Enable and start ---
systemctl daemon-reload
systemctl enable --now grafana-server
log "Grafana service enabled and started."

# --- Verify ---
sleep 2
if systemctl is-active --quiet grafana-server; then
    log "Grafana is running on port ${PORT}."
else
    err "Grafana failed to start. Check: journalctl -u grafana-server -n 20"
    exit 1
fi

# --- Firewall ---
if [[ "${SKIP_FIREWALL:-0}" != "1" ]]; then
    if command -v firewall-cmd >/dev/null 2>&1; then
        firewall-cmd --permanent --add-port="${PORT}/tcp" 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        log "Firewalld configured for port ${PORT}/tcp."
    elif command -v ufw >/dev/null 2>&1; then
        ufw allow "${PORT}/tcp" 2>/dev/null || true
        log "UFW configured for port ${PORT}/tcp."
    fi
fi

log "=========================================="
log "  Grafana Installation Complete"
log "=========================================="
log "  URL:      http://aio-01:${PORT}"
log "  Login:    admin / admin (change on first login)"
log "  Dashboard: Node Exporter Full (auto-provisioned)"
log "  Datasource: Prometheus (auto-provisioned)"
log "=========================================="
