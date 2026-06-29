import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { withRetry } from '../../lib/retry.js';

test('SSH timeout triggers retry logic', async () => {
  let attempts = 0;
  const fn = async () => {
    attempts++;
    if (attempts < 3) {
      const err = new Error('ssh: connect timeout');
      err.code = 'ETIMEDOUT';
      throw err;
    }
    return 'success';
  };
  const result = await withRetry(fn, { maxRetries: 3, backoffMs: 10 });
  assert.equal(result, 'success');
  assert.equal(attempts, 3);
});
