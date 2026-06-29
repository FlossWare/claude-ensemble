#!/usr/bin/env node

/**
 * Test workflow to verify host display in /workflows command
 * Creates 4 parallel agents that should land on different hosts
 */

export default async function({ parallel, log }) {
  log('Starting host display test with 4 parallel agents');

  const workers = await parallel([
    {
      label: 'Worker A',
      model: 'claude-sonnet-4',
      systemPrompt: 'You are Worker A. Return your hostname and a simple calculation.',
      prompt: 'Run: hostname && echo "2 + 2 = 4"'
    },
    {
      label: 'Worker B',
      model: 'claude-sonnet-4',
      systemPrompt: 'You are Worker B. Return your hostname and a simple calculation.',
      prompt: 'Run: hostname && echo "3 + 3 = 6"'
    },
    {
      label: 'Worker C',
      model: 'claude-sonnet-4',
      systemPrompt: 'You are Worker C. Return your hostname and a simple calculation.',
      prompt: 'Run: hostname && echo "4 + 4 = 8"'
    },
    {
      label: 'Worker D',
      model: 'claude-sonnet-4',
      systemPrompt: 'You are Worker D. Return your hostname and a simple calculation.',
      prompt: 'Run: hostname && echo "5 + 5 = 10"'
    }
  ]);

  log('\n=== Test Results ===');
  workers.forEach((w, i) => {
    log(`Worker ${String.fromCharCode(65 + i)}: ${w.output}`);
  });

  return {
    success: true,
    workers: workers.map((w, i) => ({
      label: `Worker ${String.fromCharCode(65 + i)}`,
      output: w.output
    }))
  };
}
