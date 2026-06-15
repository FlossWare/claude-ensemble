/**
 * Tests for GitHub Issue Integration
 *
 * Run: node github-issue-integration.test.js
 *
 * These tests verify the issue integration module works correctly.
 * For real testing, set up a test repository on GitHub.
 */

const assert = require('assert');
const {
  buildIssueBody,
  buildFixComment,
  detectRepository,
  CONFIG
} = require('./github-issue-integration.js');

// ============================================================================
// Test Utilities
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function describe(name, fn) {
  console.log(`\n${name}`);
  try {
    fn();
  } catch (err) {
    console.error(`  Error: ${err.message}`);
    testsFailed++;
  }
}

function it(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    testsPassed++;
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${err.message}`);
    testsFailed++;
  }
}

function assertEqual(actual, expected, message) {
  assert.strictEqual(actual, expected, message || 'Values not equal');
}

function assertIncludes(str, substr, message) {
  assert(str.includes(substr), message || `"${str}" does not include "${substr}"`);
}

function assertMatches(str, regex, message) {
  assert(regex.test(str), message || `"${str}" does not match ${regex}`);
}

// ============================================================================
// TESTS
// ============================================================================

describe('Issue Body Builder', () => {
  it('builds basic issue body', () => {
    const body = buildIssueBody({
      description: 'App crashes on startup',
      severity: 'blocker',
      workflowRunId: 'test-123',
      createdBy: 'fleet-validation',
      timestamp: '2024-01-15T10:30:00Z'
    });

    assertIncludes(body, 'App crashes on startup', 'Should include description');
    assertIncludes(body, '**Severity**: blocker', 'Should include severity');
    assertIncludes(body, 'test-123', 'Should include workflow run ID');
    assertIncludes(body, 'fleet-validation', 'Should include creator');
    assertIncludes(body, '2024-01-15T10:30:00Z', 'Should include timestamp');
  });

  it('includes failure details as JSON', () => {
    const body = buildIssueBody({
      description: 'Test failed',
      severity: 'bug',
      workflowRunId: 'test-456',
      failureDetails: {
        testName: 'smoke-api',
        error: 'Connection timeout',
        statusCode: 504
      },
      createdBy: 'fleet',
      timestamp: '2024-01-15T10:30:00Z'
    });

    assertIncludes(body, 'Failure Details', 'Should have failure details section');
    assertIncludes(body, 'testName', 'Should include test name');
    assertIncludes(body, 'smoke-api', 'Should include test value');
    assertIncludes(body, 'Connection timeout', 'Should include error');
    assertIncludes(body, '504', 'Should include status code');
  });

  it('omits failure details when empty', () => {
    const body = buildIssueBody({
      description: 'Simple test failure',
      severity: 'bug',
      workflowRunId: 'test-789',
      failureDetails: {},
      createdBy: 'fleet',
      timestamp: '2024-01-15T10:30:00Z'
    });

    assert(!body.includes('Failure Details'), 'Should not include empty failure details');
  });

  it('marks as auto-created', () => {
    const body = buildIssueBody({
      description: 'Test',
      severity: 'bug',
      workflowRunId: 'test',
      createdBy: 'fleet-validation',
      timestamp: '2024-01-15T10:30:00Z'
    });

    assertIncludes(body, 'automatically created', 'Should mark as automatically created');
    assertIncludes(body, 'fleet validation workflow', 'Should mention validation workflow');
  });
});

describe('Fix Comment Builder', () => {
  it('builds fix comment with details and commits', () => {
    const comment = buildFixComment({
      fixDetails: 'Updated health check to return 200 OK',
      commitShas: ['abc123def456', 'ghi789jkl012'],
      appliedBy: 'fleet-validation',
      timestamp: '2024-01-15T10:31:00Z'
    });

    assertIncludes(comment, 'Fix Applied', 'Should have fix section');
    assertIncludes(comment, 'Updated health check', 'Should include fix details');
    assertIncludes(comment, 'abc123def456', 'Should include first commit');
    assertIncludes(comment, 'ghi789jkl012', 'Should include second commit');
    assertIncludes(comment, 'fleet-validation', 'Should include applier');
    assertIncludes(comment, '2024-01-15T10:31:00Z', 'Should include timestamp');
  });

  it('builds fix comment without commits', () => {
    const comment = buildFixComment({
      fixDetails: 'Applied manual fix',
      commitShas: [],
      appliedBy: 'human',
      timestamp: '2024-01-15T10:31:00Z'
    });

    assertIncludes(comment, 'Applied manual fix', 'Should include fix details');
    assert(!comment.includes('Related Commits'), 'Should not have commits section if empty');
  });

  it('formats commits as code blocks', () => {
    const comment = buildFixComment({
      fixDetails: 'Fix',
      commitShas: ['abc123'],
      appliedBy: 'fleet',
      timestamp: '2024-01-15T10:31:00Z'
    });

    assertIncludes(comment, '`abc123`', 'Should format commit as code');
  });
});

describe('Repository Detection', () => {
  it('detects when not in git repo', () => {
    try {
      detectRepository();
      assert.fail('Should throw error when not in git repo');
    } catch (err) {
      assertIncludes(err.message, 'Could not detect', 'Should mention detection failure');
    }
  });
});

describe('Configuration', () => {
  it('has all required labels', () => {
    const labels = CONFIG.LABELS;

    assertEqual(labels.BLOCKER, 'validation-blocker');
    assertEqual(labels.BUG, 'validation-bug');
    assertEqual(labels.FLAKY, 'validation-flaky');
    assertEqual(labels.PERFORMANCE, 'validation-performance');
    assertEqual(labels.SECURITY, 'validation-security');
    assertEqual(labels.AUTO_CREATED, 'auto-created');
  });

  it('has state file configured', () => {
    assertEqual(CONFIG.STATE_FILE, '.claude/workflow-issue-state.json');
  });
});

describe('Issue Body Structure', () => {
  it('contains proper markdown headers', () => {
    const body = buildIssueBody({
      description: 'Test failure',
      severity: 'blocker',
      workflowRunId: 'test',
      failureDetails: { error: 'Segfault' },
      createdBy: 'fleet',
      timestamp: '2024-01-15T10:30:00Z'
    });

    assertMatches(body, /## Metadata/, 'Should have Metadata header');
    assertMatches(body, /## Failure Details/, 'Should have Failure Details header');
  });

  it('includes all metadata fields', () => {
    const body = buildIssueBody({
      description: 'Description',
      severity: 'bug',
      workflowRunId: 'workflow-123',
      createdBy: 'automation',
      timestamp: '2024-01-15T10:30:00Z',
      failureDetails: {}
    });

    assertIncludes(body, '**Severity**:', 'Should include severity field');
    assertIncludes(body, '**Created by**:', 'Should include created by field');
    assertIncludes(body, '**Timestamp**:', 'Should include timestamp field');
    assertIncludes(body, '**Workflow Run ID**:', 'Should include workflow run ID field');
  });

  it('escapes JSON special characters in failure details', () => {
    const body = buildIssueBody({
      description: 'Test',
      severity: 'bug',
      workflowRunId: 'test',
      failureDetails: {
        message: 'Failed with "quote" and \\ backslash',
        code: '<script>alert("xss")</script>'
      },
      createdBy: 'fleet',
      timestamp: '2024-01-15T10:30:00Z'
    });

    // JSON should be properly formatted
    assertIncludes(body, 'Failed with', 'Should include message');
    assertIncludes(body, '<script>', 'Should include HTML (in JSON block)');
  });
});

describe('Fix Comment Structure', () => {
  it('has required sections', () => {
    const comment = buildFixComment({
      fixDetails: 'Applied patch',
      commitShas: ['abc123'],
      appliedBy: 'fleet',
      timestamp: '2024-01-15T10:31:00Z'
    });

    assertMatches(comment, /## Fix Applied/, 'Should have Fix Applied header');
    assertMatches(comment, /### Related Commits/, 'Should have Related Commits subheader');
    assertIncludes(comment, 'Applied by:', 'Should have applied by field');
    assertIncludes(comment, 'Timestamp:', 'Should have timestamp field');
  });

  it('formats multiple commits properly', () => {
    const comment = buildFixComment({
      fixDetails: 'Fix',
      commitShas: ['sha1', 'sha2', 'sha3'],
      appliedBy: 'fleet',
      timestamp: '2024-01-15T10:31:00Z'
    });

    assertEqual((comment.match(/^- `/gm) || []).length, 3, 'Should have 3 commit lines');
  });
});

describe('Severity Labels', () => {
  it('maps severity to correct label', () => {
    const severities = {
      'blocker': CONFIG.LABELS.BLOCKER,
      'bug': CONFIG.LABELS.BUG,
      'flaky': CONFIG.LABELS.FLAKY,
      'performance': CONFIG.LABELS.PERFORMANCE,
      'security': CONFIG.LABELS.SECURITY
    };

    Object.entries(severities).forEach(([sev, label]) => {
      assertEqual(
        label,
        `validation-${sev}`,
        `Severity ${sev} should map to validation-${sev}`
      );
    });
  });
});

describe('Integration Scenarios', () => {
  it('creates complete validation failure issue body', () => {
    const scenario = {
      description: 'Smoke test failed: App crashes on startup',
      severity: 'blocker',
      workflowRunId: 'smoke-test-2024-01-15-abc123',
      failureDetails: {
        phase: 'Launch',
        command: './run.sh',
        exitCode: 139,
        signal: 'SIGSEGV',
        error: 'Segmentation fault in native module'
      },
      createdBy: 'fleet-validation',
      timestamp: '2024-01-15T10:30:00Z'
    };

    const body = buildIssueBody(scenario);

    // Verify complete structure
    assertIncludes(body, 'Smoke test failed', 'Should include description');
    assertIncludes(body, 'Blocker', 'Should include severity');
    assertIncludes(body, 'smoke-test-2024-01-15-abc123', 'Should include run ID');
    assertIncludes(body, 'SIGSEGV', 'Should include error details');
    assertIncludes(body, 'fleet-validation', 'Should include creator');
  });

  it('creates complete fix comment', () => {
    const scenario = {
      fixDetails: `Applied fix for native module segfault.

      - Updated binding.gyp to fix memory allocation
      - Rebuilt native module with sanitizers
      - Verified with AddressSanitizer`,
      commitShas: ['abc123def456', 'ghi789jkl012'],
      appliedBy: 'fleet-validation',
      timestamp: '2024-01-15T10:31:00Z'
    };

    const comment = buildFixComment(scenario);

    assertIncludes(comment, 'Fix Applied', 'Should be marked as fix');
    assertIncludes(comment, 'binding.gyp', 'Should include fix details');
    assertIncludes(comment, 'abc123def456', 'Should link first commit');
    assertIncludes(comment, 'ghi789jkl012', 'Should link second commit');
    assertIncludes(comment, 'fleet-validation', 'Should show who applied it');
  });
});

// ============================================================================
// Results
// ============================================================================

console.log(`\n${'='.repeat(60)}`);
console.log(`Tests: ${testsPassed} passed, ${testsFailed} failed`);
console.log(`${'='.repeat(60)}`);

if (testsFailed > 0) {
  process.exit(1);
} else {
  console.log('\nAll tests passed!');
  process.exit(0);
}
