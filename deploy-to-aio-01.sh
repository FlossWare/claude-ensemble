#!/bin/bash
# Deploy orchestrator from laptop-01 to aio-01

set -e

echo "=========================================="
echo "Deploying orchestrator to aio-01"
echo "=========================================="
echo ""

# Deploy orchestrator files
echo "1. Copying orchestrator files..."
scp orchestrator/orchestrate.py root@aio-01:/mnt/aio-01/claude-orchestrator/
scp orchestrator/shared/fleet_executor.py root@aio-01:/mnt/aio-01/claude-orchestrator/shared/

echo "✓ Orchestrator deployed"
echo ""

# Deploy proxy (if changed)
if [ -f "proxy/api-proxy.py" ]; then
  echo "2. Deploying API proxy..."
  scp proxy/api-proxy.py root@aio-01:/opt/api-proxy.py
  ssh root@aio-01 "systemctl restart api-proxy"
  echo "✓ Proxy deployed and restarted"
else
  echo "2. No proxy changes to deploy"
fi

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Test with:"
echo "  ssh root@aio-01 'cd /mnt/aio-01/claude-orchestrator && python3 orchestrate.py \"test\" llama-3.1-8b-instant'"


# Deploy model maintenance
echo "3. Deploying model maintenance..."
scp scripts/maintain-models.py root@aio-01:/mnt/aio-01/claude-orchestrator/scripts/
scp scripts/model-maintenance.service root@aio-01:/etc/systemd/system/
scp scripts/model-maintenance.timer root@aio-01:/etc/systemd/system/

ssh root@aio-01 "
  systemctl daemon-reload
  systemctl enable model-maintenance.timer
  systemctl start model-maintenance.timer
  echo '✓ Model maintenance timer enabled (runs daily at 3 AM)'
"

# Deploy fleet health monitor
echo "4. Deploying fleet health monitor..."
scp tools/fleet_health_monitor.py root@aio-01:/mnt/aio-01/claude-orchestrator/tools/
scp shared/fleet_health_client.py root@aio-01:/mnt/aio-01/claude-orchestrator/shared/
scp scripts/fleet-health-monitor.service root@aio-01:/etc/systemd/system/

ssh root@aio-01 "
  systemctl daemon-reload
  systemctl enable fleet-health-monitor.service
  systemctl restart fleet-health-monitor.service
  echo '✓ Fleet health monitor enabled and started'
"

echo ""
echo "Verify health monitor:"
echo "  ssh root@aio-01 'systemctl status fleet-health-monitor.service'
  ssh root@aio-01 'journalctl -u fleet-health-monitor -n 20 -f'"
