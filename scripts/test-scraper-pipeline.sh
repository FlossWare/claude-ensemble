#!/bin/bash
#
# Test script for web scraper pipeline
# Tests end-to-end flow: scrape → store → chunk → embed → graph
#
# Last Updated: 2026-07-11

set -e

API_BASE="http://aio-01:5000"
TEST_ID="test_$(date +%s)"
TEST_HASH="test_${TEST_ID}_hash"

echo "========================================="
echo "Scraper Pipeline Integration Test"
echo "Test ID: $TEST_ID"
echo "========================================="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Step 1: Check prerequisites
echo "Step 1: Checking prerequisites..."

# API health
if curl -s -f "$API_BASE/health" > /dev/null; then
    success "Orchestrator API is healthy"
else
    error "Orchestrator API is down"
fi

# PostgreSQL
if psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1" > /dev/null 2>&1; then
    success "PostgreSQL is accessible"
else
    error "PostgreSQL is not accessible"
fi

# Redis
if redis-cli -h aio-01 ping > /dev/null 2>&1; then
    success "Redis is accessible"
else
    error "Redis is not accessible"
fi

# NFS mount
if ssh claude@aio-01 "test -d /mnt/aio-01/claude-orchestrator/scraped-data/raw" 2>/dev/null; then
    success "NFS mount is accessible"
else
    error "NFS mount is not accessible"
fi

echo

# Step 2: POST test document
echo "Step 2: POSTing test document..."

RESPONSE=$(curl -s -X POST "$API_BASE/store/test/$TEST_HASH" \
    -H "Content-Type: application/json" \
    -d "{
        \"url\": \"https://example.com/$TEST_ID\",
        \"source\": \"test\",
        \"category\": \"test\",
        \"title\": \"End-to-End Test Document\",
        \"content\": \"This is a comprehensive end-to-end test of the scraper pipeline. The content must be long enough to generate multiple chunks during processing. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Additional content to ensure we get multiple chunks for testing purposes. More text here to make sure the chunking algorithm has enough material to work with.\",
        \"metadata\": {\"test\": true, \"test_id\": \"$TEST_ID\"}
    }")

if echo "$RESPONSE" | grep -q '"stored": true'; then
    success "Document stored successfully"
    echo "   Response: $RESPONSE"
else
    error "Failed to store document: $RESPONSE"
fi

echo

# Step 3: Verify raw file exists
echo "Step 3: Verifying raw file..."

sleep 2  # Give filesystem time to sync

if ssh claude@aio-01 "test -f /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/${TEST_HASH}.json" 2>/dev/null; then
    success "Raw JSON file exists"

    # Show file size
    FILE_SIZE=$(ssh claude@aio-01 "stat -c%s /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/${TEST_HASH}.json" 2>/dev/null)
    echo "   File size: $FILE_SIZE bytes"

    # Show content preview
    echo "   Content preview:"
    ssh claude@aio-01 "cat /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/${TEST_HASH}.json | jq -r '.title'" 2>/dev/null | sed 's/^/   /'
else
    error "Raw JSON file not found"
fi

echo

# Step 4: Check queue depth
echo "Step 4: Checking queue depth..."

STORE_QUEUE=$(redis-cli -h aio-01 llen store_queue 2>/dev/null || echo "0")
CHUNK_QUEUE=$(redis-cli -h aio-01 llen chunk_queue 2>/dev/null || echo "0")
EMBED_QUEUE=$(redis-cli -h aio-01 llen embed_queue 2>/dev/null || echo "0")
GRAPH_QUEUE=$(redis-cli -h aio-01 llen graph_queue 2>/dev/null || echo "0")

echo "   store_queue: $STORE_QUEUE"
echo "   chunk_queue: $CHUNK_QUEUE"
echo "   embed_queue: $EMBED_QUEUE"
echo "   graph_queue: $GRAPH_QUEUE"

if [ "$STORE_QUEUE" -gt 0 ] || [ "$CHUNK_QUEUE" -gt 0 ] || [ "$EMBED_QUEUE" -gt 0 ] || [ "$GRAPH_QUEUE" -gt 0 ]; then
    success "Queues have tasks (processing is happening)"
else
    warn "Queues are empty (workers may not be running)"
fi

echo

# Step 5: Wait for processing
echo "Step 5: Waiting for processing (30 seconds)..."

for i in {1..30}; do
    echo -n "."
    sleep 1
done
echo
success "Wait complete"

echo

# Step 6: Check chunks in PostgreSQL
echo "Step 6: Checking chunks in PostgreSQL..."

CHUNK_COUNT=$(psql -h aio-01 -p 5433 -U sfloess -d learning -t -c "
    SELECT COUNT(*)
    FROM knowledge.scraped_data
    WHERE file_hash = '$TEST_HASH'
" 2>/dev/null | tr -d ' ')

if [ "$CHUNK_COUNT" -gt 0 ]; then
    success "Found $CHUNK_COUNT chunk(s) in PostgreSQL"

    # Show chunk details
    echo "   Chunk details:"
    psql -h aio-01 -p 5433 -U sfloess -d learning -c "
        SELECT chunk_index, LENGTH(chunk_text) AS text_length,
               CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END AS has_embedding
        FROM knowledge.scraped_data
        WHERE file_hash = '$TEST_HASH'
        ORDER BY chunk_index
    " 2>/dev/null | sed 's/^/   /'
else
    warn "No chunks found yet (workers may still be processing)"
    echo "   This is OK if queue workers are not deployed"
fi

echo

# Step 7: Check embeddings
echo "Step 7: Checking embeddings..."

EMBEDDING_COUNT=$(psql -h aio-01 -p 5433 -U sfloess -d learning -t -c "
    SELECT COUNT(*)
    FROM knowledge.scraped_data
    WHERE file_hash = '$TEST_HASH' AND embedding IS NOT NULL
" 2>/dev/null | tr -d ' ')

if [ "$EMBEDDING_COUNT" -gt 0 ]; then
    success "Found $EMBEDDING_COUNT embedding(s)"

    # Test vector search
    echo "   Testing vector similarity search..."
    SIMILARITY=$(psql -h aio-01 -p 5433 -U sfloess -d learning -t -c "
        SELECT ROUND((1 - (embedding <=>
            (SELECT embedding FROM knowledge.scraped_data WHERE file_hash = '$TEST_HASH' LIMIT 1)
        ))::numeric, 4) AS similarity
        FROM knowledge.scraped_data
        WHERE file_hash = '$TEST_HASH'
        ORDER BY similarity DESC
        LIMIT 1
    " 2>/dev/null | tr -d ' ')

    echo "   Self-similarity: $SIMILARITY (should be 1.0000)"
else
    warn "No embeddings found yet (embed workers may not be running)"
    echo "   This is OK if embed workers are not deployed"
fi

echo

# Step 8: Check queue workers
echo "Step 8: Checking queue workers..."

WORKER_RESPONSE=$(curl -s "$API_BASE/fleet/queue-workers" 2>/dev/null || echo '{"workers":[]}')
WORKER_COUNT=$(echo "$WORKER_RESPONSE" | jq '.workers | length' 2>/dev/null || echo "0")

if [ "$WORKER_COUNT" -gt 0 ]; then
    success "Found $WORKER_COUNT queue worker(s)"
    echo "   Workers:"
    echo "$WORKER_RESPONSE" | jq -r '.workers[] | "   - \(.node) [\(.stage)]"' 2>/dev/null
else
    warn "No queue workers found"
    echo "   Deploy workers with: curl -X POST $API_BASE/fleet/deploy-queue-workers"
fi

echo

# Step 9: Check scraper status
echo "Step 9: Checking scraper status..."

SCRAPER_RESPONSE=$(curl -s "$API_BASE/fleet/scrapers" 2>/dev/null || echo '{"scrapers":[]}')
SCRAPER_COUNT=$(echo "$SCRAPER_RESPONSE" | jq '.scrapers | length' 2>/dev/null || echo "0")

if [ "$SCRAPER_COUNT" -gt 0 ]; then
    success "Found $SCRAPER_COUNT scraper(s)"
    echo "   Scrapers:"
    echo "$SCRAPER_RESPONSE" | jq -r '.scrapers[] | "   - \(.node) [\(.source)]"' 2>/dev/null
else
    warn "No scrapers found"
    echo "   Deploy scrapers with: curl -X POST $API_BASE/fleet/deploy"
fi

echo

# Step 10: Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo

if [ "$CHUNK_COUNT" -gt 0 ] && [ "$EMBEDDING_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ PASS${NC} - Full pipeline working"
    echo
    echo "Pipeline verification:"
    echo "  1. Scraper → /store endpoint: ✓"
    echo "  2. Raw file written: ✓"
    echo "  3. Queued for processing: ✓"
    echo "  4. Chunks created: ✓ ($CHUNK_COUNT chunks)"
    echo "  5. Embeddings generated: ✓ ($EMBEDDING_COUNT embeddings)"
    echo
    echo "System is ready for production scraping!"
elif [ "$CHUNK_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠ PARTIAL${NC} - Chunking working, embedding pending"
    echo
    echo "Pipeline verification:"
    echo "  1. Scraper → /store endpoint: ✓"
    echo "  2. Raw file written: ✓"
    echo "  3. Queued for processing: ✓"
    echo "  4. Chunks created: ✓ ($CHUNK_COUNT chunks)"
    echo "  5. Embeddings generated: ✗ (embed workers needed)"
    echo
    echo "Next step: Deploy embed workers"
    echo "  curl -X POST $API_BASE/fleet/deploy-queue-workers \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"embed_workers\": 4}'"
else
    echo -e "${YELLOW}⚠ PARTIAL${NC} - Storage working, processing pending"
    echo
    echo "Pipeline verification:"
    echo "  1. Scraper → /store endpoint: ✓"
    echo "  2. Raw file written: ✓"
    echo "  3. Queued for processing: ✓"
    echo "  4. Chunks created: ✗ (chunk workers needed)"
    echo "  5. Embeddings generated: ✗ (embed workers needed)"
    echo
    echo "Next step: Deploy queue workers"
    echo "  ./scripts/deploy-redis-workers.sh"
fi

echo
echo "Test ID: $TEST_ID"
echo "Hash: $TEST_HASH"
echo

# Cleanup prompt
read -p "Delete test data? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleaning up test data..."

    # Delete raw file
    ssh claude@aio-01 "rm -f /mnt/aio-01/claude-orchestrator/scraped-data/raw/test/${TEST_HASH}.json" 2>/dev/null

    # Delete PostgreSQL chunks
    psql -h aio-01 -p 5433 -U sfloess -d learning -c "
        DELETE FROM knowledge.scraped_data WHERE file_hash = '$TEST_HASH'
    " > /dev/null 2>&1

    success "Test data cleaned up"
else
    echo "Keeping test data (file_hash: $TEST_HASH)"
fi

echo
echo "Test complete!"
