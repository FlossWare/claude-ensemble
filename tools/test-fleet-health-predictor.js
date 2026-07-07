#!/usr/bin/env node
/**
 * Fleet Health Predictor - Test Script
 *
 * Tests the predictive health system with synthetic metrics
 * to validate AI analysis pipeline without waiting for real degradation.
 */

import { analyzeWithHaiku, validateWithSonnet, decideMigrationWithOpus, checkImmediateTrigger } from './fleet-health-predictor.js';

// Synthetic test cases
const testCases = [
  {
    name: 'Healthy Server',
    hostname: 'server-01',
    metrics: {
      cpu_usage: generateHealthy(40, 60, 2016), // 7 days * 24h * 12 (5min intervals)
      memory_usage: generateHealthy(50, 60, 2016),
      load_avg: generateHealthy(1.5, 2.0, 2016),
      cpu_cores: Array(2016).fill(8),
      iowait: generateHealthy(5, 10, 2016),
      cpu_temp: generateHealthy(55, 65, 2016),
      memory_rss: generateLinear(8e9, 8.5e9, 2016) // Slight growth (normal)
    },
    expectedProbability: { min: 0.0, max: 0.3 }
  },
  {
    name: 'Memory Leak',
    hostname: 'server-02',
    metrics: {
      cpu_usage: generateHealthy(40, 60, 2016),
      memory_usage: generateLinear(60, 85, 2016), // Steady growth
      load_avg: generateHealthy(2.0, 2.5, 2016),
      cpu_cores: Array(2016).fill(8),
      iowait: generateHealthy(5, 10, 2016),
      cpu_temp: generateHealthy(55, 65, 2016),
      memory_rss: generateLinear(10e9, 28e9, 2016) // Severe growth
    },
    expectedProbability: { min: 0.7, max: 1.0 }
  },
  {
    name: 'CPU Thermal Degradation',
    hostname: 'server-03',
    metrics: {
      cpu_usage: generateHealthy(60, 80, 2016),
      memory_usage: generateHealthy(50, 60, 2016),
      load_avg: generateLinear(2.0, 3.5, 2016), // Increasing load
      cpu_cores: Array(2016).fill(8),
      iowait: generateHealthy(5, 10, 2016),
      cpu_temp: generateLinear(60, 82, 2016), // Temperature creep (approaching 85°C threshold)
      memory_rss: generateHealthy(10e9, 12e9, 2016)
    },
    expectedProbability: { min: 0.6, max: 0.9 }
  },
  {
    name: 'Disk I/O Saturation',
    hostname: 'laptop-01',
    metrics: {
      cpu_usage: generateHealthy(40, 60, 2016),
      memory_usage: generateHealthy(50, 60, 2016),
      load_avg: generateSpiky(1.5, 8.0, 2016), // Spikes due to I/O
      cpu_cores: Array(2016).fill(8),
      iowait: generateLinear(10, 45, 2016), // Increasing I/O wait (approaching 50% threshold)
      cpu_temp: generateHealthy(55, 65, 2016),
      memory_rss: generateHealthy(10e9, 12e9, 2016)
    },
    expectedProbability: { min: 0.5, max: 0.8 }
  },
  {
    name: 'Immediate Trigger (High CPU)',
    hostname: 'server-04',
    metrics: {
      cpu_usage: generateLinear(60, 88, 2016), // Approaching 90% (80% trigger = 72%)
      memory_usage: generateHealthy(50, 60, 2016),
      load_avg: generateHealthy(3.0, 4.0, 2016),
      cpu_cores: Array(2016).fill(8),
      iowait: generateHealthy(5, 10, 2016),
      cpu_temp: generateHealthy(55, 65, 2016),
      memory_rss: generateHealthy(10e9, 12e9, 2016)
    },
    expectedProbability: { min: 0.7, max: 1.0 },
    expectImmediateTrigger: true
  }
];

/**
 * Generate healthy fluctuating values
 */
function generateHealthy(min, max, count) {
  const values = [];
  const baseTime = Date.now() / 1000 - (count * 300); // 5-minute intervals

  for (let i = 0; i < count; i++) {
    const value = min + Math.random() * (max - min);
    values.push({
      timestamp: baseTime + (i * 300),
      value: parseFloat(value.toFixed(2))
    });
  }

  return values;
}

/**
 * Generate linear growth pattern
 */
function generateLinear(start, end, count) {
  const values = [];
  const baseTime = Date.now() / 1000 - (count * 300);
  const slope = (end - start) / count;

  for (let i = 0; i < count; i++) {
    const value = start + (slope * i) + (Math.random() * (end - start) * 0.05); // Add 5% noise
    values.push({
      timestamp: baseTime + (i * 300),
      value: parseFloat(value.toFixed(2))
    });
  }

  return values;
}

/**
 * Generate spiky pattern (periodic high values)
 */
function generateSpiky(baseline, spike, count) {
  const values = [];
  const baseTime = Date.now() / 1000 - (count * 300);

  for (let i = 0; i < count; i++) {
    // Spike every ~6 hours (72 intervals)
    const isSpike = i % 72 < 6;
    const value = isSpike
      ? spike + (Math.random() * spike * 0.1)
      : baseline + (Math.random() * baseline * 0.2);

    values.push({
      timestamp: baseTime + (i * 300),
      value: parseFloat(value.toFixed(2))
    });
  }

  return values;
}

/**
 * Run a single test case
 */
async function runTestCase(testCase) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`TEST CASE: ${testCase.name}`);
  console.log('='.repeat(60));

  // Step 1: Check immediate triggers
  console.log('\n[1/4] Checking immediate triggers...');
  const triggers = checkImmediateTrigger(testCase.metrics);
  if (triggers.length > 0) {
    console.log('  ⚠️  IMMEDIATE TRIGGERS DETECTED:');
    triggers.forEach(t => console.log(`    - ${t}`));
  } else {
    console.log('  ✅ No immediate triggers');
  }

  if (testCase.expectImmediateTrigger && triggers.length === 0) {
    console.log('  ❌ EXPECTED immediate trigger but none found');
  } else if (!testCase.expectImmediateTrigger && triggers.length > 0) {
    console.log('  ⚠️  Unexpected immediate trigger');
  }

  // Step 2: Haiku analysis
  console.log('\n[2/4] Analyzing with Haiku...');
  const analysis = await analyzeWithHaiku(testCase.metrics, testCase.hostname);
  console.log(`  Degradation probability: ${(analysis.degradation_probability * 100).toFixed(1)}%`);
  console.log(`  Primary risk: ${analysis.primary_risk}`);
  console.log(`  Recommendation: ${analysis.recommendation}`);
  console.log(`  Evidence: ${analysis.evidence.join(', ')}`);

  // Step 3: Sonnet validation
  console.log('\n[3/4] Validating with Sonnet...');
  const validation = await validateWithSonnet(analysis, testCase.metrics, testCase.hostname);
  console.log(`  Validated probability: ${(validation.validated_probability * 100).toFixed(1)}%`);
  console.log(`  Agreement: ${validation.agreement}`);
  console.log(`  Confidence: ${(validation.confidence * 100).toFixed(1)}%`);
  console.log(`  Reasoning: ${validation.reasoning}`);

  // Step 4: Opus migration decision
  console.log('\n[4/4] Decision with Opus...');
  const decision = await decideMigrationWithOpus(analysis, validation, testCase.hostname, 5);
  console.log(`  Action: ${decision.action}`);
  console.log(`  Urgency: ${decision.urgency}`);
  console.log(`  Reasoning: ${decision.reasoning}`);

  // Validate expected probability range
  const probInRange =
    validation.validated_probability >= testCase.expectedProbability.min &&
    validation.validated_probability <= testCase.expectedProbability.max;

  console.log('\n' + '-'.repeat(60));
  if (probInRange) {
    console.log(`✅ PASS: Probability ${(validation.validated_probability * 100).toFixed(1)}% within expected range [${(testCase.expectedProbability.min * 100).toFixed(0)}%-${(testCase.expectedProbability.max * 100).toFixed(0)}%]`);
  } else {
    console.log(`❌ FAIL: Probability ${(validation.validated_probability * 100).toFixed(1)}% outside expected range [${(testCase.expectedProbability.min * 100).toFixed(0)}%-${(testCase.expectedProbability.max * 100).toFixed(0)}%]`);
  }

  return {
    testCase: testCase.name,
    passed: probInRange,
    probability: validation.validated_probability,
    action: decision.action,
    urgency: decision.urgency
  };
}

/**
 * Main test runner
 */
async function main() {
  console.log('='.repeat(60));
  console.log('FLEET HEALTH PREDICTOR - TEST SUITE');
  console.log('='.repeat(60));
  console.log(`Running ${testCases.length} test cases with synthetic metrics`);

  const results = [];

  for (const testCase of testCases) {
    try {
      const result = await runTestCase(testCase);
      results.push(result);
    } catch (error) {
      console.error(`\n❌ Test case "${testCase.name}" failed: ${error.message}`);
      results.push({
        testCase: testCase.name,
        passed: false,
        error: error.message
      });
    }
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;

  results.forEach(r => {
    const status = r.passed ? '✅' : '❌';
    const prob = r.probability ? `${(r.probability * 100).toFixed(1)}%` : 'N/A';
    const action = r.action || 'N/A';
    console.log(`  ${status} ${r.testCase}: ${prob} → ${action}`);
  });

  console.log(`\nTotal: ${results.length} | Passed: ${passed} | Failed: ${failed}`);

  if (failed === 0) {
    console.log('\n✅ All tests passed!');
    process.exit(0);
  } else {
    console.log(`\n❌ ${failed} test(s) failed`);
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error(`Fatal error: ${error.message}`);
    process.exit(1);
  });
}
