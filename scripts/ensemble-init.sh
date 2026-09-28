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

# Discover latest models at session start (background)
python3 "$ENSEMBLE_ROOT/tools/discover-models.py" > /dev/null 2>&1 &

echo "✓ Claude Ensemble Toolkit initialized"
echo "  Tools: caching, compression, cost_tracking, ga_tuning, thompson_router, arbitration"
echo "  Cost logging: $ENSEMBLE_COST_LOG"
echo "  Memory: $ENSEMBLE_MEMORY_DIR"
echo "  Model discovery: running in background"
echo "  Arbitration: multi-phase orchestrator for critical decisions"
echo "  Autonomous learning: Thompson continuously improving from real tasks"
