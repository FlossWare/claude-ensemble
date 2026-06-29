#!/bin/bash
# Test script for migration 023_evaluation_schema.sql
# Usage: ./db/test-migration-023.sh [psql-connection-string]

set -e

# Default connection (can be overridden)
DB_HOST="${1:-localhost}"
DB_PORT="${2:-5432}"
DB_NAME="${3:-learning}"
DB_USER="${4:-sfloess}"

echo "Testing migration 023_evaluation_schema.sql"
echo "==========================================="
echo "Target: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "✗ psql command not found. Please install PostgreSQL client."
    exit 1
fi

# Test database connection
if ! psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT version();" > /dev/null 2>&1; then
    echo "✗ Cannot connect to PostgreSQL database."
    echo "  Connection string: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    exit 1
fi

echo "✓ Database connection successful"
echo ""

# Apply migration
echo "Applying migration..."
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -f "db/migrations/023_evaluation_schema.sql" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Migration applied successfully"
else
    echo "✗ Migration failed"
    exit 1
fi

echo ""
echo "Verifying schema..."

# Check if evaluation schema exists
SCHEMA_EXISTS=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c \
    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'evaluation';" 2>/dev/null)

if [ "$SCHEMA_EXISTS" = "1" ]; then
    echo "✓ Evaluation schema created"
else
    echo "✗ Evaluation schema not found"
    exit 1
fi

# Check if benchmarks table exists
BENCHMARKS_EXISTS=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'evaluation' AND table_name = 'benchmarks';" 2>/dev/null)

if [ "$BENCHMARKS_EXISTS" = "1" ]; then
    echo "✓ evaluation.benchmarks table created"
else
    echo "✗ evaluation.benchmarks table not found"
    exit 1
fi

# Check if results table exists
RESULTS_EXISTS=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'evaluation' AND table_name = 'results';" 2>/dev/null)

if [ "$RESULTS_EXISTS" = "1" ]; then
    echo "✓ evaluation.results table created"
else
    echo "✗ evaluation.results table not found"
    exit 1
fi

# Check materialized views
STATS_VIEW=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c \
    "SELECT COUNT(*) FROM pg_matviews WHERE matviewname = 'benchmark_stats' AND schemaname = 'evaluation';" 2>/dev/null)

if [ "$STATS_VIEW" = "1" ]; then
    echo "✓ evaluation.benchmark_stats materialized view created"
else
    echo "✗ evaluation.benchmark_stats view not found"
    exit 1
fi

echo ""
echo "✓ All migration checks passed!"
echo ""
echo "Next steps:"
echo "1. Load benchmark dataset: psql -d learning -c \"COPY evaluation.benchmarks (task_type, question, ground_truth, difficulty, category) FROM STDIN;\""
echo "2. Refresh materialized views: SELECT evaluation.refresh_materialized_views();"
echo "3. Query results: SELECT * FROM evaluation.model_performance;"
