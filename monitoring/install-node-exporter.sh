#!/usr/bin/env bash
# =============================================================================
# install-node-exporter.sh - Install Prometheus node_exporter
#
# Works on x86_64 (amd64) and ARM64 (aarch64) architectures.
# Idempotent: safe to run multiple times.
#
# Usage:
#   sudo ./install-node-exporter.sh
#
# Environment variables:
#   NODE_EXPORTER_VERSION  - Version to install (default: 1.11.1)
#   NODE_EXPORTER_PORT     - Listen port (default: 9100)
#   SKIP_FIREWALL          - Set to 1 to skip firewall configuration
# =============================================================================
set -euo pipefail

# --- Configuration ---
readonly VERSION="${NODE_EXPORTER_VERSION:-1.11.1}"
readonly PORT="${NODE_EXPORTER_PORT:-9100}"
readonly SERVICE_USER="node_exporter"
readonly INSTALL_DIR="/usr/local/bin"
readonly BINARY="${INSTALL_DIR}/node_exporter"
readonly SERVICE_FILE="/etc/systemd/system/node_exporter.service"
readonly DOWNLOAD_BASE="https://github.com/prometheus/node_exporter/releases/download"

# --- Logging ---
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
err()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

# --- Preflight checks ---
[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."

command -v curl  >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || die "Neither curl nor wget found. Install one and retry."
command -v tar   >/dev/null 2>&1 || die "tar is required but not found."
command -v systemctl >/dev/null 2>&1 || die "systemctl is required (systemd not found)."

# --- Detect architecture ---
detect_arch() {
    local arch
    arch="$(uname -m)"
    case "${arch}" in
        x86_64|amd64)   echo "amd64" ;;
        aarch64|arm64)  echo "arm64" ;;
        armv7l)         echo "armv7" ;;
        armv6l)         echo "armv6" ;;
        *)              die "Unsupported architecture: ${arch}" ;;
    esac
}

ARCH="$(detect_arch)"
log "Detected architecture: ${ARCH}"

# --- Check if already installed at correct version ---
if [[ -x "${BINARY}" ]]; then
    CURRENT_VERSION="$("${BINARY}" --version 2>&1 | grep -oP 'version \K[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")"
    if [[ "${CURRENT_VERSION}" == "${VERSION}" ]]; then
        log "node_exporter ${VERSION} already installed at ${BINARY}. Ensuring service is running."
        systemctl enable --now node_exporter 2>/dev/null || true
        systemctl is-active --quiet node_exporter && log "node_exporter is running on port ${PORT}."
        exit 0
    else
        log "node_exporter ${CURRENT_VERSION} found, upgrading to ${VERSION}."
    fi
fi

# --- Create service user ---
if ! id "${SERVICE_USER}" &>/dev/null; then
    log "Creating system user: ${SERVICE_USER}"
    useradd --system --no-create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
else
    log "User ${SERVICE_USER} already exists."
fi

# --- Download and install ---
TARBALL="node_exporter-${VERSION}.linux-${ARCH}.tar.gz"
DOWNLOAD_URL="${DOWNLOAD_BASE}/v${VERSION}/${TARBALL}"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

log "Downloading node_exporter ${VERSION} for linux-${ARCH}..."
if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "${TMPDIR}/${TARBALL}" "${DOWNLOAD_URL}" || die "Download failed: ${DOWNLOAD_URL}"
else
    wget -q -O "${TMPDIR}/${TARBALL}" "${DOWNLOAD_URL}" || die "Download failed: ${DOWNLOAD_URL}"
fi

log "Extracting..."
tar -xzf "${TMPDIR}/${TARBALL}" -C "${TMPDIR}"

# Stop service if running (for upgrade)
if systemctl is-active --quiet node_exporter 2>/dev/null; then
    log "Stopping existing node_exporter service for upgrade..."
    systemctl stop node_exporter
fi

# Install binary
EXTRACT_DIR="${TMPDIR}/node_exporter-${VERSION}.linux-${ARCH}"
[[ -f "${EXTRACT_DIR}/node_exporter" ]] || die "Binary not found in archive: ${EXTRACT_DIR}/node_exporter"
install -m 0755 "${EXTRACT_DIR}/node_exporter" "${BINARY}"
chown root:root "${BINARY}"
log "Installed ${BINARY}"

# --- Create systemd service ---
log "Creating systemd service..."
cat > "${SERVICE_FILE}" <<UNIT
[Unit]
Description=Prometheus Node Exporter
Documentation=https://github.com/prometheus/node_exporter
Wants=network-online.target
After=network-online.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_USER}
Type=simple
Restart=on-failure
RestartSec=5
ExecStart=${BINARY} \\
    --web.listen-address=:${PORT} \\
    --collector.systemd \\
    --collector.processes

# Hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes
ProtectControlGroups=yes
ProtectKernelModules=yes
RestrictSUIDSGID=yes

[Install]
WantedBy=multi-user.target
UNIT

# --- Enable and start ---
systemctl daemon-reload
systemctl enable --now node_exporter
log "node_exporter service enabled and started."

# --- Verify ---
sleep 1
if systemctl is-active --quiet node_exporter; then
    log "SUCCESS: node_exporter ${VERSION} is running on port ${PORT}."
else
    err "node_exporter failed to start. Check: journalctl -u node_exporter -n 20"
    exit 1
fi

# --- Firewall (optional) ---
if [[ "${SKIP_FIREWALL:-0}" != "1" ]]; then
    if command -v firewall-cmd >/dev/null 2>&1; then
        log "Configuring firewalld for port ${PORT}/tcp..."
        firewall-cmd --permanent --add-port="${PORT}/tcp" 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
    elif command -v ufw >/dev/null 2>&1; then
        log "Configuring ufw for port ${PORT}/tcp..."
        ufw allow "${PORT}/tcp" 2>/dev/null || true
    else
        warn "No firewall manager detected. Ensure port ${PORT}/tcp is open."
    fi
fi

log "Installation complete. Verify with: curl -s http://localhost:${PORT}/metrics | head"
