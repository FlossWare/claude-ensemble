#!/bin/bash
# Claude Ensemble Toolkit Initialization
# Sourced at session start to activate all tools

export ENSEMBLE_ROOT="$HOME/Development/FlossWare/claude-ensemble"
export ENSEMBLE_COST_LOG="$HOME/.claude/cost_tracking/cost.log"
export ENSEMBLE_MEMORY_DIR="$HOME/.claude/projects/memory"

# Add toolkit to PATH
export PATH="$ENSEMBLE_ROOT/tools:$PATH"

# Initialize cost tracking
mkdir -p "$(dirname "$ENSEMBLE_COST_LOG")"
touch "$ENSEMBLE_COST_LOG"

# Shell functions for easy memory access
query_memory() {
  python3 "$ENSEMBLE_ROOT/tools/query-memory.py" "$@"
}

mem_list() {
  echo "=== Project Memory Files ==="
  python3 "$ENSEMBLE_ROOT/tools/query-memory.py" list
}

mem_read() {
  if [ -z "$1" ]; then
    echo "Usage: mem_read <name>"
    return 1
  fi
  python3 "$ENSEMBLE_ROOT/tools/query-memory.py" read "$1"
}

mem_search() {
  if [ -z "$1" ]; then
    echo "Usage: mem_search <keyword>"
    return 1
  fi
  python3 "$ENSEMBLE_ROOT/tools/query-memory.py" search "$1"
}

# Save learning immediately (not just at session end)
save_learning() {
  local title="$1"
  local detail="$2"

  if [ -z "$title" ]; then
    echo "Usage: save_learning '<title>' '<detail>'"
    return 1
  fi

  python3 << EOF
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ensemble_root = os.getenv('ENSEMBLE_ROOT', '')
if not ensemble_root:
    sys.exit(1)

sys.path.insert(0, str(Path(ensemble_root) / 'memory-service'))

try:
    from memory_client import MemoryClient

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "title": "$title",
        "detail": "$detail"
    }

    client = MemoryClient()
    if client.connect():
        client.append('session_learnings', entry)
        print("✓ Learning saved to memory service")
    else:
        print("⚠ Memory service unavailable (will save at session end)")
except:
    print("⚠ Could not save learning")
EOF
}

# Save architecture decision immediately
save_architecture() {
  local decision="$1"

  if [ -z "$decision" ]; then
    echo "Usage: save_architecture '<decision>'"
    return 1
  fi

  python3 << EOF
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ensemble_root = os.getenv('ENSEMBLE_ROOT', '')
if not ensemble_root:
    sys.exit(1)

sys.path.insert(0, str(Path(ensemble_root) / 'memory-service'))

try:
    from memory_client import MemoryClient

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "decision": "$decision"
    }

    client = MemoryClient()
    if client.connect():
        client.append('architecture_decisions', entry)
        print("✓ Architecture decision saved")
except:
    pass
EOF
}

# Function: Log API usage to cost tracking
log_ensemble_cost() {
  local model=$1
  local input_tokens=$2
  local output_tokens=$3
  local cost=$4
  local workflow=${5:-"ensemble-work"}

  python3 << EOF
import json
from datetime import datetime

entry = {
  "timestamp": datetime.utcnow().isoformat(),
  "model": "$model",
  "provider": "anthropic",
  "input_tokens": $input_tokens,
  "output_tokens": $output_tokens,
  "total_cost_usd": $cost,
  "workflow_id": "$workflow"
}

with open("$ENSEMBLE_COST_LOG", "a") as f:
  f.write(json.dumps(entry) + "\n")
EOF
}

# Function: Get Thompson routing decision
get_ensemble_model() {
  local task_type=$1

  python3 "$ENSEMBLE_ROOT/shared/thompson_router.py" << EOF 2>/dev/null | grep "Selected:" | head -1 | awk '{print $NF}'
EOF
}

# Function: Compress prompt
compress_ensemble_prompt() {
  local prompt=$1
  python3 << EOF
from compression.compression_api import compress_prompt
result = compress_prompt("$prompt", target_reduction=0.35)
print(f"{result.text}")
EOF
}

# Connect to Memory Service (central memory authority for all sessions)
python3 "$ENSEMBLE_ROOT/memory-service/memory_client.py" 2>&1 | grep -E "✓|✗" || true

# Initialize Autonomous Learning (Thompson self-improvement)
python3 "$ENSEMBLE_ROOT/tools/autonomous-learner.py" 2>&1 | grep "✓\|✗" || true

# Discover latest models only once per day (not on every session)
mkdir -p "$ENSEMBLE_MEMORY_DIR"
LAST_DISCOVERY="$ENSEMBLE_MEMORY_DIR/.last_model_discovery"
if [ ! -f "$LAST_DISCOVERY" ] || [ $(( $(date +%s) - $(stat -c %Y "$LAST_DISCOVERY" 2>/dev/null || echo 0) )) -gt 86400 ]; then
    python3 "$ENSEMBLE_ROOT/tools/discover-models.py" > /dev/null 2>&1 &
    disown $! 2>/dev/null || true
    touch "$LAST_DISCOVERY" 2>/dev/null || true
fi

echo "✓ Claude Ensemble Toolkit initialized"
echo "  Tools: caching, compression, cost_tracking, ga_tuning, thompson_router, arbitration"
echo "  Cost logging: $ENSEMBLE_COST_LOG"
echo "  Memory: $ENSEMBLE_MEMORY_DIR"
echo "  Model discovery: running in background"
echo "  Arbitration: multi-phase orchestrator for critical decisions"
echo "  Autonomous learning: Thompson continuously improving from real tasks"

# Display available memories at session start
python3 << 'MEMORY_STATUS'
import sys
import os
from pathlib import Path

ensemble_root = os.getenv('ENSEMBLE_ROOT', '')
if not ensemble_root:
    sys.exit(0)

sys.path.insert(0, str(Path(ensemble_root) / 'memory-service'))

try:
    from memory_client import MemoryClient
    client = MemoryClient()
    if client.connect():
        memories = sorted([m for m in client.list() if m != 'MEMORY'])
        if memories:
            print("\n📚 Project Memory Available:")
            for mem in memories[:8]:
                print(f"   • {mem}")
            if len(memories) > 8:
                print(f"   ... and {len(memories) - 8} more")
            print("   Use: mem_search <keyword> | mem_read <name>")
except:
    pass
MEMORY_STATUS

