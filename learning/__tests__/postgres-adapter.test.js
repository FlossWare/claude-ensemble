/**
 * Unit tests for postgres-adapter.js
 * Framework: Node.js Built-in Test Runner (node:test)
 */

import { describe, test, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  LearningDB,
  StrategyPerformance,
  ExecutionMonitor,
  CostTracker,
  ExperienceMemory,
  WorkflowsLearning,
  OUTCOMES
} = require('../postgres-adapter.js');

// Create mock pool and client for dependency injection
const mockClient = {
  query: mock.fn(async () => ({ rows: [], rowCount: 0 })),
  release: mock.fn()
};

const mockPool = {
  connect: mock.fn(async () => mockClient),
  end: mock.fn(async () => {}),
  query: mock.fn(async () => ({ rows: [] }))
};

/**
 * Create a LearningDB instance with an injected mock pool.
 * This bypasses the module-level pg.Pool so we can test without
 * a real database or mock.module() (which Node.js 22 does not support).
 */
function createMockDB() {
  const db = Object.create(LearningDB.prototype);
  db.pool = mockPool;
  return db;
}

describe('postgres-adapter', () => {
  beforeEach(() => {
    // Reset mocks before each test
    mockPool.connect.mock.resetCalls();
    mockPool.end.mock.resetCalls();
    mockPool.query.mock.resetCalls();
    mockClient.query.mock.resetCalls();
    mockClient.release.mock.resetCalls();
  });

  describe('OUTCOMES constants', () => {
    test('Exports standardized outcome values', () => {
      assert.strictEqual(OUTCOMES.SUCCESS, 'success');
      assert.strictEqual(OUTCOMES.FAILED, 'failed');
      assert.strictEqual(OUTCOMES.ERROR, 'error');
    });
  });

  describe('LearningDB', () => {
    let db;

    beforeEach(() => {
      db = createMockDB();
    });

    describe('query', () => {
      test('Executes query and returns rows', async () => {
        const expectedRows = [{ id: 1, name: 'test' }];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: expectedRows }));

        const result = await db.query('SELECT * FROM test', []);

        assert.deepStrictEqual(result, expectedRows);
        assert.strictEqual(mockPool.connect.mock.calls.length, 1);
        assert.strictEqual(mockClient.release.mock.calls.length, 1);
      });

      test('Releases client even on query error', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => {
          throw new Error('Query failed');
        });

        await assert.rejects(
          async () => await db.query('SELECT * FROM test', []),
          { message: 'Query failed' }
        );

        assert.strictEqual(mockClient.release.mock.calls.length, 1);
      });

      test('Passes parameters to query', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(sql, 'SELECT * FROM test WHERE id = $1');
          assert.deepStrictEqual(params, [42]);
          return { rows: [] };
        });

        await db.query('SELECT * FROM test WHERE id = $1', [42]);
      });
    });

    describe('get', () => {
      test('Returns first row', async () => {
        const expectedRows = [{ id: 1 }, { id: 2 }];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: expectedRows }));

        const result = await db.get('SELECT * FROM test', []);

        assert.deepStrictEqual(result, { id: 1 });
      });

      test('Returns null when no rows', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [] }));

        const result = await db.get('SELECT * FROM test', []);

        assert.strictEqual(result, null);
      });
    });

    describe('all', () => {
      test('Returns all rows', async () => {
        const expectedRows = [{ id: 1 }, { id: 2 }];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: expectedRows }));

        const result = await db.all('SELECT * FROM test', []);

        assert.deepStrictEqual(result, expectedRows);
      });
    });

    describe('run', () => {
      test('Returns changes and lastID', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({
          rows: [{ id: 123 }],
          rowCount: 1
        }));

        const result = await db.run('INSERT INTO test (name) VALUES ($1)', ['test']);

        assert.strictEqual(result.changes, 1);
        assert.strictEqual(result.lastID, 123);
      });

      test('Returns undefined lastID when no rows returned', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({
          rows: [],
          rowCount: 1
        }));

        const result = await db.run('UPDATE test SET name = $1', ['test']);

        assert.strictEqual(result.changes, 1);
        assert.strictEqual(result.lastID, undefined);
      });

      test('Releases client even on error', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => {
          throw new Error('Insert failed');
        });

        await assert.rejects(
          async () => await db.run('INSERT INTO test VALUES ($1)', ['test']),
          { message: 'Insert failed' }
        );

        assert.strictEqual(mockClient.release.mock.calls.length, 1);
      });
    });

    describe('transaction', () => {
      test('Executes BEGIN, callback, COMMIT', async () => {
        const callback = mock.fn(async (client) => {
          return 'success';
        });

        const result = await db.transaction(callback);

        assert.strictEqual(result, 'success');
        assert.strictEqual(mockClient.query.mock.calls.length, 2);
        assert.strictEqual(mockClient.query.mock.calls[0].arguments[0], 'BEGIN');
        assert.strictEqual(mockClient.query.mock.calls[1].arguments[0], 'COMMIT');
        assert.strictEqual(callback.mock.calls.length, 1);
        assert.strictEqual(mockClient.release.mock.calls.length, 1);
      });

      test('Executes ROLLBACK on error', async () => {
        const callback = mock.fn(async (client) => {
          throw new Error('Transaction failed');
        });

        await assert.rejects(
          async () => await db.transaction(callback),
          { message: 'Transaction failed' }
        );

        assert.strictEqual(mockClient.query.mock.calls.length, 2);
        assert.strictEqual(mockClient.query.mock.calls[0].arguments[0], 'BEGIN');
        assert.strictEqual(mockClient.query.mock.calls[1].arguments[0], 'ROLLBACK');
        assert.strictEqual(mockClient.release.mock.calls.length, 1);
      });

      test('Releases client even on rollback', async () => {
        const callback = mock.fn(async (client) => {
          throw new Error('Transaction failed');
        });

        await assert.rejects(
          async () => await db.transaction(callback),
          { message: 'Transaction failed' }
        );

        assert.strictEqual(mockClient.release.mock.calls.length, 1);
      });
    });

    describe('close', () => {
      test('Calls pool.end()', async () => {
        await db.close();

        assert.strictEqual(mockPool.end.mock.calls.length, 1);
      });
    });
  });

  describe('StrategyPerformance', () => {
    let db, strategy;

    beforeEach(() => {
      db = createMockDB();
      strategy = new StrategyPerformance(db);
    });

    describe('getStrategy', () => {
      test('Returns strategy row', async () => {
        const expectedRow = { strategy: 'test', alpha: 2, beta: 1 };
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [expectedRow] }));

        const result = await strategy.getStrategy('test');

        assert.deepStrictEqual(result, expectedRow);
      });

      test('Returns null when strategy not found', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [] }));

        const result = await strategy.getStrategy('nonexistent');

        assert.strictEqual(result, null);
      });
    });

    describe('updateStrategy', () => {
      test('Inserts or updates strategy', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('INSERT INTO learning.strategy_performance'));
          assert.ok(sql.includes('ON CONFLICT (strategy) DO UPDATE'));
          assert.deepStrictEqual(params, ['test', 5, 2, 6, 3, 12.5, 2.5]);
          return { rows: [], rowCount: 1 };
        });

        await strategy.updateStrategy('test', {
          successes: 5,
          failures: 2,
          alpha: 6,
          beta: 3,
          total_reward: 12.5,
          avg_reward: 2.5
        });
      });
    });

    describe('getAllStrategies', () => {
      test('Returns all strategies ordered by avg_reward DESC', async () => {
        const expectedRows = [
          { strategy: 'best', avg_reward: 0.9 },
          { strategy: 'medium', avg_reward: 0.5 }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: expectedRows }));

        const result = await strategy.getAllStrategies();

        assert.deepStrictEqual(result, expectedRows);
      });
    });

    describe('record', () => {
      test('Creates new strategy with uniform prior when not exists', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [] })); // getStrategy returns null
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          // updateStrategy call
          assert.deepStrictEqual(params, ['new_strategy', 1, 0, 2, 1, 0.85, 0.85]);
          return { rows: [], rowCount: 1 };
        });

        await strategy.record('new_strategy', true, 0.85);
      });

      test('Initializes failure correctly when first attempt fails', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [] })); // getStrategy returns null
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          // updateStrategy call
          assert.deepStrictEqual(params, ['new_strategy', 0, 1, 1, 2, 0.25, 0.25]);
          return { rows: [], rowCount: 1 };
        });

        await strategy.record('new_strategy', false, 0.25);
      });

      test('Updates existing strategy on success', async () => {
        const existing = {
          strategy: 'existing',
          successes: 3,
          failures: 1,
          total_reward: 2.5
        };
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [existing] })); // getStrategy
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          // updateStrategy call
          const [strat, successes, failures, alpha, beta, total_reward, avg_reward] = params;
          assert.strictEqual(strat, 'existing');
          assert.strictEqual(successes, 4);
          assert.strictEqual(failures, 1);
          assert.strictEqual(alpha, 5); // 1 + 4
          assert.strictEqual(beta, 2); // 1 + 1
          assert.strictEqual(total_reward, 3.4); // 2.5 + 0.9
          assert.strictEqual(avg_reward, 3.4 / 5); // 0.68
          return { rows: [], rowCount: 1 };
        });

        await strategy.record('existing', true, 0.9);
      });

      test('Updates existing strategy on failure', async () => {
        const existing = {
          strategy: 'existing',
          successes: 3,
          failures: 1,
          total_reward: 2.5
        };
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [existing] })); // getStrategy
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          // updateStrategy call
          const [strat, successes, failures, alpha, beta, total_reward, avg_reward] = params;
          assert.strictEqual(strat, 'existing');
          assert.strictEqual(successes, 3);
          assert.strictEqual(failures, 2);
          assert.strictEqual(alpha, 4); // 1 + 3
          assert.strictEqual(beta, 3); // 1 + 2
          assert.strictEqual(total_reward, 2.7); // 2.5 + 0.2
          assert.strictEqual(avg_reward, 2.7 / 5); // 0.54
          return { rows: [], rowCount: 1 };
        });

        await strategy.record('existing', false, 0.2);
      });
    });
  });

  describe('ExecutionMonitor', () => {
    let db, monitor;

    beforeEach(() => {
      db = createMockDB();
      monitor = new ExecutionMonitor(db);
    });

    describe('logExecution', () => {
      test('Normalizes outcome values (pass -> success)', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[8], 'success'); // outcome normalized from 'pass'
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.9,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'pass'
        });
      });

      test('Normalizes outcome values (fail -> failed)', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[8], 'failed'); // outcome normalized from 'fail'
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.5,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'fail'
        });
      });

      test('Normalizes outcome values (failure -> failed)', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[8], 'failed'); // outcome normalized from 'failure'
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.5,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'failure'
        });
      });

      test('Normalizes outcome values (ERROR -> error)', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[8], 'error'); // outcome normalized from 'ERROR'
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.0,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'ERROR'
        });
      });

      test('Handles unknown outcome values (defaults to failed)', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[8], 'failed'); // unknown value normalized to 'failed'
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.5,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'unknown_value'
        });
      });

      test('Detects multi-model operations (comma-separated)', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[0], 'multi-model-adversarial'); // model normalized
          const metadata = JSON.parse(params[9]);
          assert.deepStrictEqual(metadata.verifier_models, ['opus', 'sonnet', 'haiku']);
          assert.strictEqual(metadata.original_value, 'opus,sonnet,haiku');
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus,sonnet,haiku',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.9,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'success'
        });
      });

      test('Stores metadata as NULL when no multi-model or custom metadata', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.strictEqual(params[9], null); // metadata is null
          return { rows: [], rowCount: 1 };
        });

        await monitor.logExecution({
          model: 'opus',
          workflow: 'test',
          task_type: 'test',
          quality_score: 0.9,
          input_tokens: 100,
          output_tokens: 50,
          cost_usd: 0.01,
          duration_ms: 1000,
          outcome: 'success'
        });
      });
    });

    describe('getExecutionStats', () => {
      test('Filters by model and workflow', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('WHERE model = $1 AND workflow = $2'));
          assert.deepStrictEqual(params, ['opus', 'test']);
          return { rows: [] };
        });

        await monitor.getExecutionStats('opus', 'test');
      });

      test('Filters by model only when workflow null', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('WHERE model = $1'));
          assert.ok(!sql.includes('AND workflow'));
          assert.deepStrictEqual(params, ['opus']);
          return { rows: [] };
        });

        await monitor.getExecutionStats('opus', null);
      });
    });

    describe('getRecentExecutions', () => {
      test('Returns recent executions with limit', async () => {
        const expectedRows = [{ id: 1 }, { id: 2 }];
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('ORDER BY timestamp DESC LIMIT $1'));
          assert.deepStrictEqual(params, [50]);
          return { rows: expectedRows };
        });

        const result = await monitor.getRecentExecutions(50);

        assert.deepStrictEqual(result, expectedRows);
      });
    });

    describe('getModelDiversity', () => {
      test('Returns percentage distribution as numbers', async () => {
        const mockRows = [
          { metric: 'opus', value: '65.5' },
          { metric: 'sonnet', value: '34.5' }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: mockRows }));

        const result = await monitor.getModelDiversity(100);

        assert.strictEqual(result[0].metric, 'opus');
        assert.strictEqual(result[0].value, 65.5); // Converted to number
        assert.strictEqual(result[1].metric, 'sonnet');
        assert.strictEqual(result[1].value, 34.5); // Converted to number
      });
    });

    describe('checkModelDominance', () => {
      test('Detects dominance when threshold exceeded', async () => {
        const mockRows = [
          { metric: 'opus', value: '75.0' },
          { metric: 'sonnet', value: '25.0' }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: mockRows }));

        const result = await monitor.checkModelDominance(100, 70);

        assert.strictEqual(result.isDominant, true);
        assert.strictEqual(result.model, 'opus');
        assert.strictEqual(result.percentage, 75.0);
        assert.strictEqual(result.distribution.length, 2);
      });

      test('Does not detect dominance when below threshold', async () => {
        const mockRows = [
          { metric: 'opus', value: '60.0' },
          { metric: 'sonnet', value: '40.0' }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: mockRows }));

        const result = await monitor.checkModelDominance(100, 70);

        assert.strictEqual(result.isDominant, false);
        assert.strictEqual(result.model, null);
        assert.strictEqual(result.percentage, 60.0);
      });

      test('Handles empty distribution', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [] }));

        const result = await monitor.checkModelDominance(100, 70);

        assert.strictEqual(result.isDominant, false);
        assert.strictEqual(result.model, null);
        assert.strictEqual(result.percentage, 0);
      });
    });
  });

  describe('CostTracker', () => {
    let db, costTracker;

    beforeEach(() => {
      db = createMockDB();
      costTracker = new CostTracker(db);
    });

    describe('logCost', () => {
      test('Inserts cost entry', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('INSERT INTO costs.entries'));
          assert.deepStrictEqual(params, ['opus', 1000, 500, 0.05]);
          return { rows: [], rowCount: 1 };
        });

        await costTracker.logCost({
          model: 'opus',
          input_tokens: 1000,
          output_tokens: 500,
          total_cost: 0.05
        });
      });
    });

    describe('getDailyCosts', () => {
      test('Returns daily costs as numbers', async () => {
        const mockRows = [
          { date: '2026-06-20', total_cost: '1.5', input_tokens: '10000', output_tokens: '5000' }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: mockRows }));

        const result = await costTracker.getDailyCosts(30);

        assert.strictEqual(result[0].date, '2026-06-20');
        assert.strictEqual(result[0].total_cost, 1.5); // Converted to number
        assert.strictEqual(result[0].input_tokens, 10000); // Converted to number
        assert.strictEqual(result[0].output_tokens, 5000); // Converted to number
      });

      test('Handles null values', async () => {
        const mockRows = [
          { date: '2026-06-20', total_cost: null, input_tokens: null, output_tokens: null }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: mockRows }));

        const result = await costTracker.getDailyCosts(30);

        assert.strictEqual(result[0].total_cost, 0);
        assert.strictEqual(result[0].input_tokens, 0);
        assert.strictEqual(result[0].output_tokens, 0);
      });
    });

    describe('getModelCosts', () => {
      test('Returns model costs as numbers', async () => {
        const mockRows = [
          { model: 'opus', total_cost: '2.5', input_tokens: '20000', output_tokens: '10000' }
        ];
        mockClient.query.mock.mockImplementationOnce(async () => ({ rows: mockRows }));

        const result = await costTracker.getModelCosts(30);

        assert.strictEqual(result[0].model, 'opus');
        assert.strictEqual(result[0].total_cost, 2.5); // Converted to number
        assert.strictEqual(result[0].input_tokens, 20000); // Converted to number
        assert.strictEqual(result[0].output_tokens, 10000); // Converted to number
      });
    });

    describe('getTotalCost', () => {
      test('Returns total cost as number', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({
          rows: [{ total_cost: '15.75' }]
        }));

        const result = await costTracker.getTotalCost(30);

        assert.strictEqual(result, 15.75); // Converted to number
      });

      test('Returns 0 when null', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({
          rows: [{ total_cost: null }]
        }));

        const result = await costTracker.getTotalCost(30);

        assert.strictEqual(result, 0);
      });

      test('Returns 0 when no rows', async () => {
        mockClient.query.mock.mockImplementationOnce(async () => ({
          rows: []
        }));

        const result = await costTracker.getTotalCost(30);

        assert.strictEqual(result, 0);
      });
    });
  });

  describe('ExperienceMemory', () => {
    let db, memory;

    beforeEach(() => {
      db = createMockDB();
      memory = new ExperienceMemory(db);
    });

    describe('addExperience', () => {
      test('Inserts experience with JSON context', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('INSERT INTO learning.experiences'));
          const context = JSON.parse(params[2]); // context is stringified
          assert.deepStrictEqual(context, { key: 'value' });
          return { rows: [], rowCount: 1 };
        });

        await memory.addExperience({
          problem_type: 'test',
          problem_hash: 'hash123',
          context: { key: 'value' },
          embedding: '[1,2,3]',
          strategy: 'test_strategy',
          success: true,
          reward: 0.9,
          novelty_score: 0.5,
          importance: 0.8
        });
      });
    });

    describe('findSimilar', () => {
      test('Finds similar embeddings without filters', async () => {
        const expectedRows = [{ id: 1, distance: 0.1 }];
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('embedding <=> $1::vector'));
          assert.ok(sql.includes('ORDER BY embedding <=> $1::vector LIMIT'));
          assert.deepStrictEqual(params, ['[1,2,3]', 10]);
          return { rows: expectedRows };
        });

        const result = await memory.findSimilar('[1,2,3]', 10, {});

        assert.deepStrictEqual(result, expectedRows);
      });

      test('Applies success filter', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('AND success = $2'));
          assert.deepStrictEqual(params, ['[1,2,3]', true, 10]);
          return { rows: [] };
        });

        await memory.findSimilar('[1,2,3]', 10, { success: true });
      });

      test('Applies min_reward filter', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('AND reward >= $2'));
          assert.deepStrictEqual(params, ['[1,2,3]', 0.7, 10]);
          return { rows: [] };
        });

        await memory.findSimilar('[1,2,3]', 10, { min_reward: 0.7 });
      });

      test('Applies both filters', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('AND success = $2'));
          assert.ok(sql.includes('AND reward >= $3'));
          assert.deepStrictEqual(params, ['[1,2,3]', true, 0.7, 10]);
          return { rows: [] };
        });

        await memory.findSimilar('[1,2,3]', 10, { success: true, min_reward: 0.7 });
      });
    });

    describe('getRecentExperiences', () => {
      test('Returns recent experiences with limit', async () => {
        const expectedRows = [{ id: 1 }, { id: 2 }];
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('ORDER BY timestamp DESC LIMIT $1'));
          assert.deepStrictEqual(params, [50]);
          return { rows: expectedRows };
        });

        const result = await memory.getRecentExperiences(50);

        assert.deepStrictEqual(result, expectedRows);
      });
    });
  });

  describe('WorkflowsLearning', () => {
    let db, workflows;

    beforeEach(() => {
      db = createMockDB();
      workflows = new WorkflowsLearning(db);
    });

    describe('_chunkText', () => {
      test('Returns empty array for null/empty/whitespace-only text', () => {
        assert.deepStrictEqual(workflows._chunkText(null), []);
        assert.deepStrictEqual(workflows._chunkText(''), []);
        assert.deepStrictEqual(workflows._chunkText('   '), []);
        assert.deepStrictEqual(workflows._chunkText('\n\n'), []);
      });

      test('Returns single-element array when text is shorter than maxChunkSize', () => {
        const shortText = 'This is a short text under 4000 chars.';
        const result = workflows._chunkText(shortText, 4000);

        assert.strictEqual(result.length, 1);
        assert.strictEqual(result[0], shortText);
      });

      test('Splits at paragraph boundaries (double newline) when available', () => {
        const text = 'First paragraph with 2500 chars.' + 'a'.repeat(2465) + '\n\n' +
                     'Second paragraph with 2500 chars.' + 'b'.repeat(2464);

        const result = workflows._chunkText(text, 4000, 200);

        // Should split at paragraph boundary, not mid-word
        assert.ok(result.length >= 2, 'Should create at least 2 chunks');
        assert.ok(result[0].includes('First paragraph'), 'First chunk has first paragraph');
        assert.ok(result[1].includes('Second paragraph'), 'Second chunk has second paragraph');
      });

      test('Splits at sentence boundaries (period-space) as fallback', () => {
        const sentence1 = 'First sentence with 2500 chars.' + 'x'.repeat(2467);
        const sentence2 = ' Second sentence with 2500 chars.' + 'y'.repeat(2466);
        const text = sentence1 + '.' + sentence2;

        const result = workflows._chunkText(text, 4000, 200);

        assert.ok(result.length >= 2, 'Should create at least 2 chunks');
        assert.ok(result[0].endsWith('.'), 'First chunk ends at sentence boundary');
      });

      test('Clamps overlap to maxChunkSize-1 to prevent infinite loop', () => {
        const text = 'a'.repeat(10000);

        // Overlap >= maxChunkSize would cause infinite loop without clamping
        const result = workflows._chunkText(text, 4000, 5000);

        assert.ok(result.length > 0, 'Should produce chunks despite invalid overlap');
        assert.ok(result.length < 100, 'Should not create excessive chunks (infinite loop check)');
      });

      test('Guarantees forward progress even with large overlap values', () => {
        const text = 'a'.repeat(10000);

        // Should make progress even with overlap = maxChunkSize - 1
        const result = workflows._chunkText(text, 4000, 3999);

        assert.ok(result.length > 1, 'Should create multiple chunks');
        assert.ok(result.length < 10000, 'Should not create excessive chunks (stuck check)');
      });

      test('Handles text with no natural break points', () => {
        const text = 'x'.repeat(10000); // No periods, no newlines

        const result = workflows._chunkText(text, 4000, 200);

        assert.ok(result.length >= 2, 'Should create chunks even without break points');
        assert.ok(result.every(chunk => chunk.length <= 4000), 'All chunks under max size');
      });

      test('Trims whitespace from each chunk', () => {
        const text = '  chunk1  \n\n  chunk2  ';

        const result = workflows._chunkText(text, 20, 5);

        assert.ok(result.every(chunk => chunk === chunk.trim()), 'All chunks trimmed');
        assert.ok(result.every(chunk => chunk.length > 0), 'No empty chunks after trim');
      });

      test('Does not produce empty chunks', () => {
        const text = 'a\n\n\n\n\n\nb'; // Many empty paragraphs

        const result = workflows._chunkText(text, 10, 2);

        assert.ok(result.every(chunk => chunk.length > 0), 'No empty chunks');
      });

      test('Handles exactly maxChunkSize boundary', () => {
        const text = 'a'.repeat(4000);

        const result = workflows._chunkText(text, 4000, 200);

        assert.strictEqual(result.length, 1, 'Single chunk when exactly at boundary');
        assert.strictEqual(result[0].length, 4000);
      });

      test('Handles maxChunkSize + 1 boundary', () => {
        const text = 'a'.repeat(4001);

        const result = workflows._chunkText(text, 4000, 200);

        assert.ok(result.length >= 2, 'Splits when exceeding maxChunkSize by 1 char');
      });

      test('Preserves content across chunks (no data loss)', () => {
        const text = 'Line1\n\nLine2\n\nLine3\n\nLine4';

        const result = workflows._chunkText(text, 15, 5);
        const reconstructed = result.join('');

        // Chunks may overlap, but all content should be present
        assert.ok(reconstructed.includes('Line1'), 'Contains Line1');
        assert.ok(reconstructed.includes('Line2'), 'Contains Line2');
        assert.ok(reconstructed.includes('Line3'), 'Contains Line3');
        assert.ok(reconstructed.includes('Line4'), 'Contains Line4');
      });
    });

    describe('recordLearning', () => {
      test('Throws when workflow_execution_id is missing', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              learning_type: 'pattern',
              description: 'Test',
              actionable_insight: 'Insight'
            });
          },
          { message: /workflow_execution_id is required/ }
        );
      });

      test('Throws when learning_type is missing', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              workflow_execution_id: 1,
              description: 'Test',
              actionable_insight: 'Insight'
            });
          },
          { message: /learning_type is required/ }
        );
      });

      test('Throws when description is missing', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              workflow_execution_id: 1,
              learning_type: 'pattern',
              actionable_insight: 'Insight'
            });
          },
          { message: /description is required/ }
        );
      });

      test('Throws when actionable_insight is missing', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              workflow_execution_id: 1,
              learning_type: 'pattern',
              description: 'Test'
            });
          },
          { message: /actionable_insight is required/ }
        );
      });

      test('Throws when learning_type is not pattern/failure/optimization', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              workflow_execution_id: 1,
              learning_type: 'invalid_type',
              description: 'Test',
              actionable_insight: 'Insight'
            });
          },
          { message: /learning_type must be one of/ }
        );
      });

      test('Throws when importance is outside 0.0-1.0 range', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              workflow_execution_id: 1,
              learning_type: 'pattern',
              description: 'Test',
              actionable_insight: 'Insight',
              importance: 1.5
            });
          },
          { message: /importance must be between 0.0 and 1.0/ }
        );
      });

      test('Stores single learning when combined text is under 4000 chars', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('INSERT INTO workflow.learnings'));
          assert.strictEqual(params[0], 1); // workflow_execution_id
          assert.strictEqual(params[1], 'pattern');
          assert.strictEqual(params[2], 'Short description');
          assert.strictEqual(params[3], 'Short insight');
          assert.strictEqual(params[4], 0.8);
          return { rows: [{ id: 123, created_at: new Date() }] };
        });

        const result = await workflows.recordLearning({
          workflow_execution_id: 1,
          learning_type: 'pattern',
          description: 'Short description',
          actionable_insight: 'Short insight',
          importance: 0.8
        });

        assert.ok(result.id, 'Returns ID from RETURNING clause');
      });

      test('Creates parent + chunk learnings when combined text exceeds 4000 chars', async () => {
        const longText = 'x'.repeat(5000);

        // Mock transaction: BEGIN, parent INSERT, chunk INSERTs, COMMIT
        const queryMock = mock.fn();
        queryMock.mock.mockImplementationOnce(async () => {}); // BEGIN
        queryMock.mock.mockImplementationOnce(async () => ({ rows: [{ id: 999 }] })); // Parent INSERT
        queryMock.mock.mockImplementationOnce(async () => ({ rows: [{ id: 1000 }] })); // Chunk 1
        queryMock.mock.mockImplementationOnce(async () => ({ rows: [{ id: 1001 }] })); // Chunk 2
        queryMock.mock.mockImplementationOnce(async () => {}); // COMMIT

        const txnClient = {
          query: queryMock,
          release: mock.fn()
        };

        mockPool.connect.mock.mockImplementationOnce(async () => txnClient);

        const result = await workflows.recordLearning({
          workflow_execution_id: 1,
          learning_type: 'pattern',
          description: longText,
          actionable_insight: 'Insight',
          importance: 0.8
        });

        assert.ok(result.id, 'Returns parent ID');
        assert.ok(queryMock.mock.calls.length >= 4, 'Creates BEGIN + parent + chunks + COMMIT');
      });

      test('Uses transaction for chunked learnings (rolls back on partial failure)', async () => {
        const longText = 'x'.repeat(5000);

        const queryMock = mock.fn();
        queryMock.mock.mockImplementationOnce(async () => {}); // BEGIN
        queryMock.mock.mockImplementationOnce(async () => ({ rows: [{ id: 999 }] })); // Parent INSERT
        queryMock.mock.mockImplementationOnce(async () => {
          throw new Error('Simulated chunk insert failure');
        }); // Chunk 1 fails
        queryMock.mock.mockImplementationOnce(async () => {}); // ROLLBACK

        const txnClient = {
          query: queryMock,
          release: mock.fn()
        };

        mockPool.connect.mock.mockImplementationOnce(async () => txnClient);

        await assert.rejects(
          async () => {
            await workflows.recordLearning({
              workflow_execution_id: 1,
              learning_type: 'pattern',
              description: longText,
              actionable_insight: 'Insight'
            });
          },
          { message: /Simulated chunk insert failure/ }
        );

        // Verify rollback was called
        const rollbackCalls = queryMock.mock.calls.filter(c => c.arguments[0] === 'ROLLBACK');
        assert.strictEqual(rollbackCalls.length, 1, 'Transaction rolled back on error');
      });

      test('Stores chunk metadata (chunk_index, total_chunks, parent_learning_id)', async () => {
        const longText = 'x'.repeat(5000);

        const insertedChunks = [];
        const queryMock = mock.fn();
        queryMock.mock.mockImplementationOnce(async () => {}); // BEGIN
        queryMock.mock.mockImplementationOnce(async () => ({ rows: [{ id: 999 }] })); // Parent INSERT

        // Capture chunk inserts
        queryMock.mock.mockImplementation(async (sql, params) => {
          if (sql.includes('INSERT INTO workflow.learnings') && params[6]) {
            const metadata = JSON.parse(params[6]);
            if (metadata.chunk_index !== undefined) {
              insertedChunks.push(metadata);
            }
            return { rows: [{ id: 1000 + insertedChunks.length }] };
          }
          return {}; // COMMIT
        });

        const txnClient = {
          query: queryMock,
          release: mock.fn()
        };

        mockPool.connect.mock.mockImplementationOnce(async () => txnClient);

        const result = await workflows.recordLearning({
          workflow_execution_id: 1,
          learning_type: 'pattern',
          description: longText,
          actionable_insight: 'Insight'
        });

        assert.ok(insertedChunks.length >= 2, 'Created multiple chunks');
        insertedChunks.forEach((chunk, idx) => {
          assert.strictEqual(chunk.chunk_index, idx, `Chunk ${idx} has correct index`);
          assert.strictEqual(chunk.total_chunks, insertedChunks.length, 'Total chunks matches');
          assert.strictEqual(chunk.parent_learning_id, result.id, 'Parent ID set');
        });
      });
    });

    describe('recordRun', () => {
      test('Throws when workflow_id is missing', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordRun({
              workflow_name: 'test',
              task_description: 'Test task',
              total_workers: 3,
              total_duration_ms: 1000,
              outcome: 'success'
            });
          },
          { message: /workflow_id is required/ }
        );
      });

      test('Throws when outcome is invalid', async () => {
        await assert.rejects(
          async () => {
            await workflows.recordRun({
              workflow_id: 'wf-123',
              workflow_name: 'test',
              task_description: 'Test task',
              total_workers: 3,
              total_duration_ms: 1000,
              outcome: 'invalid'
            });
          },
          { message: /outcome must be one of/ }
        );
      });

      test('Returns auto-generated execution id', async () => {
        mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
          assert.ok(sql.includes('INSERT INTO workflow.executions'));
          assert.ok(sql.includes('RETURNING id, created_at'));
          return { rows: [{ id: 456, created_at: new Date() }] };
        });

        const execId = await workflows.recordRun({
          workflow_id: 'wf-123',
          workflow_name: 'test',
          task_description: 'Test task',
          total_workers: 3,
          total_duration_ms: 1000,
          outcome: 'success'
        });

        assert.strictEqual(execId, 456);
      });

      test('Accepts all valid outcomes', async () => {
        for (const outcome of ['success', 'failed', 'error']) {
          mockClient.query.mock.resetCalls();
          mockClient.query.mock.mockImplementationOnce(async () => ({
            rows: [{ id: 456, created_at: new Date() }]
          }));

          await workflows.recordRun({
            workflow_id: 'wf-123',
            workflow_name: 'test',
            task_description: 'Test task',
            total_workers: 3,
            total_duration_ms: 1000,
            outcome
          });
        }
      });
    });
  });

  describe('StrategyPerformance.getStats', () => {
    let db, strategy;

    beforeEach(() => {
      db = createMockDB();
      strategy = new StrategyPerformance(db);
    });

    test('getStats delegates to getStrategy and returns same result', async () => {
      const expectedRow = { strategy: 'test', alpha: 3, beta: 2, avg_reward: 0.75 };
      mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [expectedRow] }));

      const result = await strategy.getStats('test');
      assert.deepStrictEqual(result, expectedRow);
    });

    test('getStats returns null when strategy not found', async () => {
      mockClient.query.mock.mockImplementationOnce(async () => ({ rows: [] }));

      const result = await strategy.getStats('nonexistent');
      assert.strictEqual(result, null);
    });
  });

  describe('WorkflowsLearning.queryLearnings', () => {
    let db, workflows;

    beforeEach(() => {
      db = createMockDB();
      workflows = new WorkflowsLearning(db);
    });

    test('Builds query with all five filter fields', async () => {
      mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
        assert.ok(sql.includes('$1'), 'Missing $1 placeholder');
        assert.ok(sql.includes('$5'), 'Missing $5 placeholder');
        assert.ok(sql.includes('$6'), 'Missing $6 placeholder for limit');
        assert.strictEqual(params.length, 6);
        assert.deepStrictEqual(params, ['wf-name', 'code', 'hard', 'success', 'pattern', 50]);
        return { rows: [] };
      });

      await workflows.queryLearnings({
        workflow_name: 'wf-name',
        task_type: 'code',
        task_difficulty: 'hard',
        outcome: 'success',
        learning_type: 'pattern',
        limit: 50
      });
    });

    test('Uses default limit of 100 when not specified', async () => {
      mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
        assert.strictEqual(params[params.length - 1], 100);
        return { rows: [] };
      });

      await workflows.queryLearnings({});
    });

    test('SQL injection in workflow_name is parameterized', async () => {
      const malicious = "'; DROP TABLE workflows.learnings; --";
      mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
        assert.ok(!sql.includes('DROP TABLE'), 'SQL injection payload found in query string');
        assert.ok(params.includes(malicious), 'Malicious value must be in params');
        return { rows: [] };
      });

      await workflows.queryLearnings({ workflow_name: malicious });
    });
  });

  describe('CostTracker SQL injection on interval construction', () => {
    let db, costTracker;

    beforeEach(() => {
      db = createMockDB();
      costTracker = new CostTracker(db);
    });

    test('getModelCosts: SQL injection via days parameter is parameterized', async () => {
      const maliciousDays = "1 day); DROP TABLE costs.entries; SELECT interval('1";
      mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
        assert.ok(sql.includes('$1'), 'days parameter must use parameterized binding');
        assert.ok(!sql.includes('DROP TABLE'), 'SQL injection found in query string');
        assert.strictEqual(params[0], maliciousDays);
        return { rows: [] };
      });

      await costTracker.getModelCosts(maliciousDays);
    });

    test('getTotalCost: SQL injection via days parameter is parameterized', async () => {
      const maliciousDays = "1 day); DROP TABLE costs.entries; SELECT interval('1";
      mockClient.query.mock.mockImplementationOnce(async (sql, params) => {
        assert.ok(sql.includes('$1'), 'days parameter must use parameterized binding');
        assert.ok(!sql.includes('DROP TABLE'), 'SQL injection found in query string');
        assert.strictEqual(params[0], maliciousDays);
        return { rows: [{ total_cost: null }] };
      });

      await costTracker.getTotalCost(maliciousDays);
    });
  });
});
