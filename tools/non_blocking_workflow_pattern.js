#!/usr/bin/env node

/**
 * Non-Blocking Workflow Pattern Template
 *
 * PURPOSE: Prevent workflow failures from blocking operations
 * PROBLEM: Blocking waits cause 10.1% failure rate in orchestration
 * SOLUTION: Start task → return immediately → check status later
 *
 * ANTI-PATTERN (10.1% failure rate):
 *   execSync('long-running-command');
 *   while (!done) { sleep(10000); }
 *   return 'done';
 *
 * RECOMMENDED PATTERN:
 *   spawn('long-running-command', { detached, logged });
 *   return { status: 'started', log: '/path/to/log' };
 */

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { validateReadPath, validateWritePath } from '../shared/path-validator.js';

// ============================================================================
// PATTERN 1: Database Batch Operations (OrientDB, PostgreSQL, etc.)
// ============================================================================

/**
 * Example: Non-blocking OrientDB batch insert
 *
 * USE CASE: Inserting thousands of nodes/edges without blocking
 * FAILURE MODE: Blocking waits timeout or cause orchestrator hangs
 */
export function startOrientDBBatchInsert(batchFile, logDir = '/tmp') {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const logFile = path.join(logDir, `orientdb-batch-${timestamp}.log`);
  const statusFile = path.join(logDir, `orientdb-batch-${timestamp}.status`);

  // Validate paths before use
  const validBatchFile = validateReadPath(batchFile);
  const validLogFile = validateWritePath(logFile);
  const validStatusFile = validateWritePath(statusFile);

  // Write initial status
  fs.writeFileSync(validStatusFile, JSON.stringify({
    status: 'starting',
    started_at: new Date().toISOString(),
    log: validLogFile,
    batch_file: validBatchFile
  }));

  // Start detached process with logging
  const proc = spawn('orientdb-console', ['-f', validBatchFile], {
    detached: true,
    stdio: [
      'ignore',
      fs.openSync(validLogFile, 'w'),  // stdout → log file
      fs.openSync(validLogFile, 'a')   // stderr → log file (append)
    ]
  });

  // Track completion in background
  proc.on('exit', (code) => {
    fs.writeFileSync(validStatusFile, JSON.stringify({
      status: code === 0 ? 'completed' : 'failed',
      exit_code: code,
      completed_at: new Date().toISOString(),
      log: validLogFile
    }));
  });

  // Unref to allow parent process to exit
  proc.unref();

  // Return immediately with tracking info
  return {
    status: 'started',
    pid: proc.pid,
    log: logFile,
    status_file: statusFile,
    check_command: `tail -f ${logFile}`,
    check_status: `cat ${statusFile} | jq .`
  };
}

// ============================================================================
// PATTERN 2: File Processing Workflows
// ============================================================================

/**
 * Example: Non-blocking large file processing
 *
 * USE CASE: Processing large datasets, code analysis, vectorization
 * FAILURE MODE: Blocking on file I/O causes timeouts
 */
export function startFileProcessing(inputFile, processScript, outputFile) {
  const logFile = `${outputFile}.log`;
  const statusFile = `${outputFile}.status`;

  fs.writeFileSync(statusFile, JSON.stringify({
    status: 'processing',
    started_at: new Date().toISOString(),
    input: inputFile,
    output: outputFile
  }));

  const proc = spawn(processScript, [inputFile, outputFile], {
    detached: true,
    stdio: [
      'ignore',
      fs.openSync(logFile, 'w'),
      fs.openSync(logFile, 'a')
    ]
  });

  proc.on('exit', (code) => {
    fs.writeFileSync(statusFile, JSON.stringify({
      status: code === 0 ? 'completed' : 'failed',
      exit_code: code,
      completed_at: new Date().toISOString(),
      output_exists: fs.existsSync(outputFile),
      output_size: fs.existsSync(outputFile) ? fs.statSync(outputFile).size : 0
    }));
  });

  proc.unref();

  return {
    status: 'processing',
    pid: proc.pid,
    input: inputFile,
    output: outputFile,
    log: logFile,
    status_file: statusFile,
    check_progress: `wc -l ${outputFile}`,
    check_log: `tail -20 ${logFile}`
  };
}

// ============================================================================
// PATTERN 3: External API Calls (Web scraping, data fetch)
// ============================================================================

/**
 * Example: Non-blocking web data collection
 *
 * USE CASE: Fetching data from slow APIs, web scraping
 * FAILURE MODE: Network timeouts block entire workflow
 */
export function startWebDataFetch(urls, outputDir) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const logFile = path.join(outputDir, `fetch-${timestamp}.log`);
  const statusFile = path.join(outputDir, `fetch-${timestamp}.status`);
  const urlsFile = path.join(outputDir, `fetch-${timestamp}-urls.txt`);

  // Write URLs to temp file
  fs.writeFileSync(urlsFile, urls.join('\n'));

  fs.writeFileSync(statusFile, JSON.stringify({
    status: 'fetching',
    started_at: new Date().toISOString(),
    total_urls: urls.length,
    completed: 0
  }));

  // Example: Using wget or custom fetcher
  const proc = spawn('wget', [
    '-i', urlsFile,
    '-P', outputDir,
    '-o', logFile,
    '--progress=bar:force'
  ], {
    detached: true,
    stdio: 'ignore'
  });

  proc.on('exit', (code) => {
    const files = fs.readdirSync(outputDir).filter(f => !f.match(/\.(log|status|txt)$/));
    fs.writeFileSync(statusFile, JSON.stringify({
      status: code === 0 ? 'completed' : 'partial',
      exit_code: code,
      completed_at: new Date().toISOString(),
      files_fetched: files.length,
      total_urls: urls.length
    }));
  });

  proc.unref();

  return {
    status: 'fetching',
    pid: proc.pid,
    output_dir: outputDir,
    log: logFile,
    status_file: statusFile,
    check_progress: `ls -1 ${outputDir} | wc -l`,
    check_log: `tail -10 ${logFile}`
  };
}

// ============================================================================
// PATTERN 4: Model Training / Fine-Tuning
// ============================================================================

/**
 * Example: Non-blocking model fine-tuning
 *
 * USE CASE: CPU fine-tuning (hours-long operations)
 * FAILURE MODE: Blocking on training causes workflow timeout
 */
export function startModelFineTuning(modelName, datasetPath, outputDir) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const logFile = path.join(outputDir, `train-${modelName}-${timestamp}.log`);
  const statusFile = path.join(outputDir, `train-${modelName}-${timestamp}.status`);

  fs.writeFileSync(statusFile, JSON.stringify({
    status: 'training',
    started_at: new Date().toISOString(),
    model: modelName,
    dataset: datasetPath,
    estimated_duration_hours: 4
  }));

  const proc = spawn('python3', [
    path.join(process.env.HOME, 'fine-tuning/scripts/train_cpu.py'),
    '--model', modelName,
    '--dataset', datasetPath,
    '--output', outputDir
  ], {
    detached: true,
    stdio: [
      'ignore',
      fs.openSync(logFile, 'w'),
      fs.openSync(logFile, 'a')
    ]
  });

  proc.on('exit', (code) => {
    fs.writeFileSync(statusFile, JSON.stringify({
      status: code === 0 ? 'completed' : 'failed',
      exit_code: code,
      completed_at: new Date().toISOString(),
      checkpoint_exists: fs.existsSync(path.join(outputDir, 'checkpoint-final'))
    }));
  });

  proc.unref();

  return {
    status: 'training',
    pid: proc.pid,
    model: modelName,
    output_dir: outputDir,
    log: logFile,
    status_file: statusFile,
    check_progress: `grep -i "step\\|epoch\\|loss" ${logFile} | tail -5`,
    check_status: `cat ${statusFile} | jq .`
  };
}

// ============================================================================
// PATTERN 5: Status Checking Helper
// ============================================================================

/**
 * Check status of non-blocking operation
 *
 * USE CASE: Verify completion, get progress, check errors
 */
export function checkOperationStatus(statusFile) {
  if (!fs.existsSync(statusFile)) {
    return {
      status: 'unknown',
      error: 'Status file not found'
    };
  }

  try {
    const status = JSON.parse(fs.readFileSync(statusFile, 'utf8'));

    // Add runtime duration if still running
    if (status.status === 'processing' || status.status === 'training' || status.status === 'fetching') {
      const started = new Date(status.started_at);
      const now = new Date();
      status.runtime_seconds = Math.floor((now - started) / 1000);
      status.runtime_minutes = Math.floor(status.runtime_seconds / 60);
    }

    return status;
  } catch (err) {
    return {
      status: 'error',
      error: err.message
    };
  }
}

/**
 * Get recent log lines
 */
export function getRecentLogs(logFile, lines = 20) {
  if (!fs.existsSync(logFile)) {
    return { error: 'Log file not found' };
  }

  try {
    const content = fs.readFileSync(logFile, 'utf8');
    const allLines = content.split('\n');
    return {
      total_lines: allLines.length,
      recent_lines: allLines.slice(-lines).join('\n')
    };
  } catch (err) {
    return { error: err.message };
  }
}

// ============================================================================
// USAGE EXAMPLES
// ============================================================================

/**
 * Example 1: OrientDB batch insert workflow
 */
export async function exampleOrientDBWorkflow() {
  // Start batch insert (non-blocking)
  const task = startOrientDBBatchInsert('/tmp/batch-insert.osql', '/tmp/logs');

  console.log('Batch insert started:', task);
  console.log('Check progress:', task.check_command);

  // Return immediately - no blocking!
  return {
    message: 'Batch insert started in background',
    tracking: task
  };

  // User can check status later:
  // const status = checkOperationStatus(task.status_file);
  // const logs = getRecentLogs(task.log);
}

/**
 * Example 2: Multi-stage workflow with non-blocking steps
 */
export async function exampleMultiStageWorkflow() {
  const results = [];

  // Stage 1: Fetch data (non-blocking)
  const fetchTask = startWebDataFetch(
    ['https://example.com/data1', 'https://example.com/data2'],
    '/tmp/fetched-data'
  );
  results.push({ stage: 'fetch', task: fetchTask });

  // Stage 2: Process data (can start immediately, non-blocking)
  const processTask = startFileProcessing(
    '/tmp/input-data.json',
    '/usr/local/bin/process-data.sh',
    '/tmp/processed-data.json'
  );
  results.push({ stage: 'process', task: processTask });

  // Return immediately with all task info
  return {
    message: 'Multi-stage workflow started',
    stages: results,
    check_all: `for f in ${results.map(r => r.task.status_file).join(' ')}; do echo "=== $f ==="; cat $f | jq .; done`
  };
}

// ============================================================================
// ERROR HANDLING
// ============================================================================

/**
 * Verify task completion with error detection
 */
export function verifyTaskCompletion(statusFile, logFile) {
  const status = checkOperationStatus(statusFile);

  if (status.status === 'error' || status.status === 'unknown') {
    return { success: false, error: status.error };
  }

  if (status.status === 'failed') {
    const logs = getRecentLogs(logFile, 50);
    return {
      success: false,
      error: 'Task failed',
      exit_code: status.exit_code,
      recent_logs: logs.recent_lines
    };
  }

  if (status.status === 'completed') {
    return {
      success: true,
      completed_at: status.completed_at,
      runtime_minutes: status.runtime_minutes
    };
  }

  // Still running
  return {
    success: false,
    in_progress: true,
    status: status.status,
    runtime_minutes: status.runtime_minutes
  };
}

// ============================================================================
// EXPORT ALL PATTERNS
// ============================================================================

export default {
  // Start operations (non-blocking)
  startOrientDBBatchInsert,
  startFileProcessing,
  startWebDataFetch,
  startModelFineTuning,

  // Check status
  checkOperationStatus,
  getRecentLogs,
  verifyTaskCompletion,

  // Examples
  exampleOrientDBWorkflow,
  exampleMultiStageWorkflow
};
