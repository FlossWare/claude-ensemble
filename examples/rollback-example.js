#!/usr/bin/env node
/**
 * Auto Rollback Example
 *
 * Demonstrates how to use automatic rollback on verification failure
 */

const { withRollback } = require('../lib/auto-rollback.js');
const fs = require('fs');
const path = require('path');

// Example 1: Simple rollback on error
async function example1() {
  console.log('=== Example 1: Basic Rollback ===\n');

  const testFile = path.join(__dirname, 'test-file.txt');

  // Create initial file
  fs.writeFileSync(testFile, 'Original content\n');

  try {
    await withRollback(async () => {
      console.log('Making changes...');
      fs.writeFileSync(testFile, 'Modified content\n');

      console.log('Simulating verification failure...');
      throw new Error('Verification failed');
    }, {
      files: [testFile],
      verbose: true
    });
  } catch (err) {
    console.log(`\nCaught error: ${err.message}`);
  }

  const content = fs.readFileSync(testFile, 'utf8');
  console.log(`\nFinal content: ${content}`);

  // Cleanup
  fs.unlinkSync(testFile);
}

// Example 2: Rollback with verification function
async function example2() {
  console.log('\n=== Example 2: Rollback with Verification ===\n');

  const testFile = path.join(__dirname, 'test-config.json');

  // Create initial config
  fs.writeFileSync(testFile, JSON.stringify({ version: 1, enabled: true }, null, 2));

  try {
    await withRollback(async () => {
      console.log('Updating configuration...');
      const config = JSON.parse(fs.readFileSync(testFile, 'utf8'));
      config.version = 2;
      config.newFeature = true;
      fs.writeFileSync(testFile, JSON.stringify(config, null, 2));

      return config;
    }, {
      files: [testFile],
      verify: async (result) => {
        console.log('Verifying configuration...');
        // Simulate verification (e.g., schema validation)
        return result.version >= 2 && result.newFeature === true;
      },
      verbose: true
    });

    console.log('Configuration updated successfully!');
  } catch (err) {
    console.log(`\nConfiguration update failed: ${err.message}`);
  }

  const finalConfig = JSON.parse(fs.readFileSync(testFile, 'utf8'));
  console.log(`\nFinal config: ${JSON.stringify(finalConfig, null, 2)}`);

  // Cleanup
  fs.unlinkSync(testFile);
}

// Example 3: Database-like transaction rollback
async function example3() {
  console.log('\n=== Example 3: Transaction-like Rollback ===\n');

  const dataFile = path.join(__dirname, 'data.json');
  const initialData = { users: [], count: 0 };

  fs.writeFileSync(dataFile, JSON.stringify(initialData, null, 2));

  try {
    await withRollback(async () => {
      console.log('Starting transaction...');
      const data = JSON.parse(fs.readFileSync(dataFile, 'utf8'));

      // Add users
      data.users.push({ id: 1, name: 'Alice' });
      data.users.push({ id: 2, name: 'Bob' });
      data.count = data.users.length;

      fs.writeFileSync(dataFile, JSON.stringify(data, null, 2));
      console.log('Added 2 users');

      return data;
    }, {
      files: [dataFile],
      verify: async (result) => {
        console.log('Verifying transaction...');
        // Simulate business logic validation
        const valid = result.count === result.users.length && result.count > 0;
        console.log(`Validation result: ${valid ? 'PASS' : 'FAIL'}`);
        return valid;
      },
      verbose: true
    });

    console.log('Transaction committed!');
  } catch (err) {
    console.log(`\nTransaction rolled back: ${err.message}`);
  }

  const finalData = JSON.parse(fs.readFileSync(dataFile, 'utf8'));
  console.log(`\nFinal data: ${JSON.stringify(finalData, null, 2)}`);

  // Cleanup
  fs.unlinkSync(dataFile);
}

// Run examples
async function main() {
  try {
    await example1();
    await example2();
    await example3();
    console.log('\n✅ All examples completed');
  } catch (err) {
    console.error(`\n❌ Example failed: ${err.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
