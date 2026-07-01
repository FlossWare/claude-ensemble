#!/usr/bin/env node

import { loadModelsFromDB, selectWorkerModels, selectArbiterModel } from './model-loader.js';

async function test() {
  console.log('=== Testing PostgreSQL Model Loader ===\n');

  // Load all models
  console.log('1. Loading all models from PostgreSQL...');
  const models = await loadModelsFromDB();
  console.log(`   High tier: ${models.high.length} models`);
  console.log(`   Medium tier: ${models.medium.length} models`);
  console.log(`   Fast tier: ${models.fast.length} models`);
  console.log(`   Total: ${models.all.length} models\n`);

  // Show sample models
  console.log('   Sample high tier:', models.high.slice(0, 3).map(m => m.name).join(', '));
  console.log('   Sample medium tier:', models.medium.slice(0, 3).map(m => m.name).join(', '));
  console.log('   Sample fast tier:', models.fast.slice(0, 3).map(m => m.name).join(', '));
  console.log('');

  // Select workers
  console.log('2. Selecting 5 diverse workers...');
  const workers = await selectWorkerModels(5, []);
  console.log(`   Workers: ${workers.join(', ')}\n`);

  // Select arbiter
  console.log('3. Selecting arbiter (highest tier)...');
  const arbiter = await selectArbiterModel(workers);
  console.log(`   Arbiter: ${arbiter}\n`);

  // Test with exclusions
  console.log('4. Selecting with exclusions...');
  const workers2 = await selectWorkerModels(3, ['opus', 'sonnet']);
  console.log(`   Workers (excluding opus, sonnet): ${workers2.join(', ')}\n`);

  const arbiter2 = await selectArbiterModel([...workers2, 'opus', 'sonnet']);
  console.log(`   Arbiter (excluding workers + opus/sonnet): ${arbiter2}\n`);

  console.log('✓ All tests passed!');
  process.exit(0);
}

test().catch(err => {
  console.error('✗ Test failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
