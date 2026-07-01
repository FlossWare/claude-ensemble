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

