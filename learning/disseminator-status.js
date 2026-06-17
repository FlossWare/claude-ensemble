#!/usr/bin/env node
/**
 * Disseminator Learning Status Dashboard
 *
 * Shows what has been learned from disseminator conversations:
 * - Total conversations processed
 * - Knowledge items extracted by type
 * - Model performance comparison
 * - Cost tracking
 * - Recent extractions
 */

const fs = require('fs');
const path = require('path');

const STATE_FILE = path.join(process.env.HOME, '.claude/learning/disseminator-learner-state.json');
const KNOWLEDGE_FILE = path.join(process.env.HOME, '.claude/learning/disseminator-knowledge.jsonl');
const VECTOR_INDEX = path.join(process.env.HOME, '.claude/learning/disseminator-index.json');

function loadState() {
  if (!fs.existsSync(STATE_FILE)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
}

function loadKnowledge() {
  if (!fs.existsSync(KNOWLEDGE_FILE)) {
    return [];
  }

  return fs.readFileSync(KNOWLEDGE_FILE, 'utf8')
    .trim()
    .split('\n')
    .filter(l => l.trim())
    .map(l => JSON.parse(l));
}

function loadVectorIndex() {
  if (!fs.existsSync(VECTOR_INDEX)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(VECTOR_INDEX, 'utf8'));
}

function formatDuration(startIso) {
  const start = new Date(startIso);
  const now = new Date();
  const diff = now - start;

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function displayDashboard() {
  console.clear();
  console.log('═'.repeat(80));
  console.log('  🧠 DISSEMINATOR AUTONOMOUS LEARNING SYSTEM - STATUS DASHBOARD');
  console.log('═'.repeat(80));

  const state = loadState();
  const knowledge = loadKnowledge();
  const vectorIndex = loadVectorIndex();

  if (!state) {
    console.log('\n❌ No learning state found. Run disseminator-learner.js first.\n');
    return;
  }

  // Overview
  console.log('\n📊 OVERVIEW');
  console.log('─'.repeat(80));
  console.log(`  Running since:       ${state.started_at}`);
  console.log(`  Duration:            ${formatDuration(state.started_at)}`);
  console.log(`  Last run:            ${state.last_run || 'Never'}`);
  console.log(`  Conversations:       ${state.processed_conversations.length} processed`);
  console.log(`  Extractions:         ${state.total_extractions} total`);
  console.log(`  Total cost:          $${state.total_cost.toFixed(2)}`);

  // Knowledge by type
  console.log('\n📚 KNOWLEDGE BASE');
  console.log('─'.repeat(80));

  const knowledgeByType = {};
  const knowledgeByConfidence = { high: 0, medium: 0, low: 0 };

  for (const item of knowledge) {
    knowledgeByType[item.type] = (knowledgeByType[item.type] || 0) + 1;

    if (item.confidence >= 0.85) knowledgeByConfidence.high++;
    else if (item.confidence >= 0.70) knowledgeByConfidence.medium++;
    else knowledgeByConfidence.low++;
  }

  console.log(`  Total items:         ${knowledge.length}`);
  console.log(`  High confidence:     ${knowledgeByConfidence.high} (≥0.85)`);
  console.log(`  Medium confidence:   ${knowledgeByConfidence.medium} (0.70-0.84)`);
  console.log(`  Low confidence:      ${knowledgeByConfidence.low} (<0.70)`);

  console.log('\n  By Type:');
  const sortedTypes = Object.entries(knowledgeByType).sort((a, b) => b[1] - a[1]);
  for (const [type, count] of sortedTypes) {
    const bar = '█'.repeat(Math.ceil(count / 2));
    console.log(`    ${type.padEnd(30)} ${bar} ${count}`);
  }

  // Model performance
  console.log('\n🤖 MODEL PERFORMANCE');
  console.log('─'.repeat(80));

  const models = Object.entries(state.model_performance || {}).sort((a, b) => b[1].count - a[1].count);

  if (models.length > 0) {
    console.log('  Model           Uses    Avg Quality    Total Cost');
    console.log('  ' + '─'.repeat(76));
    for (const [model, stats] of models) {
      const avgQuality = stats.total_quality / stats.count;
      console.log(
        `  ${model.padEnd(15)} ${String(stats.count).padStart(5)}   ` +
        `${avgQuality.toFixed(3).padStart(11)}    $${stats.total_cost.toFixed(2).padStart(8)}`
      );
    }
  } else {
    console.log('  No model performance data yet.');
  }

  // Extraction quality by type
  console.log('\n📈 EXTRACTION QUALITY BY TYPE');
  console.log('─'.repeat(80));

  const qualityByType = Object.entries(state.extraction_quality_by_type || {})
    .sort((a, b) => b[1].avg_quality - a[1].avg_quality);

  if (qualityByType.length > 0) {
    console.log('  Type                           Count    Avg Quality');
    console.log('  ' + '─'.repeat(76));
    for (const [type, stats] of qualityByType) {
      console.log(
        `  ${type.padEnd(30)} ${String(stats.count).padStart(5)}   ${stats.avg_quality.toFixed(3)}`
      );
    }
  } else {
    console.log('  No quality data yet.');
  }

  // Recent extractions
  console.log('\n🆕 RECENT EXTRACTIONS (Last 10)');
  console.log('─'.repeat(80));

  const recent = knowledge.slice(-10).reverse();
  for (const item of recent) {
    const timestamp = new Date(item.extracted_at).toLocaleString();
    console.log(`  [${timestamp}] ${item.type}`);
    console.log(`    ${item.title} (confidence: ${item.confidence.toFixed(2)}, model: ${item.model_used})`);
    console.log();
  }

  // Vector index
  if (vectorIndex) {
    console.log('🔍 VECTOR SEARCH INDEX');
    console.log('─'.repeat(80));
    console.log(`  Total vectors:       ${vectorIndex.total_vectors}`);
    console.log(`  Embedding dim:       ${vectorIndex.embedding_dim}`);
    console.log(`  Last updated:        ${vectorIndex.created}`);
    console.log();
  }

  // Files
  console.log('📁 DATA FILES');
  console.log('─'.repeat(80));
  console.log(`  State:               ${STATE_FILE}`);
  console.log(`  Knowledge base:      ${KNOWLEDGE_FILE}`);
  if (fs.existsSync(KNOWLEDGE_FILE)) {
    const size = fs.statSync(KNOWLEDGE_FILE).size;
    console.log(`                       ${(size / 1024).toFixed(1)} KB`);
  }
  console.log(`  Vector database:     ${path.join(process.env.HOME, '.claude/learning/disseminator-vectors.jsonl')}`);
  console.log(`  Vector index:        ${VECTOR_INDEX}`);
  console.log();

  console.log('═'.repeat(80));
  console.log('  Run: node disseminator-learner.js --incremental    (process new conversations)');
  console.log('  Run: node disseminator-search.js "query"           (search knowledge base)');
  console.log('═'.repeat(80));
  console.log();
}

// Watch mode
const args = process.argv.slice(2);
if (args.includes('--watch')) {
  console.log('👀 Watch mode enabled. Press Ctrl+C to exit.\n');
  setInterval(() => {
    displayDashboard();
  }, 5000);
} else {
  displayDashboard();
}
