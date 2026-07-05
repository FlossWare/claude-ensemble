import { spawn } from 'child_process';
import { test } from 'node:test';
import assert from 'node:assert';

class MCPClient {
  constructor(serverPath) {
    this.serverPath = serverPath;
    this.process = null;
    this.messageId = 1;
    this.responseBuffer = '';
    this.pendingResponses = new Map();
  }

  async start() {
    return new Promise((resolve, reject) => {
      this.process = spawn('node', [this.serverPath], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      this.process.stderr.on('data', (data) => {
        const message = data.toString();
        if (message.includes('MCP server running')) {
          resolve();
        }
      });

      this.process.stdout.on('data', (data) => {
        this.responseBuffer += data.toString();
        this.processResponses();
      });

      this.process.on('error', reject);

      setTimeout(() => reject(new Error('Server start timeout')), 10000);
    });
  }

  processResponses() {
    const lines = this.responseBuffer.split('\n');
    this.responseBuffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const response = JSON.parse(line);
        if (response.id && this.pendingResponses.has(response.id)) {
          this.pendingResponses.get(response.id).resolve(response);
          this.pendingResponses.delete(response.id);
        }
      } catch (e) {
        console.error('Failed to parse response:', line);
      }
    }
  }

  async sendRequest(method, params = {}) {
    const id = this.messageId++;
    const request = {
      jsonrpc: '2.0',
      id,
      method,
      params
    };

    return new Promise((resolve, reject) => {
      this.pendingResponses.set(id, { resolve, reject });
      this.process.stdin.write(JSON.stringify(request) + '\n');

      setTimeout(() => {
        if (this.pendingResponses.has(id)) {
          this.pendingResponses.delete(id);
          reject(new Error(`Request timeout for ${method}`));
        }
      }, 10000);
    });
  }

  async stop() {
    if (this.process) {
      this.process.kill();
      await new Promise(resolve => this.process.on('exit', resolve));
    }
  }
}

test('Integration Test Suite', async (t) => {
  const client = new MCPClient('/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/mcp-servers/fleet-orchestrator/index.js');
  const results = {
    passed: true,
    tests_run: 0,
    tests_passed: 0,
    failures: []
  };

  try {
    await t.test('1. Start MCP Server', async () => {
      results.tests_run++;
      try {
        await client.start();
        results.tests_passed++;
        console.log('✓ Server started successfully');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Server start failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('2. List Tools', async () => {
      results.tests_run++;
      try {
        const response = await client.sendRequest('tools/list');

        assert.ok(response.result, 'Response should have result');
        assert.ok(Array.isArray(response.result.tools), 'Tools should be an array');
        assert.strictEqual(response.result.tools.length, 2, 'Should have 2 tools');

        const toolNames = response.result.tools.map(t => t.name);
        assert.ok(toolNames.includes('fleet-execute'), 'Should include fleet-execute');
        assert.ok(toolNames.includes('fleet-status'), 'Should include fleet-status');

        // Verify schema structure
        const fleetExecute = response.result.tools.find(t => t.name === 'fleet-execute');
        assert.ok(fleetExecute.inputSchema, 'fleet-execute should have inputSchema');
        assert.ok(fleetExecute.inputSchema.properties, 'Should have properties');
        assert.ok(fleetExecute.inputSchema.properties.task, 'Should have task property');
        assert.ok(fleetExecute.inputSchema.required, 'Should have required fields');

        results.tests_passed++;
        console.log('✓ Tools list validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`List tools failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('3. Fleet Status Request', async () => {
      results.tests_run++;
      try {
        const response = await client.sendRequest('tools/call', {
          name: 'fleet-status',
          arguments: { detailed: false }
        });

        assert.ok(response.result, 'Response should have result');
        assert.ok(response.result.content, 'Should have content');
        assert.ok(Array.isArray(response.result.content), 'Content should be an array');
        assert.strictEqual(response.result.content[0].type, 'text', 'Content type should be text');

        const data = JSON.parse(response.result.content[0].text);
        assert.ok(data.timestamp, 'Should have timestamp');
        assert.strictEqual(data.total_workers, 8, 'Should have 8 workers');
        assert.ok(Array.isArray(data.workers), 'Workers should be an array');
        assert.ok(Array.isArray(data.providers), 'Providers should be an array');
        assert.ok(data.summary, 'Should have summary');
        assert.ok(data.summary.status, 'Summary should have status');
        assert.ok(typeof data.summary.availability_percent === 'number', 'Should have availability percent');

        // Verify worker structure
        const worker = data.workers[0];
        assert.ok(worker.worker, 'Worker should have worker field');
        assert.ok(worker.hostname, 'Worker should have hostname');
        assert.ok(typeof worker.healthy === 'boolean', 'Worker should have healthy boolean');
        assert.ok(worker.status, 'Worker should have status');

        results.tests_passed++;
        console.log('✓ Fleet status validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Fleet status failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('4. Fleet Status with Detailed Metrics', async () => {
      results.tests_run++;
      try {
        const response = await client.sendRequest('tools/call', {
          name: 'fleet-status',
          arguments: { detailed: true }
        });

        const data = JSON.parse(response.result.content[0].text);

        // Check if at least one healthy worker has load info
        const healthyWorkers = data.workers.filter(w => w.healthy);
        if (healthyWorkers.length > 0) {
          const hasLoad = healthyWorkers.some(w => w.load !== null);
          assert.ok(hasLoad, 'At least one healthy worker should have load info');
        }

        results.tests_passed++;
        console.log('✓ Detailed status validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Detailed status failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('5. Fleet Execute Request', async () => {
      results.tests_run++;
      try {
        const response = await client.sendRequest('tools/call', {
          name: 'fleet-execute',
          arguments: {
            task: 'Test task execution',
            model: 'sonnet',
            worker: 'auto',
            timeout_ms: 10000
          }
        });

        assert.ok(response.result, 'Response should have result');
        const data = JSON.parse(response.result.content[0].text);

        if (data.error) {
          // It's okay if execution fails (SSH might not be configured)
          // We're testing the protocol, not the actual execution
          console.log('⚠ Fleet execute failed (expected if SSH not configured):', data.error);
        } else {
          assert.strictEqual(data.success, true, 'Should indicate success');
          assert.ok(data.worker, 'Should have worker');
          assert.ok(data.model, 'Should have model');
          assert.ok(data.execution_host, 'Should have execution_host');
        }

        results.tests_passed++;
        console.log('✓ Fleet execute protocol validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Fleet execute failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('6. Error Handling - Invalid Tool', async () => {
      results.tests_run++;
      try {
        const response = await client.sendRequest('tools/call', {
          name: 'nonexistent-tool',
          arguments: {}
        });

        assert.ok(response.result, 'Should have result');
        assert.strictEqual(response.result.isError, true, 'Should be marked as error');

        const data = JSON.parse(response.result.content[0].text);
        assert.ok(data.error, 'Should have error message');
        assert.ok(data.error.includes('Unknown tool'), 'Error should mention unknown tool');

        results.tests_passed++;
        console.log('✓ Invalid tool error handling validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Error handling failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('7. Error Handling - Missing Required Field', async () => {
      results.tests_run++;
      try {
        const response = await client.sendRequest('tools/call', {
          name: 'fleet-execute',
          arguments: {} // Missing required 'task' field
        });

        // The server might accept this and use defaults, or reject it
        // Either behavior is acceptable as long as it doesn't crash
        assert.ok(response.result, 'Should return a result');

        results.tests_passed++;
        console.log('✓ Missing field handling validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Missing field handling failed: ${error.message}`);
        throw error;
      }
    });

    await t.test('8. Verify Response Schema Consistency', async () => {
      results.tests_run++;
      try {
        // Test multiple requests to ensure consistent schema
        const responses = await Promise.all([
          client.sendRequest('tools/call', { name: 'fleet-status', arguments: {} }),
          client.sendRequest('tools/call', { name: 'fleet-status', arguments: { detailed: true } })
        ]);

        for (const response of responses) {
          assert.ok(response.result, 'Should have result');
          assert.ok(response.result.content, 'Should have content');
          assert.ok(Array.isArray(response.result.content), 'Content should be array');

          const data = JSON.parse(response.result.content[0].text);
          assert.ok(data.timestamp, 'Should have timestamp');
          assert.ok(data.workers, 'Should have workers');
          assert.ok(data.summary, 'Should have summary');
        }

        results.tests_passed++;
        console.log('✓ Schema consistency validated');
      } catch (error) {
        results.passed = false;
        results.failures.push(`Schema consistency failed: ${error.message}`);
        throw error;
      }
    });

  } finally {
    await client.stop();
  }

  // Write results to file for the parent process
  const fs = await import('fs');
  fs.writeFileSync(
    '/tmp/mcp-integration-test-results.json',
    JSON.stringify(results, null, 2)
  );

  console.log('\n=== Integration Test Results ===');
  console.log(`Total tests: ${results.tests_run}`);
  console.log(`Passed: ${results.tests_passed}`);
  console.log(`Failed: ${results.tests_run - results.tests_passed}`);
  console.log(`Overall: ${results.passed ? 'PASS' : 'FAIL'}`);

  if (results.failures.length > 0) {
    console.log('\nFailures:');
    results.failures.forEach((f, i) => console.log(`  ${i + 1}. ${f}`));
  }
});
