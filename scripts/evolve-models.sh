#!/bin/bash
# Run genetic algorithm to evolve model-task mappings
# Uses REAL execution data from monitoring.execution_summary

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Genetic Algorithm Model Optimizer ==="
echo ""
echo "This will:"
echo "  1. Load execution history from PostgreSQL"
echo "  2. Evolve 30 strategies over 50 generations"
echo "  3. Store best strategy in learning.model_capabilities"
echo ""
echo "Expected runtime: 5-10 minutes"
echo "Uses: 0 API calls (all local computation)"
echo ""

# Check dependencies
if ! python3 -c "import numpy" 2>/dev/null; then
    echo "Installing numpy..."
    pip3 install --user numpy
fi

if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "Installing psycopg2..."
    pip3 install --user psycopg2-binary
fi

# Run GA
echo "Starting evolution..."
python3 tools/genetic_model_optimizer.py

echo ""
echo "✅ Evolution complete!"
echo ""
echo "Check results:"
echo "  psql -h aio-01 -p 5433 -U sfloess -d learning -c \\"
echo "    'SELECT model_id, code_generation, code_review, research, notes"
echo "     FROM learning.model_capabilities"
echo "     WHERE notes LIKE '%GA evolved%'"
echo "     ORDER BY (code_generation + code_review + research)/3 DESC LIMIT 10;'"
