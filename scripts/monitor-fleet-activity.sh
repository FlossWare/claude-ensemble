#!/bin/bash
#
# Monitor what's running on each fleet worker
# Shows: Node processes, API activity, recent SSH connections
#

WORKERS=(server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap)

echo "🔍 Fleet Activity Monitor"
echo "=========================="
echo

for worker in "${WORKERS[@]}"; do
  echo "=== $worker ==="

  # Check if online
  if ! ssh -o ConnectTimeout=2 claude@$worker echo ping &>/dev/null; then
    echo "   ❌ OFFLINE"
    echo
    continue
  fi

  # Get load average
  load=$(ssh claude@$worker "uptime | awk -F'load average:' '{print \$2}' | awk '{print \$1}'" 2>/dev/null)
  echo "   Load: ${load:-N/A}"

  # Check for active Node.js processes (excluding system services)
  node_procs=$(ssh claude@$worker "ps aux | grep -E 'node.*claude-global-skills' | grep -v grep | wc -l" 2>/dev/null)
  if [[ "$node_procs" -gt 0 ]]; then
    echo "   🟢 Node processes: $node_procs"
    ssh claude@$worker "ps aux | grep -E 'node.*claude-global-skills' | grep -v grep | awk '{print \"      \"substr(\$0, index(\$0,\$11))}' | head -3" 2>/dev/null
  else
    echo "   ⚪ No active tasks"
  fi

  # Check recent SSH connections from aio-01
  recent_ssh=$(ssh claude@$worker "last -n 5 -F | grep 'aio-01' | wc -l" 2>/dev/null || echo "0")
  if [[ "$recent_ssh" -gt 0 ]]; then
    echo "   📡 Recent SSH from aio-01: $recent_ssh connections"
  fi

  echo
done

echo "=========================="
echo "Summary: ${#WORKERS[@]} workers checked"
