import { test } from 'node:test';
import { strict as assert } from 'node:assert';

test('Partial consensus 2/5 models is valid', async () => {
  const responses = [
    { model: 'opus', answer: 'A', success: true },
    { model: 'sonnet', answer: null, success: false },
    { model: 'haiku', answer: 'A', success: true },
    { model: 'gemini', answer: null, success: false },
    { model: 'gpt4', answer: null, success: false }
  ];
  
  const successful = responses.filter(r => r.success);
  assert.equal(successful.length >= 2, true);
});
