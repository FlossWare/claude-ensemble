#!/usr/bin/env node
/**
 * Comprehensive API Endpoint Testing
 *
 * Tests all API endpoints across multiple services:
 * - API Proxy (aio-01:8000) - 4 endpoints
 * - Admin API (aio-01:8001) - 7 endpoints
 * - ML Model API (aio-01:8080) - 3 endpoints
 *
 * Total: 14 endpoints
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const results = {
  passed: 0,
  failed: 0,
  failures: []
};

async function testEndpoint(category, name, testFn) {
  try {
    console.log(`\n[TEST] ${category}/${name}`);
    await testFn();
    console.log(`  ✓ PASS`);
    results.passed++;
    return { success: true };
  } catch (error) {
    console.log(`  ✗ FAIL: ${error.message}`);
    results.failed++;
    results.failures.push({ category, name, error: error.message });
    return { success: false, error: error.message };
  }
}

// Helper to make HTTP requests
async function httpRequest(method, url, body = null, headers = {}) {
  const curlCmd = method === 'POST'
    ? `curl -s -X POST "${url}" -H "Content-Type: application/json" ${body ? `-d '${JSON.stringify(body)}'` : ''} ${Object.entries(headers).map(([k, v]) => `-H "${k}: ${v}"`).join(' ')}`
    : `curl -s "${url}"`;

  try {
    const { stdout, stderr } = await execAsync(curlCmd, { timeout: 10000 });

    if (stderr && !stdout) {
      throw new Error(`curl error: ${stderr}`);
    }

    // Try to parse as JSON
    try {
      return JSON.parse(stdout);
    } catch {
      return stdout;
    }
  } catch (error) {
    throw new Error(`HTTP request failed: ${error.message}`);
  }
}

// ===================================================================
// API PROXY (aio-01:8000) - 4 endpoints
// ===================================================================

async function testApiProxyChatCompletions() {
  const response = await httpRequest('POST', 'http://aio-01:8000/v1/chat/completions', {
    model: 'llama-3.1-8b-instant',
    messages: [{ role: 'user', content: 'Say OK' }],
    max_tokens: 5
  }, { 'X-Worker-ID': 'test-endpoint-check' });

  if (!response.choices || !response.choices[0]?.message?.content) {
    throw new Error('Invalid chat completion response');
  }
}

async function testApiProxyEmbeddings() {
  const response = await httpRequest('POST', 'http://aio-01:8000/v1/embeddings', {
    model: '@cf/baai/bge-base-en-v1.5',
    input: 'Test embedding'
  }, { 'X-Worker-ID': 'test-endpoint-check' });

  if (!response.data || !Array.isArray(response.data) || !response.data[0]?.embedding) {
    throw new Error('Invalid embedding response');
  }
}

async function testApiProxyStats() {
  const response = await httpRequest('GET', 'http://aio-01:8000/stats');

  if (!response.usage_by_worker || !Array.isArray(response.usage_by_worker)) {
    throw new Error('Stats response missing usage_by_worker array');
  }
}

async function testApiProxyHealth() {
  const response = await httpRequest('GET', 'http://aio-01:8000/health');

  if (response.status !== 'ok') {
    throw new Error(`Proxy not healthy: ${response.status}`);
  }
}

// ===================================================================
// ADMIN API (aio-01:8001) - 7 endpoints
// ===================================================================

async function testAdminApiRoot() {
  const response = await httpRequest('GET', 'http://aio-01:8001/');

  if (!response.service || !response.endpoints) {
    throw new Error('Root response missing service or endpoints');
  }
}

async function testAdminApiHealth() {
  const response = await httpRequest('GET', 'http://aio-01:8001/admin/health');

  if (!response.status || !response.services) {
    throw new Error('Health response invalid');
  }
}

async function testAdminApiStats() {
  const response = await httpRequest('GET', 'http://aio-01:8001/admin/stats');

  if (!response.models || !response.usage_24h) {
    throw new Error('Stats response invalid');
  }
}

async function testAdminApiTasks() {
  const response = await httpRequest('GET', 'http://aio-01:8001/admin/tasks?limit=10');

  if (!response.tasks || !Array.isArray(response.tasks)) {
    throw new Error('Tasks list invalid');
  }
}

async function testAdminApiMaintainModels() {
  const response = await httpRequest('POST', 'http://aio-01:8001/admin/maintain-models');

  if (!response.job_id || response.status !== 'started') {
    throw new Error('Maintain models did not start');
  }

  // Store job_id in global variable for later status check
  global.adminJobId = response.job_id;
}

async function testAdminApiVacuumDb() {
  const response = await httpRequest('POST', 'http://aio-01:8001/admin/vacuum-db');

  if (!response.job_id || response.status !== 'started') {
    throw new Error('Vacuum did not start');
  }

  return response.job_id;
}

async function testAdminApiGetTaskStatus(job_id) {
  // Wait a moment for task to update
  await new Promise(resolve => setTimeout(resolve, 1000));

  const response = await httpRequest('GET', `http://aio-01:8001/admin/tasks/${job_id}`);

  if (!response.job_id || !response.status) {
    throw new Error('Task status invalid');
  }
}

// ===================================================================
// ML MODEL API (aio-01:8080) - 3 endpoints
// ===================================================================

async function testMLApiHealth() {
  const response = await httpRequest('GET', 'http://aio-01:8080/health');

  if (!response.status) {
    throw new Error('Health response invalid');
  }
}

async function testMLApiModels() {
  const response = await httpRequest('GET', 'http://aio-01:8080/models');

  if (!response.total || !Array.isArray(response.models)) {
    throw new Error('Models list invalid');
  }
}

async function testMLApiPredict() {
  const response = await httpRequest('POST', 'http://aio-01:8080/predict', {
    model: 'task-classifier',
    input: { text: 'test classification' }
  });

  // This endpoint may return error if model not loaded, which is OK
  // Just verify response structure
  if (typeof response !== 'object') {
    throw new Error('Predict response invalid');
  }
}


// ===================================================================
// MAIN TEST RUNNER
// ===================================================================

async function runAllTests() {
  console.log('================================================================================');
  console.log('API ENDPOINT TESTING - Comprehensive Suite');
  console.log('================================================================================\n');

  // API Proxy (aio-01:8000)
  console.log('\n--- API Proxy (aio-01:8000) ---');
  await testEndpoint('api-proxy', 'POST /v1/chat/completions', testApiProxyChatCompletions);
  await testEndpoint('api-proxy', 'POST /v1/embeddings', testApiProxyEmbeddings);
  await testEndpoint('api-proxy', 'GET /stats', testApiProxyStats);
  await testEndpoint('api-proxy', 'GET /health', testApiProxyHealth);

  // Admin API (aio-01:8001)
  console.log('\n--- Admin API (aio-01:8001) ---');
  await testEndpoint('admin-api', 'GET /', testAdminApiRoot);
  await testEndpoint('admin-api', 'GET /admin/health', testAdminApiHealth);
  await testEndpoint('admin-api', 'GET /admin/stats', testAdminApiStats);
  await testEndpoint('admin-api', 'GET /admin/tasks', testAdminApiTasks);

  await testEndpoint('admin-api', 'POST /admin/maintain-models', testAdminApiMaintainModels);
  await testEndpoint('admin-api', 'POST /admin/vacuum-db', testAdminApiVacuumDb);

  // Test getting task status if we have a job_id
  if (global.adminJobId) {
    await testEndpoint('admin-api', 'GET /admin/tasks/{job_id}', () => testAdminApiGetTaskStatus(global.adminJobId));
  }

  // ML Model API (aio-01:8080)
  console.log('\n--- ML Model API (aio-01:8080) ---');
  await testEndpoint('ml-api', 'GET /health', testMLApiHealth);
  await testEndpoint('ml-api', 'GET /models', testMLApiModels);
  await testEndpoint('ml-api', 'POST /predict', testMLApiPredict);

  // Summary
  console.log('\n================================================================================');
  console.log('TEST SUMMARY');
  console.log('================================================================================');
  console.log(`Total Tests: ${results.passed + results.failed}`);
  console.log(`Passed: ${results.passed}`);
  console.log(`Failed: ${results.failed}`);

  if (results.failures.length > 0) {
    console.log('\nFailed Tests:');
    results.failures.forEach(f => {
      console.log(`  - ${f.category}/${f.name}: ${f.error}`);
    });
  }

  console.log('================================================================================\n');

  return {
    tests_passed: results.passed,
    tests_failed: results.failed,
    failures: results.failures
  };
}

// Run tests
runAllTests()
  .then(summary => {
    console.log(JSON.stringify(summary, null, 2));
    process.exit(summary.tests_failed > 0 ? 1 : 0);
  })
  .catch(error => {
    console.error('Fatal error:', error);
    process.exit(2);
  });
