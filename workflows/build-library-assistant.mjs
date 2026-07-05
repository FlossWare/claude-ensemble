export const meta = {
  name: 'build-library-assistant',
  description: 'Build PDF library assistant components in parallel across 6 workers',
  phases: [
    { title: 'Build', detail: '6 workers building components in parallel' },
    { title: 'Integrate', detail: 'Connect all components' }
  ]
};

export default async function({ phase, parallel, agent, log }) {

  phase('Build');
  log('Building 6 components in parallel across workers...');

  const components = await parallel([
    // Worker 1: Semantic Search
    () => agent(`Create semantic search function in shared/semantic-search.js

Requirements:
- Function: semanticSearch(query, options)
- Generate embedding for query
- PostgreSQL pgvector similarity search
- Return top PDFs with similarity scores

Return: file path and brief status`, {
      label: 'semantic-search'
    }),

    // Worker 2: Recommendation API
    () => agent(`Create recommendation API endpoint

File: api/library-assistant-api.js
- POST /api/library/recommend
- Uses semantic search
- Generates rationales
- Context-aware suggestions

Return: file path and endpoints created`, {
      label: 'api'
    }),

    // Worker 3: Learning Path Builder
    () => agent(`Create learning path builder

File: tools/learning-path-builder.js
- buildLearningPath(goal)
- Orders PDFs by difficulty
- Detects prerequisites
- Time estimates

Return: file path and status`, {
      label: 'learning-path'
    }),

    // Worker 4: CLI Tool
    () => agent(`Create CLI recommendation tool

File: scripts/library-recommend
- Interactive CLI
- Calls semantic search
- Formats output nicely

Return: file path`, {
      label: 'cli'
    }),

    // Worker 5: Tests
    () => agent(`Create test suite

File: tests/library-assistant.test.js
- Semantic search tests
- API tests
- Integration tests

Return: test count`, {
      label: 'tests'
    }),

    // Worker 6: Documentation
    () => agent(`Create documentation

File: docs/LIBRARY_ASSISTANT.md
- Usage examples
- API docs
- Query examples

Return: sections created`, {
      label: 'docs'
    })
  ]);

  log(`Completed ${components.filter(Boolean).length}/6 components`);

  return {
    components: components.filter(Boolean).length,
    status: 'complete'
  };
}
