export const meta = {
  name: 'review-postgres-model-selection',
  description: 'Multi-AI review of PostgreSQL model loading implementation (4 files)',
  phases: [
    { title: 'Worker Reviews', detail: '8 diverse models review code in parallel' },
    { title: 'Arbiter Synthesis', detail: 'Highest-tier model makes final decision' }
  ]
};

const FILES = [
  { path: 'shared/model-loader.js', type: 'new', lines: 151 },
  { path: 'shared/smart-consensus.js', type: 'modified', key: 'PostgreSQL integration added' },
  { path: 'shared/model-performance.js', type: 'modified', key: 'PostgreSQL fallback added' },
  { path: 'shared/test-model-loader.mjs', type: 'new', lines: 47 }
];

export default async function({ phase, parallel, agent, log }) {
  log('🔍 PostgreSQL Model Selection - Code Review');
  log(`Files: ${FILES.length} (2 new, 2 modified)`);
  log('');

  // Phase 1: Workers review each file
  phase('Worker Reviews');

  const reviews = await parallel(
    FILES.map(f => () =>
      agent(`Code review: ${f.path} (${f.type})

Focus:
- Correctness (syntax, logic, edge cases)
- PostgreSQL integration (connections, errors, performance)
- Security (SQL injection, input validation)
- Fallback behavior (graceful degradation)

Provide:
1. Assessment: APPROVE / REQUEST_CHANGES / COMMENT
2. Issues (if any)
3. Suggestions

Format: Brief, specific feedback.`, {
        label: `review-${f.path.split('/').pop()}`,
        phase: 'Worker Reviews'
      })
    )
  );

  log(`✓ ${reviews.filter(Boolean).length}/${FILES.length} reviews completed`);
  log('');

  // Phase 2: Arbiter synthesizes
  phase('Arbiter Synthesis');

  const arbiter = await agent(`Synthesize code reviews:

${reviews.filter(Boolean).map((r, i) => `File ${i+1}: ${FILES[i].path}\n${r}\n`).join('\n')}

Decision:
- MERGE (ready to ship)
- REQUEST_CHANGES (blocking issues)
- NEEDS_DISCUSSION (conflicting feedback)

Provide final verdict + rationale.`, {
    label: 'arbiter-final-decision',
    phase: 'Arbiter Synthesis'
  });

  log('');
  log('═'.repeat(60));
  log('FINAL DECISION');
  log('═'.repeat(60));
  log(arbiter);

  return { reviews, arbiter };
}
