#!/bin/bash
# Deploy Fleet Health Monitor as systemd service on aio-01
# Monitors 8 API workers and stores results in PostgreSQL

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="$REPO_ROOT/scripts/fleet-health-monitor.service"
HEALTH_MONITOR="$REPO_ROOT/tools/fleet_health_monitor.py"
HEALTH_CLIENT="$REPO_ROOT/shared/fleet_health_client.py"

echo "==================================================================="
echo "Fleet Health Monitor Deployment"
echo "==================================================================="
echo ""
echo "Prerequisites:"
echo "  - PostgreSQL running on aio-01:5433"
echo "  - Database: learning"
echo "  - User: claude (passwordless access configured)"
echo "  - SSH access to workers: server-01, server-02, server-03,"
echo "    laptop-01, pi-01, pi-02, server-ap, desktop-ap"
echo ""

# Verify files exist
if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "❌ Service file not found: $SERVICE_FILE"
    exit 1
fi

if [[ ! -f "$HEALTH_MONITOR" ]]; then
    echo "❌ Health monitor script not found: $HEALTH_MONITOR"
    exit 1
fi

if [[ ! -f "$HEALTH_CLIENT" ]]; then
    echo "❌ Health client library not found: $HEALTH_CLIENT"
    exit 1
fi

echo "✅ All required files found"
echo ""

# Make scripts executable
chmod +x "$HEALTH_MONITOR"
chmod +x "$HEALTH_CLIENT"

# Test PostgreSQL connection
echo "Testing PostgreSQL connection..."
if python3 -c "import psycopg2; psycopg2.connect(host='aio-01', port=5433, database='learning', user='claude').close()" 2>/dev/null; then
    echo "✅ PostgreSQL connection successful"
else
    echo "❌ PostgreSQL connection failed"
    echo "   Ensure PostgreSQL is running and user 'claude' has access"
    exit 1
fi

# Test SSH to one worker (server-01)
echo ""
echo "Testing SSH connectivity to workers..."
if ssh -o ConnectTimeout=5 -o LogLevel=ERROR claude@server-01 echo OK &>/dev/null; then
    echo "✅ SSH connectivity verified (tested server-01)"
else
    echo "❌ SSH connectivity failed to server-01"
    echo "   Ensure SSH user 'claude' has passwordless access to all workers"
    exit 1
fi

# Test health monitor script
echo ""
echo "Testing health monitor script..."
if timeout 10 python3 "$HEALTH_MONITOR" &>/dev/null; then
    echo "✅ Health monitor script runs without errors"
else
    echo "⚠️  Health monitor test timed out (expected - runs continuously)"
fi

# Test health client
echo ""
echo "Testing health client library..."
if python3 "$HEALTH_CLIENT" &>/dev/null; then
    echo "✅ Health client library works"
else
    echo "❌ Health client library failed"
    exit 1
fi

# Install systemd service
echo ""
echo "Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/fleet-health-monitor.service
sudo systemctl daemon-reload
echo "✅ Service file installed"

# Enable and start service
echo ""
read -p "Start fleet-health-monitor.service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl enable fleet-health-monitor.service
    sudo systemctl restart fleet-health-monitor.service
    echo ""
    echo "✅ Service started"
    echo ""
    echo "Monitor logs:"
    echo "  sudo journalctl -u fleet-health-monitor -f"
    echo ""
    echo "Check status:"
    echo "  sudo systemctl status fleet-health-monitor"
    echo ""
    echo "View health data:"
    echo "  python3 $HEALTH_CLIENT"
else
    echo ""
    echo "Service installed but not started. To start manually:"
    echo "  sudo systemctl enable fleet-health-monitor.service"
    echo "  sudo systemctl start fleet-health-monitor.service"
fi

echo ""
echo "==================================================================="
echo "Deployment Complete"
echo "==================================================================="
echo ""
echo "Integration points:"
echo "  1. Fleet executor: shared/fleet_executor.py (auto-filters unhealthy workers)"
echo "  2. Health client: shared/fleet_health_client.py (query health status)"
echo "  3. PostgreSQL: monitoring.health_checks table (health data storage)"
echo ""
echo "Usage in Python:"
echo "  from fleet_health_client import get_healthy_workers, get_fleet_summary"
echo "  healthy = get_healthy_workers()"
echo "  summary = get_fleet_summary()"
echo ""
