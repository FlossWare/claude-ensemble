#!/bin/bash
# Model Profiling Helper Script
# Profiles models in batches to build capability database

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Model Capability Profiling ==="
echo ""

# Parse arguments
MODE=${1:-help}
COUNT=${2:-10}

case "$MODE" in
  quick)
    echo "Quick profile: Top 10 high-value models"
    echo ""
    node "$PROJECT_DIR/workflows/profile-model-capabilities.mjs" \
      --count=10 \
      --parallel
    ;;

  tier1)
    echo "Tier 1 profile: Top 50 models (large, code specialists, reasoning)"
    echo "Estimated time: ~10 hours across fleet"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      node "$PROJECT_DIR/workflows/profile-model-capabilities.mjs" \
        --count=50 \
        --parallel
    fi
    ;;

  provider)
    PROVIDER=${2:-mistral}
    echo "Profiling all $PROVIDER models"
    echo ""
    node "$PROJECT_DIR/workflows/profile-model-capabilities.mjs" \
      --provider="$PROVIDER" \
      --parallel
    ;;

  single)
    MODEL=${2}
    if [ -z "$MODEL" ]; then
      echo "Usage: $0 single <model_id>"
      echo "Example: $0 single qwen/qwen3-coder:free"
      exit 1
    fi
    echo "Profiling single model: $MODEL"
    echo ""
    node "$PROJECT_DIR/workflows/profile-model-capabilities.mjs" \
      --model="$MODEL"
    ;;

  batch)
    echo "Batch profile: $COUNT models"
    echo ""
    node "$PROJECT_DIR/workflows/profile-model-capabilities.mjs" \
      --count=$COUNT \
      --parallel
    ;;

  status)
    echo "Checking profiling status..."
    echo ""
    psql -h aio-01 -p 5433 -U sfloess -d learning << 'EOF'
SELECT
  'Total free models' as metric,
  COUNT(*)::text as value
FROM learning.free_models
UNION ALL
SELECT
  'Models with capabilities',
  COUNT(*)::text
FROM learning.model_capabilities
UNION ALL
SELECT
  'Coverage percentage',
  ROUND(
    ((SELECT COUNT(*)::float FROM learning.model_capabilities) /
    (SELECT COUNT(*)::float FROM learning.free_models) * 100)::numeric,
    1
  )::text || '%';

\echo ''
\echo 'Breakdown by provider:'

SELECT
  fm.provider,
  COUNT(DISTINCT fm.model_id) as total_models,
  COUNT(DISTINCT mc.model_id) as profiled,
  ROUND(
    (COUNT(DISTINCT mc.model_id)::float /
    COUNT(DISTINCT fm.model_id)::float * 100)::numeric,
    1
  ) as coverage_pct
FROM learning.free_models fm
LEFT JOIN learning.model_capabilities mc ON fm.model_id = mc.model_id
GROUP BY fm.provider
ORDER BY total_models DESC;
EOF
    ;;

  top)
    echo "Top models by capability:"
    echo ""
    psql -h aio-01 -p 5433 -U sfloess -d learning << 'EOF'
\echo 'Top 10 code generation:'
SELECT
  model_id,
  provider,
  ROUND(code_generation::numeric, 3) as score,
  avg_latency_ms
FROM learning.model_capabilities
WHERE code_generation IS NOT NULL
ORDER BY code_generation DESC
LIMIT 10;

\echo ''
\echo 'Top 10 general QA:'
SELECT
  model_id,
  provider,
  ROUND(general_qa::numeric, 3) as score,
  avg_latency_ms
FROM learning.model_capabilities
WHERE general_qa IS NOT NULL
ORDER BY general_qa DESC
LIMIT 10;
EOF
    ;;

  help|*)
    cat << 'HELP'
Model Profiling Helper

Usage:
  ./scripts/profile-models.sh <command> [options]

Commands:
  quick              Profile top 10 high-value models (~2 hours)
  tier1              Profile top 50 models (~10 hours)
  provider <name>    Profile all models from a provider
  single <model_id>  Profile a specific model
  batch <count>      Profile N models (default: 10)
  status             Show profiling coverage status
  top                Show top models by capability
  help               Show this help

Examples:
  ./scripts/profile-models.sh quick
  ./scripts/profile-models.sh provider mistral
  ./scripts/profile-models.sh single qwen/qwen3-coder:free
  ./scripts/profile-models.sh batch 25
  ./scripts/profile-models.sh status

Notes:
  - Profiling uses Opus to evaluate model responses
  - Parallel mode uses fleet workers (faster but costs more)
  - Results are stored in learning.model_capabilities
  - Profiling ~15 min per model (5 tasks × 3 min each)
HELP
    ;;
esac
