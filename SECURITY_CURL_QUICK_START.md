# Security Test Quick Start: curl without auth

## Quick Summary

Two test files are available to verify that API endpoints properly require authentication:

1. **test-security-curl.sh** - Bash/curl-based tests
2. **test-security-curl-auth.js** - Node.js test suite

Both verify that APIs reject unauthenticated requests with HTTP 401/403.

## 30-Second Setup

### Option 1: Run Node.js Tests (Recommended)

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Run the test
node test-security-curl-auth.js

# Results saved to: security-curl-results.json
```

### Option 2: Run Bash Tests

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Run the test
./test-security-curl.sh

# Results saved to: security-curl-results.json
```

## What Gets Tested

| Test | Endpoint | Expected | Purpose |
|------|----------|----------|---------|
| 1 | GET /agent/execute | 401/403 | Verify auth required |
| 2 | POST /agent/execute | 401/403 | Verify auth required |
| 3 | GET /api/learning | 401/403 | Verify auth required |
| 4 | POST /api/learning/record-feedback | 401/403 | Verify auth required |
| 5 | GET /fleet/status | 401/403 | Verify auth required |
| 6 | POST /fleet/dispatch | 401/403 | Verify auth required |
| 7 | GET /agent/execute-command | 401/403 | Verify auth required |
| 8 | POST /agent/execute-command | 401/403 | Verify auth required |
| 9-10 | Same endpoints with valid auth | 200/201 | Verify auth accepted |

## Reading Results

### PASS ✅
Endpoint correctly rejected unauthenticated request:
```
✅ GET /agent/execute (no auth)
   HTTP 401
   Correctly rejected with HTTP 401
```

### FAIL ❌
Endpoint accessible without authentication (SECURITY ISSUE):
```
❌ GET /agent/execute (no auth)
   HTTP 200
   Endpoint accessible without auth! HTTP 200
```

### SKIP ⊘
Endpoint unavailable (server not running):
```
⊘ GET /agent/execute (no auth)
   HTTP null
   Server not running
```

## Common Use Cases

### 1. Pre-Deployment Security Check

```bash
# Run before deploying to ensure endpoints are protected
node test-security-curl-auth.js

# Check results
cat security-curl-results.json | grep '"failed": 0'
```

### 2. Manual Testing of Specific Endpoint

```bash
# Test with curl directly
curl -v http://localhost:3000/agent/execute
# Should return: HTTP 401 Unauthorized

# Test with authentication
curl -v -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:3000/agent/execute
# Should return: HTTP 200 OK or 201 Created
```

### 3. CI/CD Integration

```yaml
# Add to your CI pipeline
- name: Run security tests
  run: node test-security-curl-auth.js

- name: Check results
  run: |
    FAILED=$(grep '"failed":' security-curl-results.json | grep -o '[0-9]')
    if [ "$FAILED" != "0" ]; then
      echo "Security tests failed!"
      exit 1
    fi
```

### 4. Custom URL Testing

```bash
# Test against different server
API_BASE_URL=https://api.production.com \
  node test-security-curl-auth.js

# Test with custom token
AUTH_TOKEN="abc123xyz" \
  node test-security-curl-auth.js

# Test custom learning API
LEARNING_API_URL=https://learning.prod.com \
  node test-security-curl-auth.js
```

## Response Codes Explained

| Code | Meaning | Action |
|------|---------|--------|
| 200 | OK | Request successful |
| 201 | Created | Resource created (expected for POST) |
| 401 | Unauthorized | Missing/invalid credentials (EXPECTED for unauthenticated requests) |
| 403 | Forbidden | Credentials invalid (EXPECTED for unauthenticated requests) |
| 404 | Not Found | Endpoint doesn't exist (test skipped) |
| 500 | Server Error | Server problem |

## Troubleshooting

### "Server not running"
The API servers are not listening on the expected ports.

```bash
# Check if servers are running
netstat -tuln | grep -E "3000|8000"

# Or with lsof
lsof -i :3000  # Main API
lsof -i :8000  # Learning API

# Start the servers if needed
node your-api-server.js &
```

### "Endpoint not found (404)"
The endpoint exists but isn't implemented yet.

```bash
# Verify endpoint exists in your code
grep -r "/agent/execute" /your/api/path

# Check API documentation
cat AGENT_EXECUTE_ENDPOINT.md
```

### "Connection refused"
API server isn't running or listening on wrong port.

```bash
# Update the test with correct URL
API_BASE_URL=http://localhost:5000 node test-security-curl-auth.js
```

### Tests pass but expect failures
Your authentication might be too permissive.

```bash
# Review your auth middleware
grep -r "auth\|Auth\|401\|403" /your/api/path

# Ensure all sensitive endpoints have auth checks
grep -r "app.get\|app.post" /your/api/path | grep agent
```

## Manual curl Testing

### Test without auth (should be rejected)
```bash
curl -v http://localhost:3000/agent/execute
# Expected: HTTP 401 Unauthorized
```

### Test with auth (should be accepted)
```bash
curl -v \
  -H "Authorization: Bearer your-token-here" \
  http://localhost:3000/agent/execute
# Expected: HTTP 200 OK
```

### Send JSON data
```bash
curl -v -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token-here" \
  -d '{
    "server": "server-01",
    "model": "haiku",
    "prompt": "test prompt"
  }' \
  http://localhost:3000/agent/execute
```

### See all response details
```bash
curl -i http://localhost:3000/agent/execute
# Shows: status, headers, and body
```

## Results File Format

Both test scripts save a `security-curl-results.json` file:

```json
{
  "test_name": "Security Test: curl without auth",
  "timestamp": "2026-06-13T10:30:00Z",
  "summary": {
    "passed": 10,
    "failed": 0,
    "skipped": 0,
    "total": 10
  },
  "tests": [
    {
      "name": "GET /agent/execute (no auth)",
      "url": "http://localhost:3000/agent/execute",
      "method": "GET",
      "status": "PASS",
      "statusCode": 401,
      "message": "Correctly rejected with HTTP 401"
    }
  ]
}
```

### Parse results in scripts

```bash
# Count failures
jq '.summary.failed' security-curl-results.json

# List failed tests
jq '.tests[] | select(.status=="FAIL")' security-curl-results.json

# Check if all passed
jq '.summary.failed == 0' security-curl-results.json
```

## Key Points

✅ **PASS means**: Endpoint properly requires authentication
❌ **FAIL means**: Endpoint is accessible without credentials (SECURITY ISSUE)
⊘ **SKIP means**: Endpoint not available (server not running)

## Environment Variables

```bash
# Set these before running tests:

# Main API base URL
export API_BASE_URL=http://localhost:3000

# Learning API URL
export LEARNING_API_URL=http://localhost:8000

# Valid auth token for authenticated tests
export AUTH_TOKEN="your-bearer-token-here"

# Then run tests
node test-security-curl-auth.js
```

## Security Checklist

Before deploying:

- [ ] Run security tests
- [ ] All tests should PASS (not FAIL)
- [ ] Review any SKIP results
- [ ] Verify authentication middleware is enabled
- [ ] Check that all sensitive endpoints require auth
- [ ] Test with invalid/expired tokens
- [ ] Test with multiple user roles if applicable
- [ ] Run tests in CI/CD pipeline

## Next Steps

1. **Run the tests**: `node test-security-curl-auth.js`
2. **Check results**: `cat security-curl-results.json`
3. **Fix any failures**: Add authentication to endpoints that fail
4. **Integrate into CI**: Add test to your pipeline
5. **Monitor regularly**: Run tests before each deployment

## More Information

See `SECURITY_CURL_TEST.md` for detailed documentation, examples, and troubleshooting.

## Quick Command Reference

```bash
# Run tests
node test-security-curl-auth.js
./test-security-curl.sh

# Test specific endpoint
curl -v http://localhost:3000/agent/execute

# Test with auth
curl -H "Authorization: Bearer TOKEN" http://localhost:3000/agent/execute

# View results
cat security-curl-results.json
jq . security-curl-results.json

# Parse results
jq '.summary' security-curl-results.json
jq '.tests[] | {name, status, statusCode}' security-curl-results.json
```

---

**Status**: Ready to use  
**Last Updated**: 2026-06-13  
**Files**: test-security-curl-auth.js, test-security-curl.sh, SECURITY_CURL_TEST.md
