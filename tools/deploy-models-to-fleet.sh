#!/bin/bash
#
# Deploy ML Prediction Models to Fleet
#
# Copies 81 trained models from local machine to aio-01 and starts prediction API
#
# Usage:
#   bash tools/deploy-models-to-fleet.sh
#
# Created: 2026-07-05

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LEARNING_DIR="$HOME/.claude/learning"
PREDICTOR_DIR="$LEARNING_DIR/predictors"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if models exist locally
if [[ ! -d "$PREDICTOR_DIR" ]]; then
    log_error "Predictor directory not found: $PREDICTOR_DIR"
    exit 1
fi

MODEL_COUNT=$(find "$PREDICTOR_DIR" -name "*.pkl" -type f | wc -l)
log_info "Found $MODEL_COUNT model files in $PREDICTOR_DIR"

if [[ $MODEL_COUNT -eq 0 ]]; then
    log_error "No model files found. Please train models first."
    exit 1
fi

# Deploy to aio-01
log_info "Deploying to aio-01..."

# 1. Create directory structure
log_info "Creating directory structure on aio-01..."
ssh claude@aio-01 "mkdir -p ~/.claude/learning/predictors ~/.claude/logs ~/bin"

# 2. Copy model files
log_info "Copying $MODEL_COUNT model files to aio-01..."
rsync -avz --progress \
    "$PREDICTOR_DIR/" \
    claude@aio-01:~/.claude/learning/predictors/

# 3. Copy prediction API server
log_info "Copying prediction API server..."
scp "$PROJECT_ROOT/prediction-api/server.py" \
    claude@aio-01:~/bin/prediction-api-server.py

ssh claude@aio-01 "chmod +x ~/bin/prediction-api-server.py"

# 4. Create systemd service
log_info "Creating systemd service..."
ssh claude@aio-01 "mkdir -p ~/.config/systemd/user"

cat <<'EOF' | ssh claude@aio-01 "cat > ~/.config/systemd/user/prediction-api.service"
[Unit]
Description=ML Prediction API Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/claude/bin/prediction-api-server.py
Restart=always
RestartSec=10
Environment="PREDICTION_HOST=0.0.0.0"
Environment="PREDICTION_PORT=8080"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# 5. Enable and start service
log_info "Enabling and starting prediction-api service..."
ssh claude@aio-01 "systemctl --user daemon-reload"
ssh claude@aio-01 "systemctl --user enable prediction-api.service"
ssh claude@aio-01 "systemctl --user restart prediction-api.service"

# Wait for service to start
log_info "Waiting for service to start..."
sleep 3

# 6. Verify deployment
log_info "Verifying deployment..."

# Check service status
SERVICE_STATUS=$(ssh claude@aio-01 "systemctl --user is-active prediction-api.service" || echo "failed")
if [[ "$SERVICE_STATUS" == "active" ]]; then
    log_info "✓ Service is active"
else
    log_error "✗ Service failed to start"
    ssh claude@aio-01 "systemctl --user status prediction-api.service"
    exit 1
fi

# Check health endpoint
HEALTH_CHECK=$(ssh claude@aio-01 "curl -s http://localhost:8080/health" || echo "failed")
if [[ "$HEALTH_CHECK" == "failed" ]]; then
    log_error "✗ Health check failed"
    ssh claude@aio-01 "journalctl --user -u prediction-api -n 50"
    exit 1
fi

log_info "✓ Health check passed"
echo "$HEALTH_CHECK" | jq .

# Check models endpoint
MODELS_CHECK=$(ssh claude@aio-01 "curl -s http://localhost:8080/models" || echo "failed")
if [[ "$MODELS_CHECK" == "failed" ]]; then
    log_error "✗ Models endpoint failed"
    exit 1
fi

MODELS_LOADED=$(echo "$MODELS_CHECK" | jq -r '.total')
log_info "✓ Models endpoint: $MODELS_LOADED models available"

# Test prediction endpoint
log_info "Testing prediction endpoint..."
PREDICTION_TEST=$(ssh claude@aio-01 'curl -s http://localhost:8080/predict-workflow -H "Content-Type: application/json" -d "{\"workflow_name\":\"test\",\"task_description\":\"Test workflow\",\"total_workers\":4}"' || echo "failed")

if [[ "$PREDICTION_TEST" == "failed" ]]; then
    log_error "✗ Prediction endpoint failed"
    exit 1
fi

log_info "✓ Prediction endpoint working"
echo "$PREDICTION_TEST" | jq .

# Summary
echo ""
log_info "============================================"
log_info "Deployment Summary"
log_info "============================================"
log_info "Models deployed: $MODEL_COUNT"
log_info "Models available: $MODELS_LOADED"
log_info "Service status: $SERVICE_STATUS"
log_info "API endpoint: http://aio-01:8080"
log_info "Health check: http://aio-01:8080/health"
log_info "Models list: http://aio-01:8080/models"
log_info "============================================"
log_info ""
log_info "To view logs:"
log_info "  ssh claude@aio-01 'journalctl --user -u prediction-api -f'"
log_info ""
log_info "To restart service:"
log_info "  ssh claude@aio-01 'systemctl --user restart prediction-api'"
log_info ""
log_info "Deployment complete! ✓"
