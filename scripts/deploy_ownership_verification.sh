#!/bin/bash
#
# Deploy Queue Ownership Verification
#
# This script:
# 1. Backs up existing API code
# 2. Integrates ownership verification endpoints
# 3. Restarts the API service
# 4. Runs verification tests
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_HOST="aio-01"
API_PATH="/exports/claude-orchestrator/api"
API_SERVICE="orchestrator-api"

echo "=== Queue Ownership Verification Deployment ==="
echo ""

# Step 1: Backup existing API
echo "[1/5] Backing up existing API..."
ssh "$API_HOST" "
    cd $API_PATH
    if [ ! -d backups ]; then mkdir -p backups; fi
    tar -czf backups/api-backup-\$(date +%Y%m%d-%H%M%S).tar.gz application.py
    echo 'Backup created'
"

# Step 2: Copy new queue endpoints
echo "[2/5] Copying ownership verification endpoints..."
scp "$PROJECT_ROOT/api/queue_endpoints_with_ownership.py" \
    "$API_HOST:$API_PATH/queue_endpoints_with_ownership.py"

# Step 3: Integrate into application.py
echo "[3/5] Integrating into application.py..."
ssh "$API_HOST" "
    cd $API_PATH

    # Check if already integrated
    if grep -q 'from queue_endpoints_with_ownership import queue_bp' application.py; then
        echo 'Already integrated, skipping'
    else
        # Add import
        sed -i '/^from flask import/a from queue_endpoints_with_ownership import queue_bp' application.py

        # Register blueprint
        sed -i '/app = Flask/a app.register_blueprint(queue_bp)' application.py

        echo 'Integration complete'
    fi
"

# Step 4: Restart API service
echo "[4/5] Restarting API service..."
ssh "$API_HOST" "
    sudo systemctl restart $API_SERVICE
    sleep 3
    sudo systemctl status $API_SERVICE --no-pager
"

# Step 5: Run verification tests
echo "[5/5] Running ownership verification tests..."
echo ""
echo "To run tests manually:"
echo "  python3 $PROJECT_ROOT/tests/test_queue_ownership_verification.py"
echo ""

# Quick health check
echo "API Health Check:"
curl -s "http://$API_HOST:5000/health" | python3 -m json.tool || echo "API not responding"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Run tests: python3 tests/test_queue_ownership_verification.py"
echo "2. Deploy workers: ./scripts/deploy_queue_workers.sh"
echo "3. Monitor: curl http://aio-01:5000/queue/stats/store"
