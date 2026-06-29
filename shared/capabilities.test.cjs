/**
 * Tests for Capability Interfaces
 */

const {
  CAPABILITIES,
  getCapability,
  getAllCapabilities,
  hasCapability,
  meetsCapabilityRequirements
} = require('./capabilities.cjs');

console.log('Testing Capability Interfaces...\n');

// Test 1: Get all capabilities
console.log('Test 1: Get all capabilities');
const allCaps = getAllCapabilities();
console.log(`  Found ${allCaps.length} capabilities:`, allCaps);
console.assert(allCaps.length === 6, 'Should have 6 capabilities');
console.log('  ✓ PASSED\n');

// Test 2: Get specific capability
console.log('Test 2: Get specific capability');
const reasoner = getCapability('reasoner');
console.log('  Reasoner:', reasoner);
console.assert(reasoner !== null, 'Should find reasoner');
console.assert(reasoner.minQualityScore === 0.80, 'Reasoner should have 0.80 min quality');
console.log('  ✓ PASSED\n');

// Test 3: Check capability exists
console.log('Test 3: Check capability exists');
console.assert(hasCapability('code_reviewer'), 'Should have code_reviewer');
console.assert(!hasCapability('nonexistent'), 'Should not have nonexistent');
console.log('  ✓ PASSED\n');

// Test 4: Meets requirements - passing case
console.log('Test 4: Meets requirements - passing case');
const goodPerf = {
  qualityScore: 0.85,
  avgCostUsd: 0.02,
  avgLatencyMs: 5000
};
const passResult = meetsCapabilityRequirements('reasoner', goodPerf);
console.log('  Result:', passResult);
console.assert(passResult.meets === true, 'Should meet requirements');
console.assert(passResult.reasons.length === 0, 'Should have no failure reasons');
console.log('  ✓ PASSED\n');

// Test 5: Meets requirements - failing case
console.log('Test 5: Meets requirements - failing case');
const badPerf = {
  qualityScore: 0.50,
  avgCostUsd: 0.20,
  avgLatencyMs: 50000
};
const failResult = meetsCapabilityRequirements('reasoner', badPerf);
console.log('  Result:', failResult);
console.assert(failResult.meets === false, 'Should not meet requirements');
console.assert(failResult.reasons.length === 3, 'Should have 3 failure reasons');
console.log('  ✓ PASSED\n');

// Test 6: All capability definitions have required fields
console.log('Test 6: All capability definitions have required fields');
for (const capName of allCaps) {
  const cap = CAPABILITIES[capName];
  console.assert(typeof cap.name === 'string', `${capName} should have name`);
  console.assert(typeof cap.description === 'string', `${capName} should have description`);
  console.assert(typeof cap.minQualityScore === 'number', `${capName} should have minQualityScore`);
  console.assert(typeof cap.maxCostUsd === 'number', `${capName} should have maxCostUsd`);
  console.assert(typeof cap.maxLatencyMs === 'number', `${capName} should have maxLatencyMs`);
  console.assert(Array.isArray(cap.requiredSkills), `${capName} should have requiredSkills array`);
}
console.log('  ✓ PASSED\n');

console.log('All tests PASSED');
process.exit(0);
