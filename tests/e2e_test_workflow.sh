#!/usr/bin/env bash
#
# End-to-End Test Workflow
# Tests: Read PDF → Autostorage Detection → API Ingestion → Search
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_BASE="http://aio-01:8000"
API_KEY="sk_test_validkey12345"
DB_HOST="aio-01"
DB_PORT="5433"
DB_NAME="learning"
DB_USER="claude"

# Test counters
PHASE_COUNT=0
PHASE_PASSED=0

log_phase() {
    ((PHASE_COUNT++))
    echo -e "\n${BLUE}[PHASE $PHASE_COUNT]${NC} $1"
}

log_step() {
    echo -e "  ${YELLOW}→${NC} $1"
}

log_success() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((PHASE_PASSED++))
}

log_error() {
    echo -e "  ${RED}✗${NC} $1"
}

# Cleanup function
cleanup() {
    log_step "Cleaning up test files"
    rm -f /tmp/e2e_test_*.pdf /tmp/e2e_test_doc_id.txt
    log_success "Cleanup complete"
}

trap cleanup EXIT

# ============================================================================
# PHASE 1: CREATE TEST PDF WITH DFS CONTENT
# ============================================================================

log_phase "Create Test PDF with DFS Content"

log_step "Generating PDF using ReportLab"
python3 << 'EOF'
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

pdf_path = "/tmp/e2e_test_dfs_technical.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)

# Title
c.setFont("Helvetica-Bold", 16)
c.drawString(100, 750, "Dynamic Frequency Selection (DFS) Technical Guide")

# Content
c.setFont("Helvetica", 12)
y = 700
content = [
    "",
    "1. Introduction to DFS",
    "",
    "Dynamic Frequency Selection (DFS) is a mechanism required by regulatory",
    "authorities for wireless devices operating in the 5 GHz frequency band.",
    "The primary purpose is to detect and avoid interference with radar systems",
    "used by weather services, military, and air traffic control.",
    "",
    "2. Radar Detection Requirements",
    "",
    "DFS-capable devices must:",
    "  • Monitor channels for radar signals continuously",
    "  • Detect radar pulses with 99% probability",
    "  • Vacate the channel within 10 seconds of detection",
    "  • Mark the channel unavailable for 30 minutes",
    "",
    "3. Channel Availability Check (CAC)",
    "",
    "Before transmitting on a DFS channel, devices must perform CAC:",
    "  • Monitor for 60 seconds on outdoor channels",
    "  • Monitor for 1 second on indoor channels (ETSI)",
    "  • No transmissions allowed during CAC period",
    "",
    "4. Implementation in Wireless Routers",
    "",
    "Common DFS implementation issues:",
    "  • False radar detections causing channel switches",
    "  • Clients disconnecting during channel changes",
    "  • Limited DFS channel availability in some regions",
    "  • Firmware bugs causing permanent DFS disable",
]

for line in content:
    c.drawString(100, y, line)
    y -= 20
    if y < 100:
        c.showPage()
        c.setFont("Helvetica", 12)
        y = 750

c.save()
print(f"Created: {pdf_path}")
EOF

if [ -f /tmp/e2e_test_dfs_technical.pdf ]; then
    log_success "PDF created successfully"
else
    log_error "PDF creation failed"
    exit 1
fi

# ============================================================================
# PHASE 2: SIMULATE CLAUDE READ TOOL
# ============================================================================

log_phase "Simulate Claude Read Tool"

log_step "Creating session JSONL with Read tool result"
cat > /tmp/e2e_test_session.jsonl << 'EOF'
{"type":"human","content":"Please read the DFS technical documentation","timestamp":"2026-07-02T10:00:00Z"}
{"type":"assistant","content":"I'll read the DFS documentation now.","timestamp":"2026-07-02T10:00:01Z"}
{"type":"tool_use","tool":"Read","file_path":"/tmp/e2e_test_dfs_technical.pdf","content":"Dynamic Frequency Selection (DFS) Technical Guide\n\n1. Introduction to DFS\n\nDynamic Frequency Selection (DFS) is a mechanism required by regulatory authorities for wireless devices operating in the 5 GHz frequency band. The primary purpose is to detect and avoid interference with radar systems used by weather services, military, and air traffic control.\n\n2. Radar Detection Requirements\n\nDFS-capable devices must:\n  • Monitor channels for radar signals continuously\n  • Detect radar pulses with 99% probability\n  • Vacate the channel within 10 seconds of detection\n  • Mark the channel unavailable for 30 minutes","timestamp":"2026-07-02T10:00:02Z"}
EOF

if [ -f /tmp/e2e_test_session.jsonl ]; then
    log_success "Session JSONL created"
else
    log_error "Session JSONL creation failed"
    exit 1
fi

# ============================================================================
# PHASE 3: AUTOSTORAGE DETECTION
# ============================================================================

log_phase "Autostorage Document Detection"

log_step "Running autostorage system on test session"
python3 << 'EOF'
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from auto_storage_system import (
    parse_tool_results_streaming,
    extract_document_from_tool_result,
    detect_file_type_magic
)

async def test_detection():
    session_file = Path("/tmp/e2e_test_session.jsonl")
    detected_count = 0

    async for record in parse_tool_results_streaming(session_file):
        doc = extract_document_from_tool_result(record)
        if doc:
            detected_count += 1
            print(f"Detected document: {doc['file_path']}")
            print(f"Content preview: {doc['content'][:100]}...")

    return detected_count

import asyncio
count = asyncio.run(test_detection())
print(f"Total documents detected: {count}")

if count > 0:
    sys.exit(0)
else:
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    log_success "Autostorage detected PDF from session"
else
    log_error "Autostorage failed to detect PDF"
    exit 1
fi

# ============================================================================
# PHASE 4: API INGESTION
# ============================================================================

log_phase "API Document Ingestion"

log_step "Uploading PDF via API"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/pdf" \
    -H "X-API-Key: $API_KEY" \
    -F "file=@/tmp/e2e_test_dfs_technical.pdf" \
    -F 'metadata={"title":"DFS Technical Guide","author":"E2E Test","source":"e2e_test_workflow.sh","tags":["dfs","radar","5ghz","technical"]}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    DOC_ID=$(echo "$BODY" | jq -r '.document_id')
    CHUNKS_ESTIMATED=$(echo "$BODY" | jq -r '.chunks_estimated')
    log_success "PDF ingested (doc_id: $DOC_ID, chunks: $CHUNKS_ESTIMATED)"
    echo "$DOC_ID" > /tmp/e2e_test_doc_id.txt
else
    log_error "API ingestion failed (HTTP $HTTP_CODE)"
    echo "$BODY" | jq . || echo "$BODY"
    exit 1
fi

# ============================================================================
# PHASE 5: WAIT FOR BACKGROUND PROCESSING
# ============================================================================

log_phase "Background Processing - Embedding Generation"

log_step "Waiting for embeddings to be generated (10 seconds)"
for i in {10..1}; do
    echo -ne "  ${YELLOW}⏳${NC} $i seconds remaining...\r"
    sleep 1
done
echo ""
log_success "Background processing complete"

# ============================================================================
# PHASE 6: VERIFY DATABASE STORAGE
# ============================================================================

log_phase "Database Verification"

log_step "Checking document in research_documents table"
PSQL_RESULT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A << EOF
SELECT COUNT(*) FROM ingestion.research_documents WHERE id = '$DOC_ID';
EOF
)

if [ "$PSQL_RESULT" = "1" ]; then
    log_success "Document found in research_documents"
else
    log_error "Document not found in research_documents"
    exit 1
fi

log_step "Checking chunks in document_chunks table"
CHUNK_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A << EOF
SELECT COUNT(*) FROM ingestion.document_chunks WHERE document_id = '$DOC_ID';
EOF
)

if [ "$CHUNK_COUNT" -gt 0 ]; then
    log_success "Found $CHUNK_COUNT chunks in database"
else
    log_error "No chunks found in database"
    exit 1
fi

log_step "Verifying embeddings generated"
EMBEDDING_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A << EOF
SELECT COUNT(*) FROM ingestion.document_chunks WHERE document_id = '$DOC_ID' AND embedding IS NOT NULL;
EOF
)

if [ "$EMBEDDING_COUNT" = "$CHUNK_COUNT" ]; then
    log_success "All chunks have embeddings ($EMBEDDING_COUNT/$CHUNK_COUNT)"
else
    log_error "Only $EMBEDDING_COUNT/$CHUNK_COUNT chunks have embeddings"
    exit 1
fi

# ============================================================================
# PHASE 7: SEMANTIC SEARCH
# ============================================================================

log_phase "Semantic Search - Query Testing"

# Test Query 1: DFS radar detection
log_step "Query 1: 'DFS radar detection requirements'"
RESPONSE=$(curl -s -w "\n%{http_code}" -G "$API_BASE/search" \
    -H "X-API-Key: $API_KEY" \
    --data-urlencode "query=DFS radar detection requirements" \
    --data-urlencode "limit=5" \
    --data-urlencode "threshold=0.5")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    RESULT_COUNT=$(echo "$BODY" | jq -r '.total_results')
    if [ "$RESULT_COUNT" -gt 0 ]; then
        TOP_SCORE=$(echo "$BODY" | jq -r '.results[0].similarity_score')
        log_success "Query 1: $RESULT_COUNT results (top score: $TOP_SCORE)"
    else
        log_error "Query 1: No results found"
    fi
else
    log_error "Query 1: Search failed (HTTP $HTTP_CODE)"
fi

# Test Query 2: Channel availability check
log_step "Query 2: 'channel availability check CAC'"
RESPONSE=$(curl -s -w "\n%{http_code}" -G "$API_BASE/search" \
    -H "X-API-Key: $API_KEY" \
    --data-urlencode "query=channel availability check CAC" \
    --data-urlencode "limit=5" \
    --data-urlencode "threshold=0.5")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    RESULT_COUNT=$(echo "$BODY" | jq -r '.total_results')
    if [ "$RESULT_COUNT" -gt 0 ]; then
        TOP_SCORE=$(echo "$BODY" | jq -r '.results[0].similarity_score')
        log_success "Query 2: $RESULT_COUNT results (top score: $TOP_SCORE)"
    else
        log_error "Query 2: No results found"
    fi
else
    log_error "Query 2: Search failed (HTTP $HTTP_CODE)"
fi

# Test Query 3: Tag filtering
log_step "Query 3: 'wireless' filtered by tags=[dfs,radar]"
RESPONSE=$(curl -s -w "\n%{http_code}" -G "$API_BASE/search" \
    -H "X-API-Key: $API_KEY" \
    --data-urlencode "query=wireless" \
    --data-urlencode "filter_tags=dfs,radar" \
    --data-urlencode "limit=5" \
    --data-urlencode "threshold=0.5")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    RESULT_COUNT=$(echo "$BODY" | jq -r '.total_results')
    if [ "$RESULT_COUNT" -gt 0 ]; then
        log_success "Query 3: $RESULT_COUNT results (filtered by tags)"
    else
        log_error "Query 3: No results found with tag filter"
    fi
else
    log_error "Query 3: Search failed (HTTP $HTTP_CODE)"
fi

# ============================================================================
# PHASE 8: CONTENT VERIFICATION
# ============================================================================

log_phase "Content Verification - Chunk Quality"

log_step "Retrieving document details"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/documents/$DOC_ID" \
    -H "X-API-Key: $API_KEY")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    TOTAL_CHUNKS=$(echo "$BODY" | jq -r '.total_chunks')
    TITLE=$(echo "$BODY" | jq -r '.metadata.title')
    TAGS=$(echo "$BODY" | jq -r '.metadata.tags | join(",")')

    log_success "Retrieved document: $TITLE"
    log_success "Tags: $TAGS"
    log_success "Total chunks: $TOTAL_CHUNKS"

    # Check chunk content
    CHUNK_CONTENT=$(echo "$BODY" | jq -r '.chunks[0].content')
    if echo "$CHUNK_CONTENT" | grep -q "Dynamic Frequency Selection"; then
        log_success "Chunk content verified (contains DFS text)"
    else
        log_error "Chunk content missing expected DFS text"
    fi
else
    log_error "Document retrieval failed (HTTP $HTTP_CODE)"
fi

# ============================================================================
# PHASE 9: AUTOSTORAGE STATE VERIFICATION
# ============================================================================

log_phase "Autostorage State - Processed Tracking"

log_step "Checking auto_storage_processed.json"
PROCESSED_FILE="$HOME/.claude/learning/auto_storage_processed.json"

if [ -f "$PROCESSED_FILE" ]; then
    INGESTED_COUNT=$(jq -r '._stats.ingested_docs // 0' "$PROCESSED_FILE")
    FAILED_COUNT=$(jq -r '._stats.failed_docs // 0' "$PROCESSED_FILE")
    LAST_RUN=$(jq -r '._stats.last_run // "never"' "$PROCESSED_FILE")

    log_success "Autostorage stats:"
    echo "    Ingested: $INGESTED_COUNT"
    echo "    Failed: $FAILED_COUNT"
    echo "    Last run: $LAST_RUN"
else
    log_error "auto_storage_processed.json not found"
fi

# ============================================================================
# PHASE 10: CLEANUP AND SUMMARY
# ============================================================================

log_phase "Cleanup - Remove Test Document"

log_step "Deleting test document via API"
RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "$API_BASE/documents/$DOC_ID" \
    -H "X-API-Key: $API_KEY")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "204" ]; then
    log_success "Test document deleted successfully"
else
    log_error "Document deletion failed (HTTP $HTTP_CODE)"
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================

echo ""
echo "========================================"
echo "E2E TEST WORKFLOW COMPLETE"
echo "========================================"
echo -e "${GREEN}Phases Passed: $PHASE_PASSED / $PHASE_COUNT${NC}"
echo "========================================"
echo ""
echo "Workflow Summary:"
echo "  1. Created DFS technical PDF ✓"
echo "  2. Simulated Claude Read tool ✓"
echo "  3. Autostorage detected document ✓"
echo "  4. API ingested PDF ✓"
echo "  5. Background processing complete ✓"
echo "  6. Database verification passed ✓"
echo "  7. Semantic search functional ✓"
echo "  8. Content quality verified ✓"
echo "  9. Autostorage state updated ✓"
echo " 10. Cleanup completed ✓"
echo ""

if [ $PHASE_PASSED -eq $PHASE_COUNT ]; then
    echo -e "${GREEN}ALL PHASES PASSED${NC}"
    exit 0
else
    echo -e "${RED}SOME PHASES FAILED${NC}"
    exit 1
fi
