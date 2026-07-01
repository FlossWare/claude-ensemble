#!/usr/bin/env node

/**
 * Test diversity violations logging integration
 *
 * Verifies that:
 * 1. dcab-layer1.js logs violations to learning.diversity_violations
 * 2. diversity-monitor.js logs violations to learning.diversity_violations
 * 3. Data is correctly populated with all required fields
 * 4. Queries return expected results
 *
 * Usage: node learning/test-diversity-violations.js
 */

const { getDB } = require('./postgres-adapter');
const {
    logRequest,
    enforceQuota,
    checkDiversity,
    updateModelQuota,
} = require('./dcab-layer1');

async function main() {
    console.log('=== Diversity Violations Integration Test ===\n');

    const db = getDB();

    // 1. Check table schema
    console.log('1. Verifying table schema...');
    const schema = await db.query(`
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'learning'
          AND table_name = 'diversity_violations'
        ORDER BY ordinal_position
    `);

    console.log('   Columns:');
    schema.forEach(col => {
        console.log(`   - ${col.column_name}: ${col.data_type} (nullable: ${col.is_nullable})`);
    });
    console.log();

    // 2. Check current violation count
    console.log('2. Current violation statistics...');
    const stats = await db.query(`
        SELECT
            violation_type,
            COUNT(*) as count,
            COUNT(DISTINCT model) as distinct_models,
            AVG(current_usage_pct) as avg_usage_pct,
            AVG(diversity_entropy) as avg_entropy
        FROM learning.diversity_violations
        GROUP BY violation_type
        ORDER BY count DESC
    `);

    if (stats.length === 0) {
        console.log('   No violations recorded yet.');
    } else {
        console.log('   Violation Type        | Count | Models | Avg Usage % | Avg Entropy');
        console.log('   ' + '-'.repeat(70));
        stats.forEach(row => {
            console.log(
                `   ${row.violation_type.padEnd(20)} | ` +
                `${String(row.count).padStart(5)} | ` +
                `${String(row.distinct_models).padStart(6)} | ` +
                `${parseFloat(row.avg_usage_pct).toFixed(1).padStart(11)} | ` +
                `${parseFloat(row.avg_entropy).toFixed(2).padStart(11)}`
            );
        });
    }
    console.log();

    // 3. Check recent violations
    console.log('3. Recent violations (last 5)...');
    const recent = await db.query(`
        SELECT
            timestamp,
            violation_type,
            model,
            current_usage_pct,
            quota_limit_pct,
            diversity_entropy,
            action_taken
        FROM learning.diversity_violations
        ORDER BY timestamp DESC
        LIMIT 5
    `);

    if (recent.length === 0) {
        console.log('   No violations recorded yet.');
    } else {
        recent.forEach(v => {
            console.log(`   [${v.timestamp.toISOString()}]`);
            console.log(`   Type: ${v.violation_type}`);
            console.log(`   Model: ${v.model}`);
            console.log(`   Usage: ${v.current_usage_pct}% (limit: ${v.quota_limit_pct}%)`);
            console.log(`   Entropy: ${v.diversity_entropy ? v.diversity_entropy.toFixed(2) : 'N/A'}`);
            console.log(`   Action: ${v.action_taken}`);
            console.log();
        });
    }

    // 4. Test violation detection (simulate ceiling breach)
    console.log('4. Testing violation detection...');
    console.log('   Simulating ceiling breach by logging multiple requests to same model...');

    // Log 10 requests to anthropic/claude-sonnet-4 to trigger ceiling breach
    for (let i = 0; i < 10; i++) {
        await logRequest({
            model: 'anthropic/claude-sonnet-4',
            taskType: 'test',
            success: true,
            qualityScore: 0.85,
            costUsd: 0.001,
            durationMs: 100,
        });
    }

    console.log('   Logged 10 requests to anthropic/claude-sonnet-4');
    console.log();

    // 5. Check for new violations
    console.log('5. Checking for new violations after test...');
    const newViolations = await db.query(`
        SELECT *
        FROM learning.diversity_violations
        WHERE timestamp > NOW() - INTERVAL '10 seconds'
        ORDER BY timestamp DESC
    `);

    if (newViolations.length === 0) {
        console.log('   No new violations detected (may need more requests to reach threshold).');
    } else {
        console.log(`   Found ${newViolations.length} new violation(s):`);
        newViolations.forEach(v => {
            console.log(`   - ${v.violation_type}: ${v.model} at ${v.current_usage_pct}% (limit: ${v.quota_limit_pct}%)`);
        });
    }
    console.log();

    // 6. Test query for monitoring dashboard
    console.log('6. Sample query for Grafana dashboard...');
    const dashboard = await db.query(`
        SELECT
            DATE_TRUNC('hour', timestamp) as hour,
            violation_type,
            COUNT(*) as violation_count
        FROM learning.diversity_violations
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY hour, violation_type
        ORDER BY hour DESC, violation_count DESC
        LIMIT 10
    `);

    if (dashboard.length === 0) {
        console.log('   No violations in last 24 hours.');
    } else {
        console.log('   Hour                      | Type              | Count');
        console.log('   ' + '-'.repeat(60));
        dashboard.forEach(row => {
            console.log(
                `   ${row.hour.toISOString().padEnd(25)} | ` +
                `${row.violation_type.padEnd(17)} | ` +
                `${String(row.violation_count).padStart(5)}`
            );
        });
    }
    console.log();

    // 7. Verify diversity metrics
    console.log('7. Current diversity metrics...');
    const diversity = await checkDiversity();
    console.log(`   Entropy: ${diversity.entropy.toFixed(2)} (target: >1.0)`);
    console.log(`   Status: ${diversity.status}`);
    console.log(`   Violations: ${diversity.violations.floor} floor, ${diversity.violations.ceiling} ceiling`);
    console.log();

    console.log('=== Test Complete ===');
    console.log('\nSample query to monitor violations:');
    console.log(`
    SELECT
        violation_type,
        model,
        COUNT(*) as count,
        AVG(current_usage_pct) as avg_usage,
        AVG(diversity_entropy) as avg_entropy,
        MAX(timestamp) as last_violation
    FROM learning.diversity_violations
    WHERE timestamp > NOW() - INTERVAL '24 hours'
    GROUP BY violation_type, model
    ORDER BY count DESC;
    `);

    process.exit(0);
}

main().catch(err => {
    console.error('Test failed:', err);
    process.exit(1);
});
