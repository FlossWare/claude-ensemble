#!/usr/bin/env bash
# =============================================================================
# import-dashboard.sh - Import Fleet Monitoring Dashboard into Grafana
#
# Automates dashboard import with datasource discovery and validation.
# Idempotent: safe to run multiple times (updates existing dashboard).
#
# Usage:
#   ./import-dashboard.sh                              # Auto-detect aio-01
#   ./import-dashboard.sh --host grafana.example.com  # Custom host
#   ./import-dashboard.sh --token YOUR-API-TOKEN      # With API token
#   ./import-dashboard.sh --dry-run                    # Validate only
#
# Environment variables:
#   GRAFANA_HOST       - Grafana hostname (default: aio-01:3000)
#   GRAFANA_USER       - Admin username (default: admin)
#   GRAFANA_PASSWORD   - Admin password (default: admin)
#   GRAFANA_PROTOCOL   - HTTP or HTTPS (default: http)
#   GRAFANA_API_TOKEN  - API token (optional, uses basic auth if not set)
# =============================================================================
set -euo pipefail

# --- Configuration ---
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DASHBOARD_FILE_FLEET="${SCRIPT_DIR}/grafana-dashboard-fleet.json"
readonly DASHBOARD_FILE_ISSUES="${SCRIPT_DIR}/grafana-dashboard-issues.json"

# Default: import all dashboards. Override with --dashboard fleet|issues
DASHBOARD_SELECTION="all"

GRAFANA_HOST="${GRAFANA_HOST:-aio-01:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
GRAFANA_PROTOCOL="${GRAFANA_PROTOCOL:-http}"
GRAFANA_API_TOKEN="${GRAFANA_API_TOKEN:-}"

DRY_RUN=0
VERBOSE=0

# --- Logging ---
log()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
err()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }
die()   { err "$*"; exit 1; }
debug() { [[ $VERBOSE -eq 1 ]] && echo "[$(date '+%Y-%m-%d %H:%M:%S')] [DEBUG] $*"; }

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            GRAFANA_HOST="$2"
            shift 2
            ;;
        --user)
            GRAFANA_USER="$2"
            shift 2
            ;;
        --password)
            GRAFANA_PASSWORD="$2"
            shift 2
            ;;
        --token)
            GRAFANA_API_TOKEN="$2"
            shift 2
            ;;
        --protocol)
            GRAFANA_PROTOCOL="$2"
            shift 2
            ;;
        --dashboard)
            DASHBOARD_SELECTION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

# --- Build dashboard file list ---
DASHBOARD_FILES=()
case "$DASHBOARD_SELECTION" in
    fleet)
        DASHBOARD_FILES=("$DASHBOARD_FILE_FLEET")
        ;;
    issues)
        DASHBOARD_FILES=("$DASHBOARD_FILE_ISSUES")
        ;;
    all)
        DASHBOARD_FILES=("$DASHBOARD_FILE_FLEET" "$DASHBOARD_FILE_ISSUES")
        ;;
    *)
        die "Unknown dashboard: $DASHBOARD_SELECTION (use: fleet, issues, all)"
        ;;
esac

# --- Validation ---
for df in "${DASHBOARD_FILES[@]}"; do
    [[ -f "$df" ]] || die "Dashboard file not found: $df"
done

command -v curl >/dev/null 2>&1 || die "curl is required."
command -v jq >/dev/null 2>&1 || die "jq is required."

GRAFANA_URL="${GRAFANA_PROTOCOL}://${GRAFANA_HOST}"

log "Grafana URL: $GRAFANA_URL"
log "Dashboards: ${DASHBOARD_FILES[*]}"

# --- Helper functions ---

# Make authenticated HTTP request to Grafana API
grafana_api() {
    local method="$1" endpoint="$2" data="${3:-}"
    local auth_header=""

    if [[ -n "$GRAFANA_API_TOKEN" ]]; then
        auth_header="-H Authorization: Bearer ${GRAFANA_API_TOKEN}"
    else
        auth_header="-u ${GRAFANA_USER}:${GRAFANA_PASSWORD}"
    fi

    local curl_opts=(
        -s
        -X "$method"
        -H "Content-Type: application/json"
        "$auth_header"
    )

    if [[ -n "$data" ]]; then
        curl_opts+=(-d "$data")
    fi

    local response
    response=$(curl "${curl_opts[@]}" "${GRAFANA_URL}${endpoint}" 2>&1)

    if [[ $VERBOSE -eq 1 ]]; then
        debug "Response: $response"
    fi

    echo "$response"
}

# Check Grafana health
check_grafana_health() {
    log "Checking Grafana health..."
    local response
    response=$(curl -s -f "${GRAFANA_URL}/api/health" 2>&1) || {
        die "Grafana is not reachable at $GRAFANA_URL. Check hostname and firewall."
    }
    log "Grafana health check passed"
}

# Get or create Prometheus datasource
get_or_create_datasource() {
    log "Checking for Prometheus datasource..."

    local datasources
    datasources=$(grafana_api "GET" "/api/datasources")

    local prometheus_uid
    prometheus_uid=$(echo "$datasources" | jq -r '.[] | select(.type=="prometheus") | .uid' | head -1)

    if [[ -z "$prometheus_uid" ]]; then
        log "No Prometheus datasource found. Creating one..."

        # Check if Prometheus is running
        if ! curl -sf "${GRAFANA_PROTOCOL}://aio-01:9090/-/healthy" >/dev/null 2>&1; then
            warn "Warning: Prometheus not reachable at aio-01:9090"
            warn "Please ensure Prometheus is running before importing dashboard"
            prometheus_uid="prometheus"
        else
            local payload
            payload=$(cat <<EOF
{
  "name": "Prometheus",
  "type": "prometheus",
  "url": "http://aio-01:9090",
  "access": "proxy",
  "isDefault": true
}
EOF
)

            if [[ $DRY_RUN -eq 0 ]]; then
                local response
                response=$(grafana_api "POST" "/api/datasources" "$payload")
                prometheus_uid=$(echo "$response" | jq -r '.datasource.uid' 2>/dev/null || echo "prometheus")
                log "Created Prometheus datasource with UID: $prometheus_uid"
            else
                prometheus_uid="prometheus"
                log "[DRY-RUN] Would create Prometheus datasource"
            fi
        fi
    else
        log "Found existing Prometheus datasource with UID: $prometheus_uid"
    fi

    echo "$prometheus_uid"
}

# Import a single dashboard file
import_dashboard() {
    local datasource_uid="$1"
    local dashboard_file="$2"

    log "Preparing dashboard for import: $dashboard_file"

    # Read dashboard JSON and update datasource references
    local dashboard_json
    dashboard_json=$(cat "$dashboard_file")

    # Replace datasource UID references
    dashboard_json=$(echo "$dashboard_json" | jq \
        --arg uid "$datasource_uid" \
        '.panels[] |= (
            if .datasource.type == "prometheus" then
                .datasource.uid = $uid
            else
                .
            end
        )')

    # Build payload for import
    local import_payload
    import_payload=$(jq -n \
        --argjson dashboard "$dashboard_json" \
        '{
            "dashboard": $dashboard,
            "overwrite": true,
            "message": "Auto-imported Fleet Monitoring Dashboard"
        }')

    if [[ $DRY_RUN -eq 1 ]]; then
        log "[DRY-RUN] Would import dashboard with datasource UID: $datasource_uid"
        return 0
    fi

    log "Importing dashboard..."
    local response
    response=$(grafana_api "POST" "/api/dashboards/db" "$import_payload")

    local dashboard_id
    dashboard_id=$(echo "$response" | jq -r '.id // .dashboard.id // empty' 2>/dev/null)

    if [[ -z "$dashboard_id" ]]; then
        local error_msg
        error_msg=$(echo "$response" | jq -r '.message // .error // "Unknown error"' 2>/dev/null)
        die "Failed to import dashboard: $error_msg"
    fi

    local dash_uid
    dash_uid=$(echo "$dashboard_json" | jq -r '.uid // "unknown"')
    local dash_title
    dash_title=$(echo "$dashboard_json" | jq -r '.title // "Unknown"')

    log "Dashboard imported successfully!"
    log "Dashboard ID: $dashboard_id"
    log "Dashboard UID: $dash_uid"
    log "Access at: ${GRAFANA_URL}/d/${dash_uid}/${dash_title// /-}"

    return 0
}

# --- Main flow ---
main() {
    log "Starting dashboard import process..."
    log "========================================="

    check_grafana_health
    local datasource_uid
    datasource_uid=$(get_or_create_datasource)

    for dashboard_file in "${DASHBOARD_FILES[@]}"; do
        import_dashboard "$datasource_uid" "$dashboard_file"
    done

    log "========================================="
    log "Dashboard import completed successfully!"

    if [[ $DRY_RUN -eq 1 ]]; then
        log "Note: This was a dry-run. No changes were made to Grafana."
        log "Run without --dry-run to actually import the dashboard."
    fi
}

# --- Help ---
show_help() {
    cat <<'EOF'
import-dashboard.sh - Import Fleet Monitoring Dashboard into Grafana

USAGE:
    ./import-dashboard.sh [OPTIONS]

OPTIONS:
    --host HOST              Grafana hostname (default: aio-01:3000)
    --user USER              Admin username (default: admin)
    --password PASSWORD      Admin password (default: admin)
    --token TOKEN            API token (optional, uses basic auth if not set)
    --protocol PROTOCOL      HTTP or HTTPS (default: http)
    --dry-run                Validate without making changes
    --verbose                Show detailed output
    --help                   Show this help message

EXAMPLES:
    # Import to default aio-01:3000
    ./import-dashboard.sh

    # Import to custom Grafana instance
    ./import-dashboard.sh --host grafana.example.com:3000

    # Use API token for authentication
    ./import-dashboard.sh --token YOUR-API-TOKEN-HERE

    # Dry-run to validate configuration
    ./import-dashboard.sh --dry-run --verbose

ENVIRONMENT VARIABLES:
    GRAFANA_HOST        Grafana hostname (default: aio-01:3000)
    GRAFANA_USER        Admin username (default: admin)
    GRAFANA_PASSWORD    Admin password (default: admin)
    GRAFANA_PROTOCOL    HTTP or HTTPS (default: http)
    GRAFANA_API_TOKEN   API token (optional)

DASHBOARD DETAILS:
    - UID: fleet-monitoring
    - Name: Fleet Monitoring Dashboard
    - Panels: 14 (overview, trends, network, advanced)
    - Refresh: 30 seconds
    - Time Range: Last 6 hours

EOF
}

# --- Execute ---
main "$@"
