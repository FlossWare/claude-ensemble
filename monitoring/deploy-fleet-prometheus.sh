#!/usr/bin/env bash
# =============================================================================
# deploy-fleet-prometheus.sh - Orchestrate Prometheus stack deployment
#
# Deploys node_exporter to all 5 fleet machines, then installs Prometheus,
# Alertmanager, and Grafana on aio-01 (controller).
#
# Prerequisites:
#   - SSH key-based auth to all machines (as current user with sudo NOPASSWD)
#   - Machines resolvable by hostname (via /etc/hosts or DNS)
#   - Internet access on all machines (to download binaries)
#
# Usage:
#   ./deploy-fleet-prometheus.sh [OPTIONS]
#
# Options:
#   --dry-run           Show what would be done without executing
#   --node-exporter     Only deploy node_exporter (skip Prometheus/Grafana)
#   --prometheus        Only deploy Prometheus server (skip node_exporter/Grafana)
#   --grafana           Only deploy Grafana (skip node_exporter/Prometheus)
#   --skip-grafana      Deploy everything except Grafana
#   --host HOST         Deploy to a single host only
#   --parallel          Deploy node_exporter to all hosts in parallel
#   --ntfy-topic TOPIC  Set ntfy topic for alerts (default: fleet-alerts)
#   --ntfy-url URL      Set ntfy server URL (default: https://ntfy.sh)
#   --help              Show this help
# =============================================================================
set -euo pipefail

# --- Fleet definition ---
declare -A FLEET_ARCH
declare -a ALL_HOSTS=("aio-01" "server-01" "server-02" "server-03" "pi-02")
FLEET_ARCH["aio-01"]="amd64"
FLEET_ARCH["server-01"]="amd64"
FLEET_ARCH["server-02"]="amd64"
FLEET_ARCH["server-03"]="amd64"
FLEET_ARCH["pi-02"]="arm64"

readonly CONTROLLER="aio-01"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults ---
DRY_RUN=false
DEPLOY_NODE_EXPORTER=true
DEPLOY_PROMETHEUS=true
DEPLOY_GRAFANA=true
SINGLE_HOST=""
PARALLEL=false
NTFY_TOPIC="fleet-alerts"
NTFY_URL="https://ntfy.sh"

# --- Logging ---
log()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
warn()    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
err()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [OK]    $*"; }
die()     { err "$*"; exit 1; }

# --- Parse arguments ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)         DRY_RUN=true ;;
            --node-exporter)   DEPLOY_PROMETHEUS=false; DEPLOY_GRAFANA=false ;;
            --prometheus)      DEPLOY_NODE_EXPORTER=false; DEPLOY_GRAFANA=false ;;
            --grafana)         DEPLOY_NODE_EXPORTER=false; DEPLOY_PROMETHEUS=false ;;
            --skip-grafana)    DEPLOY_GRAFANA=false ;;
            --host)            shift; SINGLE_HOST="$1" ;;
            --parallel)        PARALLEL=true ;;
            --ntfy-topic)      shift; NTFY_TOPIC="$1" ;;
            --ntfy-url)        shift; NTFY_URL="$1" ;;
            --help|-h)         usage; exit 0 ;;
            *)                 die "Unknown option: $1. Use --help for usage." ;;
        esac
        shift
    done
}

usage() {
    head -n 25 "${BASH_SOURCE[0]}" | grep '^#' | sed 's/^# \?//'
}

# --- SSH helpers ---
ssh_check() {
    local host="$1"
    ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=yes \
        "${host}" 'echo ok' >/dev/null 2>&1
}

ssh_exec() {
    local host="$1"
    shift
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "${host}" "$@"
}

scp_file() {
    local src="$1" host="$2" dest="$3"
    scp -o BatchMode=yes -o StrictHostKeyChecking=yes "${src}" "${host}:${dest}"
}

# --- Health check all hosts ---
check_fleet_health() {
    log "Checking fleet connectivity..."
    local failed=()

    for host in "${ALL_HOSTS[@]}"; do
        if [[ -n "${SINGLE_HOST}" && "${host}" != "${SINGLE_HOST}" ]]; then
            continue
        fi

        if ssh_check "${host}"; then
            success "${host}: reachable"
        else
            err "${host}: UNREACHABLE"
            failed+=("${host}")
        fi
    done

    if [[ ${#failed[@]} -gt 0 ]]; then
        die "Cannot reach: ${failed[*]}. Fix SSH connectivity first."
    fi

    log "All target hosts are reachable."
}

# --- Deploy node_exporter to a single host ---
deploy_node_exporter_to() {
    local host="$1"

    log "Deploying node_exporter to ${host}..."

    if $DRY_RUN; then
        log "[DRY-RUN] Would deploy node_exporter to ${host}"
        return 0
    fi

    # Copy the install script
    scp_file "${SCRIPT_DIR}/install-node-exporter.sh" "${host}" "/tmp/install-node-exporter.sh"

    # Execute remotely with sudo
    ssh_exec "${host}" "sudo bash /tmp/install-node-exporter.sh && rm -f /tmp/install-node-exporter.sh"

    if [[ $? -eq 0 ]]; then
        success "node_exporter deployed to ${host}"
    else
        err "node_exporter deployment FAILED on ${host}"
        return 1
    fi
}

# --- Deploy node_exporter to all hosts ---
deploy_node_exporter_all() {
    log "=========================================="
    log "  Phase 1: Deploy node_exporter"
    log "=========================================="

    local hosts=("${ALL_HOSTS[@]}")
    if [[ -n "${SINGLE_HOST}" ]]; then
        hosts=("${SINGLE_HOST}")
    fi

    if $PARALLEL; then
        log "Deploying in parallel to ${#hosts[@]} hosts..."
        local pids=()
        local results=()

        for host in "${hosts[@]}"; do
            deploy_node_exporter_to "${host}" &
            pids+=($!)
            results+=("${host}")
        done

        local any_failed=false
        for i in "${!pids[@]}"; do
            if wait "${pids[$i]}"; then
                success "${results[$i]}: parallel deploy completed"
            else
                err "${results[$i]}: parallel deploy FAILED"
                any_failed=true
            fi
        done

        if $any_failed; then
            die "One or more parallel deployments failed."
        fi
    else
        for host in "${hosts[@]}"; do
            deploy_node_exporter_to "${host}" || die "Deployment to ${host} failed. Aborting."
        done
    fi

    log "node_exporter deployed to all target hosts."
}

# --- Deploy Prometheus server ---
deploy_prometheus() {
    log "=========================================="
    log "  Phase 2: Deploy Prometheus + Alertmanager"
    log "=========================================="

    if $DRY_RUN; then
        log "[DRY-RUN] Would deploy Prometheus to ${CONTROLLER}"
        return 0
    fi

    # Copy install script
    scp_file "${SCRIPT_DIR}/install-prometheus.sh" "${CONTROLLER}" "/tmp/install-prometheus.sh"

    # Execute with environment variables
    ssh_exec "${CONTROLLER}" \
        "sudo NTFY_TOPIC='${NTFY_TOPIC}' NTFY_URL='${NTFY_URL}' bash /tmp/install-prometheus.sh && rm -f /tmp/install-prometheus.sh"

    if [[ $? -eq 0 ]]; then
        success "Prometheus + Alertmanager deployed to ${CONTROLLER}"
    else
        die "Prometheus deployment FAILED on ${CONTROLLER}"
    fi
}

# --- Deploy Grafana ---
deploy_grafana() {
    log "=========================================="
    log "  Phase 3: Deploy Grafana"
    log "=========================================="

    if $DRY_RUN; then
        log "[DRY-RUN] Would deploy Grafana to ${CONTROLLER}"
        return 0
    fi

    # Copy install script
    scp_file "${SCRIPT_DIR}/install-grafana.sh" "${CONTROLLER}" "/tmp/install-grafana.sh"

    # Execute
    ssh_exec "${CONTROLLER}" \
        "sudo bash /tmp/install-grafana.sh && rm -f /tmp/install-grafana.sh"

    if [[ $? -eq 0 ]]; then
        success "Grafana deployed to ${CONTROLLER}"
    else
        err "Grafana deployment failed on ${CONTROLLER} (non-fatal)."
    fi
}

# --- Verify deployment ---
verify_deployment() {
    log "=========================================="
    log "  Verification"
    log "=========================================="

    if $DRY_RUN; then
        log "[DRY-RUN] Would verify deployment."
        return 0
    fi

    local hosts=("${ALL_HOSTS[@]}")
    if [[ -n "${SINGLE_HOST}" ]]; then
        hosts=("${SINGLE_HOST}")
    fi

    # Verify node_exporter on all hosts
    if $DEPLOY_NODE_EXPORTER; then
        log "Verifying node_exporter on fleet..."
        for host in "${hosts[@]}"; do
            if ssh_exec "${host}" "systemctl is-active --quiet node_exporter" 2>/dev/null; then
                success "${host}: node_exporter RUNNING"
            else
                warn "${host}: node_exporter NOT RUNNING"
            fi
        done
    fi

    # Verify Prometheus and Alertmanager
    if $DEPLOY_PROMETHEUS; then
        for svc in prometheus alertmanager; do
            if ssh_exec "${CONTROLLER}" "systemctl is-active --quiet ${svc}" 2>/dev/null; then
                success "${CONTROLLER}: ${svc} RUNNING"
            else
                warn "${CONTROLLER}: ${svc} NOT RUNNING"
            fi
        done

        # Check that Prometheus can reach targets (give it a moment)
        log "Checking Prometheus target status (waiting 10s for first scrape)..."
        sleep 10
        local targets
        targets="$(ssh_exec "${CONTROLLER}" \
            "curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool 2>/dev/null" 2>/dev/null || echo "unavailable")"

        if [[ "${targets}" != "unavailable" ]]; then
            local up_count
            up_count="$(echo "${targets}" | grep -c '"health": "up"' || echo "0")"
            log "Prometheus targets UP: ${up_count}"
        else
            warn "Could not query Prometheus targets API."
        fi
    fi

    # Verify Grafana
    if $DEPLOY_GRAFANA; then
        if ssh_exec "${CONTROLLER}" "systemctl is-active --quiet grafana-server" 2>/dev/null; then
            success "${CONTROLLER}: grafana-server RUNNING"
        else
            warn "${CONTROLLER}: grafana-server NOT RUNNING"
        fi
    fi
}

# --- Print summary ---
print_summary() {
    echo ""
    log "=========================================="
    log "  Deployment Summary"
    log "=========================================="
    echo ""

    if $DEPLOY_NODE_EXPORTER; then
        local hosts=("${ALL_HOSTS[@]}")
        [[ -n "${SINGLE_HOST}" ]] && hosts=("${SINGLE_HOST}")
        log "node_exporter: ${hosts[*]}"
        log "  Port: 9100"
    fi

    if $DEPLOY_PROMETHEUS; then
        echo ""
        log "Prometheus: http://aio-01:9090"
        log "  Retention: 15 days / max 3GB"
        log "  Scrape interval: 30s"
        echo ""
        log "Alertmanager: http://aio-01:9093"
        log "  Notifications: ${NTFY_URL}/${NTFY_TOPIC}"
        log "  Critical channel: ${NTFY_URL}/${NTFY_TOPIC}-critical"
    fi

    if $DEPLOY_GRAFANA; then
        echo ""
        log "Grafana: http://aio-01:3000"
        log "  Login: admin / admin (change on first login)"
        log "  Dashboard: Node Exporter Full (auto-provisioned)"
    fi

    echo ""
    log "=========================================="
    log "  Next Steps"
    log "=========================================="
    log "  1. Subscribe to ntfy topic: ntfy subscribe ${NTFY_TOPIC}"
    log "  2. Change Grafana admin password"
    log "  3. Import additional dashboards from grafana.com"
    log "  4. Optional: Set up ntfy self-hosted for privacy"
    log "=========================================="
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    parse_args "$@"

    log "Fleet Prometheus Deployment"
    log "Controller: ${CONTROLLER}"
    log "Targets: ${ALL_HOSTS[*]}"
    $DRY_RUN && log "*** DRY RUN MODE ***"
    echo ""

    # Validate required scripts exist
    if $DEPLOY_NODE_EXPORTER; then
        [[ -f "${SCRIPT_DIR}/install-node-exporter.sh" ]] || \
            die "Missing: ${SCRIPT_DIR}/install-node-exporter.sh"
    fi
    if $DEPLOY_PROMETHEUS; then
        [[ -f "${SCRIPT_DIR}/install-prometheus.sh" ]] || \
            die "Missing: ${SCRIPT_DIR}/install-prometheus.sh"
    fi
    if $DEPLOY_GRAFANA; then
        [[ -f "${SCRIPT_DIR}/install-grafana.sh" ]] || \
            die "Missing: ${SCRIPT_DIR}/install-grafana.sh"
    fi

    # Phase 0: Connectivity check
    check_fleet_health

    # Phase 1: node_exporter on all machines
    $DEPLOY_NODE_EXPORTER && deploy_node_exporter_all

    # Phase 2: Prometheus + Alertmanager on controller
    $DEPLOY_PROMETHEUS && deploy_prometheus

    # Phase 3: Grafana on controller
    $DEPLOY_GRAFANA && deploy_grafana

    # Verify
    verify_deployment

    # Summary
    print_summary
}

main "$@"
