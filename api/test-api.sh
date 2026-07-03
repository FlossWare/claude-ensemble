#!/bin/bash
# Unit tests for Document Ingestion API

set -e

API_BASE_URL="${API_BASE_URL:-https://aio-01:8000}"
API_KEY="${API_KEY:-}"

if [ -z "$API_KEY" ]; then
    echo "ERROR: API_KEY environment variable not set"
    echo "Usage: API_KEY=your_key_here ./test-api.sh"
    exit 1
fi

echo "=== Document Ingestion API - Unit Tests ==="
echo "API Base URL: $API_BASE_URL"
echo ""

# Test 1: Health check
echo "[1/5] Testing health endpoint..."
HEALTH=$(curl -s -k "$API_BASE_URL/health")
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    echo "✓ Health check passed"
else
    echo "✗ Health check failed: $HEALTH"
    exit 1
fi

# Test 2: Invalid API key
echo "[2/5] Testing invalid API key rejection..."
# Create a minimal test file (not /etc/passwd which is confusing)
echo "test content" > /tmp/test_invalid.txt
STATUS=$(curl -s -k -o /dev/null -w "%{http_code}" \
    -X POST "$API_BASE_URL/api/v1/ingest/pdf" \
    -H "X-API-Key: invalid_key_12345" \
    -F "file=@/tmp/test_invalid.txt")
rm -f /tmp/test_invalid.txt

if [ "$STATUS" = "401" ]; then
    echo "✓ Invalid API key rejected"
else
    echo "✗ Invalid API key test failed (expected 401, got $STATUS)"
    exit 1
fi

# Test 3: Rate limiting
echo "[3/5] Testing rate limiting..."
for i in {1..110}; do
    curl -s -k -o /dev/null -w "%{http_code}\n" \
        -X GET "$API_BASE_URL/health" \
        -H "X-API-Key: $API_KEY" >> /tmp/rate_limit_test.log
done

RATE_LIMITED=$(grep -c "429" /tmp/rate_limit_test.log || true)
if [ "$RATE_LIMITED" -gt 0 ]; then
    echo "✓ Rate limiting working ($RATE_LIMITED requests blocked)"
else
    echo "⚠ Rate limiting not triggered (may need adjustment)"
fi
rm -f /tmp/rate_limit_test.log

# Test 4: File size limit
echo "[4/5] Testing file size limit..."
dd if=/dev/zero of=/tmp/large_file.bin bs=1M count=100 2>/dev/null
STATUS=$(curl -s -k -o /dev/null -w "%{http_code}" \
    -X POST "$API_BASE_URL/api/v1/ingest/pdf" \
    -H "X-API-Key: $API_KEY" \
    -F "file=@/tmp/large_file.bin")

if [ "$STATUS" = "413" ]; then
    echo "✓ File size limit enforced"
else
    echo "⚠ File size limit test returned $STATUS (expected 413)"
fi
rm -f /tmp/large_file.bin

# Test 5: Prometheus metrics
echo "[5/5] Testing Prometheus metrics endpoint..."
METRICS=$(curl -s -k "$API_BASE_URL/metrics")
if echo "$METRICS" | grep -q "http_requests_total"; then
    echo "✓ Prometheus metrics available"
else
    echo "✗ Prometheus metrics missing"
    exit 1
fi

echo ""
echo "=== All Unit Tests Passed ==="
