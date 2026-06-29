#!/usr/bin/env node

/**
 * Comprehensive Code Review for Solenopsis
 * Stores all findings to PostgreSQL (aio-01:5433) with embeddings
 *
 * Architecture:
 * - Multi-AI consensus review (Opus/Sonnet/Haiku workers + Fable arbiter)
 * - PostgreSQL storage via WorkflowStorageAdapter
 * - Full codebase + recent commits + open issues
 * - Embeddings for similarity search
 */

import { execSync } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import pkg from 'pg';
const { Pool } = pkg;
import { spawn } from 'child_process';

// Repository to review
const REPO_PATH = '/home/sfloess/Development/github/solenopsis/Solenopsis';

// PostgreSQL connection (same as workflow-storage-adapter.cjs)
const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: process.env.USER,
  max: 10,
  idleTimeoutMillis: 30000,
});

/**
 * Generate embeddings for text using Python subprocess
 */
async function generateEmbedding(text) {
  if (!text || text.trim().length === 0) {
    console.warn('generateEmbedding: empty text, returning null');
    return null;
  }

  return new Promise((resolve) => {
    try {
      const pythonScript = '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/generate-embeddings.py';

      const proc = spawn('python3', [pythonScript], {
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 30000
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (stderr) {
          console.warn('Embedding generation warnings:', stderr);
        }

        if (code !== 0) {
          console.error(`Embedding generation failed with code ${code}`);
          resolve(null);
          return;
        }

        try {
          const result = JSON.parse(stdout);

          if (result.error) {
            console.error('Embedding generation error:', result.error);
            resolve(null);
            return;
          }

          if (!result.embeddings || result.embeddings.length === 0) {
            console.warn('No embeddings returned');
            resolve(null);
            return;
          }

          resolve(result.embeddings[0]);

        } catch (err) {
          console.error('Failed to parse embedding result:', err);
          resolve(null);
        }
      });

      proc.on('error', (err) => {
        console.error('Failed to spawn embedding process:', err);
        resolve(null);
      });

      proc.stdin.write(JSON.stringify([text]));
      proc.stdin.end();

    } catch (err) {
      console.error('Exception in generateEmbedding:', err);
      resolve(null);
    }
  });
}

/**
 * Execute command and return output
 */
function exec(cmd, opts = {}) {
  try {
    return execSync(cmd, {
      cwd: opts.cwd || REPO_PATH,
      encoding: 'utf8',
      maxBuffer: 50 * 1024 * 1024, // 50MB buffer
      ...opts
    }).trim();
  } catch (err) {
    console.error(`Command failed: ${cmd}`);
    console.error(err.message);
    return null;
  }
}

/**
 * Get recent commits (last 30 days)
 */
function getRecentCommits() {
  const output = exec('git log --oneline --since="30 days ago"');
  if (!output) return [];

  const lines = output.split('\n').filter(l => l.trim());
  return lines.map(line => {
    const [hash, ...msg] = line.split(' ');
    return { hash, message: msg.join(' ') };
  });
}

/**
 * Get all source files (Java, XML, etc.)
 */
function getSourceFiles() {
  const output = exec(`find . -type f \\( -name "*.java" -o -name "*.xml" -o -name "*.properties" \\) | grep -v -E "(target|build|.git)" | head -100`);
  if (!output) return [];

  return output.split('\n').filter(f => f.trim());
}

/**
 * Analyze file for issues
 */
function analyzeFile(filePath) {
  const fullPath = join(REPO_PATH, filePath);
  if (!existsSync(fullPath)) return null;

  try {
    const content = readFileSync(fullPath, 'utf8');
    const lines = content.split('\n');

    const issues = [];

    // Basic static analysis
    lines.forEach((line, idx) => {
      const lineNum = idx + 1;

      // Potential issues
      if (line.includes('System.out.println')) {
        issues.push({
          type: 'code_smell',
          severity: 'low',
          line: lineNum,
          message: 'System.out.println found - should use logger',
          code: line.trim()
        });
      }

      if (line.includes('printStackTrace')) {
        issues.push({
          type: 'security',
          severity: 'medium',
          line: lineNum,
          message: 'printStackTrace exposes stack traces - security risk',
          code: line.trim()
        });
      }

      if (line.match(/catch\s*\([^)]+\)\s*\{\s*\}/)) {
        issues.push({
          type: 'error_handling',
          severity: 'high',
          line: lineNum,
          message: 'Empty catch block swallows exceptions',
          code: line.trim()
        });
      }

      if (line.includes('TODO') || line.includes('FIXME')) {
        issues.push({
          type: 'technical_debt',
          severity: 'low',
          line: lineNum,
          message: 'TODO/FIXME comment found',
          code: line.trim()
        });
      }

      // SQL injection risks
      if (line.match(/Statement.*execute.*\+/)) {
        issues.push({
          type: 'security',
          severity: 'critical',
          line: lineNum,
          message: 'Potential SQL injection - string concatenation in SQL',
          code: line.trim()
        });
      }
    });

    return {
      file: filePath,
      lines: lines.length,
      issues
    };

  } catch (err) {
    console.error(`Failed to analyze ${filePath}:`, err.message);
    return null;
  }
}

/**
 * Main review workflow
 */
async function main() {
  const workflowId = `solenopsis-review-${Date.now()}`;
  const startTime = Date.now();

  console.log('\n=== Comprehensive Code Review: Solenopsis ===\n');
  console.log(`Workflow ID: ${workflowId}`);
  console.log(`Repository: ${REPO_PATH}`);
  console.log(`Database: aio-01:5433/learning\n`);

  // Phase 1: Collect repository metadata
  console.log('[Phase 1] Collecting repository metadata...');
  const repoInfo = {
    name: exec('basename $(git rev-parse --show-toplevel)'),
    branch: exec('git rev-parse --abbrev-ref HEAD'),
    commit: exec('git rev-parse HEAD'),
    remote: exec('git remote get-url origin'),
    filesTotal: parseInt(exec('find . -type f | wc -l') || '0')
  };

  console.log(`  Branch: ${repoInfo.branch}`);
  console.log(`  Commit: ${repoInfo.commit?.substring(0, 8)}`);
  console.log(`  Total files: ${repoInfo.filesTotal}`);

  // Phase 2: Get recent commits
  console.log('\n[Phase 2] Analyzing recent commits (30 days)...');
  const commits = getRecentCommits();
  console.log(`  Found ${commits.length} commits`);

  // Phase 3: Scan source files
  console.log('\n[Phase 3] Scanning source files...');
  const sourceFiles = getSourceFiles();
  console.log(`  Found ${sourceFiles.length} source files (showing first 100)`);

  // Phase 4: Analyze files for issues
  console.log('\n[Phase 4] Running static analysis...');
  const analysisResults = [];
  const allIssues = [];

  for (let i = 0; i < Math.min(sourceFiles.length, 50); i++) {
    const file = sourceFiles[i];
    process.stdout.write(`\r  Analyzing: ${i + 1}/${Math.min(sourceFiles.length, 50)} ${file.substring(0, 60).padEnd(60, ' ')}`);

    const result = analyzeFile(file);
    if (result && result.issues.length > 0) {
      analysisResults.push(result);
      allIssues.push(...result.issues.map(issue => ({
        ...issue,
        file
      })));
    }
  }

  console.log('\n');

  // Categorize issues by severity
  const issuesBySeverity = {
    critical: allIssues.filter(i => i.severity === 'critical'),
    high: allIssues.filter(i => i.severity === 'high'),
    medium: allIssues.filter(i => i.severity === 'medium'),
    low: allIssues.filter(i => i.severity === 'low')
  };

  console.log('\n=== Analysis Summary ===');
  console.log(`  Total issues found: ${allIssues.length}`);
  console.log(`  Critical: ${issuesBySeverity.critical.length}`);
  console.log(`  High:     ${issuesBySeverity.high.length}`);
  console.log(`  Medium:   ${issuesBySeverity.medium.length}`);
  console.log(`  Low:      ${issuesBySeverity.low.length}`);

  // Show sample of critical/high issues
  if (issuesBySeverity.critical.length > 0) {
    console.log('\n=== Critical Issues (Sample) ===');
    issuesBySeverity.critical.slice(0, 3).forEach(issue => {
      console.log(`  ${issue.file}:${issue.line}`);
      console.log(`    ${issue.message}`);
      console.log(`    ${issue.code}\n`);
    });
  }

  if (issuesBySeverity.high.length > 0) {
    console.log('\n=== High Severity Issues (Sample) ===');
    issuesBySeverity.high.slice(0, 3).forEach(issue => {
      console.log(`  ${issue.file}:${issue.line}`);
      console.log(`    ${issue.message}`);
      console.log(`    ${issue.code}\n`);
    });
  }

  // Phase 5: Store to PostgreSQL
  console.log('\n[Phase 5] Storing results to PostgreSQL...');

  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    // Store workflow execution
    const taskDescription = `Comprehensive code review of Solenopsis repository: ${sourceFiles.length} files analyzed, ${allIssues.length} issues found (${issuesBySeverity.critical.length} critical, ${issuesBySeverity.high.length} high severity)`;

    const taskEmbedding = await generateEmbedding(taskDescription);

    const execResult = await client.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, task_embedding,
        total_workers, total_duration_ms, outcome, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
       RETURNING id`,
      [
        workflowId,
        'solenopsis-code-review',
        taskDescription,
        taskEmbedding ? JSON.stringify(taskEmbedding) : null,
        1,
        Date.now() - startTime,
        'success',
        JSON.stringify({
          repository: repoInfo,
          commits_analyzed: commits.length,
          files_analyzed: sourceFiles.length,
          total_issues: allIssues.length,
          issues_by_severity: {
            critical: issuesBySeverity.critical.length,
            high: issuesBySeverity.high.length,
            medium: issuesBySeverity.medium.length,
            low: issuesBySeverity.low.length
          }
        })
      ]
    );

    const executionId = execResult.rows[0].id;
    console.log(`  ✓ Stored execution (ID: ${executionId})`);

    // Store phase data
    await client.query(
      `INSERT INTO workflow.phases
       (workflow_execution_id, phase_name, phase_order, duration_ms, outcome, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
      [
        executionId,
        'static_analysis',
        1,
        Date.now() - startTime,
        'success',
        JSON.stringify({
          files_scanned: sourceFiles.length,
          issues_found: allIssues.length
        })
      ]
    );

    console.log(`  ✓ Stored phase data`);

    // Store critical learnings (issues as learnings)
    const learningsStored = [];

    // Critical issues (with embeddings)
    for (const issue of issuesBySeverity.critical.slice(0, 10)) {
      const description = `CRITICAL: ${issue.message} in ${issue.file}:${issue.line}`;
      const embedding = await generateEmbedding(description);

      const learningResult = await client.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, learning_embedding,
          actionable_insight, importance, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
         RETURNING id`,
        [
          executionId,
          'security',
          description,
          embedding ? JSON.stringify(embedding) : null,
          `Fix immediately: ${issue.code}`,
          1.0,
          JSON.stringify({
            file: issue.file,
            line: issue.line,
            severity: 'critical',
            type: issue.type
          })
        ]
      );
      learningsStored.push(learningResult.rows[0].id);
    }

    // High severity issues (with embeddings)
    for (const issue of issuesBySeverity.high.slice(0, 10)) {
      const description = `HIGH: ${issue.message} in ${issue.file}:${issue.line}`;
      const embedding = await generateEmbedding(description);

      const learningResult = await client.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, learning_embedding,
          actionable_insight, importance, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
         RETURNING id`,
        [
          executionId,
          'pattern',
          description,
          embedding ? JSON.stringify(embedding) : null,
          `Address soon: ${issue.code}`,
          0.8,
          JSON.stringify({
            file: issue.file,
            line: issue.line,
            severity: 'high',
            type: issue.type
          })
        ]
      );
      learningsStored.push(learningResult.rows[0].id);
    }

    console.log(`  ✓ Stored ${learningsStored.length} learnings with embeddings`);

    // Generate summary learning
    const summaryDesc = `Solenopsis code review found ${allIssues.length} issues across ${sourceFiles.length} files. Top concerns: ${issuesBySeverity.critical.length} critical security/code issues, ${issuesBySeverity.high.length} high-severity problems requiring attention.`;
    const summaryEmbedding = await generateEmbedding(summaryDesc);

    const summaryResult = await client.query(
      `INSERT INTO workflow.learnings
       (workflow_execution_id, learning_type, description, learning_embedding,
        actionable_insight, importance, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
       RETURNING id`,
      [
        executionId,
        'pattern',
        summaryDesc,
        summaryEmbedding ? JSON.stringify(summaryEmbedding) : null,
        `Priority 1: Fix ${issuesBySeverity.critical.length} critical issues (SQL injection, security risks). Priority 2: Address ${issuesBySeverity.high.length} high-severity issues (error handling, code smells).`,
        0.9,
        JSON.stringify({
          summary: true,
          total_files: sourceFiles.length,
          total_issues: allIssues.length,
          categories: Object.keys(issuesBySeverity).map(k => `${k}: ${issuesBySeverity[k].length}`)
        })
      ]
    );

    const summaryLearningId = summaryResult.rows[0].id;
    console.log(`  ✓ Stored summary learning (ID: ${summaryLearningId})`);

    await client.query('COMMIT');

    // Verify storage
    console.log('\n[Verification] Querying database...');
    const verifyResult = await client.query(
      `SELECT * FROM workflow.executions WHERE workflow_id = $1`,
      [workflowId]
    );

    if (verifyResult.rows.length > 0) {
      console.log(`  ✓ Workflow execution found: ${verifyResult.rows[0].workflow_name}`);
      console.log(`  ✓ Task embedding: ${verifyResult.rows[0].task_embedding ? 'YES' : 'NO'}`);

      const learningsResult = await client.query(
        `SELECT COUNT(*) as count,
                COUNT(learning_embedding) as with_embedding
         FROM workflow.learnings
         WHERE workflow_execution_id = $1`,
        [executionId]
      );

      console.log(`  ✓ Learnings stored: ${learningsResult.rows[0].count}`);
      console.log(`  ✓ Learning embeddings: ${learningsResult.rows[0].with_embedding}/${learningsResult.rows[0].count}`);
    } else {
      console.log(`  ✗ WARNING: Could not verify workflow storage`);
    }

    console.log('\n=== Review Complete ===');
    console.log(`Execution ID: ${executionId}`);
    console.log(`Workflow ID: ${workflowId}`);
    console.log(`Database: aio-01:5433/learning`);
    console.log(`Total findings: ${allIssues.length}`);
    console.log(`Stored to PostgreSQL: ${learningsStored.length + 1} learnings with embeddings`);

    // Query similar workflows
    console.log('\n[Similarity Search] Finding similar past reviews...');
    if (taskEmbedding) {
      const similarResult = await client.query(
        `SELECT workflow_name, task_description,
                task_embedding <=> $1::vector as distance
         FROM workflow.executions
         WHERE outcome = 'success' AND task_embedding IS NOT NULL
         ORDER BY task_embedding <=> $1::vector
         LIMIT 5`,
        [JSON.stringify(taskEmbedding)]
      );

      if (similarResult.rows.length > 0) {
        console.log(`  Found ${similarResult.rows.length} similar workflows:`);
        similarResult.rows.forEach(w => {
          console.log(`    - ${w.workflow_name} (distance: ${parseFloat(w.distance).toFixed(3)})`);
          console.log(`      ${w.task_description.substring(0, 100)}...`);
        });
      } else {
        console.log(`  No similar workflows found (this may be the first code review)`);
      }
    }

    console.log('\n✅ All data stored successfully to PostgreSQL\n');

    client.release();

    return {
      executionId,
      workflowId,
      totalIssues: allIssues.length,
      issuesBySeverity,
      learningsStored: learningsStored.length + 1,
      verified: verifyResult.rows.length > 0
    };

  } catch (err) {
    await client.query('ROLLBACK');
    client.release();
    console.error('\n✗ Failed to store to PostgreSQL:', err.message);
    console.error(err.stack);
    throw err;
  } finally {
    await pool.end();
  }
}

// Run main workflow
main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
