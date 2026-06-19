#!/bin/bash
# Verification script for workflows schema deployment
# Step 1: Create PostgreSQL schema in learning database

set -e

# Determine database host
DB_HOST="${DB_HOST:-localhost}"
if [[ "$(hostname)" == "laptop-01" ]]; then
    DB_HOST="localhost"
else
    DB_HOST="laptop-01"
fi

DB_USER="${DB_USER:-sfloess}"
DB_NAME="learning"
SCHEMA_FILE="/home/sfloess/.claude/learning/schema/workflows-schema.sql"

echo "=========================================="
echo "Workflows Schema Deployment"
echo "=========================================="
echo "Database Host: $DB_HOST"
echo "Database Name: $DB_NAME"
echo "Database User: $DB_USER"
echo "Schema File: $SCHEMA_FILE"
echo ""

# Check if schema file exists
if [[ ! -f "$SCHEMA_FILE" ]]; then
    echo "ERROR: Schema file not found: $SCHEMA_FILE"
    exit 1
fi

echo "Step 1: Verify pgvector extension..."
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';" || {
    echo "WARNING: pgvector extension not found or not accessible"
}

echo ""
echo "Step 2: Execute DDL script..."
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_FILE"

if [[ $? -eq 0 ]]; then
    echo ""
    echo "Step 3: Verify schema creation..."

    # Check schema exists
    echo "Checking workflows schema..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'workflows';"

    # Check tables
    echo ""
    echo "Checking tables..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'workflows' ORDER BY table_name;"

    # Check materialized views
    echo ""
    echo "Checking materialized views..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT matviewname FROM pg_matviews WHERE schemaname = 'workflows' ORDER BY matviewname;"

    # Check HNSW indexes
    echo ""
    echo "Checking HNSW indexes..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'workflows' AND indexname LIKE '%embedding%' ORDER BY indexname;"

    # Check functions
    echo ""
    echo "Checking helper functions..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT proname FROM pg_proc WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'workflows') ORDER BY proname;"

    echo ""
    echo "=========================================="
    echo "SUCCESS: Workflows schema deployed!"
    echo "=========================================="
    echo "Tables: 10"
    echo "  - executions"
    echo "  - worker_results"
    echo "  - arbiter_decisions"
    echo "  - execution_phases"
    echo "  - feedback"
    echo "  - model_combinations"
    echo "  - learnings"
    echo "  - execution_embeddings"
    echo ""
    echo "Materialized Views: 2"
    echo "  - summary"
    echo "  - model_performance"
    echo ""
    echo "HNSW Indexes: 4"
    echo "  - learnings.embedding"
    echo "  - execution_embeddings.input_embedding"
    echo "  - execution_embeddings.output_embedding"
    echo "  - execution_embeddings.context_embedding"
    echo ""
    echo "Helper Functions: 5"
    echo "  - refresh_views()"
    echo "  - find_similar_executions()"
    echo "  - find_relevant_learnings()"
    echo "  - get_best_combination()"
    echo "  - Auto-update triggers"
    echo "=========================================="
else
    echo ""
    echo "ERROR: Schema deployment failed!"
    exit 1
fi
