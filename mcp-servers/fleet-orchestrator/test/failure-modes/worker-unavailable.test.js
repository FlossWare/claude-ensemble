import { test } from 'node:test';
import { strict as assert } from 'node:assert';

test('All workers unavailable falls back to localhost', async () => {
  const workers = ['server-01', 'server-02', 'server-03'];
  const unavailable = new Set(workers);
  
  function selectWorker(unavailableSet) {
    const available = workers.filter(w => !unavailableSet.has(w));
    return available.length === 0 ? 'localhost' : available[0];
  }
  
  const selected = selectWorker(unavailable);
  assert.equal(selected, 'localhost');
});
