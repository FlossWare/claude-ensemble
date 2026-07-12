# Auto Rollback System

**Automatic rollback on verification failure**

## Overview

The Auto Rollback system provides automatic restoration of previous state when verification fails. It supports:

- ✅ Git-based rollback (commits, stashes)
- ✅ File system snapshots (backup/restore)
- ✅ Transaction-like semantics (commit on success, rollback on failure)
- ✅ Multiple checkpoint management
- ✅ Verification function integration

## Quick Start

```javascript
const { withRollback } = require('./lib/auto-rollback.js');

// Execute with automatic rollback on failure
await withRollback(async () => {
  // Make changes
  fs.writeFileSync('config.json', newConfig);

  // Changes will be rolled back if this throws
  if (!isValid(newConfig)) {
    throw new Error('Invalid configuration');
  }

  return { success: true };
}, {
  files: ['config.json'],  // Files to protect
  verbose: true
});
```

## Features

### 1. Automatic Rollback on Error

Any exception thrown during execution triggers automatic rollback:

```javascript
try {
  await withRollback(async () => {
    modifyDatabase();
    updateFiles();

    // If this fails, everything rolls back
    throw new Error('Verification failed');
  }, {
    files: ['data.json', 'config.json']
  });
} catch (err) {
  // All changes have been rolled back
  console.log('Changes rolled back:', err.message);
}
```

### 2. Verification Function

Provide a verification function to automatically validate results:

```javascript
await withRollback(async () => {
  const result = await makeChanges();
  return result;
}, {
  files: ['output.json'],
  verify: async (result) => {
    // Return false to trigger rollback
    return result.status === 'success' && result.errors.length === 0;
  }
});
```

### 3. Git Integration

Automatically creates git checkpoints and can rollback git state:

```javascript
const { RollbackManager } = require('./lib/auto-rollback.js');

const manager = new RollbackManager({ verbose: true });

// Create git checkpoint
const checkpointId = manager.createCheckpoint({
  description: 'Before risky operation'
});

// ... make changes ...

// Rollback if needed
if (somethingWentWrong) {
  manager.rollbackToCheckpoint(checkpointId);
}
```

### 4. File System Snapshots

Create snapshots of specific files before modification:

```javascript
const { createCheckpoint, rollbackToCheckpoint } = require('./lib/auto-rollback.js');

// Create checkpoint
const checkpointId = createCheckpoint({
  files: [
    'database.json',
    'config.json',
    'state.json'
  ],
  description: 'Before migration'
});

// ... perform migration ...

// Rollback if migration failed
if (migrationFailed) {
  rollbackToCheckpoint(checkpointId);
}
```

### 5. Multiple Checkpoints

Create and manage multiple checkpoints:

```javascript
const manager = new RollbackManager();

// Checkpoint 1: Initial state
const checkpoint1 = manager.createCheckpoint({
  description: 'Initial state',
  files: ['data.json']
});

// Make changes
modifyData();

// Checkpoint 2: After first change
const checkpoint2 = manager.createCheckpoint({
  description: 'After first change',
  files: ['data.json']
});

// Make more changes
modifyDataAgain();

// Rollback to checkpoint 1 (skipping checkpoint 2)
manager.rollbackToCheckpoint(checkpoint1);
```

## API Reference

### `withRollback(fn, options)`

Execute function with automatic rollback protection.

**Parameters:**

- `fn` (Function): Async function to execute
- `options` (Object):
  - `files` (Array<string>): Files to backup before execution
  - `verify` (Function): Verification function (async)
  - `description` (string): Checkpoint description
  - `verbose` (boolean): Enable verbose logging
  - `dryRun` (boolean): Simulate without actual changes
  - `metadata` (Object): Custom metadata for checkpoint

**Returns:** Promise resolving to function result

**Example:**

```javascript
const result = await withRollback(async () => {
  await performRiskyOperation();
  return { success: true };
}, {
  files: ['critical.json'],
  verify: async (result) => result.success,
  verbose: true
});
```

### `createCheckpoint(options)`

Create a manual checkpoint.

**Parameters:**

- `options` (Object):
  - `files` (Array<string>): Files to backup
  - `description` (string): Checkpoint description
  - `type` (string): Checkpoint type ('manual' | 'auto')
  - `metadata` (Object): Custom metadata

**Returns:** String (checkpoint ID)

**Example:**

```javascript
const checkpointId = createCheckpoint({
  files: ['config.json', 'data.json'],
  description: 'Before configuration change',
  metadata: { user: 'admin', timestamp: Date.now() }
});
```

### `rollbackToCheckpoint(checkpointId, options)`

Rollback to a specific checkpoint.

**Parameters:**

- `checkpointId` (string): Checkpoint ID to rollback to
- `options` (Object):
  - `verbose` (boolean): Enable verbose logging
  - `dryRun` (boolean): Simulate rollback

**Returns:** Boolean (success status)

**Example:**

```javascript
const success = rollbackToCheckpoint('a3f5d8e2b1c4', {
  verbose: true
});

if (!success) {
  console.error('Rollback failed');
}
```

### `RollbackManager`

Low-level rollback manager class.

**Methods:**

- `createCheckpoint(options)`: Create checkpoint
- `rollbackToCheckpoint(checkpointId)`: Rollback to checkpoint
- `cleanupCheckpoints(maxAge)`: Remove old checkpoints
- `isGitRepo()`: Check if in git repository

**Example:**

```javascript
const { RollbackManager } = require('./lib/auto-rollback.js');

const manager = new RollbackManager({
  verbose: true,
  checkpointDir: '/custom/checkpoint/dir'
});

const checkpoint = manager.createCheckpoint({
  description: 'Custom checkpoint',
  files: ['file1.txt', 'file2.txt']
});

// Later...
manager.rollbackToCheckpoint(checkpoint);

// Cleanup old checkpoints (older than 7 days)
manager.cleanupCheckpoints(7 * 24 * 60 * 60 * 1000);
```

## CLI Usage

The rollback system can be used from the command line:

```bash
# Create checkpoint
node lib/auto-rollback.js create "Before deployment"

# Rollback to checkpoint
node lib/auto-rollback.js rollback <checkpoint-id>

# Cleanup old checkpoints (default: 7 days)
node lib/auto-rollback.js cleanup 14
```

## Integration Examples

### Database Migration

```javascript
const { withRollback } = require('./lib/auto-rollback.js');
const db = require('./database.js');

async function migrateDatabase() {
  await withRollback(async () => {
    // Run migration
    await db.runMigration('2024-01-schema-update.sql');

    // Verify migration
    const tables = await db.query('SHOW TABLES');
    if (!tables.includes('new_table')) {
      throw new Error('Migration verification failed');
    }

    return { success: true };
  }, {
    description: 'Database migration v2024.01',
    verify: async () => {
      // Run integration tests
      return await db.runTests();
    }
  });
}
```

### Configuration Update

```javascript
const { withRollback } = require('./lib/auto-rollback.js');
const fs = require('fs');

async function updateConfig(newSettings) {
  await withRollback(async () => {
    const configPath = '/etc/app/config.json';
    const config = JSON.parse(fs.readFileSync(configPath));

    // Apply new settings
    Object.assign(config, newSettings);

    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

    return config;
  }, {
    files: ['/etc/app/config.json'],
    verify: async (config) => {
      // Validate configuration
      return validateConfig(config);
    }
  });
}
```

### Deployment Pipeline

```javascript
const { RollbackManager } = require('./lib/auto-rollback.js');

async function deploy() {
  const manager = new RollbackManager({ verbose: true });

  // Create pre-deployment checkpoint
  const checkpoint = manager.createCheckpoint({
    description: 'Pre-deployment state'
  });

  try {
    // Deploy
    await buildApplication();
    await runTests();
    await deployToProduction();

    console.log('Deployment successful');
  } catch (err) {
    console.error('Deployment failed:', err.message);

    // Automatic rollback
    manager.rollbackToCheckpoint(checkpoint);

    throw err;
  }
}
```

## Best Practices

### 1. Always Specify Files to Protect

```javascript
// ❌ Bad: No file protection
await withRollback(async () => {
  fs.writeFileSync('important.json', data);
});

// ✅ Good: Explicit file protection
await withRollback(async () => {
  fs.writeFileSync('important.json', data);
}, {
  files: ['important.json']
});
```

### 2. Use Verification Functions

```javascript
// ❌ Bad: No verification
await withRollback(async () => {
  await deployApplication();
});

// ✅ Good: Verify deployment
await withRollback(async () => {
  await deployApplication();
}, {
  verify: async () => {
    return await healthCheck();
  }
});
```

### 3. Provide Descriptive Checkpoint Names

```javascript
// ❌ Bad: Generic description
createCheckpoint({ description: 'Checkpoint 1' });

// ✅ Good: Descriptive name
createCheckpoint({
  description: 'Before database schema migration v2.3.0'
});
```

### 4. Clean Up Old Checkpoints

```javascript
// Run cleanup regularly (e.g., daily cron job)
const manager = new RollbackManager();
manager.cleanupCheckpoints(7 * 24 * 60 * 60 * 1000); // 7 days
```

### 5. Use Dry Run for Testing

```javascript
// Test rollback without actual changes
await withRollback(async () => {
  // ... operations ...
}, {
  dryRun: true,  // Simulates rollback
  verbose: true
});
```

## Limitations

1. **Git Rollback**: Only works in git repositories
2. **File Permissions**: Requires write access to checkpoint directory
3. **Disk Space**: Checkpoints consume disk space (cleanup regularly)
4. **Atomic Operations**: File operations are not truly atomic
5. **External State**: Cannot rollback external API calls, database changes on remote servers, etc.

## Troubleshooting

### Checkpoint Directory Not Found

**Problem:** `ENOENT: no such file or directory`

**Solution:** Ensure checkpoint directory exists or specify custom directory:

```javascript
const manager = new RollbackManager({
  checkpointDir: '/path/to/existing/dir'
});
```

### Git Rollback Fails

**Problem:** `git reset --hard` fails

**Solution:** Check git status and ensure working tree is clean:

```bash
git status
git stash  # If needed
```

### File Restore Fails

**Problem:** `EACCES: permission denied`

**Solution:** Ensure write permissions to files:

```bash
chmod u+w file.txt
```

### Checkpoint Not Found

**Problem:** `Checkpoint <id> not found`

**Solution:** List available checkpoints:

```bash
ls .rollback/*.json
```

## Future Enhancements

- [ ] PostgreSQL transaction integration
- [ ] Redis state snapshots
- [ ] Remote checkpoint storage (S3, NFS)
- [ ] Checkpoint compression
- [ ] Incremental backups
- [ ] Multi-server coordination
- [ ] Webhook notifications
- [ ] Web UI for checkpoint management

## Related

- [Auto Memory Saver](../lib/auto-memory-saver.js) - Automatic memory persistence
- [Workflow Storage](../shared/workflow-storage-adapter.js) - Workflow tracking
- [Feedback Loop Optimizer](./FEEDBACK_LOOP_OPTIMIZER.md) - Feedback loop monitoring

## License

MIT
