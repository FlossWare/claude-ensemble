# Security Test: curl without auth

## Overview

This document describes security testing for API endpoints to ensure they properly require authentication. Tests verify that unauthenticated requests (curl without auth headers) are properly rejected with HTTP 401 (Unauthorized) or HTTP 403 (Forbidden) responses.

## Purpose

- **Verify Authentication Enforcement**: Ensure all sensitive endpoints require valid credentials
- **Prevent Unauthorized Access**: Detect accidental exposure of protected endpoints
- **Compliance Testing**: Validate security requirements are met
- **Security Auditing**: Document which endpoints require authentication

## Test Files

### 1. Bash Script: `test-security-curl.sh`

A bash-based security test that uses curl directly to test endpoints.

#### Usage

```bash
# Run the test script
./test-security-curl.sh

# The script outputs:
# - Test results for each endpoint
# - Summary of passed/failed tests
# - Results saved to security-curl-results.json
```

#### Features

- Tests both GET and POST requests
- Checks HTTP status codes (401/403 for protected endpoints)
- Graceful handling of unavailable endpoints (404)
- JSON results file for CI/CD integration
- Color-coded output for easy reading

#### Tested Endpoints

1. **Agent Execute Endpoints**
   - `GET /agent/execute` (should require auth)
   - `POST /agent/execute` (should require auth)

2. **Learning API Endpoints**
   - `GET /api/learning` (should require auth)
   - `POST /api/learning/record-feedback` (should require auth)

3. **Fleet Dispatcher Endpoints**
   - `GET /fleet/status` (should require auth)
   - `POST /fleet/dispatch` (should require auth)

4. **SSH Command Generation**
   - `GET /agent/execute-command` (should require auth)

### 2. Node.js Test Suite: `test-security-curl-auth.js`

A comprehensive Node.js test suite that programmatically tests API authentication.

#### Usage

```bash
# Run basic test
node test-security-curl-auth.js

# With custom API URL
API_BASE_URL=https://api.example.com node test-security-curl-auth.js

# With custom learning API URL
LEARNING_API_URL=https://learning.example.com node test-security-curl-auth.js

# With valid auth token for comparison testing
AUTH_TOKEN="your-token-here" node test-security-curl-auth.js
```

#### Features

- Programmatic HTTP requests (no curl dependency)
- Tests with and without authentication headers
- Detailed error reporting
- Timeout handling for unavailable servers
- JSON results file for automation
- Supports both HTTP and HTTPS

#### Environment Variables

- `API_BASE_URL`: Base URL for main API (default: `http://localhost:3000`)
- `LEARNING_API_URL`: Base URL for learning API (default: `http://localhost:8000`)
- `AUTH_TOKEN`: Valid auth token for authenticated tests (default: `invalid-token-test`)

#### Test Scenarios

**Suite 1: Agent Execute Endpoints**
```javascript
// These should return 401/403 without auth
GET /agent/execute
POST /agent/execute (with body)
```

**Suite 2: Learning API Endpoints**
```javascript
// These should return 401/403 without auth
GET /api/learning
POST /api/learning/record-feedback
```

**Suite 3: Fleet Dispatcher Endpoints**
```javascript
// These should return 401/403 without auth
GET /fleet/status
POST /fleet/dispatch
```

**Suite 4: SSH Command Generation**
```javascript
// These should return 401/403 without auth
GET /agent/execute-command
POST /agent/execute-command
```

**Suite 5: With Valid Authentication**
```javascript
// Test that valid auth is accepted (or at least not blocked)
GET /agent/execute (with Bearer token)
POST /agent/execute (with Bearer token)
```

## Test Results

### Output Format

Both test files produce results in similar formats:

#### Bash Script Output
```
========================================
Security Test: curl without auth
========================================

=== Agent Execute Endpoints ===
Testing: GET /agent/execute ... PASS (HTTP 401)
Testing: POST /agent/execute ... PASS (HTTP 403)

...

========================================
Test Summary
========================================
Passed:  12
Failed:  0
Total:   15
```

#### Node.js Test Output
```
========================================
Security Test: curl without auth
========================================
API Base URL: http://localhost:3000
Learning API URL: http://localhost:8000

=== Agent Execute Endpoints ===
=== Learning API Endpoints ===
=== Fleet Dispatcher Endpoints ===
=== SSH Command Generation ===
=== With Valid Authentication ===

========================================
Test Results Summary
========================================
Passed:  12
Failed:  0
Skipped: 3
Total:   15

Detailed Results:
────────────────────────────────────────
✅ GET /agent/execute (no auth)
   GET http://localhost:3000/agent/execute → HTTP 401
   Correctly rejected with HTTP 401
...
```

### Results File

Both tests save results to JSON files:

**Bash**: `security-curl-results.json`
```json
{
  "test_name": "Security - curl without auth",
  "timestamp": "2026-06-13T10:30:00Z",
  "summary": {
    "passed": 12,
    "failed": 0,
    "total": 15
  },
  "results": {
    "GET /agent/execute": "PASS: HTTP 401 (Auth required)",
    "POST /agent/execute": "PASS: HTTP 403 (Auth required)"
  }
}
```

**Node.js**: `security-curl-results.json`
```json
{
  "test_name": "Security Test: curl without auth",
  "timestamp": "2026-06-13T10:30:00Z",
  "config": {
    "baseUrl": "http://localhost:3000",
    "learningApiUrl": "http://localhost:8000"
  },
  "summary": {
    "passed": 12,
    "failed": 0,
    "skipped": 3,
    "total": 15
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

## Expected Test Results

### Security Test Expectations

For a properly secured API:

| Endpoint | Without Auth | With Valid Auth | Status |
|----------|-------------|-----------------|--------|
| GET /agent/execute | 401/403 | 200/201 | PASS |
| POST /agent/execute | 401/403 | 200/201 | PASS |
| GET /api/learning | 401/403 | 200/201 | PASS |
| POST /api/learning/record-feedback | 401/403 | 200/201 | PASS |
| GET /fleet/status | 401/403 | 200/201 | PASS |
| POST /fleet/dispatch | 401/403 | 200/201 | PASS |

### Response Codes

- **401 Unauthorized**: Request lacks valid authentication credentials
- **403 Forbidden**: Server understood request but refuses to authorize it
- **404 Not Found**: Endpoint doesn't exist (test skipped)
- **200 OK**: Request successful
- **201 Created**: Resource created successfully

## Security Implications

### Passing Tests ✅

If endpoints correctly return 401/403 without auth:
- Authentication is properly enforced
- Unauthorized access is prevented
- API endpoints are secure

### Failing Tests ❌

If endpoints return 200/201 without auth:
- **CRITICAL SECURITY ISSUE**: Endpoints are accessible without authentication
- Immediate action required to add authentication
- Sensitive data may be exposed

### Common Issues

1. **Endpoint not found (404)**
   - Endpoint may not be implemented yet
   - Server may not be running
   - URL may be incorrect

2. **Connection refused**
   - Server is not running
   - Port is incorrect
   - Network connectivity issue

3. **Timeout**
   - Server is slow or unresponsive
   - Network latency issue

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
name: Security Tests
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Run security tests
        run: |
          node test-security-curl-auth.js

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: security-results
          path: security-curl-results.json

      - name: Check test results
        run: |
          if grep -q '"failed": 0' security-curl-results.json; then
            echo "Security tests passed!"
            exit 0
          else
            echo "Security tests failed!"
            exit 1
          fi
```

### GitLab CI Example

```yaml
security_test:
  image: node:18
  script:
    - node test-security-curl-auth.js
  artifacts:
    paths:
      - security-curl-results.json
    reports:
      dotenv: security-curl-results.json
  allow_failure: false
```

## Manual Testing with curl

For manual testing, use curl directly:

### Test without auth (should fail)
```bash
# Should return 401 or 403
curl -v http://localhost:3000/agent/execute

# POST without auth
curl -v -X POST \
  -H "Content-Type: application/json" \
  -d '{"server":"test","model":"haiku","prompt":"test"}' \
  http://localhost:3000/agent/execute
```

### Test with auth (should succeed)
```bash
# Should return 200 or 201
curl -v \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:3000/agent/execute

# POST with auth
curl -v -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"server":"test","model":"haiku","prompt":"test"}' \
  http://localhost:3000/agent/execute
```

### Inspect Response Headers
```bash
# Show response headers and status
curl -i http://localhost:3000/agent/execute

# Verbose output with all details
curl -v http://localhost:3000/agent/execute
```

## Troubleshooting

### Test fails: "Server not running"
```bash
# Check if API servers are running
netstat -tuln | grep -E "3000|8000"

# Or use lsof
lsof -i :3000
lsof -i :8000
```

### Test returns 404 (Endpoint not found)
```bash
# Verify endpoint exists in your API
grep -r "/agent/execute\|/api/learning" /path/to/api

# Check API documentation
cat AGENT_EXECUTE_ENDPOINT.md
```

### Test hangs or times out
```bash
# Increase timeout in test file
# Edit test-security-curl-auth.js
# Change: timeout: 5000 → timeout: 10000

# Or test manually with curl timeout
curl --max-time 10 http://localhost:3000/agent/execute
```

## Authentication Methods Tested

The Node.js test suite supports these authentication methods:

1. **Bearer Token** (Default)
   ```javascript
   headers: {
     'Authorization': 'Bearer YOUR_TOKEN'
   }
   ```

2. **Custom Headers**
   ```javascript
   headers: {
     'X-API-Key': 'your-api-key',
     'Authorization': 'Bearer token'
   }
   ```

To add additional auth methods, modify the test file:

```javascript
// Add to testAuthAccepted function
headers: {
  'Authorization': `Bearer ${authToken}`,
  'X-API-Key': 'additional-key'
}
```

## Related Security Files

- `AGENT_EXECUTE_ENDPOINT.md` - API endpoint documentation
- `PERMISSIONS.md` - Permission configuration
- `code-security.js` - Security testing skill

## Recommendations

1. **Always Run Before Deployment**
   - Include these tests in CI/CD pipeline
   - Run before every deployment to production

2. **Monitor Results**
   - Track test results over time
   - Alert on any failures

3. **Regular Testing**
   - Run tests daily or on-demand
   - Test all authentication methods
   - Test with different user roles/permissions

4. **Security Audits**
   - Review failed tests immediately
   - Check server logs for suspicious activity
   - Verify authentication mechanism

5. **Token Management**
   - Use secure token storage
   - Rotate tokens regularly
   - Test with multiple token types

## References

- [HTTP Status Codes](https://httpwg.org/specs/rfc9110.html#status.codes)
- [RFC 6750 - OAuth 2.0 Bearer Token Usage](https://tools.ietf.org/html/rfc6750)
- [OWASP - Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [Node.js HTTP Module](https://nodejs.org/api/http.html)

## Author Notes

This security test suite is designed to:
- Be run in CI/CD pipelines
- Work with or without external servers
- Provide clear, actionable results
- Support both automated and manual testing

For questions or issues, refer to the documentation or run tests with DEBUG enabled.
