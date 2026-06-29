#!/usr/bin/env node
/**
 * Direct Code Review of solenopsis/soap with PostgreSQL Storage
 */

const { execSync } = require('child_process');
const { readFileSync } = require('fs');
const { Pool } = require('pg');

const REPO_PATH = '/home/sfloess/Development/github/solenopsis/soap';
const WORKFLOW_ID = `soap-direct-review-${Date.now()}`;

const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: process.env.USER,
  max: 10
});

async function main() {
  console.log('='.repeat(80));
  console.log('COMPREHENSIVE CODE REVIEW: solenopsis/soap');
  console.log('='.repeat(80));
  console.log(`Repository: ${REPO_PATH}`);
  console.log(`Workflow ID: ${WORKFLOW_ID}`);
  console.log('='.repeat(80));
  console.log();

  const startTime = Date.now();
  const findings = [];

  process.chdir(REPO_PATH);

  // Phase 1: Recent Commits
  console.log('Phase 1: Recent Commits (last 30 days)');
  console.log('-'.repeat(80));

  const commits = execSync('git log --since="30 days ago" --pretty=format:"%H|%s|%an" | head -20', { encoding: 'utf8' })
    .split('\n')
    .filter(Boolean)
    .map(line => {
      const [hash, message, author] = line.split('|');
      return { hash, message, author };
    });

  console.log(`Found ${commits.length} commits`);

  commits.forEach(commit => {
    if (commit.message.toLowerCase().includes('fix')) {
      findings.push({
        category: 'commit_pattern',
        severity: 'low',
        description: `Fix commit: ${commit.message}`,
        source: 'commit_analysis',
        evidence: `Commit ${commit.hash.substring(0, 8)} by ${commit.author}`
      });
    }
  });

  console.log(`Commit analysis: ${findings.length} findings`);
  console.log();

  // Phase 2: Java File Analysis
  console.log('Phase 2: Java File Analysis');
  console.log('-'.repeat(80));

  const javaFiles = execSync('find . -name "*.java" -type f ! -path "*/target/*"', { encoding: 'utf8' })
    .split('\n')
    .filter(Boolean);

  console.log(`Analyzing ${javaFiles.length} Java files...`);

  for (const file of javaFiles) {
    try {
      const content = readFileSync(file, 'utf8');
      const lines = content.split('\n');

      const issues = [];

      // Check for TODO/FIXME
      lines.forEach((line, idx) => {
        if (line.includes('TODO') || line.includes('FIXME')) {
          issues.push({
            line: idx + 1,
            type: 'todo',
            content: line.trim()
          });
        }
      });

      // Check for empty catch blocks
      if (content.includes('catch') && content.match(/catch\s*\([^)]+\)\s*\{\s*\}/)) {
        issues.push({ type: 'empty_catch', severity: 'medium' });
      }

      // Check for System.out/err
      if (content.includes('System.out') || content.includes('System.err')) {
        issues.push({ type: 'console_output', severity: 'low' });
      }

      if (issues.length > 0) {
        issues.forEach(issue => {
          findings.push({
            category: 'static_analysis',
            severity: issue.severity || 'low',
            description: `${issue.type} in ${file}${issue.line ? ` at line ${issue.line}` : ''}`,
            source: 'file_scan',
            file: file,
            evidence: issue.content || `Found ${issue.type}`
          });
        });
      }

      process.stdout.write('.');
    } catch (e) {
      console.error(`Error reading ${file}:`, e.message);
    }
  }

  console.log();
  console.log(`File analysis: ${findings.length} total findings`);
  console.log();

  // Phase 3: Code Metrics
  console.log('Phase 3: Code Metrics');
  console.log('-'.repeat(80));

  const metrics = {
    total_files: javaFiles.length,
    source_files: javaFiles.filter(f => f.includes('/src/main/')).length,
    test_files: javaFiles.filter(f => f.includes('/src/test/')).length,
    total_commits: commits.length,
    fix_commits: commits.filter(c => c.message.toLowerCase().includes('fix')).length
  };

  console.log('Metrics:', JSON.stringify(metrics, null, 2));
  console.log();

  // Phase 4: Store to PostgreSQL
  console.log('Phase 4: Store to PostgreSQL');
  console.log('-'.repeat(80));

  const taskDescription = `Comprehensive code review of solenopsis/soap: ${metrics.total_files} Java files, ${metrics.total_commits} commits (30 days)`;

  const client = await pool.connect();
  let executionId;

  try {
    await client.query('BEGIN');

    // Store execution
    const execResult = await client.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, task_embedding,
        total_workers, total_duration_ms, outcome, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
       RETURNING id`,
      [
        WORKFLOW_ID,
        'soap-direct-review',
        taskDescription,
        null, // Skip embeddings for speed
        1,
        Date.now() - startTime,
        'success',
        JSON.stringify(metrics)
      ]
    );

    executionId = execResult.rows[0].id;
    console.log(`✓ Execution stored: ID ${executionId}`);

    // Store findings as learnings
    for (const finding of findings.slice(0, 50)) {
      await client.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, actionable_insight,
          importance, learning_embedding, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())`,
        [
          executionId,
          'pattern',
          finding.description,
          `Review and address ${finding.category} issue`,
          finding.severity === 'high' ? 0.8 : finding.severity === 'medium' ? 0.6 : 0.4,
          null, // Skip embeddings for speed
          JSON.stringify({
            category: finding.category,
            severity: finding.severity,
            file: finding.file || 'unknown',
            source: finding.source,
            evidence: finding.evidence
          })
        ]
      );

      process.stdout.write('.');
    }

    console.log();
    console.log(`✓ Stored ${Math.min(findings.length, 50)} learnings`);

    await client.query('COMMIT');

  } catch (error) {
    await client.query('ROLLBACK');
    console.error('Storage error:', error.message);
    throw error;
  } finally {
    client.release();
  }

  // Phase 5: Verification
  console.log();
  console.log('Phase 5: Verification');
  console.log('-'.repeat(80));

  const verifyResult = await pool.query(
    'SELECT * FROM workflow.executions WHERE id = $1',
    [executionId]
  );

  if (verifyResult.rows.length > 0) {
    console.log('✓ Data confirmed in database');
  }

  const learningsCount = await pool.query(
    'SELECT COUNT(*) FROM workflow.learnings WHERE workflow_execution_id = $1',
    [executionId]
  );

  console.log(`✓ Learnings count: ${learningsCount.rows[0].count}`);

  // Summary
  console.log();
  console.log('='.repeat(80));
  console.log('SUMMARY');
  console.log('='.repeat(80));
  console.log(`Execution ID: ${executionId}`);
  console.log(`Total Findings: ${findings.length}`);
  console.log(`Stored Learnings: ${learningsCount.rows[0].count}`);
  console.log(`Duration: ${((Date.now() - startTime) / 1000).toFixed(1)}s`);
  console.log();
  console.log('By Severity:');
  const bySeverity = {
    high: findings.filter(f => f.severity === 'high').length,
    medium: findings.filter(f => f.severity === 'medium').length,
    low: findings.filter(f => f.severity === 'low').length
  };
  console.log(`  High: ${bySeverity.high}`);
  console.log(`  Medium: ${bySeverity.medium}`);
  console.log(`  Low: ${bySeverity.low}`);
  console.log();
  console.log('Database Queries:');
  console.log(`  SELECT * FROM workflow.executions WHERE id = ${executionId};`);
  console.log(`  SELECT * FROM workflow.learnings WHERE workflow_execution_id = ${executionId};`);
  console.log('='.repeat(80));

  await pool.end();

  return {
    execution_id: executionId,
    total_findings: findings.length,
    stored_learnings: parseInt(learningsCount.rows[0].count),
    metrics
  };
}

main().catch(console.error);
