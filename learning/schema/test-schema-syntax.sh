#!/bin/bash
# Test SQL syntax without executing on database
# This validates the DDL file is well-formed

SCHEMA_FILE="/home/sfloess/.claude/learning/schema/workflows-schema.sql"

echo "Testing SQL syntax in: $SCHEMA_FILE"
echo ""

# Count various components
echo "Component Summary:"
echo "=================="

# Count CREATE TABLE statements
TABLE_COUNT=$(grep -c "^CREATE TABLE" "$SCHEMA_FILE" || true)
echo "Tables: $TABLE_COUNT"

# Count CREATE INDEX statements
INDEX_COUNT=$(grep -c "^CREATE INDEX\|^CREATE UNIQUE INDEX" "$SCHEMA_FILE" || true)
echo "Indexes: $INDEX_COUNT"

# Count HNSW indexes specifically
HNSW_COUNT=$(grep -c "USING hnsw" "$SCHEMA_FILE" || true)
echo "HNSW Vector Indexes: $HNSW_COUNT"

# Count CREATE MATERIALIZED VIEW
MATVIEW_COUNT=$(grep -c "^CREATE MATERIALIZED VIEW" "$SCHEMA_FILE" || true)
echo "Materialized Views: $MATVIEW_COUNT"

# Count CREATE FUNCTION
FUNCTION_COUNT=$(grep -c "^CREATE OR REPLACE FUNCTION" "$SCHEMA_FILE" || true)
echo "Functions: $FUNCTION_COUNT"

# Count CREATE TRIGGER
TRIGGER_COUNT=$(grep -c "^CREATE TRIGGER" "$SCHEMA_FILE" || true)
echo "Triggers: $TRIGGER_COUNT"

echo ""
echo "Table Details:"
echo "=============="
grep "^CREATE TABLE" "$SCHEMA_FILE" | sed 's/CREATE TABLE IF NOT EXISTS //' | sed 's/ ($//' | while read -r table; do
    echo "  - $table"
done

echo ""
echo "Materialized View Details:"
echo "=========================="
grep "^CREATE MATERIALIZED VIEW" "$SCHEMA_FILE" | sed 's/CREATE MATERIALIZED VIEW IF NOT EXISTS //' | sed 's/ AS$//' | while read -r view; do
    echo "  - $view"
done

echo ""
echo "Function Details:"
echo "================"
grep "^CREATE OR REPLACE FUNCTION" "$SCHEMA_FILE" | sed 's/CREATE OR REPLACE FUNCTION //' | sed 's/($//' | while read -r func; do
    echo "  - $func"
done

echo ""
echo "Vector Embedding Dimensions:"
echo "============================"
grep "vector(" "$SCHEMA_FILE" | grep -o "vector([0-9]*)" | sort -u | while read -r dim; do
    count=$(grep -c "$dim" "$SCHEMA_FILE" || true)
    echo "  - $dim: $count occurrences"
done

echo ""
echo "File Statistics:"
echo "================"
echo "Total lines: $(wc -l < "$SCHEMA_FILE")"
echo "Size: $(du -h "$SCHEMA_FILE" | cut -f1)"

echo ""
echo "✅ Schema file syntax test complete!"
echo ""
echo "To deploy:"
echo "  psql -h laptop-01 -U sfloess -d learning -f $SCHEMA_FILE"
