import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { CircuitBreaker } from '../../lib/circuit-breaker.js';

test('SSH connection refused opens circuit breaker', async () => {
  const breaker = new CircuitBreaker({ threshold: 3, resetTimeout: 1000 });
  const fn = async () => { throw new Error('Connection refused'); };
  
  for (let i = 0; i < 3; i++) {
    try { await breaker.execute('server-01', fn); } catch (e) {}
  }
  
  try {
    await breaker.execute('server-01', fn);
    assert.fail('Should have thrown circuit breaker error');
  } catch (error) {
    assert.match(error.message, /Circuit breaker OPEN/);
  }
});
