#!/bin/bash
# RH Global Skills Toolkit Initialization
# Sourced at session start to activate all tools

export RH_TOOLS_ROOT="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
export RH_COST_LOG="$HOME/.claude/cost_tracking/cost.log"
export RH_MEMORY_DIR="$HOME/.claude/projects/-home-sfloess/memory"

# Add toolkit to PATH
export PATH="$RH_TOOLS_ROOT/tools:$PATH"

# Initialize cost tracking
mkdir -p "$(dirname "$RH_COST_LOG")"
touch "$RH_COST_LOG"

# Function: Log API usage to cost tracking
log_rh_cost() {
  local model=$1
  local input_tokens=$2
  local output_tokens=$3
  local cost=$4
  local workflow=${5:-"rh-work"}

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

with open("$RH_COST_LOG", "a") as f:
  f.write(json.dumps(entry) + "\n")
EOF
}

# Function: Get Thompson routing decision
get_rh_model() {
  local task_type=$1

  python3 "$RH_TOOLS_ROOT/shared/thompson_router.py" << EOF 2>/dev/null | grep "Selected:" | head -1 | awk '{print $NF}'
EOF
}

# Function: Compress prompt
compress_rh_prompt() {
  local prompt=$1
  python3 << EOF
from compression.compression_api import compress_prompt
result = compress_prompt("$prompt", target_reduction=0.35)
print(f"{result.text}")
EOF
}

# Connect to Memory Service (central memory authority for all sessions)
python3 "$RH_TOOLS_ROOT/memory-service/memory_client.py" 2>&1 | grep -E "✓|✗"

# Initialize Autonomous Learning (Thompson self-improvement)
python3 "$RH_TOOLS_ROOT/tools/autonomous-learner.py" 2>&1 | grep "✓\|✗"

# Discover latest models at session start (background)
python3 "$RH_TOOLS_ROOT/tools/discover-models.py" > /dev/null 2>&1 &

echo "✓ RH Global Skills Toolkit initialized"
echo "  Tools: caching, compression, cost_tracking, ga_tuning, thompson_router, arbitration"
echo "  Cost logging: $RH_COST_LOG"
echo "  Memory: $RH_MEMORY_DIR"
echo "  Model discovery: running in background"
echo "  Arbitration: multi-phase orchestrator for critical decisions"
echo "  Autonomous learning: Thompson continuously improving from real tasks"
