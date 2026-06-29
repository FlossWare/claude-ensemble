import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { withRetry } from '../../lib/retry.js';

test('Database write failure retries', async () => {
  let attempts = 0;
  const fn = async () => {
    attempts++;
    if (attempts < 2) {
      const err = new Error('Connection pool exhausted');
      err.code = 'ECONNREFUSED';
      throw err;
    }
    return { rowsAffected: 1 };
  };
  const result = await withRetry(fn, { maxRetries: 3, backoffMs: 10 });
  assert.equal(result.rowsAffected, 1);
});
