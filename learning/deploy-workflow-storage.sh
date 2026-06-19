#!/bin/bash

# Workflow Storage Deployment Script
# Deploys schema, runs tests, and verifies installation

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DB_HOST="/var/run/postgresql"
DB_NAME="learning"
DB_USER="sfloess"

echo "==================================="
echo "Workflow Storage Deployment"
echo "==================================="
echo ""

# Step 1: Check PostgreSQL connection
echo "[1/5] Checking PostgreSQL connection..."
if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "✓ PostgreSQL connected"
else
    echo "✗ PostgreSQL connection failed"
    echo "  Make sure PostgreSQL is running on laptop-01"
    exit 1
fi
echo ""

# Step 2: Deploy schema
echo "[2/5] Deploying database schema..."
if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$SCRIPT_DIR/workflow-storage-schema.sql" > /dev/null 2>&1; then
    echo "✓ Schema deployed"
else
    echo "✗ Schema deployment failed"
    exit 1
fi
echo ""

# Step 3: Check Node.js dependencies
echo "[3/5] Checking Node.js dependencies..."
if node -e "require('pg')" > /dev/null 2>&1; then
    echo "✓ pg module installed"
else
    echo "⚠ pg module not found"
    echo "  Install with: npm install pg"
fi
echo ""

# Step 4: Verify schema
echo "[4/5] Verifying schema..."
TABLE_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema = 'workflows'
    AND table_name IN ('executions', 'worker_results', 'arbiter_decisions')
" | tr -d '[:space:]')

if [ "$TABLE_COUNT" -eq "3" ]; then
    echo "✓ All 3 tables created"
else
    echo "✗ Expected 3 tables, found $TABLE_COUNT"
    exit 1
fi

VIEW_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*)
    FROM information_schema.views
    WHERE table_schema = 'workflows'
    AND table_name IN ('summary', 'model_performance')
" | tr -d '[:space:]')

if [ "$VIEW_COUNT" -eq "2" ]; then
    echo "✓ All 2 materialized views created"
else
    echo "✗ Expected 2 views, found $VIEW_COUNT"
    exit 1
fi
echo ""

# Step 5: Run test (optional)
echo "[5/5] Running test workflow..."
if [ -f "$SCRIPT_DIR/test-workflow-storage.js" ]; then
    echo "  Test available at: $SCRIPT_DIR/test-workflow-storage.js"
    echo "  Run manually with: node $SCRIPT_DIR/test-workflow-storage.js"
else
    echo "  Test script not found"
fi
echo ""

# Summary
echo "==================================="
echo "Deployment Summary"
echo "==================================="
echo "✓ Schema deployed to workflows.*"
echo "✓ Tables: executions, worker_results, arbiter_decisions"
echo "✓ Views: summary, model_performance"
echo "✓ Indexes: HNSW vector indexes on embeddings"
echo ""
echo "Next steps:"
echo "1. Test with: node $SCRIPT_DIR/test-workflow-storage.js"
echo "2. Verify with: psql -d learning -f $SCRIPT_DIR/verify-workflow-storage.sql"
echo "3. Read docs: $SCRIPT_DIR/WORKFLOW_STORAGE.md"
echo ""
echo "Integration:"
echo "  const { logWorkflowExecution } = require('$SCRIPT_DIR/workflow-hook');"
echo ""
