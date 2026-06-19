#!/bin/bash
#
# Setup Workflows Schema in PostgreSQL
# Creates tables, indexes, and views for workflow learning integration
#
# Usage:
#   ./setup-workflows-schema.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="${SCRIPT_DIR}/schemas/workflows_schema.sql"
DB_NAME="learning"
DB_USER="${USER}"

echo "================================================================================"
echo "Workflows Schema Setup"
echo "================================================================================"
echo ""
echo "Database: ${DB_NAME}"
echo "User: ${DB_USER}"
echo "Schema file: ${SCHEMA_FILE}"
echo ""

# Check if schema file exists
if [ ! -f "${SCHEMA_FILE}" ]; then
  echo "ERROR: Schema file not found: ${SCHEMA_FILE}"
  exit 1
fi

# Check if PostgreSQL is accessible
if ! psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1" &>/dev/null; then
  echo "ERROR: Cannot connect to PostgreSQL database '${DB_NAME}' as user '${DB_USER}'"
  echo ""
  echo "Troubleshooting:"
  echo "  1. Check if PostgreSQL is running:"
  echo "     sudo systemctl status postgresql"
  echo ""
  echo "  2. Check if database exists:"
  echo "     psql -U ${DB_USER} -l | grep ${DB_NAME}"
  echo ""
  echo "  3. Check peer authentication (should use Unix socket):"
  echo "     grep 'local.*all.*all.*peer' /var/lib/pgsql/data/pg_hba.conf"
  echo ""
  exit 1
fi

echo "PostgreSQL connection verified ✓"
echo ""

# Check if workflows schema already exists
if psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'workflows'" | grep -q workflows; then
  echo "WARNING: workflows schema already exists"
  echo ""
  read -p "Do you want to drop and recreate it? (yes/no): " -r
  echo ""
  if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Dropping existing workflows schema..."
    psql -U "${DB_USER}" -d "${DB_NAME}" -c "DROP SCHEMA workflows CASCADE;" 2>&1 | grep -v "does not exist" || true
    echo "Dropped ✓"
    echo ""
  else
    echo "Aborting setup"
    exit 0
  fi
fi

# Execute schema creation
echo "Creating workflows schema..."
psql -U "${DB_USER}" -d "${DB_NAME}" -f "${SCHEMA_FILE}"

echo ""
echo "Schema created ✓"
echo ""

# Verify tables created
echo "Verifying tables..."
TABLE_COUNT=$(psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'workflows'")
TABLE_COUNT=$(echo "${TABLE_COUNT}" | xargs)  # Trim whitespace

if [ "${TABLE_COUNT}" -eq 0 ]; then
  echo "ERROR: No tables found in workflows schema"
  exit 1
fi

echo "Found ${TABLE_COUNT} tables in workflows schema ✓"
echo ""

# List tables
echo "Tables created:"
psql -U "${DB_USER}" -d "${DB_NAME}" -c "\dt workflows.*"
echo ""

# List views
echo "Views created:"
psql -U "${DB_USER}" -d "${DB_NAME}" -c "\dv workflows.*"
echo ""

# Verify indexes
echo "Indexes created:"
psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT schemaname, tablename, indexname FROM pg_indexes WHERE schemaname = 'workflows' ORDER BY tablename, indexname;"
echo ""

# Test insert (and rollback)
echo "Testing insert/rollback..."
psql -U "${DB_USER}" -d "${DB_NAME}" -c "
BEGIN;
INSERT INTO workflows.learnings (run_id, workflow_name, learning_type, task_type, outcome)
VALUES ('test_run_123', 'test-workflow', 'model_behavior', 'test', 'success');
SELECT COUNT(*) AS inserted_count FROM workflows.learnings WHERE run_id = 'test_run_123';
ROLLBACK;
" | grep -q "inserted_count" && echo "Insert test passed ✓" || echo "Insert test failed ✗"

echo ""
echo "================================================================================"
echo "Setup Complete"
echo "================================================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Test the integration:"
echo "     cd ${SCRIPT_DIR}/../workflows/examples"
echo "     node reaction-tracker-integration-example.js"
echo ""
echo "  2. Query the views:"
echo "     psql -U ${DB_USER} -d ${DB_NAME} -c 'SELECT * FROM workflows.performance_summary;'"
echo ""
echo "  3. View the documentation:"
echo "     cat ${SCRIPT_DIR}/../workflows/REACTION_TRACKER_POSTGRES_INTEGRATION.md"
echo ""
echo "================================================================================"
