#!/usr/bin/env node
/**
 * Red Hat Compliance Checker
 *
 * Checks for violations where Red Hat tasks used non-Anthropic models.
 * Exit codes:
 *   0 = No violations
 *   1 = Violations found
 *
 * Usage:
 *   node tools/check-redhat-compliance.cjs [hours]
 *   node tools/check-redhat-compliance.cjs 24  # Check last 24 hours
 *   node tools/check-redhat-compliance.cjs 168 # Check last 7 days
 */

const { checkRedHatCompliance } = require('../shared/model-usage-tracker.cjs');

const HOURS = process.argv[2] ? parseInt(process.argv[2]) : 24;

async function main() {
  console.log('========================================');
  console.log('RED HAT COMPLIANCE CHECK');
  console.log(`Period: Last ${HOURS} hours`);
  console.log('========================================\n');

  const violations = await checkRedHatCompliance(HOURS);

  if (violations.length === 0) {
    console.log('✓ NO VIOLATIONS DETECTED');
    console.log('');
    console.log('All Red Hat tasks used Anthropic models only.');
    console.log('Compliance status: PASS ✓');
    process.exit(0);
  }

  // Violations found!
  console.log(`✗ ${violations.length} VIOLATION(S) DETECTED!\n`);
  console.log('═══════════════════════════════════════════════════════════\n');

  for (let i = 0; i < violations.length; i++) {
    const v = violations[i];
    console.log(`VIOLATION #${i + 1}:`);
    console.log(`  Timestamp: ${new Date(v.timestamp).toLocaleString()}`);
    console.log(`  Task Type: ${v.task_type}`);
    console.log(`  Model Used: ${v.model} ⚠️  (NOT ANTHROPIC!)`);
    console.log(`  Workflow: ${v.workflow || 'unknown'}`);
    console.log(`  Filter Reason: ${v.filter_reason || 'none'}`);
    console.log(`  Pool Source: ${v.pool_source || 'unknown'}`);
    console.log('');
  }

  console.log('═══════════════════════════════════════════════════════════');
  console.log('\nCOMPLIANCE STATUS: FAIL ✗');
  console.log('\nACTION REQUIRED:');
  console.log('1. Investigate why non-Anthropic models were used');
  console.log('2. Check task-model-rules.cjs for correct filtering');
  console.log('3. Verify get-next-arbiter.js applies filters');
  console.log('4. Review workflow code that invoked these tasks');
  console.log('\nFor details:');
  console.log('  psql -h aio-01 -p 5433 -U claude -d learning');
  console.log('  SELECT * FROM monitoring.model_usage');
  console.log(`  WHERE task_type LIKE 'redhat_%'`);
  console.log(`  AND timestamp > NOW() - INTERVAL '${HOURS} hours';`);

  process.exit(1);
}

main().catch(err => {
  console.error('Error checking compliance:', err.message);
  process.exit(2);
});
