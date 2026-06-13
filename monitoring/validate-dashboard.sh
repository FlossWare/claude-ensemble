#!/usr/bin/env bash
# =============================================================================
# validate-dashboard.sh - Validate Grafana dashboard JSON
#
# Checks dashboard for required fields and valid structure.
# Useful for debugging dashboard import issues.
#
# Usage:
#   ./validate-dashboard.sh [dashboard-file.json]
# =============================================================================
set -euo pipefail

DASHBOARD_FILE="${1:-grafana-dashboard-fleet.json}"

log()  { echo "[INFO]  $*"; }
warn() { echo "[WARN]  $*" >&2; }
err()  { echo "[ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

# Check dependencies
command -v jq >/dev/null 2>&1 || die "jq is required"

log "Validating dashboard: $DASHBOARD_FILE"

[[ -f "$DASHBOARD_FILE" ]] || die "Dashboard file not found: $DASHBOARD_FILE"

# Parse JSON
log "Parsing JSON..."
DASHBOARD=$(jq . "$DASHBOARD_FILE" 2>/dev/null) || die "Invalid JSON format"

# Validate required fields
log "Checking required fields..."

check_field() {
    local field="$1" path="$2"
    local value
    value=$(echo "$DASHBOARD" | jq -r "$path // empty" 2>/dev/null)
    if [[ -z "$value" ]]; then
        warn "Missing field: $field ($path)"
        return 1
    fi
    log "✓ $field: $value"
    return 0
}

ERRORS=0

check_field "Title" ".title" || ((ERRORS++))
check_field "UID" ".uid" || ((ERRORS++))
check_field "Version" ".version" || ((ERRORS++))

# Count panels
PANEL_COUNT=$(echo "$DASHBOARD" | jq '.panels | length')
log "Panel count: $PANEL_COUNT"
[[ $PANEL_COUNT -ge 10 ]] || ((ERRORS++)); warn "Expected at least 10 panels"

# Check datasources
log "Checking datasources..."
DATASOURCES=$(echo "$DASHBOARD" | jq '.panels[].datasource.type' | sort | uniq)
log "Datasource types: $(echo "$DATASOURCES" | tr '\n' ' ')"

# Validate panel structure
log "Validating panel structure..."
for i in $(seq 0 $((PANEL_COUNT - 1))); do
    PANEL=$(echo "$DASHBOARD" | jq ".panels[$i]")
    TITLE=$(echo "$PANEL" | jq -r '.title // "Unknown"')
    TYPE=$(echo "$PANEL" | jq -r '.type // "unknown"')
    
    if [[ -z "$TITLE" || "$TITLE" == "null" ]]; then
        err "Panel $i: Missing title"
        ((ERRORS++))
    else
        log "✓ Panel $i: $TITLE ($TYPE)"
    fi
done

# Check template variables
log "Checking template variables..."
VAR_COUNT=$(echo "$DASHBOARD" | jq '.templating.list | length')
log "Template variables: $VAR_COUNT"

# Summary
echo ""
if [[ $ERRORS -eq 0 ]]; then
    log "✓ Dashboard validation passed!"
    exit 0
else
    err "✗ Dashboard validation failed with $ERRORS errors"
    exit 1
fi
