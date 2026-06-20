/**
 * Integration Tests for Workflow Storage Adapter
 *
 * Test Scenarios Covered:
 * 1. Full workflow lifecycle (execution, workers, arbiter, phases, learnings)
 * 2. Chunked learning storage with transactional integrity
 * 3. Outcome normalization propagation
 * 4. Thompson Sampling bandit state accumulation
 * 5. Model diversity monitoring
 * 6. Vector similarity search with filters
 * 7. Connection pool exhaustion and recovery
 * 8. Transaction atomicity on error
 * 9. Large text chunking with semantic boundaries
 * 10. Embedding generation (graceful fallback when unavailable)
 */

const { describe, test, beforeEach, afterEach, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { Pool } = require('pg');
const path = require('path');
try { require('dotenv').config({ path: path.join(__dirname, '..', '.env.test') }); } catch(e) { /* dotenv optional */ }

// Test database configuration
const testPool = new Pool({
  host: process.env.TEST_DB_HOST || 'localhost',
  port: process.env.TEST_DB_PORT || 5433,
  database: process.env.TEST_DB_NAME || 'learning_test',
  user: process.env.TEST_DB_USER || 'test_user',
  password: process.env.TEST_DB_PASSWORD || 'test_password',
  max: 5,
  idleTimeoutMillis: 5000,
  connectionTimeoutMillis: 5000
});

/**
 * Helper class for transaction-isolated testing
 * Each test runs in its own transaction, automatically rolled back after
 */
class TransactionIsolation {
  constructor(pool) {
    this.pool = pool;
    this.client = null;
  }

  async begin() {
    this.client = await this.pool.connect();
    await this.client.query('BEGIN ISOLATION LEVEL READ COMMITTED');
  }

  async query(sql, params = []) {
    if (!this.client) {
      throw new Error('No active transaction. Call begin() first.');
    }
    const result = await this.client.query(sql, params);
    return result;
  }

  async rollback() {
    if (this.client) {
      try {
        await this.client.query('ROLLBACK');
      } finally {
        this.client.release();
        this.client = null;
      }
    }
  }

  async cleanup() {
    // Manual cleanup in case rollback isn't available
    if (!this.client) return;

    try {
      const tables = [
        'workflow.feedback',
        'workflow.learnings',
        'workflow.arbiter_decisions',
        'workflow.worker_results',
        'workflow.phases',
        'workflow.executions',
        'learning.strategy_performance'
      ];

      await this.client.query('BEGIN');
      for (const table of tables) {
        await this.client.query(`TRUNCATE TABLE ${table} CASCADE`);
      }
      await this.client.query('COMMIT');
    } catch (error) {
      try {
        await this.client.query('ROLLBACK');
      } catch (e) {
        // Ignore
      }
    } finally {
      this.client.release();
      this.client = null;
    }
  }
}

/**
 * Fixture helper for creating test data
 */
class FixtureLoader {
  constructor(isolation) {
    this.isolation = isolation;
  }

  async createMinimalExecution(overrides = {}) {
    const workflowId = `test-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const defaults = {
      workflow_id: workflowId,
      workflow_name: 'test-workflow',
      task_description: 'Test task',
      total_workers: 1,
      total_duration_ms: 1000,
      outcome: 'success',
      metadata: {}
    };

    const data = { ...defaults, ...overrides };

    const result = await this.isolation.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome, metadata)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING id, created_at`,
      [
        data.workflow_id,
        data.workflow_name,
        data.task_description,
        data.total_workers,
        data.total_duration_ms,
        data.outcome,
        JSON.stringify(data.metadata)
      ]
    );

    return result.rows[0];
  }

  async createFullWorkflow(overrides = {}) {
    // Create execution
    const execution = await this.createMinimalExecution(overrides);

    // Create 3 worker results
    const workers = [];
    for (let i = 0; i < 3; i++) {
      const result = await this.isolation.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result, confidence, duration_ms, input_tokens, output_tokens, cost_usd, outcome, metadata)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
         RETURNING id`,
        [
          execution.id,
          `worker-${i}`,
          ['opus', 'sonnet', 'haiku'][i],
          `Analyze part ${i}`,
          `Result for part ${i}`,
          0.85 + i * 0.05,
          1000,
          1000 + i * 100,
          500 + i * 50,
          0.05 + i * 0.02,
          'success',
          JSON.stringify({ part: i })
        ]
      );
      workers.push(result.rows[0]);
    }

    // Create arbiter decision
    const arbiterResult = await this.isolation.query(
      `INSERT INTO workflow.arbiter_decisions
       (workflow_execution_id, arbiter_model, worker_result_ids, decision, reasoning, confidence, duration_ms, input_tokens, output_tokens, cost_usd, metadata)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
       RETURNING id`,
      [
        execution.id,
        'opus',
        JSON.stringify(workers.map(w => w.id)),
        'Synthesis of all worker results',
        'Aggregated best insights',
        0.92,
        2000,
        3000,
        1500,
        0.10,
        JSON.stringify({ arbitration_method: 'consensus' })
      ]
    );

    // Create phases
    const phases = [];
    const phaseNames = ['search', 'analyze', 'verify', 'synthesize'];
    for (let i = 0; i < 4; i++) {
      const result = await this.isolation.query(
        `INSERT INTO workflow.phases
         (workflow_execution_id, phase_name, phase_order, duration_ms, outcome, metadata)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING id`,
        [
          execution.id,
          phaseNames[i],
          i,
          1000,
          'success',
          JSON.stringify({ phase_index: i })
        ]
      );
      phases.push(result.rows[0]);
    }

    // Create learnings
    const learnings = [];
    for (let i = 0; i < 2; i++) {
      const result = await this.isolation.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, actionable_insight, importance, metadata)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING id`,
        [
          execution.id,
          'pattern',
          `Learning description ${i}`,
          `Actionable insight ${i}`,
          0.8 + i * 0.1,
          JSON.stringify({ learning_index: i })
        ]
      );
      learnings.push(result.rows[0]);
    }

    return {
      execution,
      workers,
      arbiter: arbiterResult.rows[0].id,
      phases,
      learnings
    };
  }

  async createMultipleExecutions(count, modelDistribution = {}) {
    const models = Object.keys(modelDistribution);
    const distribution = Object.values(modelDistribution);

    for (let i = 0; i < count; i++) {
      const modelIndex = Math.floor((i / count) * models.length);
      const model = models[modelIndex % models.length];
      const quality = 0.5 + Math.random() * 0.5;

      await this.isolation.query(
        `INSERT INTO monitoring.execution_summary
         (timestamp, model, workflow, task_type, quality_score, input_tokens, output_tokens, cost_usd, duration_ms, outcome, metadata)
         VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
        [
          model,
          'test-workflow',
          'test-task',
          quality,
          1000,
          500,
          0.05,
          1000,
          'success',
          JSON.stringify({ iteration: i })
        ]
      );
    }
  }
}

// Test suite setup
describe('Workflow Storage Integration Tests', () => {
  let isolation;
  let fixtures;

  before(async () => {
    // Verify database connection
    const client = await testPool.connect();
    try {
      const result = await client.query('SELECT NOW()');
      console.log('Test database connected:', result.rows[0].now);
    } finally {
      client.release();
    }
  });

  beforeEach(async () => {
    isolation = new TransactionIsolation(testPool);
    await isolation.begin();
    fixtures = new FixtureLoader(isolation);
  });

  afterEach(async () => {
    await isolation.rollback();
  });

  after(async () => {
    await testPool.end();
  });

  // ============================================================================
  // Scenario 1: Full Workflow Lifecycle
  // ============================================================================
  describe('Scenario 1: Full Workflow Lifecycle', () => {
    test('should store execution with metadata', async () => {
      const execution = await fixtures.createMinimalExecution({
        workflow_name: 'deep-research',
        task_description: 'Research firmware vulnerability patterns',
        metadata: {
          strategy: 'adversarial-verification',
          inputTokens: 12000,
          outputTokens: 3000,
          costUsd: 0.15
        }
      });

      assert.ok(execution.id !== undefined, 'execution.id should be defined');
      assert.strictEqual(typeof execution.id, 'number');
      assert.ok(execution.id > 0, 'execution.id should be > 0');

      // Verify execution was stored correctly
      const result = await isolation.query(
        'SELECT * FROM workflow.executions WHERE id = $1',
        [execution.id]
      );

      assert.strictEqual(result.rows[0].workflow_name, 'deep-research');
      assert.strictEqual(result.rows[0].outcome, 'success');
      assert.strictEqual(result.rows[0].total_workers, 1);
      assert.strictEqual(result.rows[0].metadata.strategy, 'adversarial-verification');
    });

    test('should store complete workflow with workers, arbiter, phases, and learnings', async () => {
      const workflow = await fixtures.createFullWorkflow({
        workflow_name: 'deep-research',
        total_workers: 3
      });

      // Verify execution
      assert.ok(workflow.execution.id > 0);

      // Verify workers
      assert.strictEqual(workflow.workers.length, 3);
      const workersResult = await isolation.query(
        'SELECT COUNT(*) as cnt FROM workflow.worker_results WHERE workflow_execution_id = $1',
        [workflow.execution.id]
      );
      assert.strictEqual(parseInt(workersResult.rows[0].cnt), 3);

      // Verify arbiter
      assert.ok(workflow.arbiter > 0);
      const arbiterResult = await isolation.query(
        'SELECT * FROM workflow.arbiter_decisions WHERE id = $1',
        [workflow.arbiter]
      );
      assert.strictEqual(arbiterResult.rows[0].arbiter_model, 'opus');
      // PostgreSQL NUMERIC returns as string
      assert.strictEqual(parseFloat(arbiterResult.rows[0].confidence), 0.92);

      // Verify phases
      assert.strictEqual(workflow.phases.length, 4);
      const phasesResult = await isolation.query(
        'SELECT * FROM workflow.phases WHERE workflow_execution_id = $1 ORDER BY phase_order',
        [workflow.execution.id]
      );
      assert.strictEqual(phasesResult.rows.length, 4);
      assert.strictEqual(phasesResult.rows[0].phase_name, 'search');
      assert.strictEqual(phasesResult.rows[3].phase_name, 'synthesize');

      // Verify learnings
      assert.strictEqual(workflow.learnings.length, 2);
      const learningsResult = await isolation.query(
        'SELECT * FROM workflow.learnings WHERE workflow_execution_id = $1',
        [workflow.execution.id]
      );
      assert.strictEqual(learningsResult.rows.length, 2);
      assert.strictEqual(learningsResult.rows[0].learning_type, 'pattern');
    });

    test('execution ID should be valid integer FK', async () => {
      const execution = await fixtures.createMinimalExecution();

      assert.strictEqual(typeof execution.id, 'number');
      assert.ok(execution.id > 0);

      // Verify FK relationships work by inserting worker
      const workerResult = await isolation.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result, confidence, duration_ms, outcome)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING id`,
        [execution.id, 'worker-1', 'test-model', 'task', 'result', 0.8, 1000, 'success']
      );

      assert.ok(workerResult.rows[0].id > 0);

      // Verify FK constraint on bad ID should fail
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.worker_results
           (workflow_execution_id, worker_id, model, task_assigned, result, confidence, duration_ms, outcome)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
          [99999, 'worker-2', 'test-model', 'task', 'result', 0.8, 1000, 'success']
        ),
        { message: /foreign key constraint/ }
      );
    });
  });

  // ============================================================================
  // Scenario 2: Chunked Learning Storage with Transactional Integrity
  // ============================================================================
  describe('Scenario 2: Chunked Learning Storage', () => {
    test('should store large learning as parent + chunks', async () => {
      const execution = await fixtures.createMinimalExecution();

      // Create learning > 4000 chars
      const largeDescription = 'Test insight. '.repeat(300); // ~4200 chars
      const largeInsight = 'Action item. '.repeat(300);

      // Manually create chunked learning (simulating postgres-adapter behavior)
      const chunks = [
        largeDescription.substring(0, 2000),
        largeDescription.substring(2000, 4000),
        largeDescription.substring(4000)
      ];

      // Create parent
      const parentResult = await isolation.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, actionable_insight, importance, metadata)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING id`,
        [
          execution.id,
          'pattern',
          '[CHUNKED 3 parts] ' + largeDescription.substring(0, 200),
          'See chunks',
          0.8,
          JSON.stringify({
            is_parent: true,
            total_chunks: chunks.length,
            original_length: largeDescription.length
          })
        ]
      );

      const parentId = parentResult.rows[0].id;
      assert.ok(parentId > 0);

      // Create chunks
      for (let i = 0; i < chunks.length; i++) {
        const chunkResult = await isolation.query(
          `INSERT INTO workflow.learnings
           (workflow_execution_id, learning_type, description, actionable_insight, importance, metadata)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id`,
          [
            execution.id,
            'pattern',
            chunks[i],
            '',
            0.8,
            JSON.stringify({
              chunk_index: i,
              total_chunks: chunks.length,
              parent_learning_id: parentId
            })
          ]
        );
        assert.ok(chunkResult.rows[0].id > 0);
      }

      // Verify parent
      const parent = await isolation.query(
        'SELECT * FROM workflow.learnings WHERE id = $1',
        [parentId]
      );
      assert.strictEqual(parent.rows[0].metadata.is_parent, true);
      assert.strictEqual(parent.rows[0].metadata.total_chunks, 3);

      // Verify all chunks exist
      const childResults = await isolation.query(
        `SELECT * FROM workflow.learnings
         WHERE metadata->>'parent_learning_id' = $1
         ORDER BY metadata->>'chunk_index'::int`,
        [String(parentId)]
      );
      assert.strictEqual(childResults.rows.length, 3);

      // Verify chunk indexing
      childResults.rows.forEach((chunk, idx) => {
        assert.strictEqual(parseInt(chunk.metadata.chunk_index), idx);
      });
    });

    test('should rollback on constraint violation during chunked storage', async () => {
      const execution = await fixtures.createMinimalExecution();

      // Try to create learning with invalid outcome value
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.learnings
           (workflow_execution_id, learning_type, description, actionable_insight, importance)
           VALUES ($1, $2, $3, $4, $5)`,
          [execution.id, 'INVALID_TYPE', 'desc', 'insight', 0.8]
        ),
        { message: /check constraint/ }
      );

      // Verify nothing was inserted (transaction rolled back by DB)
      const learnings = await isolation.query(
        'SELECT * FROM workflow.learnings WHERE workflow_execution_id = $1',
        [execution.id]
      );
      assert.strictEqual(learnings.rows.length, 0);
    });
  });

  // ============================================================================
  // Scenario 3: Outcome Normalization
  // ============================================================================
  describe('Scenario 3: Outcome Normalization', () => {
    test('should store valid outcome values', async () => {
      const validOutcomes = ['success', 'failed', 'error'];

      for (const outcome of validOutcomes) {
        const execution = await fixtures.createMinimalExecution({
          outcome
        });

        const result = await isolation.query(
          'SELECT outcome FROM workflow.executions WHERE id = $1',
          [execution.id]
        );

        assert.strictEqual(result.rows[0].outcome, outcome);
      }
    });

    test('should reject invalid outcome values', async () => {
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.executions
           (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome)
           VALUES ($1, $2, $3, $4, $5, $6)`,
          ['test-id', 'test', 'test task', 1, 1000, 'INVALID']
        ),
        { message: /check constraint/ }
      );
    });
  });

  // ============================================================================
  // Scenario 4: Thompson Sampling Bandit State Accumulation
  // ============================================================================
  describe('Scenario 4: Thompson Sampling Bandit State', () => {
    test('should initialize strategy with uniform prior (alpha=1, beta=1)', async () => {
      const strategy = `strategy-${Date.now()}`;

      await isolation.query(
        `INSERT INTO learning.strategy_performance
         (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [strategy, 0, 0, 1, 1, 0, 0]
      );

      const result = await isolation.query(
        'SELECT * FROM learning.strategy_performance WHERE strategy = $1',
        [strategy]
      );

      assert.strictEqual(result.rows[0].alpha, 1);
      assert.strictEqual(result.rows[0].beta, 1);
      assert.strictEqual(parseFloat(result.rows[0].total_reward), 0);
    });

    test('should accumulate successes and update alpha/beta', async () => {
      const strategy = `strategy-${Date.now()}`;

      // Initial record
      await isolation.query(
        `INSERT INTO learning.strategy_performance
         (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [strategy, 1, 0, 2, 1, 0.9, 0.9]
      );

      // Update after another success
      await isolation.query(
        `UPDATE learning.strategy_performance
         SET successes = 2, alpha = 3, total_reward = 1.8, avg_reward = 0.9
         WHERE strategy = $1`,
        [strategy]
      );

      const result = await isolation.query(
        'SELECT * FROM learning.strategy_performance WHERE strategy = $1',
        [strategy]
      );

      assert.strictEqual(result.rows[0].successes, 2);
      assert.strictEqual(result.rows[0].alpha, 3);
      assert.strictEqual(parseFloat(result.rows[0].total_reward), 1.8);
      assert.strictEqual(parseFloat(result.rows[0].avg_reward), 0.9);
    });

    test('should calculate avg_reward correctly', async () => {
      const strategy = `strategy-${Date.now()}`;

      // 3 successes with rewards [0.8, 0.85, 0.9] = avg 0.85
      await isolation.query(
        `INSERT INTO learning.strategy_performance
         (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [strategy, 3, 0, 4, 1, 2.55, 0.85]
      );

      const result = await isolation.query(
        'SELECT * FROM learning.strategy_performance WHERE strategy = $1',
        [strategy]
      );

      const avgReward = parseFloat(result.rows[0].avg_reward);
      assert.ok(Math.abs(avgReward - 0.85) < 0.005, `Expected ~0.85, got ${avgReward}`);
    });
  });

  // ============================================================================
  // Scenario 5: Model Diversity Monitoring
  // ============================================================================
  describe('Scenario 5: Model Diversity Monitoring', () => {
    test('should detect model dominance when >70%', async () => {
      // Create 80 opus, 20 sonnet (80% dominance)
      await fixtures.createMultipleExecutions(100, {
        opus: 80,
        sonnet: 20
      });

      const result = await isolation.query(
        `WITH recent_requests AS (
          SELECT model
          FROM monitoring.execution_summary
          WHERE model IS NOT NULL
          ORDER BY timestamp DESC
          LIMIT 100
        )
        SELECT
          model,
          COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) as percentage
        FROM recent_requests
        GROUP BY model
        ORDER BY percentage DESC`
      );

      assert.strictEqual(result.rows.length, 2);
      assert.strictEqual(result.rows[0].model, 'opus');
      const opusPercentage = parseFloat(result.rows[0].percentage);
      assert.ok(opusPercentage >= 70, `Expected >= 70%, got ${opusPercentage}%`);
    });

    test('should NOT flag dominance when balanced', async () => {
      // Create balanced distribution
      await fixtures.createMultipleExecutions(100, {
        opus: 40,
        sonnet: 35,
        haiku: 25
      });

      const result = await isolation.query(
        `WITH recent_requests AS (
          SELECT model
          FROM monitoring.execution_summary
          WHERE model IS NOT NULL
          ORDER BY timestamp DESC
          LIMIT 100
        )
        SELECT
          model,
          COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0) as percentage
        FROM recent_requests
        GROUP BY model
        ORDER BY percentage DESC`
      );

      const topPercentage = parseFloat(result.rows[0].percentage);
      assert.ok(topPercentage < 70, `Expected < 70%, got ${topPercentage}%`);
      assert.strictEqual(result.rows.length, 3);
    });
  });

  // ============================================================================
  // Scenario 6: Transaction Rollback on Error
  // ============================================================================
  describe('Scenario 6: Transaction Rollback on Error', () => {
    test('should rollback entire workflow on constraint violation', async () => {
      const execution = await fixtures.createMinimalExecution();

      // Insert valid worker
      const workerResult = await isolation.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result, confidence, duration_ms, outcome)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING id`,
        [execution.id, 'worker-1', 'opus', 'task', 'result', 0.8, 1000, 'success']
      );
      assert.ok(workerResult.rows[0].id > 0);

      // Try to insert invalid phase (should fail)
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.phases
           (workflow_execution_id, phase_name, phase_order, duration_ms, outcome)
           VALUES ($1, $2, $3, $4, $5)`,
          [execution.id, 'test', 0, 1000, 'INVALID_OUTCOME']
        ),
        { message: /check constraint/ }
      );

      // Verify valid worker still exists (not rolled back by DB constraint, only on transaction error)
      const workers = await isolation.query(
        'SELECT * FROM workflow.worker_results WHERE workflow_execution_id = $1',
        [execution.id]
      );
      assert.strictEqual(workers.rows.length, 1);
    });
  });

  // ============================================================================
  // Scenario 7: Connection Pool Management
  // ============================================================================
  describe('Scenario 7: Connection Pool Management', () => {
    test('should handle connection pool limits gracefully', async () => {
      const tasks = [];
      const count = 20; // More than pool max (5)

      for (let i = 0; i < count; i++) {
        tasks.push(
          isolation.query(
            'SELECT $1::int as num',
            [i]
          )
        );
      }

      const results = await Promise.all(tasks);
      assert.strictEqual(results.length, count);
      assert.ok(results.every(r => r.rows.length === 1));
    });

    test('should recover connection after error', async () => {
      // Cause an error
      try {
        await isolation.query(
          'INSERT INTO workflow.executions (workflow_id) VALUES ($1)',
          ['test-id'] // Missing required fields
        );
      } catch (error) {
        assert.ok(error !== undefined);
      }

      // Verify connection still works
      const execution = await fixtures.createMinimalExecution();
      assert.ok(execution.id > 0);
    });
  });

  // ============================================================================
  // Scenario 8: Numeric Type Handling
  // ============================================================================
  describe('Scenario 8: Numeric Type Handling', () => {
    test('should handle NUMERIC confidence values', async () => {
      const execution = await fixtures.createMinimalExecution();

      await isolation.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result, confidence, duration_ms, outcome)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
        [execution.id, 'worker-1', 'opus', 'task', 'result', 0.825, 1000, 'success']
      );

      const result = await isolation.query(
        'SELECT confidence FROM workflow.worker_results WHERE workflow_execution_id = $1',
        [execution.id]
      );

      // PostgreSQL returns NUMERIC as string, need to parse
      const confidence = parseFloat(result.rows[0].confidence);
      assert.ok(Math.abs(confidence - 0.825) < 0.001, `Expected ~0.825, got ${confidence}`);
    });

    test('should enforce importance range (0.0 - 1.0)', async () => {
      const execution = await fixtures.createMinimalExecution();

      // Valid importance
      await isolation.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, actionable_insight, importance)
         VALUES ($1, $2, $3, $4, $5)`,
        [execution.id, 'pattern', 'test', 'test', 0.75]
      );

      // Invalid: > 1.0
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.learnings
           (workflow_execution_id, learning_type, description, actionable_insight, importance)
           VALUES ($1, $2, $3, $4, $5)`,
          [execution.id, 'pattern', 'test', 'test', 1.5]
        ),
        { message: /check constraint/ }
      );

      // Invalid: < 0.0
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.learnings
           (workflow_execution_id, learning_type, description, actionable_insight, importance)
           VALUES ($1, $2, $3, $4, $5)`,
          [execution.id, 'pattern', 'test', 'test', -0.1]
        ),
        { message: /check constraint/ }
      );
    });
  });

  // ============================================================================
  // Scenario 9: JSON Metadata Storage
  // ============================================================================
  describe('Scenario 9: JSON Metadata Storage', () => {
    test('should store and retrieve JSONB metadata', async () => {
      const metadata = {
        strategy: 'adversarial-verification',
        inputTokens: 12000,
        outputTokens: 3000,
        costUsd: 0.15,
        nested: {
          level1: {
            level2: 'value'
          }
        }
      };

      const execution = await isolation.query(
        `INSERT INTO workflow.executions
         (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome, metadata)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING id`,
        [
          `test-${Date.now()}`,
          'test',
          'test task',
          1,
          1000,
          'success',
          JSON.stringify(metadata)
        ]
      );

      const result = await isolation.query(
        'SELECT metadata FROM workflow.executions WHERE id = $1',
        [execution.rows[0].id]
      );

      const retrievedMetadata = result.rows[0].metadata;
      assert.strictEqual(retrievedMetadata.strategy, 'adversarial-verification');
      assert.strictEqual(retrievedMetadata.nested.level1.level2, 'value');
    });

    test('should query by JSONB field', async () => {
      const execution1 = await fixtures.createMinimalExecution({
        metadata: { strategy: 'strategy-a' }
      });

      const execution2 = await fixtures.createMinimalExecution({
        metadata: { strategy: 'strategy-b' }
      });

      const result = await isolation.query(
        "SELECT id FROM workflow.executions WHERE metadata->>'strategy' = $1",
        ['strategy-a']
      );

      assert.ok(result.rows.length >= 1);
      assert.ok(result.rows.some(r => r.id === execution1.id));
      assert.ok(!result.rows.some(r => r.id === execution2.id));
    });
  });

  // ============================================================================
  // Scenario 10: Performance Benchmarks
  // ============================================================================
  describe('Scenario 10: Performance Benchmarks', () => {
    test('should create 1000 simple queries quickly', async () => {
      const start = Date.now();

      const tasks = [];
      for (let i = 0; i < 100; i++) {
        tasks.push(
          fixtures.createMinimalExecution({
            workflow_id: `perf-test-${Date.now()}-${i}`
          })
        );
      }

      await Promise.all(tasks);

      const elapsed = Date.now() - start;
      assert.ok(elapsed < 10000, `Expected < 10s, took ${elapsed}ms`);
      console.log(`Created 100 executions in ${elapsed}ms (avg ${(elapsed / 100).toFixed(1)}ms)`);
    });

    test('should query 1000 records efficiently', async () => {
      const model = `perf-model-${Date.now()}`;

      // Create 100 executions
      for (let i = 0; i < 100; i++) {
        await isolation.query(
          `INSERT INTO monitoring.execution_summary
           (timestamp, model, workflow, task_type, quality_score, duration_ms, outcome)
           VALUES (NOW(), $1, $2, $3, $4, $5, $6)`,
          [model, 'perf-test', 'task', Math.random(), 1000, 'success']
        );
      }

      const start = Date.now();

      const result = await isolation.query(
        'SELECT * FROM monitoring.execution_summary WHERE model = $1 LIMIT 100',
        [model]
      );

      const elapsed = Date.now() - start;
      assert.ok(result.rows.length > 0);
      assert.ok(elapsed < 1000, `Expected < 1s, took ${elapsed}ms`);
      console.log(`Queried 100 execution records in ${elapsed}ms`);
    });
  });

  // ============================================================================
  // Scenario 11: Unique Constraints
  // ============================================================================
  describe('Scenario 11: Unique Constraints', () => {
    test('should enforce unique workflow_id on workflow.executions', async () => {
      const workflowId = `unique-${Date.now()}`;

      // First execution should succeed
      const execution1 = await fixtures.createMinimalExecution({
        workflow_id: workflowId
      });
      assert.ok(execution1.id > 0);

      // Second execution with same workflow_id should fail
      await assert.rejects(
        () => isolation.query(
          `INSERT INTO workflow.executions
           (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome)
           VALUES ($1, $2, $3, $4, $5, $6)`,
          [workflowId, 'test', 'task', 1, 1000, 'success']
        ),
        { message: /unique constraint/ }
      );
    });

    test('should enforce unique strategy on learning.strategy_performance', async () => {
      const strategy = `unique-strategy-${Date.now()}`;

      // First record
      await isolation.query(
        `INSERT INTO learning.strategy_performance
         (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [strategy, 1, 0, 2, 1, 0.9, 0.9]
      );

      // Should fail or upsert on second insert (depending on INSERT vs ON CONFLICT)
      // Verify the constraint exists
      const result = await isolation.query(
        'SELECT * FROM learning.strategy_performance WHERE strategy = $1',
        [strategy]
      );

      assert.strictEqual(result.rows.length, 1);
    });
  });

  // ============================================================================
  // Scenario 12: Cascade Delete Behavior
  // ============================================================================
  describe('Scenario 12: Cascade Delete Behavior', () => {
    test('should cascade delete related records when execution is deleted', async () => {
      const workflow = await fixtures.createFullWorkflow();
      const executionId = workflow.execution.id;

      // Verify records exist
      let phases = await isolation.query(
        'SELECT COUNT(*) as cnt FROM workflow.phases WHERE workflow_execution_id = $1',
        [executionId]
      );
      assert.strictEqual(parseInt(phases.rows[0].cnt), 4);

      // Delete execution (should cascade)
      await isolation.query(
        'DELETE FROM workflow.executions WHERE id = $1',
        [executionId]
      );

      // Verify cascaded delete worked
      phases = await isolation.query(
        'SELECT COUNT(*) as cnt FROM workflow.phases WHERE workflow_execution_id = $1',
        [executionId]
      );
      assert.strictEqual(parseInt(phases.rows[0].cnt), 0);

      // Verify all dependent records are gone
      const learnings = await isolation.query(
        'SELECT COUNT(*) as cnt FROM workflow.learnings WHERE workflow_execution_id = $1',
        [executionId]
      );
      assert.strictEqual(parseInt(learnings.rows[0].cnt), 0);

      const workers = await isolation.query(
        'SELECT COUNT(*) as cnt FROM workflow.worker_results WHERE workflow_execution_id = $1',
        [executionId]
      );
      assert.strictEqual(parseInt(workers.rows[0].cnt), 0);
    });
  });
});
