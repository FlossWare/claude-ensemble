#!/bin/bash
# Parallel Neo4j batch inserts using GNU parallel

if [ $# -ne 2 ]; then
    echo "Usage: $0 <batch_prefix> <num_parallel>"
    echo "Example: $0 /tmp/batch_final 4"
    exit 1
fi

BATCH_PREFIX="$1"
NUM_PARALLEL="$2"

# Find all batch files
BATCH_FILES=$(ls ${BATCH_PREFIX}_* 2>/dev/null)

if [ -z "$BATCH_FILES" ]; then
    echo "No batch files found matching ${BATCH_PREFIX}_*"
    exit 1
fi

# Count batches
TOTAL=$(echo "$BATCH_FILES" | wc -l)
echo "Found $TOTAL batch files, running $NUM_PARALLEL in parallel"

# Function to insert one batch
insert_batch() {
    local batch_file="$1"
    local batch_name=$(basename "$batch_file")

    echo "Starting $batch_name..."
    /opt/neo4j/bin/cypher-shell -u neo4j -p Neo4jPass2024 \
        --file "$batch_file" > "/tmp/${batch_name}.log" 2>&1

    if [ $? -eq 0 ]; then
        echo "✓ Completed $batch_name"
    else
        echo "✗ Failed $batch_name (see /tmp/${batch_name}.log)"
    fi
}

export -f insert_batch

# Run in parallel
echo "$BATCH_FILES" | parallel -j "$NUM_PARALLEL" insert_batch {}

echo ""
echo "All batches processed. Check logs in /tmp/*.log"
echo ""
echo "Final Neo4j session count:"
/opt/neo4j/bin/cypher-shell -u neo4j -p Neo4jPass2024 \
    "MATCH (s:Session) RETURN count(s) as total" 2>&1 | tail -1
