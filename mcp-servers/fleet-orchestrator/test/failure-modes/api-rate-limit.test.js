import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { withRetry } from '../../lib/retry.js';

test('API rate limit triggers exponential backoff', async () => {
  let attempts = 0;
  const fn = async () => {
    attempts++;
    if (attempts < 3) {
      const err = new Error('Rate limit');
      err.statusCode = 429;
      throw err;
    }
    return 'success';
  };
  await withRetry(fn, { maxRetries: 3, backoffMs: 10, backoffMultiplier: 2 });
  assert.equal(attempts, 3);
});
