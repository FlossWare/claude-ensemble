/**
 * Test Tool Validation Workflow
 *
 * Demonstrates pre-tool validation hook blocking dangerous operations.
 * Tests various dangerous scenarios:
 *   - Bash: rm -rf /, dd if=/dev/zero, fork bombs
 *   - Write: Protected paths (/etc/passwd, /etc/shadow)
 *   - Edit: Non-existent files, permission issues
 *   - Read: Large files, permission denied
 *
 * Expected behavior: All dangerous operations should be blocked with validation errors.
 *
 * Created: 2026-07-01 (ECC issue #235)
 */

export const meta = {
  name: 'test-tool-validation',
  description: 'Test pre-tool validation hook - verify dangerous operations are blocked',
  whenToUse: 'Testing tool validation system (ECC issue #235)',
  phases: [
    { title: 'Setup', detail: 'Initialize validation system' },
    { title: 'Test Bash', detail: 'Test dangerous Bash commands' },
    { title: 'Test Write', detail: 'Test dangerous Write operations' },
    { title: 'Test Edit', detail: 'Test dangerous Edit operations' },
    { title: 'Test Read', detail: 'Test Read validation warnings' },
    { title: 'Report', detail: 'Show validation results' }
  ]
};

export default async function({ args, phase, log, agent, parallel }) {
  const { validateAndLogTool } = require('../hooks/pre-tool-validation.cjs');
  const { getWorkflowStorage } = require('../shared/workflow-storage-adapter.cjs');

  const db = getWorkflowStorage();
  const results = [];

  log('');
  log('='.repeat(70));
  log('Tool Validation Test Workflow');
  log('='.repeat(70));
  log('Testing pre-tool validation hook to verify dangerous operations are blocked');
  log('');

  // ============================================================================
  // PHASE 1: Setup
  // ============================================================================

  phase('Setup');

  // Create workflow execution record
  const execId = await db.storeExecution({
    workflow_id: `test-validation-${Date.now()}`,
    workflow_name: 'test-tool-validation',
    task_description: 'Test tool validation system - verify dangerous operations are blocked',
    total_workers: 0,
    total_duration_ms: 0,
    outcome: 'in_progress'
  });

  log(`✅ Workflow execution ID: ${execId}`);
  log('');

  // ============================================================================
  // PHASE 2: Test Dangerous Bash Commands
  // ============================================================================

  phase('Test Bash');

  const bashTests = [
    { command: 'rm -rf / --no-preserve-root', label: 'Delete root filesystem' },
    { command: 'dd if=/dev/zero of=/dev/sda', label: 'Overwrite disk' },
    { command: ':(){:|:&};:', label: 'Fork bomb' },
    { command: 'chmod -R 777 /', label: 'World-writable root' },
    { command: 'mkfs.ext4 /dev/sda1', label: 'Format partition' },
    { command: 'ls -la /tmp', label: 'Safe command (should pass)' }
  ];

  log(`Testing ${bashTests.length} Bash commands...`);
  log('');

  for (const test of bashTests) {
    try {
      const result = await validateAndLogTool('Bash', { command: test.command }, {
        workflowExecutionId: execId,
        blockOnError: true,
        logToDatabase: true,
        logWarnings: true
      });

      results.push({
        tool: 'Bash',
        label: test.label,
        command: test.command,
        valid: result.valid,
        errors: result.errors,
        warnings: result.warnings,
        blocked: !result.valid
      });

      if (result.valid) {
        log(`✅ PASS: ${test.label}`);
      } else {
        log(`❌ BLOCKED: ${test.label}`);
        log(`   Errors: ${result.errors.join('; ')}`);
      }

    } catch (error) {
      results.push({
        tool: 'Bash',
        label: test.label,
        command: test.command,
        valid: false,
        errors: [error.message],
        warnings: [],
        blocked: true
      });

      log(`❌ BLOCKED: ${test.label}`);
      log(`   Error: ${error.message}`);
    }
  }

  log('');

  // ============================================================================
  // PHASE 3: Test Dangerous Write Operations
  // ============================================================================

  phase('Test Write');

  const writeTests = [
    { file_path: '/etc/passwd', content: 'malicious', label: 'Write to /etc/passwd' },
    { file_path: '/etc/shadow', content: 'malicious', label: 'Write to /etc/shadow' },
    { file_path: '/etc/sudoers', content: 'malicious', label: 'Write to /etc/sudoers' },
    { file_path: '/boot/grub/grub.cfg', content: 'malicious', label: 'Write to /boot' },
    { file_path: '/tmp/test.txt', content: 'safe content', label: 'Write to /tmp (should pass)' }
  ];

  log(`Testing ${writeTests.length} Write operations...`);
  log('');

  for (const test of writeTests) {
    try {
      const result = await validateAndLogTool('Write', {
        file_path: test.file_path,
        content: test.content
      }, {
        workflowExecutionId: execId,
        blockOnError: true,
        logToDatabase: true,
        logWarnings: true
      });

      results.push({
        tool: 'Write',
        label: test.label,
        file_path: test.file_path,
        valid: result.valid,
        errors: result.errors,
        warnings: result.warnings,
        blocked: !result.valid
      });

      if (result.valid) {
        log(`✅ PASS: ${test.label}`);
        if (result.warnings.length > 0) {
          log(`   Warnings: ${result.warnings.join('; ')}`);
        }
      } else {
        log(`❌ BLOCKED: ${test.label}`);
        log(`   Errors: ${result.errors.join('; ')}`);
      }

    } catch (error) {
      results.push({
        tool: 'Write',
        label: test.label,
        file_path: test.file_path,
        valid: false,
        errors: [error.message],
        warnings: [],
        blocked: true
      });

      log(`❌ BLOCKED: ${test.label}`);
      log(`   Error: ${error.message}`);
    }
  }

  log('');

  // ============================================================================
  // PHASE 4: Test Edit Operations
  // ============================================================================

  phase('Test Edit');

  const editTests = [
    {
      file_path: '/etc/hosts',
      old_string: 'localhost',
      new_string: 'malicious',
      label: 'Edit /etc/hosts (should warn or block)'
    },
    {
      file_path: '/nonexistent/file.txt',
      old_string: 'old',
      new_string: 'new',
      label: 'Edit non-existent file (should block)'
    }
  ];

  log(`Testing ${editTests.length} Edit operations...`);
  log('');

  for (const test of editTests) {
    try {
      const result = await validateAndLogTool('Edit', {
        file_path: test.file_path,
        old_string: test.old_string,
        new_string: test.new_string
      }, {
        workflowExecutionId: execId,
        blockOnError: true,
        logToDatabase: true,
        logWarnings: true
      });

      results.push({
        tool: 'Edit',
        label: test.label,
        file_path: test.file_path,
        valid: result.valid,
        errors: result.errors,
        warnings: result.warnings,
        blocked: !result.valid
      });

      if (result.valid) {
        log(`✅ PASS: ${test.label}`);
        if (result.warnings.length > 0) {
          log(`   Warnings: ${result.warnings.join('; ')}`);
        }
      } else {
        log(`❌ BLOCKED: ${test.label}`);
        log(`   Errors: ${result.errors.join('; ')}`);
      }

    } catch (error) {
      results.push({
        tool: 'Edit',
        label: test.label,
        file_path: test.file_path,
        valid: false,
        errors: [error.message],
        warnings: [],
        blocked: true
      });

      log(`❌ BLOCKED: ${test.label}`);
      log(`   Error: ${error.message}`);
    }
  }

  log('');

  // ============================================================================
  // PHASE 5: Test Read Operations
  // ============================================================================

  phase('Test Read');

  const readTests = [
    { file_path: '/etc/hosts', label: 'Read /etc/hosts (should pass)' },
    { file_path: '/nonexistent/file.txt', label: 'Read non-existent file (should warn)' }
  ];

  log(`Testing ${readTests.length} Read operations...`);
  log('');

  for (const test of readTests) {
    try {
      const result = await validateAndLogTool('Read', {
        file_path: test.file_path
      }, {
        workflowExecutionId: execId,
        blockOnError: false, // Read validation only warns, doesn't block
        logToDatabase: true,
        logWarnings: true
      });

      results.push({
        tool: 'Read',
        label: test.label,
        file_path: test.file_path,
        valid: result.valid,
        errors: result.errors,
        warnings: result.warnings,
        blocked: !result.valid
      });

      if (result.valid) {
        log(`✅ PASS: ${test.label}`);
      } else {
        log(`⚠️  WARN: ${test.label}`);
        if (result.warnings.length > 0) {
          log(`   Warnings: ${result.warnings.join('; ')}`);
        }
      }

    } catch (error) {
      results.push({
        tool: 'Read',
        label: test.label,
        file_path: test.file_path,
        valid: false,
        errors: [error.message],
        warnings: [],
        blocked: false
      });

      log(`⚠️  WARN: ${test.label}`);
      log(`   Error: ${error.message}`);
    }
  }

  log('');

  // ============================================================================
  // PHASE 6: Report Results
  // ============================================================================

  phase('Report');

  const totalTests = results.length;
  const blockedTests = results.filter(r => r.blocked).length;
  const passedTests = results.filter(r => !r.blocked).length;

  log('');
  log('='.repeat(70));
  log('Test Summary');
  log('='.repeat(70));
  log(`Total tests: ${totalTests}`);
  log(`Blocked (dangerous): ${blockedTests}`);
  log(`Passed (safe): ${passedTests}`);
  log('');

  // Get validation stats from database
  const stats = await db.getValidationStats(execId);

  log('Database validation statistics:');
  for (const stat of stats) {
    log(`  ${stat.tool_name}: ${stat.passed}/${stat.total} passed (${stat.failed} failed)`);
    if (stat.errors && stat.errors.length > 0) {
      log(`    Common errors: ${stat.errors.slice(0, 3).join('; ')}`);
    }
  }

  log('');
  log('='.repeat(70));
  log('✅ Tool validation test complete');
  log('');

  return {
    status: 'success',
    workflow_execution_id: execId,
    total_tests: totalTests,
    blocked: blockedTests,
    passed: passedTests,
    results,
    database_stats: stats
  };
}
