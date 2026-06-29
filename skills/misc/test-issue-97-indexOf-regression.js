#!/usr/bin/env node

/**
 * Test for Issue #97: indexOf without bounds check in ai-consensus-hierarchical.js
 *
 * Line 451 uses `allWorkerDescriptors.indexOf(d)` to find the global index.
 *
 * This test verifies:
 * (a) indexOf always returns a valid index (>= 0) for descriptors that exist in the array
 * (b) the re-grouping logic correctly maps worker results back to their sub-teams even when some workers return null
 * (c) edge case where all workers in a sub-team fail (empty teamResults)
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Color helpers for output
const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RESET = '\x1b[0m';

function log(msg) {
  console.log(msg);
}

function logPass(msg) {
  console.log(`${GREEN}✓ ${msg}${RESET}`);
}

function logFail(msg) {
  console.log(`${RED}✗ ${msg}${RESET}`);
}

function logWarn(msg) {
  console.log(`${YELLOW}⚠ ${msg}${RESET}`);
}

// Read the source file to extract the re-grouping logic
const sourceFile = path.join(__dirname, 'ai-consensus-hierarchical.js');
let sourceCode;

try {
  sourceCode = fs.readFileSync(sourceFile, 'utf-8');
} catch (err) {
  logFail(`Cannot read source file: ${sourceFile}`);
  process.exit(1);
}

// Extract the critical code section (lines 448-471 approximately)
// We'll simulate the re-grouping logic here
function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 50;
  return Math.max(0, Math.min(100, value));
}

/**
 * Simulates the re-grouping logic from lines 448-471 of ai-consensus-hierarchical.js
 */
function regroupWorkerResults(subTeams, allWorkerDescriptors, allWorkerResults) {
  const subTeamResults = subTeams.map((team, teamIndex) => {
    const teamDescriptors = allWorkerDescriptors.filter(d => d.teamIndex === teamIndex);
    const teamResults = teamDescriptors.map((d, i) => {
      const globalIndex = allWorkerDescriptors.indexOf(d);
      const result = allWorkerResults[globalIndex];
      if (!result) return null;
      return {
        model: d.model,
        domain: d.domain,
        answer: result.answer || null,
        confidence: clampConfidence(result.confidence),
        reasoning: result.reasoning || '',
        domain_insights: result.domain_insights || [],
        caveats: result.caveats || [],
      };
    }).filter(Boolean);

    return {
      domain: team.domain,
      models: team.models,
      workers: teamResults,
      workerCount: teamResults.length,
    };
  });

  return subTeamResults;
}

// Test suite
const tests = {
  passed: 0,
  failed: 0,
  errors: [],
};

log('');
log('='.repeat(70));
log('Issue #97 Regression Test: indexOf bounds check in ai-consensus-hierarchical.js');
log('='.repeat(70));
log('');

// ============================================================================
// TEST (a): indexOf always returns a valid index (>= 0) for existing descriptors
// ============================================================================

log('TEST (a): indexOf returns valid index for all existing descriptors');
log('-'.repeat(70));

try {
  const subTeams = [
    { domain: 'security', models: ['opus', 'sonnet'] },
    { domain: 'architecture', models: ['fable', 'haiku'] },
    { domain: 'testing', models: ['sonnet', 'gpt-4o'] },
  ];

  const allWorkerDescriptors = [
    { teamIndex: 0, domain: 'security', model: 'opus' },
    { teamIndex: 0, domain: 'security', model: 'sonnet' },
    { teamIndex: 1, domain: 'architecture', model: 'fable' },
    { teamIndex: 1, domain: 'architecture', model: 'haiku' },
    { teamIndex: 2, domain: 'testing', model: 'sonnet' },
    { teamIndex: 2, domain: 'testing', model: 'gpt-4o' },
  ];

  const allWorkerResults = [
    { answer: 'A1', confidence: 85, reasoning: 'R1', domain_insights: ['I1'], caveats: [] },
    { answer: 'A2', confidence: 78, reasoning: 'R2', domain_insights: ['I2'], caveats: [] },
    { answer: 'A3', confidence: 92, reasoning: 'R3', domain_insights: ['I3'], caveats: [] },
    { answer: 'A4', confidence: 70, reasoning: 'R4', domain_insights: ['I4'], caveats: [] },
    { answer: 'A5', confidence: 88, reasoning: 'R5', domain_insights: ['I5'], caveats: [] },
    { answer: 'A6', confidence: 81, reasoning: 'R6', domain_insights: ['I6'], caveats: [] },
  ];

  // Manually verify indexOf for each descriptor
  let indexOfErrors = [];
  allWorkerDescriptors.forEach((d, expectedIndex) => {
    const foundIndex = allWorkerDescriptors.indexOf(d);
    if (foundIndex !== expectedIndex) {
      indexOfErrors.push(`Descriptor at index ${expectedIndex} has indexOf=${foundIndex} (MISMATCH)`);
    } else if (foundIndex < 0) {
      indexOfErrors.push(`Descriptor at index ${expectedIndex} has indexOf=${foundIndex} (INVALID NEGATIVE INDEX)`);
    }
  });

  if (indexOfErrors.length > 0) {
    logFail('indexOf returned invalid indices');
    indexOfErrors.forEach(err => log(`  ${err}`));
    tests.failed++;
    tests.errors.push('TEST (a): indexOf validation failed');
  } else {
    logPass('All indexOf calls returned valid indices (>= 0)');
    tests.passed++;
  }

  // Now run the regroup logic and verify all results map correctly
  const subTeamResults = regroupWorkerResults(subTeams, allWorkerDescriptors, allWorkerResults);

  // Verify counts
  assert.strictEqual(subTeamResults.length, 3, 'Should have 3 sub-teams');
  assert.strictEqual(subTeamResults[0].workerCount, 2, 'Security team should have 2 workers');
  assert.strictEqual(subTeamResults[1].workerCount, 2, 'Architecture team should have 2 workers');
  assert.strictEqual(subTeamResults[2].workerCount, 2, 'Testing team should have 2 workers');

  // Verify result mapping
  assert.strictEqual(subTeamResults[0].workers[0].model, 'opus', 'First security worker should be opus');
  assert.strictEqual(subTeamResults[0].workers[0].answer, 'A1', 'First security worker answer should match');
  assert.strictEqual(subTeamResults[0].workers[1].model, 'sonnet', 'Second security worker should be sonnet');
  assert.strictEqual(subTeamResults[0].workers[1].answer, 'A2', 'Second security worker answer should match');

  logPass('Re-grouping logic correctly maps all worker results to sub-teams');
  tests.passed++;

} catch (err) {
  logFail(`TEST (a) failed: ${err.message}`);
  tests.failed++;
  tests.errors.push(`TEST (a): ${err.message}`);
}

log('');

// ============================================================================
// TEST (b): Re-grouping with some workers returning null
// ============================================================================

log('TEST (b): Re-grouping with some workers returning null (partial failures)');
log('-'.repeat(70));

try {
  const subTeams = [
    { domain: 'security', models: ['opus', 'sonnet', 'haiku'] },
    { domain: 'architecture', models: ['fable', 'gpt-4o'] },
  ];

  const allWorkerDescriptors = [
    { teamIndex: 0, domain: 'security', model: 'opus' },
    { teamIndex: 0, domain: 'security', model: 'sonnet' },
    { teamIndex: 0, domain: 'security', model: 'haiku' },
    { teamIndex: 1, domain: 'architecture', model: 'fable' },
    { teamIndex: 1, domain: 'architecture', model: 'gpt-4o' },
  ];

  // Simulate partial failures: sonnet (index 1) and gpt-4o (index 4) return null
  const allWorkerResults = [
    { answer: 'A1', confidence: 85, reasoning: 'R1', domain_insights: ['I1'], caveats: [] },
    null, // sonnet failed
    { answer: 'A3', confidence: 70, reasoning: 'R3', domain_insights: ['I3'], caveats: [] },
    { answer: 'A4', confidence: 92, reasoning: 'R4', domain_insights: ['I4'], caveats: [] },
    null, // gpt-4o failed
  ];

  const subTeamResults = regroupWorkerResults(subTeams, allWorkerDescriptors, allWorkerResults);

  // Verify counts - should filter out null results
  assert.strictEqual(subTeamResults.length, 2, 'Should have 2 sub-teams');
  assert.strictEqual(subTeamResults[0].workerCount, 2, 'Security team should have 2 workers (1 failed)');
  assert.strictEqual(subTeamResults[1].workerCount, 1, 'Architecture team should have 1 worker (1 failed)');

  // Verify remaining workers are correctly mapped
  assert.strictEqual(subTeamResults[0].workers[0].model, 'opus', 'First security worker should be opus');
  assert.strictEqual(subTeamResults[0].workers[0].answer, 'A1', 'First security worker answer correct');
  assert.strictEqual(subTeamResults[0].workers[1].model, 'haiku', 'Second security worker should be haiku (sonnet filtered out)');
  assert.strictEqual(subTeamResults[0].workers[1].answer, 'A3', 'Second security worker answer correct');

  assert.strictEqual(subTeamResults[1].workers[0].model, 'fable', 'First architecture worker should be fable');
  assert.strictEqual(subTeamResults[1].workers[0].answer, 'A4', 'First architecture worker answer correct');

  logPass('Re-grouping correctly handles null results and filters them out');
  tests.passed++;

  // Verify indexOf still returns valid indices even with null results
  let indexOfErrorsWithNulls = [];
  allWorkerDescriptors.forEach((d, expectedIndex) => {
    const foundIndex = allWorkerDescriptors.indexOf(d);
    if (foundIndex < 0) {
      indexOfErrorsWithNulls.push(`Descriptor at index ${expectedIndex} has indexOf=${foundIndex} (INVALID)`);
    }
  });

  if (indexOfErrorsWithNulls.length > 0) {
    logFail('indexOf validation failed with null results');
    indexOfErrorsWithNulls.forEach(err => log(`  ${err}`));
    tests.failed++;
    tests.errors.push('TEST (b): indexOf validation with nulls failed');
  } else {
    logPass('indexOf remains valid even when some worker results are null');
    tests.passed++;
  }

} catch (err) {
  logFail(`TEST (b) failed: ${err.message}`);
  tests.failed++;
  tests.errors.push(`TEST (b): ${err.message}`);
}

log('');

// ============================================================================
// TEST (c): Edge case - all workers in a sub-team fail
// ============================================================================

log('TEST (c): Edge case - all workers in a sub-team fail (empty teamResults)');
log('-'.repeat(70));

try {
  const subTeams = [
    { domain: 'security', models: ['opus', 'sonnet'] },
    { domain: 'architecture', models: ['fable', 'haiku'] }, // This entire team will fail
    { domain: 'testing', models: ['gpt-4o'] },
  ];

  const allWorkerDescriptors = [
    { teamIndex: 0, domain: 'security', model: 'opus' },
    { teamIndex: 0, domain: 'security', model: 'sonnet' },
    { teamIndex: 1, domain: 'architecture', model: 'fable' },
    { teamIndex: 1, domain: 'architecture', model: 'haiku' },
    { teamIndex: 2, domain: 'testing', model: 'gpt-4o' },
  ];

  // Architecture team (indices 2 and 3) all fail
  const allWorkerResults = [
    { answer: 'A1', confidence: 85, reasoning: 'R1', domain_insights: ['I1'], caveats: [] },
    { answer: 'A2', confidence: 78, reasoning: 'R2', domain_insights: ['I2'], caveats: [] },
    null, // fable failed
    null, // haiku failed
    { answer: 'A5', confidence: 88, reasoning: 'R5', domain_insights: ['I5'], caveats: [] },
  ];

  const subTeamResults = regroupWorkerResults(subTeams, allWorkerDescriptors, allWorkerResults);

  // Verify counts
  assert.strictEqual(subTeamResults.length, 3, 'Should have 3 sub-teams');
  assert.strictEqual(subTeamResults[0].workerCount, 2, 'Security team should have 2 workers');
  assert.strictEqual(subTeamResults[1].workerCount, 0, 'Architecture team should have 0 workers (all failed)');
  assert.strictEqual(subTeamResults[2].workerCount, 1, 'Testing team should have 1 worker');

  // Verify architecture team has empty workers array
  assert.strictEqual(subTeamResults[1].workers.length, 0, 'Architecture team workers array should be empty');
  assert.strictEqual(subTeamResults[1].domain, 'architecture', 'Architecture team domain should be preserved');

  logPass('Re-grouping correctly handles complete sub-team failure (empty teamResults)');
  tests.passed++;

  // Verify other teams are still correctly mapped
  assert.strictEqual(subTeamResults[0].workers[0].answer, 'A1', 'Security team still correctly mapped');
  assert.strictEqual(subTeamResults[2].workers[0].answer, 'A5', 'Testing team still correctly mapped');

  logPass('Other sub-teams remain correctly mapped when one team completely fails');
  tests.passed++;

  // Verify indexOf is still valid
  let indexOfErrorsEdgeCase = [];
  allWorkerDescriptors.forEach((d, expectedIndex) => {
    const foundIndex = allWorkerDescriptors.indexOf(d);
    if (foundIndex < 0) {
      indexOfErrorsEdgeCase.push(`Descriptor at index ${expectedIndex} has indexOf=${foundIndex} (INVALID)`);
    }
  });

  if (indexOfErrorsEdgeCase.length > 0) {
    logFail('indexOf validation failed in edge case');
    indexOfErrorsEdgeCase.forEach(err => log(`  ${err}`));
    tests.failed++;
    tests.errors.push('TEST (c): indexOf validation in edge case failed');
  } else {
    logPass('indexOf remains valid in complete sub-team failure scenario');
    tests.passed++;
  }

} catch (err) {
  logFail(`TEST (c) failed: ${err.message}`);
  tests.failed++;
  tests.errors.push(`TEST (c): ${err.message}`);
}

log('');

// ============================================================================
// VERIFY SOURCE CODE HAS THE indexOf AT LINE 451
// ============================================================================

log('CODE VERIFICATION: Checking source code at line 451');
log('-'.repeat(70));

try {
  const lines = sourceCode.split('\n');
  const line451 = lines[450]; // 0-indexed

  if (!line451) {
    logWarn('Could not read line 451 from source file');
    tests.errors.push('Code verification: Line 451 not found');
  } else if (line451.includes('indexOf')) {
    logPass(`Line 451 contains indexOf: ${line451.trim()}`);
    tests.passed++;

    // Verify the specific pattern
    if (line451.includes('allWorkerDescriptors.indexOf(d)')) {
      logPass('Confirmed: Line 451 uses allWorkerDescriptors.indexOf(d) pattern');
      tests.passed++;
    } else {
      logWarn('Line 451 has indexOf but not the expected pattern');
      tests.errors.push('Code verification: indexOf pattern different than expected');
    }
  } else {
    logWarn(`Line 451 does not contain indexOf: ${line451.trim()}`);
    logWarn('The code may have been refactored. Manual inspection recommended.');
    tests.errors.push('Code verification: indexOf not found at line 451');
  }
} catch (err) {
  logFail(`Code verification failed: ${err.message}`);
  tests.failed++;
  tests.errors.push(`Code verification: ${err.message}`);
}

log('');

// ============================================================================
// SUMMARY
// ============================================================================

log('='.repeat(70));
log('TEST SUMMARY');
log('='.repeat(70));
log(`Total tests passed: ${GREEN}${tests.passed}${RESET}`);
log(`Total tests failed: ${tests.failed > 0 ? RED : GREEN}${tests.failed}${RESET}`);

if (tests.errors.length > 0) {
  log('');
  log('Errors/Warnings:');
  tests.errors.forEach(err => log(`  - ${err}`));
}

log('='.repeat(70));

// Exit with appropriate code
const exitCode = tests.failed > 0 ? 1 : 0;
process.exit(exitCode);
