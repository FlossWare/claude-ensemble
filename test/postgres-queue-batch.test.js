/**
 * Tests for PostgreSQL Queue Batch Operations
 *
 * Tests atomic batch claiming, completion, and failure handling.
 */

const { getQueueBatch } = require('../shared/postgres-queue-batch');
const { Pool } = require('pg');

// Test database configuration
const TEST_DB = {
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: 'sfloess',
  password: '',
};

const TEST_QUEUE = 'test_batch_queue';

describe('PostgresQueueBatch', () => {
  let queue;
  let pool;

  beforeAll(async () => {
    pool = new Pool(TEST_DB);
    queue = getQueueBatch(TEST_DB);

    // Create test queue table
    await pool.query(`
      CREATE TABLE IF NOT EXISTS queue.${TEST_QUEUE} (
        id SERIAL PRIMARY KEY,
        data JSONB NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        priority INTEGER DEFAULT 50,
        created_at TIMESTAMP DEFAULT NOW(),
        claimed_by VARCHAR(255),
        claimed_at TIMESTAMP,
        last_heartbeat TIMESTAMP,
        last_worker_id VARCHAR(255),
        timeout_at TIMESTAMP,
        completed_at TIMESTAMP,
        retry_count INTEGER DEFAULT 0,
        scheduled_at TIMESTAMP,
        error TEXT,
        result JSONB
      )
    `);

    // Create index for performance
    await pool.query(`
      CREATE INDEX IF NOT EXISTS idx_${TEST_QUEUE}_status_priority
      ON queue.${TEST_QUEUE}(status, priority DESC, created_at ASC)
    `);
  });

  beforeEach(async () => {
    // Clear test queue
    await pool.query(`TRUNCATE queue.${TEST_QUEUE} RESTART IDENTITY`);
  });

  afterAll(async () => {
    // Clean up test table
    await pool.query(`DROP TABLE IF EXISTS queue.${TEST_QUEUE}`);
    await queue.close();
    await pool.end();
  });

  describe('claimBatch', () => {
    test('claims multiple tasks atomically', async () => {
      // Insert test tasks
      for (let i = 0; i < 20; i++) {
        await pool.query(`
          INSERT INTO queue.${TEST_QUEUE} (data, priority)
          VALUES ($1, $2)
        `, [{ task: `task-${i}` }, i]);
      }

      // Claim batch
      const tasks = await queue.claimBatch(TEST_QUEUE, 'worker-01', 10);

      expect(tasks).toHaveLength(10);
      expect(tasks[0].workerId).toBe('worker-01');

      // Verify tasks are marked as processing
      const result = await pool.query(`
        SELECT COUNT(*) as count
        FROM queue.${TEST_QUEUE}
        WHERE status = 'processing' AND claimed_by = 'worker-01'
      `);

      expect(parseInt(result.rows[0].count)).toBe(10);
    });

    test('respects priority ordering', async () => {
      // Insert tasks with different priorities
      await pool.query(`
        INSERT INTO queue.${TEST_QUEUE} (data, priority)
        VALUES
          ($1, 10),
          ($2, 50),
          ($3, 90)
      `, [{ task: 'low' }, { task: 'medium' }, { task: 'high' }]);

      const tasks = await queue.claimBatch(TEST_QUEUE, 'worker-01', 3);

      // Should claim highest priority first
      expect(tasks[0].priority).toBe(90);
      expect(tasks[1].priority).toBe(50);
      expect(tasks[2].priority).toBe(10);
    });

    test('uses SKIP LOCKED to prevent conflicts', async () => {
      // Insert test tasks
      for (let i = 0; i < 10; i++) {
        await pool.query(`
          INSERT INTO queue.${TEST_QUEUE} (data)
          VALUES ($1)
        `, [{ task: `task-${i}` }]);
      }

      // Claim in parallel with two workers
      const [tasks1, tasks2] = await Promise.all([
        queue.claimBatch(TEST_QUEUE, 'worker-01', 10),
        queue.claimBatch(TEST_QUEUE, 'worker-02', 10),
      ]);

      // Should not overlap (atomic claiming)
      const ids1 = tasks1.map(t => t.id);
      const ids2 = tasks2.map(t => t.id);
      const overlap = ids1.filter(id => ids2.includes(id));

      expect(overlap).toHaveLength(0);
      expect(tasks1.length + tasks2.length).toBe(10);
    });

    test('respects worker affinity', async () => {
      // Insert tasks previously processed by worker-01
      await pool.query(`
        INSERT INTO queue.${TEST_QUEUE} (data, last_worker_id)
        VALUES
          ($1, 'worker-01'),
          ($2, 'worker-02'),
          ($3, NULL)
      `, [{ task: 'a' }, { task: 'b' }, { task: 'c' }]);

      const tasks = await queue.claimBatch(TEST_QUEUE, 'worker-01', 3, {
        affinityWeight: 0.5,
      });

      // Should prefer task from same worker (even if lower priority)
      expect(tasks[0].data.task).toBe('a');
    });
  });

  describe('completeBatch', () => {
    test('completes multiple tasks atomically', async () => {
      // Insert and claim tasks
      for (let i = 0; i < 5; i++) {
        await pool.query(`
          INSERT INTO queue.${TEST_QUEUE} (data, status, claimed_by)
          VALUES ($1, 'processing', 'worker-01')
        `, [{ task: `task-${i}` }]);
      }

      const tasks = await pool.query(`
        SELECT id FROM queue.${TEST_QUEUE}
      `);
      const taskIds = tasks.rows.map(r => r.id);

      // Complete batch
      const completed = await queue.completeBatch(TEST_QUEUE, taskIds, {
        success: true,
      });

      expect(completed).toBe(5);

      // Verify all completed
      const result = await pool.query(`
        SELECT COUNT(*) as count
        FROM queue.${TEST_QUEUE}
        WHERE status = 'completed'
      `);

      expect(parseInt(result.rows[0].count)).toBe(5);
    });

    test('handles empty batch', async () => {
      const completed = await queue.completeBatch(TEST_QUEUE, []);
      expect(completed).toBe(0);
    });
  });

  describe('failBatch', () => {
    test('fails multiple tasks with retry', async () => {
      // Insert and claim tasks
      for (let i = 0; i < 3; i++) {
        await pool.query(`
          INSERT INTO queue.${TEST_QUEUE} (data, status, claimed_by)
          VALUES ($1, 'processing', 'worker-01')
        `, [{ task: `task-${i}` }]);
      }

      const tasks = await pool.query(`
        SELECT id FROM queue.${TEST_QUEUE}
      `);
      const taskIds = tasks.rows.map(r => r.id);

      // Fail batch with retry
      const failed = await queue.failBatch(
        TEST_QUEUE,
        taskIds,
        'Test error',
        true
      );

      expect(failed).toBe(3);

      // Should be back to pending for retry
      const result = await pool.query(`
        SELECT status, retry_count
        FROM queue.${TEST_QUEUE}
      `);

      result.rows.forEach(row => {
        expect(row.status).toBe('pending');
        expect(row.retry_count).toBe(1);
      });
    });

    test('fails tasks permanently after max retries', async () => {
      // Insert task with high retry count
      await pool.query(`
        INSERT INTO queue.${TEST_QUEUE} (data, status, claimed_by, retry_count)
        VALUES ($1, 'processing', 'worker-01', 2)
      `, [{ task: 'task-1' }]);

      const tasks = await pool.query(`
        SELECT id FROM queue.${TEST_QUEUE}
      `);
      const taskIds = tasks.rows.map(r => r.id);

      // Fail batch
      await queue.failBatch(TEST_QUEUE, taskIds, 'Max retries', true);

      // Should be permanently failed
      const result = await pool.query(`
        SELECT status, retry_count
        FROM queue.${TEST_QUEUE}
      `);

      expect(result.rows[0].status).toBe('failed');
      expect(result.rows[0].retry_count).toBe(3);
    });
  });

  describe('heartbeatBatch', () => {
    test('updates heartbeat for multiple tasks', async () => {
      // Insert processing tasks
      for (let i = 0; i < 3; i++) {
        await pool.query(`
          INSERT INTO queue.${TEST_QUEUE} (data, status, claimed_by, last_heartbeat)
          VALUES ($1, 'processing', 'worker-01', NOW() - INTERVAL '5 minutes')
        `, [{ task: `task-${i}` }]);
      }

      const tasks = await pool.query(`
        SELECT id FROM queue.${TEST_QUEUE}
      `);
      const taskIds = tasks.rows.map(r => r.id);

      // Update heartbeat
      const updated = await queue.heartbeatBatch(TEST_QUEUE, taskIds);

      expect(updated).toBe(3);

      // Verify heartbeat updated
      const result = await pool.query(`
        SELECT last_heartbeat
        FROM queue.${TEST_QUEUE}
      `);

      result.rows.forEach(row => {
        const age = Date.now() - new Date(row.last_heartbeat).getTime();
        expect(age).toBeLessThan(5000); // Less than 5 seconds old
      });
    });
  });

  describe('getBatchStats', () => {
    test('returns queue statistics', async () => {
      // Insert tasks in different states
      await pool.query(`
        INSERT INTO queue.${TEST_QUEUE} (data, status)
        VALUES
          ($1, 'pending'),
          ($2, 'processing'),
          ($3, 'completed'),
          ($4, 'failed')
      `, [{ a: 1 }, { b: 2 }, { c: 3 }, { d: 4 }]);

      const stats = await queue.getBatchStats(TEST_QUEUE);

      expect(parseInt(stats.pending)).toBe(1);
      expect(parseInt(stats.processing)).toBe(1);
      expect(parseInt(stats.completed)).toBe(1);
      expect(parseInt(stats.failed)).toBe(1);
    });
  });

  describe('reclaimTimedOut', () => {
    test('reclaims timed-out tasks', async () => {
      // Insert timed-out task
      await pool.query(`
        INSERT INTO queue.${TEST_QUEUE} (data, status, claimed_by, timeout_at)
        VALUES ($1, 'processing', 'worker-01', NOW() - INTERVAL '1 minute')
      `, [{ task: 'task-1' }]);

      const reclaimed = await queue.reclaimTimedOut(TEST_QUEUE);

      expect(reclaimed).toBe(1);

      // Should be back to pending
      const result = await pool.query(`
        SELECT status, retry_count
        FROM queue.${TEST_QUEUE}
      `);

      expect(result.rows[0].status).toBe('pending');
      expect(result.rows[0].retry_count).toBe(1);
    });
  });
});
