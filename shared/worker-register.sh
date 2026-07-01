#!/bin/bash
# Worker Auto-Registration Client
# Runs on each worker node, registers with aio-01:8002 on startup
# Then sends heartbeat every 60 seconds

REGISTRY_URL="http://aio-01:8002"
HOSTNAME=$(hostname)
IP_ADDRESS=$(hostname -I | awk '{print $1}')
CPU_CORES=$(nproc)
RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
ARCH=$(uname -m)

# Detect roles based on hostname
case "$HOSTNAME" in
  pi-*)
    ROLES='["worker", "lightweight"]'
    CAPABILITIES='["api-only"]'
    ;;
  server-*)
    ROLES='["worker", "compute"]'
    CAPABILITIES='["api-only", "high-cpu"]'
    ;;
  laptop-*)
    ROLES='["worker", "compute"]'
    CAPABILITIES='["api-only", "high-memory"]'
    ;;
  desktop-*)
    ROLES='["worker", "compute"]'
    CAPABILITIES='["api-only"]'
    ;;
  *)
    ROLES='["worker"]'
    CAPABILITIES='["api-only"]'
    ;;
esac

register() {
  curl -s -X POST "$REGISTRY_URL/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"hostname\": \"$HOSTNAME\",
      \"ip_address\": \"$IP_ADDRESS\",
      \"cpu_cores\": $CPU_CORES,
      \"ram_gb\": $RAM_GB,
      \"architecture\": \"$ARCH\",
      \"roles\": $ROLES,
      \"capabilities\": $CAPABILITIES
    }" | grep -q '"status":"registered"' && echo "✓ Registered $HOSTNAME" || echo "✗ Registration failed"
}

heartbeat() {
  curl -s -X POST "$REGISTRY_URL/heartbeat/$HOSTNAME" | grep -q '"status":"ok"'
}

# Initial registration
register

# Heartbeat loop (runs in background)
while true; do
  sleep 60
  heartbeat || {
    echo "⚠ Heartbeat failed, re-registering..."
    register
  }
done
