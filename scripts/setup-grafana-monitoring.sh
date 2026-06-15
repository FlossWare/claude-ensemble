#!/bin/bash
#
# Complete Grafana Monitoring Setup
# Configures datasource, imports dashboard, and provides access instructions
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
GRAFANA_HOST="${GRAFANA_HOST:-aio-01}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
PROMETHEUS_HOST="${PROMETHEUS_HOST:-aio-01}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9091}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Grafana Fleet Monitoring Setup & Dashboard Import       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Helper functions
info() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }
section() { echo ""; echo -e "${BLUE}──────────────────────────────────────${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}──────────────────────────────────────${NC}"; }

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --grafana-host)
            GRAFANA_HOST="$2"
            shift 2
            ;;
        --grafana-port)
            GRAFANA_PORT="$2"
            shift 2
            ;;
        --prometheus-host)
            PROMETHEUS_HOST="$2"
            shift 2
            ;;
        --prometheus-port)
            PROMETHEUS_PORT="$2"
            shift 2
            ;;
        --admin-user)
            GRAFANA_ADMIN_USER="$2"
            shift 2
            ;;
        --admin-password)
            GRAFANA_ADMIN_PASSWORD="$2"
            shift 2
            ;;
        --help)
            cat << 'EOF'
Usage: ./setup-grafana-monitoring.sh [OPTIONS]

Options:
  --grafana-host HOST           Grafana server hostname (default: aio-01)
  --grafana-port PORT           Grafana server port (default: 3000)
  --prometheus-host HOST        Prometheus server hostname (default: aio-01)
  --prometheus-port PORT        Prometheus server port (default: 9091)
  --admin-user USER             Grafana admin username (default: admin)
  --admin-password PASSWORD     Grafana admin password (default: admin)
  --help                        Show this help message

Examples:
  ./setup-grafana-monitoring.sh
  ./setup-grafana-monitoring.sh --grafana-host localhost --prometheus-host prometheus.example.com
  ./setup-grafana-monitoring.sh --grafana-port 3001 --prometheus-port 9090

EOF
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

GRAFANA_URL="http://$GRAFANA_HOST:$GRAFANA_PORT"
PROMETHEUS_URL="http://$PROMETHEUS_HOST:$PROMETHEUS_PORT"

section "Configuration"
echo "Grafana URL:       $GRAFANA_URL"
echo "Prometheus URL:    $PROMETHEUS_URL"
echo "Admin User:        $GRAFANA_ADMIN_USER"
echo ""

# Check prerequisites
section "Prerequisites Check"

if ! command -v curl &> /dev/null; then
    error "curl is not installed. Please install curl."
fi
info "curl found"

if ! command -v jq &> /dev/null; then
    warn "jq not found (optional, for better JSON parsing)"
fi

# Test Grafana connectivity
section "Service Connectivity"

echo -n "Testing Grafana connectivity... "
if curl -s -f -o /dev/null -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" "$GRAFANA_URL/api/health" 2>/dev/null; then
    info "Grafana is reachable at $GRAFANA_URL"
else
    error "Cannot connect to Grafana at $GRAFANA_URL. Please verify:"
    echo "  1. Grafana is running on $GRAFANA_HOST:$GRAFANA_PORT"
    echo "  2. Credentials are correct (user: $GRAFANA_ADMIN_USER)"
    echo "  3. Network connectivity to $GRAFANA_HOST"
fi

echo -n "Testing Prometheus connectivity... "
if curl -s -f -o /dev/null "$PROMETHEUS_URL/-/healthy" 2>/dev/null; then
    info "Prometheus is reachable at $PROMETHEUS_URL"
else
    warn "Prometheus is not reachable at $PROMETHEUS_URL (continuing anyway)"
    warn "Ensure Prometheus is running before the dashboard becomes functional"
fi

# Create temporary dashboard JSON file
section "Preparing Dashboard"

DASHBOARD_JSON_FILE=$(mktemp)
trap "rm -f $DASHBOARD_JSON_FILE" EXIT

cat > "$DASHBOARD_JSON_FILE" << 'DASHBOARD_EOF'
{
  "title": "Fleet Node Activity Dashboard",
  "uid": "fleet-node-activity",
  "tags": ["fleet", "nodes", "infrastructure", "ai", "monitoring"],
  "timezone": "browser",
  "refresh": "30s",
  "time": {
    "from": "now-7d",
    "to": "now"
  },
  "schemaVersion": 39,
  "editable": true,
  "graphTooltip": 1,
  "templating": {
    "list": [
      {
        "name": "datasource",
        "type": "datasource",
        "query": "prometheus",
        "current": {
          "value": "Prometheus",
          "text": "Prometheus"
        }
      },
      {
        "name": "node",
        "type": "query",
        "datasource": "$datasource",
        "query": "label_values(fleet_node_info, hostname)",
        "multi": true,
        "includeAll": true,
        "allValue": ".*",
        "current": {
          "value": ["$__all"],
          "text": "All"
        }
      },
      {
        "name": "model",
        "type": "query",
        "datasource": "$datasource",
        "query": "label_values(ai_learning_execution_total, model)",
        "multi": true,
        "includeAll": true,
        "allValue": ".*"
      },
      {
        "name": "task_type",
        "type": "query",
        "datasource": "$datasource",
        "query": "label_values(ai_learning_execution_total, task_type)",
        "multi": true,
        "includeAll": true,
        "allValue": ".*"
      },
      {
        "name": "workflow",
        "type": "query",
        "datasource": "$datasource",
        "query": "label_values(ai_learning_execution_total, workflow)",
        "multi": true,
        "includeAll": true,
        "allValue": ".*"
      }
    ]
  },
  "panels": [
    {
      "id": 1,
      "title": "Fleet Topology Map",
      "type": "nodeGraph",
      "description": "Visual network graph of all fleet nodes",
      "datasource": "$datasource",
      "gridPos": {"x": 0, "y": 0, "w": 12, "h": 10},
      "targets": [
        {"expr": "fleet_node_info", "refId": "A", "format": "table"},
        {"expr": "fleet_connection", "refId": "B", "format": "table"}
      ]
    },
    {
      "id": 2,
      "title": "CPU Utilization per Node",
      "type": "timeseries",
      "description": "CPU utilization across all nodes",
      "datasource": "$datasource",
      "gridPos": {"x": 0, "y": 10, "w": 12, "h": 8},
      "targets": [
        {
          "expr": "100 - (avg by(hostname) (rate(node_cpu_seconds_total{mode=\"idle\",hostname=~\"$node\"}[5m])) * 100)",
          "refId": "A",
          "legendFormat": "{{hostname}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "max": 100
        }
      }
    },
    {
      "id": 3,
      "title": "Memory Utilization per Node",
      "type": "timeseries",
      "description": "Memory usage across all nodes",
      "datasource": "$datasource",
      "gridPos": {"x": 12, "y": 10, "w": 12, "h": 8},
      "targets": [
        {
          "expr": "(1 - (node_memory_MemAvailable_bytes{hostname=~\"$node\"} / node_memory_MemTotal_bytes{hostname=~\"$node\"})) * 100",
          "refId": "A",
          "legendFormat": "{{hostname}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "max": 100
        }
      }
    },
    {
      "id": 4,
      "title": "Active Workflows per Node",
      "type": "bargauge",
      "description": "Current workflow count per node",
      "datasource": "$datasource",
      "gridPos": {"x": 0, "y": 18, "w": 12, "h": 8},
      "targets": [
        {
          "expr": "count by(hostname) (fleet_active_workflows{hostname=~\"$node\"})",
          "refId": "A",
          "legendFormat": "{{hostname}}"
        }
      ],
      "fieldConfig": {
        "defaults": {"min": 0, "max": 10}
      }
    },
    {
      "id": 5,
      "title": "Task Distribution Heatmap",
      "type": "heatmap",
      "description": "Task completion distribution over time",
      "datasource": "$datasource",
      "gridPos": {"x": 12, "y": 18, "w": 12, "h": 8},
      "targets": [
        {
          "expr": "sum by(hostname) (increase(fleet_tasks_completed_total{hostname=~\"$node\"}[$__interval]))",
          "refId": "A",
          "legendFormat": "{{hostname}}"
        }
      ]
    }
  ]
}
DASHBOARD_EOF

info "Dashboard JSON prepared"

# Execute the import script
section "Importing Dashboard"

export GRAFANA_URL="$GRAFANA_URL"
export GRAFANA_ADMIN_USER="$GRAFANA_ADMIN_USER"
export GRAFANA_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASSWORD"
export PROMETHEUS_URL="$PROMETHEUS_URL"

if [ -f "$SCRIPT_DIR/grafana-dashboard-import.sh" ]; then
    bash "$SCRIPT_DIR/grafana-dashboard-import.sh" "$DASHBOARD_JSON_FILE"
else
    error "Import script not found at $SCRIPT_DIR/grafana-dashboard-import.sh"
fi

# Create convenience script for accessing dashboard
section "Creating Access Script"

ACCESS_SCRIPT="$SCRIPT_DIR/open-grafana-dashboard.sh"
cat > "$ACCESS_SCRIPT" << 'EOF'
#!/bin/bash
# Open Grafana Fleet Dashboard in default browser

GRAFANA_HOST="${GRAFANA_HOST:-aio-01}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
DASHBOARD_UID="fleet-node-activity"

URL="http://$GRAFANA_HOST:$GRAFANA_PORT/d/$DASHBOARD_UID/fleet-node-activity-dashboard"

echo "Opening Grafana Dashboard: $URL"

if command -v xdg-open &> /dev/null; then
    xdg-open "$URL"
elif command -v open &> /dev/null; then
    open "$URL"
else
    echo "Cannot determine how to open browser. Please visit manually:"
    echo "$URL"
fi
EOF

chmod +x "$ACCESS_SCRIPT"
info "Created access script: $ACCESS_SCRIPT"

# Final summary
section "Setup Complete"

echo ""
echo -e "${GREEN}All services configured and dashboard imported!${NC}"
echo ""
echo "Dashboard Information:"
echo "  URL: $GRAFANA_URL/d/fleet-node-activity/fleet-node-activity-dashboard"
echo "  UID: fleet-node-activity"
echo "  Refresh: 30 seconds"
echo "  Time Range: Last 7 days"
echo ""
echo "Prometheus Datasource:"
echo "  URL: $PROMETHEUS_URL"
echo "  Status: Default (all panels use this)"
echo "  Health: curl -s $PROMETHEUS_URL/-/healthy"
echo ""
echo "Quick Commands:"
echo "  # Open dashboard in browser"
echo "  bash $ACCESS_SCRIPT"
echo ""
echo "  # Check Prometheus metrics"
echo "  curl -s '$PROMETHEUS_URL/api/v1/query?query=up' | jq ."
echo ""
echo "  # Check Grafana datasources"
echo "  curl -s -u '$GRAFANA_ADMIN_USER:***' $GRAFANA_URL/api/datasources"
echo ""
echo "Troubleshooting:"
echo "  1. If panels show 'No data', verify Prometheus is running"
echo "  2. Check metric export: curl $PROMETHEUS_URL/metrics | grep fleet_"
echo "  3. Review dashboard variables: click gear icon in dashboard"
echo "  4. Check browser console for errors (F12)"
echo ""
echo "Dashboard Variables (all optional, default to all):"
echo "  - node: Filter by hostname"
echo "  - model: Filter by AI model"
echo "  - task_type: Filter by task type"
echo "  - workflow: Filter by workflow name"
echo ""
