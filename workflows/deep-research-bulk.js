/**
 * deep-research-bulk.js
 *
 * Fleet-distributed deep research across multiple topics.
 * Use case: 100 research topics processed in parallel.
 *
 * Multi-session orchestration:
 *   - Controller: Splits 100 topics into 3 batches (33 each)
 *   - Worker-01-03: Each processes batch via independent Claude Code session
 *   - Each worker calls deep-research for its topic batch
 *   - Workers output markdown reports
 *   - Controller concatenates reports with deduplication
 *
 * Per-topic timing:
 *   - Web search (3 searches per topic): 10s
 *   - Fetch 10 URLs: 30s
 *   - Extract claims: 30s
 *   - Adversarial verify (5 claims, 3-vote each): 45s
 *   - Synthesize report: 5s
 *   - Total: ~2 min per topic
 *   - Sequential (100 topics): 3+ hours
 *   - Fleet (3 workers): ~1 hour
 *
 * Report merge strategy:
 *   - Deduplicate by topic name
 *   - Keep most comprehensive report per topic
 *   - Concatenate with section dividers
 */

export const meta = {
  name: 'deep-research-bulk',
  description: 'Fleet-distributed deep research - investigate 100+ topics in parallel',
  whenToUse: 'When you need to research many topics with fact-checking and source verification',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Topic Distribution', detail: 'Split research topics across workers' },
    { title: 'Parallel Research', detail: 'Each worker researches its topics via deep-research' },
    { title: 'Report Merge', detail: 'Deduplicate and concatenate reports' },
    { title: 'Cross-Topic Index', detail: 'Build index for topic correlation analysis' },
  ],
};

import { bulkOrchestrate, mergeMarkdownResults } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

export default async function({ args, phase, log, agent, parallel }) {

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const DEPTH = args?.depth || 'standard'; // 'quick', 'standard', 'deep'
const SOURCES_PER_TOPIC = args?.sources || 10;
const VERIFY_CLAIMS = args?.verifyClaims !== false; // Default: true

log('');
log('='.repeat(70));
log('Bulk Deep Research - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`Depth: ${DEPTH}`);
log(`Sources per topic: ${SOURCES_PER_TOPIC}`);
log(`Verify claims: ${VERIFY_CLAIMS}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: Input Validation - Topics
// ============================================================================

phase('Input Validation');

// Topics can come from:
// 1. args.topics - JSON array of topic strings
// 2. args.topicFile - File with one topic per line
// 3. args.topicQueries - Array of search queries

let topics = [];

if (args?.topics && Array.isArray(args.topics)) {
  topics = args.topics;
  log(`Using ${topics.length} topics from args.topics`);
} else if (args?.topicFile) {
  const topicContent = fs.readFileSync(args.topicFile, 'utf8');
  topics = topicContent
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'));
  log(`Loaded ${topics.length} topics from ${args.topicFile}`);
} else if (args?.topicQueries && Array.isArray(args.topicQueries)) {
  topics = args.topicQueries;
  log(`Using ${topics.length} research queries`);
} else {
  return {
    status: 'error',
    message: 'No topics specified. Provide args.topics, args.topicFile, or args.topicQueries',
    examples: {
      'Array of topics': { topics: ['Climate change impacts', 'AI safety measures'] },
      'File with topics': { topicFile: '/path/to/topics.txt' },
      'Research queries': { topicQueries: ['What are the latest developments in quantum computing?'] },
    }
  };
}

if (topics.length === 0) {
  return {
    status: 'error',
    message: 'No topics found',
  };
}

log(`Total topics to research: ${topics.length}`);
log('Sample topics:');
topics.slice(0, 3).forEach(t => log(`  - ${t.slice(0, 80)}${t.length > 80 ? '...' : ''}`));
if (topics.length > 3) log(`  ... and ${topics.length - 3} more`);
log('');

// ============================================================================
// PHASE 2: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

// Custom merge strategy: deduplicate topics, keep best report
const deduplicateAndMergeReports = (results) => {
  const reportsByTopic = new Map();

  for (const result of results) {
    const markdown = result.markdown || result.report || '';
    if (!markdown) continue;

    // Extract topic names from markdown (look for ## Topic: ... headers)
    const topicMatches = markdown.match(/## Topic: ([^\n]+)/g) || [];

    for (const match of topicMatches) {
      const topicName = match.replace(/## Topic: /, '').trim();
      if (!reportsByTopic.has(topicName)) {
        // Extract the section for this topic (up to next ##)
        const sectionRegex = new RegExp(
          `## Topic: ${topicName}[\\s\\S]*?(?=## Topic:|$)`,
          'i'
        );
        const section = markdown.match(sectionRegex)?.[0] || match;
        reportsByTopic.set(topicName, section);
      }
    }
  }

  // Concatenate unique topic reports
  return Array.from(reportsByTopic.values()).join('\n\n---\n\n');
};

const orchestrationResult = await bulkOrchestrate({
  skill: 'deep-research-bulk',
  items: topics,
  workerScript: 'workflows/deep-research.js',
  mergeStrategy: deduplicateAndMergeReports,
  itemSerializer: (topics) => JSON.stringify({
    topics,
    depth: DEPTH,
    sources_per_topic: SOURCES_PER_TOPIC,
    verify_claims: VERIFY_CLAIMS,
  }),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      return { markdown: stdout };
    }
  },
  log,
  fleetOptions: { capabilities: ['research'] },
  minWorkers: 2,
  timeout: 600000, // 10 min per batch
  dryRun: DRY_RUN,
  useWeightedDistribution: true,
});

log('');

if (orchestrationResult.status === 'failed') {
  return {
    status: 'failed',
    message: 'All workers failed',
    topicsProcessed: orchestrationResult.itemsProcessed,
    totalTopics: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 3: Build Cross-Topic Index
// ============================================================================

phase('Cross-Topic Index');

log('Analyzing relationships between topics...');

const indexResult = await _agent(`Extract topic names and key findings from research report.

Report:
${(orchestrationResult.result || '').slice(0, 10000)}

Return:
1. List of topics covered
2. For each topic: 3-5 key findings
3. Potential correlations between topics`, {
  label: 'Build Index',
  schema: {
    type: 'object',
    properties: {
      topics_covered: { type: 'array', items: { type: 'string' } },
      key_findings: {
        type: 'object',
        additionalProperties: {
          type: 'array',
          items: { type: 'string' },
        }
      },
      correlations: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            topic_a: { type: 'string' },
            topic_b: { type: 'string' },
            relationship: { type: 'string' },
          }
        }
      }
    }
  }
});

log(`Topics indexed: ${indexResult.topics_covered?.length || 0}`);
log(`Correlations found: ${indexResult.correlations?.length || 0}`);
log('');

// ============================================================================
// PHASE 4: Save Results
// ============================================================================

phase('Save Results');

const reportDir = path.join(process.cwd(), '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

const reportFile = path.join(reportDir, `research-${Date.now()}.md`);
const report = orchestrationResult.result || '';

fs.writeFileSync(reportFile, report);
log(`Report saved: ${reportFile}`);

// Save index
const indexFile = path.join(reportDir, `research-index-${Date.now()}.json`);
const index = {
  timestamp: new Date().toISOString(),
  totalTopics: orchestrationResult.totalItems,
  topicsResearched: orchestrationResult.itemsProcessed,
  topicsCovered: indexResult.topics_covered || [],
  correlations: indexResult.correlations || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  status: orchestrationResult.status,
  reportFile,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(indexFile, JSON.stringify(index, null, 2));
log(`Index saved: ${indexFile}`);

// Save topics list
const topicsListFile = path.join(reportDir, `research-topics-${Date.now()}.txt`);
fs.writeFileSync(topicsListFile, topics.join('\n'));
log(`Topics list saved: ${topicsListFile}`);
log('');

log('='.repeat(70));
log('BULK RESEARCH COMPLETE');
log('='.repeat(70));
log(`Topics researched: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Topics in report: ${indexResult.topics_covered?.length || 0}`);
log(`Correlations found: ${indexResult.correlations?.length || 0}`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalTopics: orchestrationResult.totalItems,
  topicsResearched: orchestrationResult.itemsProcessed,
  topicsCovered: indexResult.topics_covered || [],
  correlationsFound: indexResult.correlations?.length || 0,
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  reportFile,
  indexFile,
  topicsListFile,
  errors: orchestrationResult.errors,
};

}

