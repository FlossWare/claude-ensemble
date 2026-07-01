#!/bin/bash
# Deploy worker daemon to all fleet workers (replaces SSH)

WORKERS="server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap"
AUTH_TOKEN="${WORKER_AUTH_TOKEN:-$(openssl rand -hex 16)}"

echo "=== Deploying Worker Daemon to Fleet ==="
echo "Auth token: ***${AUTH_TOKEN: -4}"
echo ""

for host in $WORKERS; do
  echo "Deploying to $host..."
  
  # Deploy worker daemon
  scp shared/worker-daemon.py claude@$host:~/
  
  # Deploy systemd service
  ssh claude@$host "
    sudo tee /etc/systemd/system/worker-daemon.service > /dev/null << 'EOF'
[Unit]
Description=Worker Daemon (HTTP-based fleet worker)
After=network.target

[Service]
Type=simple
User=claude
WorkingDirectory=/home/claude
ExecStart=/usr/bin/python3 /home/claude/worker-daemon.py
Restart=always
RestartSec=5

Environment=\"WORKER_AUTH_TOKEN=$AUTH_TOKEN\"

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable worker-daemon
    sudo systemctl restart worker-daemon
    echo '✓ Worker daemon deployed and started on $host'
  " 2>&1 | grep -v 'Warning\|stdin'
done

echo ""
echo "=== Testing all workers ==="
for host in $WORKERS; do
  status=$(curl -s http://$host:8003/health | jq -r '.status' 2>/dev/null || echo "FAILED")
  echo "$host: $status"
done

echo ""
echo "✓ Worker daemon deployment complete!"
echo ""
echo "Set this in your environment:"
echo "  export WORKER_AUTH_TOKEN='$AUTH_TOKEN'"
