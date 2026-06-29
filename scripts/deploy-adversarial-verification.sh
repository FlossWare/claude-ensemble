#!/bin/bash

##
## Adversarial Verification System - Deployment Script
##
## Deploys the adversarial verification infrastructure to PostgreSQL
## and validates the installation.
##
## Usage: ./scripts/deploy-adversarial-verification.sh
##

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCHEMA_FILE="$PROJECT_ROOT/db/schema/adversarial-verifications.sql"

# PostgreSQL connection details
PGHOST="${PGHOST:-aio-01}"
PGPORT="${PGPORT:-5433}"
PGDATABASE="${PGDATABASE:-learning}"
PGUSER="${PGUSER:-$USER}"

echo "========================================"
echo "Adversarial Verification Deployment"
echo "========================================"
echo ""
echo "PostgreSQL connection:"
echo "  Host: $PGHOST"
echo "  Port: $PGPORT"
echo "  Database: $PGDATABASE"
echo "  User: $PGUSER"
echo ""

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
  echo "❌ ERROR: Schema file not found: $SCHEMA_FILE"
  exit 1
fi

echo "✅ Schema file found: $SCHEMA_FILE"
echo ""

# Check PostgreSQL connectivity
echo "🔍 Testing PostgreSQL connectivity..."
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "SELECT 1;" > /dev/null 2>&1; then
  echo "❌ ERROR: Cannot connect to PostgreSQL"
  echo ""
  echo "Troubleshooting:"
  echo "  1. Check if PostgreSQL is running:"
  echo "     systemctl status postgresql"
  echo ""
  echo "  2. Verify connection details:"
  echo "     psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE"
  echo ""
  echo "  3. Set environment variables if needed:"
  echo "     export PGHOST=aio-01"
  echo "     export PGPORT=5433"
  echo "     export PGDATABASE=learning"
  echo ""
  exit 1
fi

echo "✅ PostgreSQL connectivity OK"
echo ""

# Check if workflow schema exists
echo "🔍 Checking for workflow schema..."
SCHEMA_EXISTS=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
  "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'workflow';" | xargs)

if [ "$SCHEMA_EXISTS" -eq 0 ]; then
  echo "⚠️  WARNING: workflow schema does not exist"
  echo "   Creating workflow schema..."
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c \
    "CREATE SCHEMA IF NOT EXISTS workflow;"
  echo "✅ Workflow schema created"
else
  echo "✅ Workflow schema exists"
fi
echo ""

# Check if workflow.executions table exists (dependency)
echo "🔍 Checking for workflow.executions table..."
EXECUTIONS_EXISTS=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'workflow' AND table_name = 'executions';" | xargs)

if [ "$EXECUTIONS_EXISTS" -eq 0 ]; then
  echo "⚠️  WARNING: workflow.executions table does not exist"
  echo "   This is required for adversarial_verifications foreign key."
  echo ""
  echo "   Run this first to create workflow storage tables:"
  echo "   psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f db/schema/workflow-storage.sql"
  echo ""
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
else
  echo "✅ workflow.executions table exists"
fi
echo ""

# Deploy schema
echo "📦 Deploying adversarial verification schema..."
if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$SCHEMA_FILE"; then
  echo "✅ Schema deployed successfully"
else
  echo "❌ ERROR: Schema deployment failed"
  exit 1
fi
echo ""

# Validate deployment
echo "🔍 Validating deployment..."

# Check if table exists
TABLE_EXISTS=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'workflow' AND table_name = 'adversarial_verifications';" | xargs)

if [ "$TABLE_EXISTS" -eq 0 ]; then
  echo "❌ ERROR: adversarial_verifications table was not created"
  exit 1
fi

echo "✅ adversarial_verifications table created"

# Check if materialized view exists
VIEW_EXISTS=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
  "SELECT COUNT(*) FROM pg_matviews WHERE schemaname = 'workflow' AND matviewname = 'adversarial_stats';" | xargs)

if [ "$VIEW_EXISTS" -eq 0 ]; then
  echo "❌ ERROR: adversarial_stats materialized view was not created"
  exit 1
fi

echo "✅ adversarial_stats materialized view created"

# Count indexes
INDEX_COUNT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
  "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'workflow' AND tablename = 'adversarial_verifications';" | xargs)

echo "✅ Created $INDEX_COUNT indexes on adversarial_verifications"

# Test insert (and rollback)
echo ""
echo "🧪 Testing insert..."
TEST_RESULT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c "
BEGIN;
INSERT INTO workflow.adversarial_verifications
  (workflow_execution_id, answer_candidate, original_task, verdict, confidence,
   refuters_failed, refuters_total, votes, cost_usd, duration_ms)
VALUES (1, 'test answer', 'test task', 'ACCEPT', 'high', 3, 3, '[]'::jsonb, 0, 100)
RETURNING id;
ROLLBACK;
" 2>&1)

if [[ "$TEST_RESULT" =~ ^[0-9]+$ ]]; then
  echo "✅ Test insert successful (rolled back)"
else
  echo "⚠️  Test insert returned unexpected result: $TEST_RESULT"
fi

echo ""
echo "========================================"
echo "✅ Deployment Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Test with example workflow:"
echo "   node workflows/deep-research-with-adversarial.mjs \"What is quantum computing?\""
echo ""
echo "2. Integrate into existing workflows:"
echo "   See: docs/adversarial-verification-integration.md"
echo ""
echo "3. Monitor results:"
echo "   psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c \\"
echo "     \"SELECT * FROM workflow.adversarial_stats;\""
echo ""
echo "4. View recent verifications:"
echo "   psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c \\"
echo "     \"SELECT verdict, confidence, cost_usd, created_at \\"
echo "      FROM workflow.adversarial_verifications \\"
echo "      ORDER BY created_at DESC LIMIT 10;\""
echo ""
echo "Documentation:"
echo "  - Summary: ADVERSARIAL_VERIFICATION_SUMMARY.md"
echo "  - Integration: docs/adversarial-verification-integration.md"
echo "  - Architecture: docs/adversarial-verification-architecture.md"
echo ""
