#!/bin/bash

###############################################################################
# Deploy Fleet Brain to pi-02
#
# This script deploys the complete fleet orchestration system to pi-02:
# - Model registry
# - Orchestrator
# - Health monitor
# - REST API server
# - Systemd services
# - CLI tools
###############################################################################

set -e

# Configuration
PI02_HOST="${PI02_HOST:-pi-02}"
PI02_USER="${PI02_USER:-pi}"
REMOTE_DIR="/home/pi/fleet-brain"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Fleet Brain Deployment to pi-02                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Pre-flight checks
echo -e "${YELLOW}🔍 Pre-flight checks...${NC}"

# Check if pi-02 is reachable
if ! ping -c 1 -W 2 "$PI02_HOST" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot reach pi-02 at $PI02_HOST${NC}"
    echo "   Check network connection or update PI02_HOST environment variable"
    exit 1
fi
echo -e "${GREEN}✓ pi-02 reachable${NC}"

# Check SSH access
if ! ssh -o ConnectTimeout=5 "${PI02_USER}@${PI02_HOST}" "echo ok" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot SSH to ${PI02_USER}@${PI02_HOST}${NC}"
    echo "   Set up SSH key authentication first"
    exit 1
fi
echo -e "${GREEN}✓ SSH access confirmed${NC}"

# Check required files
REQUIRED_FILES=(
    "fleet-model-registry.json"
    "orchestrator-model-mesh.cjs"
    "fleet-node-monitor.cjs"
    "pi02-orchestrator-api.cjs"
    "fleet-orchestrator-client.cjs"
    "fleet-cli.cjs"
    "fleet-hardware-prober.cjs"
    "fleet-auto-distributor.cjs"
    "fleet-deployment-planner.cjs"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$LOCAL_DIR/$file" ]; then
        echo -e "${RED}❌ Missing file: $file${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ All required files present${NC}"
echo ""

# Create remote directory
echo -e "${YELLOW}📁 Creating remote directory...${NC}"
ssh "${PI02_USER}@${PI02_HOST}" "mkdir -p $REMOTE_DIR"
echo -e "${GREEN}✓ Created $REMOTE_DIR${NC}"
echo ""

# Deploy files
echo -e "${YELLOW}📦 Deploying files to pi-02...${NC}"

FILES_TO_DEPLOY=(
    "fleet-model-registry.json"
    "orchestrator-model-mesh.cjs"
    "fleet-node-monitor.cjs"
    "pi02-orchestrator-api.cjs"
    "fleet-orchestrator-client.cjs"
    "fleet-cli.cjs"
    "fleet-hardware-prober.cjs"
    "fleet-auto-distributor.cjs"
    "fleet-deployment-planner.cjs"
    "fleet-usage-stats.json"
)

for file in "${FILES_TO_DEPLOY[@]}"; do
    if [ -f "$LOCAL_DIR/$file" ]; then
        echo -n "  Deploying $file... "
        scp -q "$LOCAL_DIR/$file" "${PI02_USER}@${PI02_HOST}:${REMOTE_DIR}/"
        echo -e "${GREEN}✓${NC}"
    fi
done

# Make scripts executable
echo -e "${YELLOW}🔧 Making scripts executable...${NC}"
ssh "${PI02_USER}@${PI02_HOST}" "chmod +x ${REMOTE_DIR}/*.cjs"
echo -e "${GREEN}✓ Scripts executable${NC}"
echo ""

# Check Node.js installation
echo -e "${YELLOW}🔍 Checking Node.js installation...${NC}"
if ssh "${PI02_USER}@${PI02_HOST}" "which node > /dev/null 2>&1"; then
    NODE_VERSION=$(ssh "${PI02_USER}@${PI02_HOST}" "node --version")
    echo -e "${GREEN}✓ Node.js installed: $NODE_VERSION${NC}"
else
    echo -e "${RED}❌ Node.js not found on pi-02${NC}"
    echo -e "${YELLOW}Installing Node.js...${NC}"
    ssh "${PI02_USER}@${PI02_HOST}" "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs"
    echo -e "${GREEN}✓ Node.js installed${NC}"
fi
echo ""

# Deploy systemd services
echo -e "${YELLOW}⚙️  Deploying systemd services...${NC}"

# Copy service files
if [ -d "$LOCAL_DIR/pi02-systemd-services" ]; then
    echo "  Copying service files..."
    ssh "${PI02_USER}@${PI02_HOST}" "sudo mkdir -p /tmp/fleet-services"
    scp -q "$LOCAL_DIR/pi02-systemd-services/"*.service "${PI02_USER}@${PI02_HOST}:/tmp/fleet-services/"

    # Install services
    ssh "${PI02_USER}@${PI02_HOST}" << 'EOF'
sudo mv /tmp/fleet-services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "  Services installed"
EOF
    echo -e "${GREEN}✓ Systemd services deployed${NC}"
else
    echo -e "${YELLOW}⚠️  Systemd services directory not found, skipping${NC}"
fi
echo ""

# Start services
echo -e "${YELLOW}🚀 Starting services...${NC}"

# Stop existing services if running
ssh "${PI02_USER}@${PI02_HOST}" << 'EOF'
if systemctl is-active --quiet fleet-brain-api.service; then
    sudo systemctl stop fleet-brain-api.service
    echo "  Stopped existing fleet-brain-api"
fi

if systemctl is-active --quiet fleet-health-monitor.service; then
    sudo systemctl stop fleet-health-monitor.service
    echo "  Stopped existing fleet-health-monitor"
fi
EOF

# Start services
ssh "${PI02_USER}@${PI02_HOST}" << 'EOF'
sudo systemctl start fleet-brain-api.service
sleep 2

if systemctl is-active --quiet fleet-brain-api.service; then
    echo "  ✓ fleet-brain-api.service started"
else
    echo "  ✗ fleet-brain-api.service failed to start"
    sudo journalctl -u fleet-brain-api.service -n 20 --no-pager
    exit 1
fi

sudo systemctl start fleet-health-monitor.service
sleep 2

if systemctl is-active --quiet fleet-health-monitor.service; then
    echo "  ✓ fleet-health-monitor.service started"
else
    echo "  ✗ fleet-health-monitor.service failed to start"
    sudo journalctl -u fleet-health-monitor.service -n 20 --no-pager
fi
EOF

echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Enable services on boot
echo -e "${YELLOW}🔄 Enabling services on boot...${NC}"
ssh "${PI02_USER}@${PI02_HOST}" << 'EOF'
sudo systemctl enable fleet-brain-api.service
sudo systemctl enable fleet-health-monitor.service
EOF
echo -e "${GREEN}✓ Services enabled${NC}"
echo ""

# Verify API is responding
echo -e "${YELLOW}🔍 Verifying API...${NC}"
sleep 3

if curl -s -m 5 "http://${PI02_HOST}:8080/status" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API is responding${NC}"
    echo ""
    echo -e "${BLUE}Fleet Brain Status:${NC}"
    curl -s "http://${PI02_HOST}:8080/status" | head -20
else
    echo -e "${RED}❌ API not responding${NC}"
    echo "   Check service logs:"
    echo "   ssh ${PI02_USER}@${PI02_HOST} sudo journalctl -u fleet-brain-api.service -f"
fi
echo ""

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Deployment Complete!                             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Fleet Brain API:${NC} http://${PI02_HOST}:8080"
echo ""
echo -e "${BLUE}Available endpoints:${NC}"
echo "  POST http://${PI02_HOST}:8080/route          - Route request"
echo "  GET  http://${PI02_HOST}:8080/models         - List models"
echo "  GET  http://${PI02_HOST}:8080/nodes          - List nodes"
echo "  GET  http://${PI02_HOST}:8080/status         - Fleet status"
echo "  POST http://${PI02_HOST}:8080/heartbeat      - Send heartbeat"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Register other nodes:"
echo "     ssh server-01 'cd /path/to/fleet && ./fleet-orchestrator-client.cjs auto-register'"
echo ""
echo "  2. Test routing:"
echo "     curl -X POST http://${PI02_HOST}:8080/route \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"capabilities\": [\"coding\"]}'"
echo ""
echo "  3. Monitor logs:"
echo "     ssh ${PI02_USER}@${PI02_HOST} sudo journalctl -u fleet-brain-api.service -f"
echo ""
echo -e "${BLUE}Service management:${NC}"
echo "  sudo systemctl status fleet-brain-api.service"
echo "  sudo systemctl status fleet-health-monitor.service"
echo "  sudo systemctl restart fleet-brain-api.service"
echo "  sudo journalctl -u fleet-brain-api.service -f"
echo ""
