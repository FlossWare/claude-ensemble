/**
 * OpenClaw Phase 1 PoC Test
 *
 * Tests OpenClaw integration as 7th consensus voter with execution verification.
 * Success criteria:
 * - openclawHealthCheck() returns true
 * - OpenClaw response includes execution_performed: true
 * - Execution results show ZeroDivisionError
 * - Total response time under 60 seconds
 */

import { openclawQuery, openclawHealthCheck } from './shared/openclaw-client.js';

console.log('🧪 OpenClaw Phase 1 PoC Test\n');

// Step 1: Health check
console.log('Step 1: Health check...');
const healthy = await openclawHealthCheck('localhost');
console.log(`  OpenClaw healthy: ${healthy ? '✅' : '❌'}\n`);

if (!healthy) {
  console.log('⚠️  OpenClaw gateway not running.');
  console.log('   Start it with: openclaw gateway --port 18789 --verbose\n');
  process.exit(1);
}

// Step 2: Verification test
console.log('Step 2: Code execution verification test...');
console.log('  Testing Python function with empty list edge case\n');

const startTime = Date.now();

try {
  const response = await openclawQuery('localhost',
    `Review this Python function:

def avg(nums):
    return sum(nums) / len(nums)

What happens when called with an empty list?
EXECUTE the code to verify your analysis.`,
    {
      schema: {
        type: 'object',
        properties: {
          reasoning: { type: 'string' },
          execution_performed: { type: 'boolean' },
          execution_results: {
            type: 'object',
            properties: {
              command: { type: 'string' },
              stdout: { type: 'string' },
              stderr: { type: 'string' },
              exit_code: { type: 'number' }
            }
          },
          verification_status: { type: 'string', enum: ['passed', 'failed', 'not_testable'] },
          confidence: { type: 'number', minimum: 0, maximum: 100 }
        },
        required: ['reasoning', 'execution_performed', 'verification_status', 'confidence']
      }
    }
  );

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log('📊 OpenClaw Response:');
  console.log('─'.repeat(60));
  console.log(`  Reasoning: ${response.reasoning}`);
  console.log(`  Execution performed: ${response.execution_performed ? '✅' : '❌'}`);
  console.log(`  Verification status: ${response.verification_status}`);
  console.log(`  Confidence: ${response.confidence}%`);

  if (response.execution_results) {
    console.log('\n  Execution Results:');
    console.log(`    Command: ${response.execution_results.command}`);
    console.log(`    Exit code: ${response.execution_results.exit_code}`);
    console.log(`    Output: ${response.execution_results.stderr || response.execution_results.stdout}`);
  }

  console.log(`\n  Response time: ${elapsed}s`);
  console.log('─'.repeat(60));

  // Success criteria validation
  console.log('\n✅ Success Criteria:');
  const checks = [
    { name: 'Health check passed', pass: healthy },
    { name: 'Execution performed', pass: response.execution_performed },
    { name: 'Found ZeroDivisionError', pass: response.execution_results?.stderr?.includes('ZeroDivisionError') },
    { name: 'Response under 60s', pass: elapsed < 60 },
  ];

  checks.forEach(check => {
    console.log(`  ${check.pass ? '✅' : '❌'} ${check.name}`);
  });

  const allPassed = checks.every(c => c.pass);
  console.log(`\n${allPassed ? '🎉 All criteria passed!' : '⚠️  Some criteria failed'}`);

  process.exit(allPassed ? 0 : 1);

} catch (error) {
  console.error('\n❌ Test failed:', error.message);
  process.exit(1);
}
