#!/usr/bin/env bash
#
# Document Ingestion API Test Suite
# Tests all endpoints with security validation
#

set -euo pipefail

API_BASE="http://aio-01:8000"
VALID_API_KEY="sk_test_validkey12345"
INVALID_API_KEY="sk_test_invalid"
EXPIRED_API_KEY="sk_test_expired"
ADMIN_API_KEY="sk_admin_test123"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0

log_test() {
    echo -e "\n${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    ((FAILED++))
}

# Test 1: Health Check (no auth required)
log_test "Health Check"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    STATUS=$(echo "$BODY" | jq -r '.status')
    if [ "$STATUS" = "healthy" ]; then
        log_pass "Health check returned healthy status"
    else
        log_fail "Health check status: $STATUS (expected healthy)"
    fi
else
    log_fail "Health check returned HTTP $HTTP_CODE (expected 200)"
fi

# Test 2: Missing API Key
log_test "Authentication - Missing API Key"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
    -H "Content-Type: application/json" \
    -d '{"content": "test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "401" ]; then
    log_pass "Missing API key rejected with 401"
else
    log_fail "Missing API key returned HTTP $HTTP_CODE (expected 401)"
fi

# Test 3: Invalid API Key
log_test "Authentication - Invalid API Key"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
    -H "X-API-Key: $INVALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"content": "test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "401" ]; then
    log_pass "Invalid API key rejected with 401"
else
    log_fail "Invalid API key returned HTTP $HTTP_CODE (expected 401)"
fi

# Test 4: Expired API Key
log_test "Authentication - Expired API Key"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
    -H "X-API-Key: $EXPIRED_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"content": "test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "401" ]; then
    log_pass "Expired API key rejected with 401"
else
    log_fail "Expired API key returned HTTP $HTTP_CODE (expected 401)"
fi

# Test 5: Valid Text Ingestion
log_test "Text Ingestion - Valid"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
    -H "X-API-Key: $VALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "content": "This is a test document about DFS radar detection in wireless routers.",
        "metadata": {
            "title": "DFS Test Document",
            "author": "Test Suite",
            "source": "api_test_script.sh",
            "tags": ["dfs", "radar", "testing"]
        }
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    DOC_ID=$(echo "$BODY" | jq -r '.document_id')
    if [ "$DOC_ID" != "null" ] && [ -n "$DOC_ID" ]; then
        log_pass "Text ingestion successful (document_id: $DOC_ID)"
        echo "$DOC_ID" > /tmp/test_doc_id.txt
    else
        log_fail "Text ingestion returned no document_id"
    fi
else
    log_fail "Text ingestion returned HTTP $HTTP_CODE (expected 200)"
fi

# Test 6: Duplicate Detection
log_test "Deduplication - Same Content Hash"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
    -H "X-API-Key: $VALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "content": "This is a test document about DFS radar detection in wireless routers.",
        "metadata": {"title": "Duplicate Test"}
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "409" ]; then
    log_pass "Duplicate content rejected with 409"
else
    log_fail "Duplicate content returned HTTP $HTTP_CODE (expected 409)"
fi

# Test 7: Code Ingestion with Language Detection
log_test "Code Ingestion - Python"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/code" \
    -H "X-API-Key: $VALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "content": "def hello_world():\n    print(\"Hello, World!\")\n\nif __name__ == \"__main__\":\n    hello_world()",
        "language": "python",
        "metadata": {
            "title": "Hello World Script",
            "tags": ["python", "example"]
        }
    }')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Code ingestion successful"
else
    log_fail "Code ingestion returned HTTP $HTTP_CODE (expected 200)"
fi

# Test 8: PDF Ingestion (create test PDF first)
log_test "PDF Ingestion - Valid PDF"
TEST_PDF="/tmp/test_dfs_document.pdf"

# Create test PDF using Python
python3 << 'EOF'
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

pdf_path = "/tmp/test_dfs_document.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)
c.setFont("Helvetica", 12)
c.drawString(100, 750, "DFS Radar Detection in Wireless Routers")
c.drawString(100, 720, "")
c.drawString(100, 690, "Dynamic Frequency Selection (DFS) is a mechanism required by")
c.drawString(100, 660, "wireless equipment operating in the 5 GHz band to avoid")
c.drawString(100, 630, "interference with radar systems.")
c.save()
print(f"Created test PDF: {pdf_path}")
EOF

if [ -f "$TEST_PDF" ]; then
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/pdf" \
        -H "X-API-Key: $VALID_API_KEY" \
        -F "file=@$TEST_PDF" \
        -F 'metadata={"title":"DFS Technical Guide","author":"Test Suite","tags":["dfs","radar","5ghz"]}')
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "200" ]; then
        PDF_DOC_ID=$(echo "$RESPONSE" | head -n -1 | jq -r '.document_id')
        log_pass "PDF ingestion successful (document_id: $PDF_DOC_ID)"
        echo "$PDF_DOC_ID" > /tmp/test_pdf_doc_id.txt
    else
        log_fail "PDF ingestion returned HTTP $HTTP_CODE (expected 200)"
    fi
else
    log_fail "Failed to create test PDF"
fi

# Test 9: File Size Limit Enforcement
log_test "File Size Validation - Oversized PDF"
# Create 51MB dummy PDF (exceeds 50MB limit)
dd if=/dev/zero of=/tmp/oversized.pdf bs=1M count=51 2>/dev/null

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/pdf" \
    -H "X-API-Key: $VALID_API_KEY" \
    -F "file=@/tmp/oversized.pdf" \
    -F 'metadata={"title":"Oversized Test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "413" ]; then
    log_pass "Oversized PDF rejected with 413"
else
    log_fail "Oversized PDF returned HTTP $HTTP_CODE (expected 413)"
fi

rm -f /tmp/oversized.pdf

# Test 10: Content-Type Validation
log_test "File Type Validation - Firmware Upload Attempt"
# Create fake firmware file with SquashFS magic bytes
printf '\x68\x73\x71\x73' > /tmp/fake_firmware.bin
dd if=/dev/urandom bs=1K count=100 >> /tmp/fake_firmware.bin 2>/dev/null

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/pdf" \
    -H "X-API-Key: $VALID_API_KEY" \
    -F "file=@/tmp/fake_firmware.bin" \
    -F 'metadata={"title":"Firmware Test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "400" ] || echo "$BODY" | grep -q "firmware"; then
    log_pass "Firmware upload blocked"
else
    log_fail "Firmware upload returned HTTP $HTTP_CODE (expected 400 or firmware error)"
fi

rm -f /tmp/fake_firmware.bin

# Test 11: Search Functionality (wait for background processing)
log_test "Search - Semantic Search"
sleep 5  # Wait for embeddings to be generated

RESPONSE=$(curl -s -w "\n%{http_code}" -G "$API_BASE/search" \
    -H "X-API-Key: $VALID_API_KEY" \
    --data-urlencode "query=DFS radar detection wireless" \
    --data-urlencode "limit=10" \
    --data-urlencode "threshold=0.5")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    RESULTS=$(echo "$BODY" | jq -r '.total_results')
    if [ "$RESULTS" -gt 0 ]; then
        log_pass "Search returned $RESULTS results"
    else
        log_fail "Search returned 0 results (expected >0)"
    fi
else
    log_fail "Search returned HTTP $HTTP_CODE (expected 200)"
fi

# Test 12: Search with Filters
log_test "Search - Filtered by Tags"
RESPONSE=$(curl -s -w "\n%{http_code}" -G "$API_BASE/search" \
    -H "X-API-Key: $VALID_API_KEY" \
    --data-urlencode "query=radar" \
    --data-urlencode "filter_tags=dfs,radar")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Filtered search successful"
else
    log_fail "Filtered search returned HTTP $HTTP_CODE (expected 200)"
fi

# Test 13: Get Document Details
log_test "Document Retrieval - Get by ID"
if [ -f /tmp/test_doc_id.txt ]; then
    DOC_ID=$(cat /tmp/test_doc_id.txt)
    RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/documents/$DOC_ID" \
        -H "X-API-Key: $VALID_API_KEY")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "Document retrieval successful"
    else
        log_fail "Document retrieval returned HTTP $HTTP_CODE (expected 200)"
    fi
else
    log_fail "No document ID available for retrieval test"
fi

# Test 14: Rate Limiting
log_test "Rate Limiting - Exceed Limit"
RATE_LIMITED=0
for i in {1..15}; do
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
        -H "X-API-Key: $VALID_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"Rate limit test $i\"}")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "429" ]; then
        RATE_LIMITED=1
        break
    fi
done

if [ $RATE_LIMITED -eq 1 ]; then
    log_pass "Rate limiting enforced (429 received)"
else
    log_fail "Rate limiting not enforced after 15 requests"
fi

# Test 15: SQL Injection Attempt
log_test "SQL Injection Prevention"
RESPONSE=$(curl -s -w "\n%{http_code}" -G "$API_BASE/search" \
    -H "X-API-Key: $VALID_API_KEY" \
    --data-urlencode "query='; DROP TABLE ingestion.research_documents; --")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "400" ]; then
    log_pass "SQL injection attempt handled safely (HTTP $HTTP_CODE)"
else
    log_fail "SQL injection attempt returned unexpected HTTP $HTTP_CODE"
fi

# Test 16: Metrics Endpoint (requires admin scope)
log_test "Metrics - Admin Access"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/metrics" \
    -H "X-API-Key: $ADMIN_API_KEY")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Metrics endpoint accessible with admin key"
else
    log_fail "Metrics endpoint returned HTTP $HTTP_CODE (expected 200)"
fi

# Test 17: Metrics - Unauthorized Access
log_test "Metrics - Non-Admin Access"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/metrics" \
    -H "X-API-Key: $VALID_API_KEY")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "403" ]; then
    log_pass "Metrics endpoint blocked for non-admin (403)"
else
    log_fail "Metrics endpoint returned HTTP $HTTP_CODE (expected 403)"
fi

# Test 18: Document Deletion
log_test "Document Deletion"
if [ -f /tmp/test_doc_id.txt ]; then
    DOC_ID=$(cat /tmp/test_doc_id.txt)
    RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "$API_BASE/documents/$DOC_ID" \
        -H "X-API-Key: $VALID_API_KEY")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" = "204" ]; then
        log_pass "Document deletion successful"
    else
        log_fail "Document deletion returned HTTP $HTTP_CODE (expected 204)"
    fi
else
    log_fail "No document ID available for deletion test"
fi

# Test 19: HTTPS Enforcement (if configured)
log_test "HTTPS Enforcement"
RESPONSE=$(curl -s -w "\n%{http_code}" "http://aio-01:8000/ingest/text" \
    -H "X-API-Key: $VALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"content": "https test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "403" ]; then
    log_pass "HTTP requests blocked (HTTPS required)"
else
    echo -e "${YELLOW}⚠ SKIP${NC} HTTPS not enforced (HTTP allowed)"
fi

# Test 20: Batch Size Limit (embeddings)
log_test "Batch Size Limit - Embedding Generation"
LARGE_TEXT=$(python3 -c "print('word ' * 2000)")
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/ingest/text" \
    -H "X-API-Key: $VALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"$LARGE_TEXT\", \"chunk_config\": {\"min_chunk_size\": 50, \"max_chunk_size\": 100}}")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "413" ]; then
    log_pass "Large document handled (HTTP $HTTP_CODE)"
else
    log_fail "Large document returned unexpected HTTP $HTTP_CODE"
fi

# Cleanup
rm -f /tmp/test_doc_id.txt /tmp/test_pdf_doc_id.txt /tmp/test_dfs_document.pdf

# Summary
echo ""
echo "========================================"
echo "API Test Suite Complete"
echo "========================================"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
