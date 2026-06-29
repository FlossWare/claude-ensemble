import { test } from 'node:test';
import { strict as assert } from 'node:assert';

test('API auth failure does not retry', async () => {
  let attempts = 0;
  const fn = async () => {
    attempts++;
    const err = new Error('Unauthorized');
    err.statusCode = 401;
    throw err;
  };
  try {
    await fn();
    assert.fail('Should have thrown');
  } catch (error) {
    assert.equal(attempts, 1);
  }
});
