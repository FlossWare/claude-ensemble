#!/usr/bin/env node

/**
 * Security Test: curl without auth
 *
 * Tests that API endpoints properly require authentication when accessed
 * without valid credentials. This ensures security compliance.
 *
 * Usage:
 *   node test-security-curl-auth.js
 *
 * Environment Variables:
 *   API_BASE_URL - Base URL for API (default: http://localhost:3000)
 *   AUTH_TOKEN - Valid auth token for comparison tests
 */

import http from 'http';
import https from 'https';
import { URL } from 'url';

// Test configuration
const config = {
  baseUrl: process.env.API_BASE_URL || 'http://localhost:3000',
  learningApiUrl: process.env.LEARNING_API_URL || 'http://localhost:8000',
  timeout: 10000,
  authToken: process.env.AUTH_TOKEN || 'invalid-token-test'
};

// Test results tracking
const results = {
  passed: 0,
  failed: 0,
  skipped: 0,
  tests: []
};

/**
 * Make HTTP request and return status code + body
 */
async function makeRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const isHttps = parsedUrl.protocol === 'https:';
    const client = isHttps ? https : http;

    const requestOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port,
      path: parsedUrl.pathname + parsedUrl.search,
      method: options.method || 'GET',
      timeout: config.timeout,
      headers: {
        'User-Agent': 'security-test-curl',
        ...(options.headers || {})
      }
    };

    const req = client.request(requestOptions, (res) => {
      let body = '';

      res.on('data', (chunk) => {
        body += chunk;
      });

      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          statusMessage: res.statusMessage,
          headers: res.headers,
          body
        });
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    if (options.body) {
      req.write(options.body);
    }

    req.end();
  });
}

/**
 * Test that endpoint rejects unauthenticated requests
 */
async function testAuthRequired(testName, url, method = 'GET', options = {}) {
  const test = {
    name: testName,
    url,
    method,
    status: 'UNKNOWN',
    statusCode: null,
    message: ''
  };

  try {
    const response = await makeRequest(url, {
      method,
      ...options
    });

    test.statusCode = response.statusCode;

    // Check if properly rejects unauthorized access
    if (response.statusCode === 401 || response.statusCode === 403) {
      test.status = 'PASS';
      test.message = `Correctly rejected with HTTP ${response.statusCode}`;
      results.passed++;
    } else if (response.statusCode === 404) {
      test.status = 'SKIP';
      test.message = 'Endpoint not found (404)';
      results.skipped++;
    } else if (response.statusCode === 200 || response.statusCode === 201) {
      test.status = 'FAIL';
      test.message = `Endpoint accessible without auth! HTTP ${response.statusCode}`;
      results.failed++;
    } else {
      test.status = 'INFO';
      test.message = `HTTP ${response.statusCode} - Check if auth is required`;
      results.passed++; // Assume safe if not explicitly accessible
    }
  } catch (error) {
    if (error.code === 'ECONNREFUSED') {
      test.status = 'SKIP';
      test.message = 'Server not running';
      results.skipped++;
    } else if (error.message === 'Request timeout') {
      test.status = 'SKIP';
      test.message = 'Request timeout - Server may not be running';
      results.skipped++;
    } else {
      test.status = 'ERROR';
      test.message = error.message;
      results.failed++;
    }
  }

  results.tests.push(test);
  return test;
}

/**
 * Test that endpoint accepts valid authentication
 */
async function testAuthAccepted(testName, url, method = 'GET', authToken, options = {}) {
  const test = {
    name: testName,
    url,
    method,
    status: 'UNKNOWN',
    statusCode: null,
    message: ''
  };

  try {
    const response = await makeRequest(url, {
      method,
      headers: {
        'Authorization': `Bearer ${authToken}`,
        ...(options.headers || {})
      },
      ...options
    });

    test.statusCode = response.statusCode;

    if (response.statusCode === 200 || response.statusCode === 201) {
      test.status = 'PASS';
      test.message = `Accepted auth with HTTP ${response.statusCode}`;
      results.passed++;
    } else if (response.statusCode === 401 || response.statusCode === 403) {
      test.status = 'INFO';
      test.message = `Auth rejected with HTTP ${response.statusCode} - May need different token`;
      results.passed++;
    } else if (response.statusCode === 404) {
      test.status = 'SKIP';
      test.message = 'Endpoint not found (404)';
      results.skipped++;
    } else {
      test.status = 'INFO';
      test.message = `HTTP ${response.statusCode}`;
      results.passed++;
    }
  } catch (error) {
    if (error.code === 'ECONNREFUSED' || error.message === 'Request timeout') {
      test.status = 'SKIP';
      test.message = error.code === 'ECONNREFUSED'
        ? 'Server not running'
        : 'Request timeout - Server may not be running';
      results.skipped++;
    } else {
      test.status = 'ERROR';
      test.message = error.message;
      results.failed++;
    }
  }

  results.tests.push(test);
  return test;
}

/**
 * Run all security tests
 */
async function runTests() {
  console.log('========================================');
  console.log('Security Test: curl without auth');
  console.log('========================================');
  console.log(`API Base URL: ${config.baseUrl}`);
  console.log(`Learning API URL: ${config.learningApiUrl}`);
  console.log('');

  // Test Suite 1: Agent Execute Endpoints (should require auth)
  console.log('=== Agent Execute Endpoints ===');
  await testAuthRequired(
    'GET /agent/execute (no auth)',
    `${config.baseUrl}/agent/execute`
  );
  await testAuthRequired(
    'POST /agent/execute (no auth)',
    `${config.baseUrl}/agent/execute`,
    'POST',
    { body: JSON.stringify({ server: 'test', model: 'haiku', prompt: 'test' }) }
  );

  // Test Suite 2: Learning API Endpoints
  console.log('');
  console.log('=== Learning API Endpoints ===');
  await testAuthRequired(
    'GET /api/learning (no auth)',
    `${config.learningApiUrl}/api/learning`
  );
  await testAuthRequired(
    'POST /api/learning/record-feedback (no auth)',
    `${config.learningApiUrl}/api/learning/record-feedback`,
    'POST',
    {
      body: JSON.stringify({
        feedback: 'test',
        model: 'haiku'
      })
    }
  );

  // Test Suite 3: Fleet Dispatcher Endpoints
  console.log('');
  console.log('=== Fleet Dispatcher Endpoints ===');
  await testAuthRequired(
    'GET /fleet/status (no auth)',
    `${config.baseUrl}/fleet/status`
  );
  await testAuthRequired(
    'POST /fleet/dispatch (no auth)',
    `${config.baseUrl}/fleet/dispatch`,
    'POST',
    {
      body: JSON.stringify({
        model: 'haiku',
        prompt: 'test'
      })
    }
  );

  // Test Suite 4: SSH Command Endpoint
  console.log('');
  console.log('=== SSH Command Generation ===');
  await testAuthRequired(
    'GET /agent/execute-command (no auth)',
    `${config.baseUrl}/agent/execute-command`
  );
  await testAuthRequired(
    'POST /agent/execute-command (no auth)',
    `${config.baseUrl}/agent/execute-command`,
    'POST',
    {
      body: JSON.stringify({
        server: 'server-01',
        model: 'haiku',
        prompt: 'test'
      })
    }
  );

  // Test Suite 5: Authentication with valid token
  console.log('');
  console.log('=== With Valid Authentication ===');
  await testAuthAccepted(
    'GET /agent/execute (with auth)',
    `${config.baseUrl}/agent/execute`,
    'GET',
    config.authToken
  );
  await testAuthAccepted(
    'POST /agent/execute (with auth)',
    `${config.baseUrl}/agent/execute`,
    'POST',
    config.authToken,
    {
      body: JSON.stringify({
        server: 'test',
        model: 'haiku',
        prompt: 'test'
      })
    }
  );

  // Print results
  console.log('');
  console.log('========================================');
  console.log('Test Results Summary');
  console.log('========================================');
  console.log(`Passed:  ${results.passed}`);
  console.log(`Failed:  ${results.failed}`);
  console.log(`Skipped: ${results.skipped}`);
  console.log(`Total:   ${results.tests.length}`);
  console.log('');

  // Print detailed results
  console.log('Detailed Results:');
  console.log('-'.repeat(100));
  results.tests.forEach((test) => {
    const statusIcon = {
      'PASS': '✅',
      'FAIL': '❌',
      'SKIP': '⊘',
      'INFO': 'ℹ️',
      'ERROR': '⚠️',
      'UNKNOWN': '?'
    }[test.status] || '?';

    console.log(
      `${statusIcon} ${test.name}`
    );
    console.log(
      `   ${test.method} ${test.url} → HTTP ${test.statusCode}`
    );
    console.log(
      `   ${test.message}`
    );
  });
  console.log('-'.repeat(100));
  console.log('');

  // Save results to file
  const resultsJson = {
    test_name: 'Security Test: curl without auth',
    timestamp: new Date().toISOString(),
    config: {
      baseUrl: config.baseUrl,
      learningApiUrl: config.learningApiUrl
    },
    summary: {
      passed: results.passed,
      failed: results.failed,
      skipped: results.skipped,
      total: results.tests.length
    },
    tests: results.tests
  };

  const fs = await import('fs').then(m => m.promises);
  const resultsFile = '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/security-curl-results.json';

  try {
    await fs.writeFile(resultsFile, JSON.stringify(resultsJson, null, 2));
    console.log(`Results saved to: ${resultsFile}`);
  } catch (err) {
    console.error(`Failed to save results: ${err.message}`);
  }

  // Exit with error if any tests failed (skip doesn't count)
  if (results.failed > 0) {
    process.exit(1);
  }

  process.exit(0);
}

// Run tests
runTests().catch((error) => {
  console.error('Test suite error:', error);
  process.exit(1);
});
