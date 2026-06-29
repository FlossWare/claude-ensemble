#!/bin/bash
set -e

echo "🚀 MCP Fleet Orchestrator Deployment"
echo

# Pre-deployment checks
echo "Checking fleet workers..."
for worker in server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap; do
  ssh -o ConnectTimeout=2 claude@$worker echo "✅ $worker" 2>/dev/null || echo "❌ $worker"
done

echo "Checking PostgreSQL..."
psql -h laptop-01 -U sfloess -d learning -c "SELECT 1" >/dev/null 2>&1 && echo "✅ PostgreSQL" || echo "❌ PostgreSQL"

echo "Installing dependencies..."
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/mcp-servers/fleet-orchestrator
npm install

echo "✅ Deployment complete"
