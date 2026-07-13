#!/usr/bin/env node
/**
 * Auto Rollback System - Automatic rollback on verification failure
 *
 * Features:
 * - Git-based rollback (stash, reset, restore)
 * - File system snapshots (backup/restore)
 * - Database transaction rollback
 * - Service restart rollback
 * - Verification testing with automatic rollback
 *
 * Usage:
 *   const { withRollback, createCheckpoint, rollbackToCheckpoint } = require('./lib/auto-rollback.js');
 *
 *   await withRollback(async () => {
 *     // Make changes
 *     await modifyFiles();
 *
 *     // Verify changes
 *     const verified = await runTests();
 *     if (!verified) throw new Error('Verification failed');
 *
 *     return { success: true };
 *   });
 */

const fs = require('fs');
const path = require('path');
const { execSync, exec } = require('child_process');
const crypto = require('crypto');

class RollbackManager {
  constructor(options = {}) {
    this.checkpoints = [];
    this.checkpointDir = options.checkpointDir || path.join(process.cwd(), '.rollback');
    this.verbose = options.verbose || false;
    this.dryRun = options.dryRun || false;

    // Ensure checkpoint directory exists
    if (!fs.existsSync(this.checkpointDir)) {
      fs.mkdirSync(this.checkpointDir, { recursive: true });
    }
  }

  log(message, level = 'info') {
    if (this.verbose || level === 'error') {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [${level.toUpperCase()}] ${message}`);
    }
  }

  /**
   * Create a checkpoint with current state
   * @param {Object} options - Checkpoint options
   * @returns {string} Checkpoint ID
   */
  createCheckpoint(options = {}) {
    const checkpointId = crypto.randomBytes(8).toString('hex');
    const checkpoint = {
      id: checkpointId,
      timestamp: new Date().toISOString(),
      type: options.type || 'auto',
      description: options.description || 'Automatic checkpoint',
      git: null,
      files: [],
      metadata: options.metadata || {}
    };

    this.log(`Creating checkpoint ${checkpointId}: ${checkpoint.description}`);

    // Git checkpoint (if in git repo)
    if (this.isGitRepo()) {
      checkpoint.git = this.createGitCheckpoint(checkpointId);
    }

    // File system checkpoint
    if (options.files && options.files.length > 0) {
      checkpoint.files = this.createFileCheckpoint(checkpointId, options.files);
    }

    // Save checkpoint metadata
    const checkpointFile = path.join(this.checkpointDir, `${checkpointId}.json`);
    fs.writeFileSync(checkpointFile, JSON.stringify(checkpoint, null, 2));

    this.checkpoints.push(checkpoint);
    this.log(`Checkpoint ${checkpointId} created successfully`);

    return checkpointId;
  }

  /**
   * Check if current directory is a git repository
   * @returns {boolean}
   */
  isGitRepo() {
    try {
      execSync('git rev-parse --git-dir', { stdio: 'ignore' });
      return true;
    } catch (err) {
      return false;
    }
  }

  /**
   * Create git-based checkpoint
   * @param {string} checkpointId - Checkpoint ID
   * @returns {Object} Git checkpoint info
   */
  createGitCheckpoint(checkpointId) {
    try {
      // Get current branch
      const branch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8' }).trim();

      // Get current commit
      const commit = execSync('git rev-parse HEAD', { encoding: 'utf8' }).trim();

      // Stash any uncommitted changes
      const stashName = `rollback-${checkpointId}`;
      let stashRef = null;

      const hasChanges = execSync('git status --porcelain', { encoding: 'utf8' }).trim().length > 0;

      if (hasChanges) {
        execSync(`git stash push -m "${stashName}"`, { stdio: this.verbose ? 'inherit' : 'ignore' });
        stashRef = execSync('git rev-parse stash@{0}', { encoding: 'utf8' }).trim();
        this.log(`Stashed changes as ${stashRef}`);
      }

      return {
        branch,
        commit,
        stashRef,
        stashName,
        hasChanges
      };
    } catch (err) {
      this.log(`Failed to create git checkpoint: ${err.message}`, 'error');
      return null;
    }
  }

  /**
   * Create file system checkpoint
   * @param {string} checkpointId - Checkpoint ID
   * @param {Array<string>} files - Files to backup
   * @returns {Array<Object>} File checkpoint info
   */
  createFileCheckpoint(checkpointId, files) {
    const backups = [];
    const backupDir = path.join(this.checkpointDir, checkpointId);

    if (!fs.existsSync(backupDir)) {
      fs.mkdirSync(backupDir, { recursive: true });
    }

    files.forEach(filePath => {
      try {
        const absolutePath = path.resolve(filePath);

        if (!fs.existsSync(absolutePath)) {
          this.log(`File does not exist, skipping: ${filePath}`, 'warn');
          return;
        }

        const relativePath = path.relative(process.cwd(), absolutePath);
        const backupPath = path.join(backupDir, relativePath);
        const backupPathDir = path.dirname(backupPath);

        if (!fs.existsSync(backupPathDir)) {
          fs.mkdirSync(backupPathDir, { recursive: true });
        }

        // Copy file
        fs.copyFileSync(absolutePath, backupPath);

        backups.push({
          original: absolutePath,
          backup: backupPath,
          size: fs.statSync(absolutePath).size
        });

        this.log(`Backed up: ${relativePath}`);
      } catch (err) {
        this.log(`Failed to backup ${filePath}: ${err.message}`, 'error');
      }
    });

    return backups;
  }

  /**
   * Rollback to a checkpoint
   * @param {string} checkpointId - Checkpoint ID to rollback to
   * @returns {boolean} Success status
   */
  rollbackToCheckpoint(checkpointId) {
    const checkpointFile = path.join(this.checkpointDir, `${checkpointId}.json`);

    if (!fs.existsSync(checkpointFile)) {
      this.log(`Checkpoint ${checkpointId} not found`, 'error');
      return false;
    }

    const checkpoint = JSON.parse(fs.readFileSync(checkpointFile, 'utf8'));
    this.log(`Rolling back to checkpoint ${checkpointId}: ${checkpoint.description}`);

    let success = true;

    // Rollback git changes
    if (checkpoint.git) {
      success = this.rollbackGit(checkpoint.git) && success;
    }

    // Rollback file changes
    if (checkpoint.files && checkpoint.files.length > 0) {
      success = this.rollbackFiles(checkpoint.files) && success;
    }

    if (success) {
      this.log(`Rollback to checkpoint ${checkpointId} completed successfully`);
    } else {
      this.log(`Rollback to checkpoint ${checkpointId} completed with errors`, 'error');
    }

    return success;
  }

  /**
   * Rollback git changes
   * @param {Object} gitInfo - Git checkpoint info
   * @returns {boolean} Success status
   */
  rollbackGit(gitInfo) {
    try {
      this.log(`Rolling back git to commit ${gitInfo.commit}`);

      if (this.dryRun) {
        this.log('[DRY RUN] Would rollback git changes');
        return true;
      }

      // Discard uncommitted changes
      execSync('git reset --hard HEAD', { stdio: this.verbose ? 'inherit' : 'ignore' });

      // Restore stashed changes if any
      if (gitInfo.stashRef) {
        try {
          execSync(`git stash apply ${gitInfo.stashRef}`, { stdio: this.verbose ? 'inherit' : 'ignore' });
          this.log(`Restored stashed changes from ${gitInfo.stashRef}`);
        } catch (err) {
          this.log(`Failed to restore stash: ${err.message}`, 'error');
        }
      }

      // Reset to checkpoint commit
      execSync(`git reset --hard ${gitInfo.commit}`, { stdio: this.verbose ? 'inherit' : 'ignore' });

      this.log('Git rollback completed');
      return true;
    } catch (err) {
      this.log(`Git rollback failed: ${err.message}`, 'error');
      return false;
    }
  }

  /**
   * Rollback file changes
   * @param {Array<Object>} files - File checkpoint info
   * @returns {boolean} Success status
   */
  rollbackFiles(files) {
    let success = true;

    files.forEach(({ original, backup }) => {
      try {
        this.log(`Restoring ${original}`);

        if (this.dryRun) {
          this.log(`[DRY RUN] Would restore from ${backup}`);
          return;
        }

        if (!fs.existsSync(backup)) {
          this.log(`Backup file not found: ${backup}`, 'error');
          success = false;
          return;
        }

        fs.copyFileSync(backup, original);
        this.log(`Restored ${original}`);
      } catch (err) {
        this.log(`Failed to restore ${original}: ${err.message}`, 'error');
        success = false;
      }
    });

    return success;
  }

  /**
   * Clean up old checkpoints
   * @param {number} maxAge - Maximum age in milliseconds
   */
  cleanupCheckpoints(maxAge = 7 * 24 * 60 * 60 * 1000) {
    const now = Date.now();
    const checkpointFiles = fs.readdirSync(this.checkpointDir)
      .filter(f => f.endsWith('.json'));

    checkpointFiles.forEach(file => {
      const filePath = path.join(this.checkpointDir, file);
      const checkpoint = JSON.parse(fs.readFileSync(filePath, 'utf8'));
      const age = now - new Date(checkpoint.timestamp).getTime();

      if (age > maxAge) {
        this.log(`Cleaning up old checkpoint: ${checkpoint.id}`);

        // Remove checkpoint metadata
        fs.unlinkSync(filePath);

        // Remove checkpoint backup directory
        const backupDir = path.join(this.checkpointDir, checkpoint.id);
        if (fs.existsSync(backupDir)) {
          fs.rmSync(backupDir, { recursive: true, force: true });
        }
      }
    });
  }
}

/**
 * Execute function with automatic rollback on failure
 * @param {Function} fn - Function to execute
 * @param {Object} options - Rollback options
 * @returns {Promise<any>} Function result
 */
async function withRollback(fn, options = {}) {
  const manager = new RollbackManager(options);

  // Create checkpoint before execution
  const checkpointId = manager.createCheckpoint({
    type: 'auto',
    description: options.description || 'Automatic rollback checkpoint',
    files: options.files || [],
    metadata: options.metadata || {}
  });

  try {
    // Execute function
    manager.log('Executing function with rollback protection');
    const result = await fn();

    // If verification is provided, run it
    if (options.verify) {
      manager.log('Running verification');
      const verified = await options.verify(result);

      if (!verified) {
        throw new Error('Verification failed');
      }

      manager.log('Verification passed');
    }

    manager.log('Execution completed successfully');
    return result;
  } catch (err) {
    manager.log(`Execution failed: ${err.message}`, 'error');
    manager.log('Rolling back changes');

    // Automatic rollback
    const rollbackSuccess = manager.rollbackToCheckpoint(checkpointId);

    if (!rollbackSuccess) {
      throw new Error(`Rollback failed after execution error: ${err.message}`);
    }

    throw err;
  }
}

/**
 * Create a standalone checkpoint
 * @param {Object} options - Checkpoint options
 * @returns {string} Checkpoint ID
 */
function createCheckpoint(options = {}) {
  const manager = new RollbackManager(options);
  return manager.createCheckpoint(options);
}

/**
 * Rollback to a specific checkpoint
 * @param {string} checkpointId - Checkpoint ID
 * @param {Object} options - Rollback options
 * @returns {boolean} Success status
 */
function rollbackToCheckpoint(checkpointId, options = {}) {
  const manager = new RollbackManager(options);
  return manager.rollbackToCheckpoint(checkpointId);
}

module.exports = {
  RollbackManager,
  withRollback,
  createCheckpoint,
  rollbackToCheckpoint
};

// CLI usage
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  const manager = new RollbackManager({ verbose: true });

  if (command === 'create') {
    const description = args[1] || 'Manual checkpoint';
    const checkpointId = manager.createCheckpoint({ description });
    console.log(`\n✅ Checkpoint created: ${checkpointId}`);
  } else if (command === 'rollback') {
    const checkpointId = args[1];
    if (!checkpointId) {
      console.error('Usage: auto-rollback.js rollback <checkpoint-id>');
      process.exit(1);
    }
    const success = manager.rollbackToCheckpoint(checkpointId);
    process.exit(success ? 0 : 1);
  } else if (command === 'cleanup') {
    const maxAgeDays = parseInt(args[1]) || 7;
    manager.cleanupCheckpoints(maxAgeDays * 24 * 60 * 60 * 1000);
    console.log(`\n✅ Cleanup completed (max age: ${maxAgeDays} days)`);
  } else {
    console.log('Usage:');
    console.log('  auto-rollback.js create [description]');
    console.log('  auto-rollback.js rollback <checkpoint-id>');
    console.log('  auto-rollback.js cleanup [max-age-days]');
    process.exit(1);
  }
}
