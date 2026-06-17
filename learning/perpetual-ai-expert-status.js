#!/usr/bin/env node

/**
 * Perpetual AI Expert - Real-time Status Dashboard
 *
 * Displays:
 * - What's currently being researched
 * - What's been understood (expertise levels)
 * - What's ready to implement
 * - What's been implemented
 * - Research velocity and quality metrics
 * - Thompson Sampling state (which queries are winning)
 */

const fs = require('fs');
const path = require('path');

const LEARNING_DIR = path.join(process.env.HOME, '.claude', 'learning');
const RESEARCH_DIR = path.join(LEARNING_DIR, 'research');
const STATE_FILE = path.join(RESEARCH_DIR, 'perpetual-ai-expert-state.json');
const KNOWLEDGE_BASE = path.join(RESEARCH_DIR, 'ai-expert-knowledge.jsonl');
const IMPLEMENTATION_QUEUE = path.join(RESEARCH_DIR, 'ai-implementation-queue.jsonl');

function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch (e) {
    return null;
  }
  return null;
}

function loadJsonl(file, limit = null) {
  if (!fs.existsSync(file)) return [];

  const lines = fs.readFileSync(file, 'utf8').trim().split('\n').filter(Boolean);
  const records = lines.map(line => {
    try {
      return JSON.parse(line);
    } catch {
      return null;
    }
  }).filter(Boolean);

  return limit ? records.slice(-limit) : records;
}

function displayStatus() {
  const state = loadState();

  if (!state) {
    console.log('No state file found. Run perpetual-ai-expert.js first.');
    return;
  }

  console.log('');
  console.log('='.repeat(80));
  console.log('PERPETUAL AI EXPERT - STATUS DASHBOARD');
  console.log('='.repeat(80));
  console.log('');

  // Run statistics
  console.log('RUN STATISTICS');
  console.log('-'.repeat(80));
  console.log(`Total runs:                ${state.runCount}`);
  console.log(`Last run:                  ${state.lastRun || 'never'}`);
  console.log(`Total queries researched:  ${state.totalQueriesResearched}`);
  console.log(`Total papers read:         ${state.totalPapersRead}`);
  console.log(`Total implementations:     ${state.totalImplementationsFound}`);
  console.log(`Techniques understood:     ${state.totalTechniquesUnderstood}`);
  console.log(`Techniques implemented:    ${state.totalTechniquesImplemented}`);
  console.log('');

  // Expertise levels by category
  console.log('EXPERTISE LEVELS (0-100%)');
  console.log('-'.repeat(80));
  const expertiseSorted = Object.entries(state.expertiseLevel || {})
    .sort((a, b) => b[1] - a[1]);

  if (expertiseSorted.length === 0) {
    console.log('No expertise data yet. Run some research first.');
  } else {
    expertiseSorted.forEach(([category, level]) => {
      const percentage = (level * 100).toFixed(1);
      const barLength = Math.floor(level * 40);
      const bar = '█'.repeat(barLength) + '░'.repeat(40 - barLength);
      console.log(`${category.padEnd(30)} ${bar} ${percentage}%`);
    });
  }
  console.log('');

  // Category progress
  console.log('CATEGORY PROGRESS');
  console.log('-'.repeat(80));
  const progressSorted = Object.entries(state.categoryProgress || {})
    .sort((a, b) => b[1].queries_researched - a[1].queries_researched);

  if (progressSorted.length === 0) {
    console.log('No category progress yet.');
  } else {
    console.log('Category'.padEnd(30) + ' Queries Papers  Impl  Understanding');
    console.log('-'.repeat(80));
    progressSorted.forEach(([category, progress]) => {
      const understanding = (progress.understanding_level * 100).toFixed(1) + '%';
      console.log(
        category.padEnd(30) +
        String(progress.queries_researched).padStart(7) +
        String(progress.papers_read).padStart(7) +
        String(progress.implementations_found).padStart(6) +
        '  ' + understanding
      );
    });
  }
  console.log('');

  // Ready to implement
  console.log('READY TO IMPLEMENT');
  console.log('-'.repeat(80));
  const readyToImplement = state.readyToImplement || [];

  if (readyToImplement.length === 0) {
    console.log('No techniques ready to implement yet. Need more research.');
  } else {
    console.log(`${readyToImplement.length} techniques ready:`);
    console.log('');
    readyToImplement.slice(0, 10).forEach((tech, i) => {
      console.log(`${i + 1}. [${tech.category}] ${tech.query}`);
      console.log(`   Confidence: ${(tech.confidence * 100).toFixed(1)}%`);
      console.log(`   Reason: ${tech.reason}`);
      console.log(`   Learnings: ${tech.learnings}`);
      console.log('');
    });
    if (readyToImplement.length > 10) {
      console.log(`... and ${readyToImplement.length - 10} more`);
      console.log('');
    }
  }

  // Top performing queries (Thompson Sampling)
  console.log('TOP PERFORMING QUERIES (Thompson Sampling)');
  console.log('-'.repeat(80));
  const topQueries = Object.entries(state.queryEffectiveness || {})
    .sort((a, b) => b[1].finding_quality - a[1].finding_quality)
    .slice(0, 10);

  if (topQueries.length === 0) {
    console.log('No query performance data yet.');
  } else {
    topQueries.forEach(([query, eff], i) => {
      const quality = (eff.finding_quality * 100).toFixed(1);
      console.log(`${i + 1}. ${query.slice(0, 65)}`);
      console.log(`   Quality: ${quality}% | Papers: ${eff.papers} | Impl: ${eff.implementations} | Runs: ${eff.runs}`);
    });
  }
  console.log('');

  // Recent queries
  console.log('RECENT QUERIES');
  console.log('-'.repeat(80));
  const recentQueries = state.recentQueries || [];
  if (recentQueries.length === 0) {
    console.log('No recent queries.');
  } else {
    recentQueries.slice(0, 10).forEach((query, i) => {
      console.log(`${i + 1}. ${query}`);
    });
  }
  console.log('');

  // Knowledge base stats
  console.log('KNOWLEDGE BASE');
  console.log('-'.repeat(80));
  const knowledge = loadJsonl(KNOWLEDGE_BASE);
  const byType = knowledge.reduce((acc, k) => {
    acc[k.type] = (acc[k.type] || 0) + 1;
    return acc;
  }, {});
  const byCategory = knowledge.reduce((acc, k) => {
    acc[k.category] = (acc[k.category] || 0) + 1;
    return acc;
  }, {});

  console.log(`Total learnings: ${knowledge.length}`);
  console.log('');
  console.log('By type:');
  Object.entries(byType).forEach(([type, count]) => {
    console.log(`  ${type}: ${count}`);
  });
  console.log('');
  console.log('By category (top 5):');
  Object.entries(byCategory)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .forEach(([category, count]) => {
      console.log(`  ${category}: ${count}`);
    });
  console.log('');

  // Implementation queue
  console.log('IMPLEMENTATION QUEUE');
  console.log('-'.repeat(80));
  const implQueue = loadJsonl(IMPLEMENTATION_QUEUE);
  console.log(`Total in queue: ${implQueue.length}`);
  if (implQueue.length > 0) {
    console.log('');
    console.log('Most recent additions:');
    implQueue.slice(-5).reverse().forEach((impl, i) => {
      console.log(`${i + 1}. [${impl.category}] ${impl.query}`);
      console.log(`   Confidence: ${(impl.confidence * 100).toFixed(1)}%`);
    });
  }
  console.log('');

  console.log('='.repeat(80));
  console.log('');
}

function displayTopicCoverage() {
  const state = loadState();
  if (!state) {
    console.log('No state found.');
    return;
  }

  const RESEARCH_CATEGORIES = {
    'Advanced Reasoning': 7,
    'Multi-Agent Orchestration': 7,
    'Meta-Learning & AutoML': 7,
    'Efficient Inference': 7,
    'RAG & Knowledge Systems': 7,
    'Training & Fine-tuning': 7,
    'Mathematical Foundations': 7,
    'Systems & Infrastructure': 7,
    'Evaluation & Robustness': 7,
    'Domain-Specific AI': 7
  };

  console.log('');
  console.log('TOPIC COVERAGE (70 queries total)');
  console.log('-'.repeat(80));

  for (const [category, totalQueries] of Object.entries(RESEARCH_CATEGORIES)) {
    const progress = state.categoryProgress[category] || { queries_researched: 0 };
    const researched = progress.queries_researched;
    const percentage = (researched / totalQueries * 100).toFixed(1);
    const bar = '█'.repeat(Math.floor(researched / totalQueries * 30)) +
                '░'.repeat(30 - Math.floor(researched / totalQueries * 30));

    console.log(`${category.padEnd(30)} ${bar} ${researched}/${totalQueries} (${percentage}%)`);
  }

  console.log('');
}

// CLI
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--help')) {
    console.log(`
Perpetual AI Expert - Status Dashboard

Usage:
  node perpetual-ai-expert-status.js              # Full status
  node perpetual-ai-expert-status.js --coverage   # Topic coverage
  node perpetual-ai-expert-status.js --watch      # Watch mode (refresh every 30s)

Status includes:
  - Run statistics
  - Expertise levels by category
  - Category progress
  - Ready to implement
  - Top performing queries
  - Knowledge base stats
  - Implementation queue
`);
    process.exit(0);
  }

  if (args.includes('--coverage')) {
    displayTopicCoverage();
    process.exit(0);
  }

  if (args.includes('--watch')) {
    const refresh = () => {
      console.clear();
      displayStatus();
      displayTopicCoverage();
    };

    refresh();
    setInterval(refresh, 30000);
  } else {
    displayStatus();
    displayTopicCoverage();
  }
}

module.exports = { displayStatus, displayTopicCoverage };
