#!/usr/bin/env node
/**
 * Initialize Transfer Learning Database
 *
 * Creates tables and indexes for transfer learning system.
 * Safe to run multiple times (uses IF NOT EXISTS).
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const os = require('os');
const fs = require('fs');

const DB_PATH = path.join(os.homedir(), '.claude', 'learning', 'db', 'learning.db');
const SCHEMA_PATH = path.join(__dirname, 'schema', 'transfer-learning-schema.sql');

function openDb() {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) return reject(err);
      db.run('PRAGMA journal_mode = WAL', () => {
        db.run('PRAGMA synchronous = NORMAL', () => {
          db.run('PRAGMA busy_timeout = 5000', () => {
            resolve(db);
          });
        });
      });
    });
  });
}

function dbExec(db, sql) {
  return new Promise((resolve, reject) => {
    db.exec(sql, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

async function initializeDatabase() {
  console.log('Transfer Learning Database Initialization');
  console.log('=========================================\n');

  console.log(`Database: ${DB_PATH}`);
  console.log(`Schema: ${SCHEMA_PATH}\n`);

  // Check if database exists
  const dbExists = fs.existsSync(DB_PATH);
  if (dbExists) {
    console.log('✓ Database file exists');
  } else {
    console.log('✓ Creating new database file');
  }

  // Read schema
  if (!fs.existsSync(SCHEMA_PATH)) {
    throw new Error(`Schema file not found: ${SCHEMA_PATH}`);
  }

  const schema = fs.readFileSync(SCHEMA_PATH, 'utf8');
  console.log('✓ Schema file loaded\n');

  // Open database and execute schema
  const db = await openDb();
  console.log('✓ Database connection opened\n');

  try {
    console.log('Executing schema...');
    await dbExec(db, schema);
    console.log('✓ Schema executed successfully\n');

    // Verify tables were created
    const tables = await new Promise((resolve, reject) => {
      db.all(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        }
      );
    });

    console.log('Tables created:');
    const transferTables = tables.filter(t =>
      t.name.includes('transfer') ||
      t.name.includes('calibration') ||
      t.name.includes('similarity') ||
      t.name.includes('taxonomy') ||
      t.name.includes('decay') ||
      t.name.includes('validation')
    );

    for (const table of transferTables) {
      console.log(`  - ${table.name}`);
    }

    console.log(`\n✓ Total transfer learning tables: ${transferTables.length}`);

    // Verify indexes
    const indexes = await new Promise((resolve, reject) => {
      db.all(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name",
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        }
      );
    });

    const transferIndexes = indexes.filter(i =>
      i.name.includes('transfer') ||
      i.name.includes('calibration') ||
      i.name.includes('similarity') ||
      i.name.includes('taxonomy') ||
      i.name.includes('decay') ||
      i.name.includes('validation')
    );

    console.log(`✓ Total transfer learning indexes: ${transferIndexes.length}\n`);

    console.log('=========================================');
    console.log('✓ Database initialization complete!');
    console.log('=========================================\n');

    console.log('Next steps:');
    console.log('  1. Run tests: node test-transfer-learning.js');
    console.log('  2. Bootstrap a model: node transfer-learning.js bootstrap <model>');
    console.log('  3. Get calibration: node transfer-learning.js calibration <model> <task-type>');

  } finally {
    await new Promise((resolve) => db.close(resolve));
  }
}

// Run if called directly
if (require.main === module) {
  initializeDatabase().catch(error => {
    console.error('\n✗ Initialization failed:');
    console.error(error);
    process.exit(1);
  });
}

module.exports = { initializeDatabase };
